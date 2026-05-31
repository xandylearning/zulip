# Postmortem — JWT first-time login fails for new users (creation race)

| | |
|---|---|
| **Date of incident** | 2026-05-12 |
| **Reported** | 2026-05-12 14:20 UTC (server error email) |
| **Author** | LMS Integration team |
| **Status** | Resolved — fix shipped in `lms_integration` v1.0.1 |
| **Severity** | Medium — intermittent, self-healing on retry; blocks *first* login only |
| **Affected component** | `lms_integration` · `TestPressJWTAuthBackend` (JWT auth) |
| **Affected versions** | v1.0.0 (since JWT auth was introduced) |
| **Related docs** | [JWT_AUTHENTICATION.md](JWT_AUTHENTICATION.md) · [SIMPLIFIED_AUTH_BACKEND.md](SIMPLIFIED_AUTH_BACKEND.md#concurrency--transaction-safety) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

---

## 1. Summary

When a **brand-new** LMS user logged in via TestPress JWT, the backend created
their Zulip account inline, during `authenticate()`. If two requests for that
same new user arrived at nearly the same time, both passed the "does this user
exist?" checks and both proceeded to create the account. The second request
collided in the database and the login failed with:

```
Could not find or create user shahana.k@xandylearning.com after error:
duplicate key value violates unique constraint
"zerver_usergroupmembersh_user_group_id_user_profi_5b32ea4b_uniq"
DETAIL:  Key (user_group_id, user_profile_id)=(14, 23194) already exists.
```

The error message is misleading: the user was *successfully created* by the
other request. The failure was a race condition compounded by broken transaction
handling in the recovery path, not data corruption.

## 2. Impact

- **Who:** First-time JWT logins only. Returning users were never affected
  (their account already exists, so creation is never attempted).
- **What:** The affected login attempt returned a generic
  `"JWT authentication failed"` to the client. Because the account *was* created
  by the winning request, **the next login attempt by the same user succeeded** —
  the failure was self-healing on retry.
- **Data integrity:** None. Exactly one `UserProfile` was created per user; no
  duplicate or partial accounts resulted. (The new user's `delivery_email` is
  protected by `zerver_userprofile_realm_id_delivery_email_uniq`, so a duplicate
  profile was never possible.)
- **Blast radius:** Limited to the seconds around a new user's very first login,
  and only when two requests overlapped (double-click, SSO redirect retry, link
  prefetch, or a bulk `user_sync` running concurrently with a login).

## 3. Timeline (UTC)

| Time | Event |
|---|---|
| 2026-05-12 14:20:43 | Server error email fires for `shahana.k@xandylearning.com`: `Could not find or create user … duplicate key … usergroupmembership`. |
| 2026-05-12 (same window) | User retries; login succeeds because the account already exists. No further user-facing impact. |
| 2026-05-31 | Root cause investigated; fix implemented in `auth_backend.py`; regression tests + docs added; released as v1.0.1. |

## 4. Root cause

### 4.1 The race

The two JWT login endpoints — `lms_jwt_auth_api` and `lms_jwt_web_login` in
`lms_integration/views.py` — both call Django's `authenticate()`, which dispatches
to `TestPressJWTAuthBackend._get_or_create_user()`. That method:

1. Looks the user up by LMS username, then by email (several strategies).
2. If not found, calls `do_create_user()` to provision the account.

There is **no lock** between the lookup and the create. So:

```
Request A ── lookups: not found ──► do_create_user ──► COMMIT
                                       creates UserProfile id 23194
                                       adds it to system user group 14
Request B ── lookups: not found ──► do_create_user ──► IntegrityError
   (B's lookups ran before A committed,                on UserGroupMembership(14, 23194)
    or against an older MVCC snapshot)
```

Group **14** is the realm's **system user group** — every user in the realm
belongs to it (`zerver/actions/create_user.py` adds the membership immediately
after creating the profile). It is therefore the *first* row in `do_create_user`
to collide once profile 23194 already exists, which is why the constraint named
in the error is `…usergroupmembersh…` rather than something on `UserProfile`.

### 4.2 Why recovery failed (the part that turned a race into a user-facing error)

`do_create_user` is decorated `@transaction.atomic(savepoint=False)`. The LMS code
wrapped the call in a plain `with transaction.atomic():` and caught the exception
in a broad `except Exception` that then ran several "find the user another way"
queries.

The problem: **once any statement errors inside a PostgreSQL transaction, the
transaction is aborted** and every subsequent statement fails with
`current transaction is aborted, commands ignored until end of transaction block`
until a rollback. Because `do_create_user` used `savepoint=False`, there was no
savepoint to roll back to. Every recovery query in the `except` block therefore
failed, so the code could never find the user it had just (via the other request)
created — and returned `None`, surfacing `Could not find or create user … after
error`.

A second, latent instance of the same bug lived in `_add_username_mapping()`: it
did `ExternalAuthID.objects.create(...)` inside a bare `try/except Exception`. A
duplicate mapping (also possible under concurrency) would be swallowed but would
leave the transaction aborted, re-triggering the same cascade.

### 4.3 Contributing design factor

User creation happens **inline during authentication, on every login**. Core
Zulip avoids this class of race by provisioning accounts in a single-threaded
registration/confirmation flow rather than inside `authenticate()`. The LMS
backend's "create on the spot" design is convenient for SSO but makes the
auth path responsible for concurrency safety.

## 5. Detection

Detected via Django's server error email (`ERROR`-level log → email). There was no
dedicated alert or dashboard for auth failures, so detection depended on someone
reading the error mail. The misleading `Could not find or create user` wording
initially suggested a data problem rather than a concurrency problem.

## 6. Resolution (shipped in v1.0.1)

Changes in `lms_integration/auth_backend.py`:

1. **Savepoint around creation.** `do_create_user` is now called inside
   `transaction.atomic(savepoint=True)`. On failure Django rolls back to the
   savepoint, leaving the connection clean so recovery queries can run.
2. **Treat `IntegrityError` as "someone beat me to it."** It is caught
   explicitly, distinct from unexpected errors. The backend then re-queries and
   returns the user the winning request created. Creation is now idempotent:
   N concurrent first-time logins create exactly one account and all return it.
3. **Extracted recovery helpers** `_recover_existing_user()` and
   `_finalize_recovered_user()` — invoked only *after* the savepoint rollback.
4. **Idempotent username mapping.** `_add_username_mapping()` now uses
   `get_or_create` inside its own savepoint and handles `IntegrityError`, so a
   duplicate mapping no longer poisons the transaction.

Verification:

- Regression tests added (`tests/test_placeholder_emails.py`):
  - `test_concurrent_creation_recovers_existing_user` — simulates the exact
    `IntegrityError` and asserts the loser recovers the same user and restores
    the username mapping.
  - `test_creation_failure_with_no_existing_user_returns_none` — an
    unrecoverable failure still returns `None`.

> **Note on verification:** the regression tests were authored against this fix
> but were **not executed in the environment where the fix was written** (no
> provisioned Zulip dev environment / `.venv` was available there). They must be
> run via `./tools/test-backend
> lms_integration.tests.test_placeholder_emails.AuthenticationBackendTest` in a
> provisioned environment before/with the v1.0.1 release. (See Action Items.)

## 7. What went well

- The bug was self-healing on retry, so user-facing impact was small.
- No data was corrupted; the database's own unique constraints prevented
  duplicate accounts.
- The error message, though misleadingly worded, contained the exact constraint
  name, which made the root cause traceable.

## 8. What went wrong / where we got lucky

- The recovery code *looked* robust (multiple lookup strategies) but was
  fundamentally broken because it ran in an aborted transaction — it could never
  have worked. We were lucky the retry path masked this.
- A bare `except Exception` swallowed the underlying error class and obscured
  that this was a transaction-state problem.
- No alerting distinguished auth failures from generic errors.

## 9. Lessons learned

1. **`savepoint=False` is a sharp edge.** Calling a `savepoint=False` atomic
   function and then doing *anything* in an `except` requires your own savepoint,
   or the connection is unusable. Recovery code that issues queries after a
   caught DB error is a red flag.
2. **Inline create-on-auth must be idempotent.** Any "find-or-create" on a hot,
   concurrent path needs to handle "created concurrently" (`IntegrityError` →
   re-fetch), not just "exists" vs "doesn't exist."
3. **Error messages should describe the situation, not the symptom.** "Could not
   find or create user" hid that the user *had* been created.
4. **Don't `except Exception` around DB writes** when a narrower
   `except IntegrityError` (plus a savepoint) expresses the real intent.

## 10. Action items

| # | Action | Type | Owner | Status |
|---|---|---|---|---|
| 1 | Wrap creation in a savepoint; handle `IntegrityError` by re-fetching | Fix | LMS team | ✅ Done (v1.0.1) |
| 2 | Make `_add_username_mapping` idempotent | Fix | LMS team | ✅ Done (v1.0.1) |
| 3 | Add regression tests for the race | Test | LMS team | ✅ Added — ⏳ must be run in a provisioned env before release |
| 4 | Run `./tools/test-backend` + `./tools/lint` on the changed files in a provisioned dev env | Verify | LMS team | ⏳ Pending |
| 5 | Add an alert/metric for `auth backend` `ERROR` logs (esp. `Could not find or create user`) | Prevent | Ops | ⏳ Pending |
| 6 | Audit other inline `do_create_user` / write paths in `lms_integration` (e.g. `user_sync.py`) for the same savepoint pattern | Prevent | LMS team | ⏳ Pending |
| 7 | Consider a short-lived per-(realm, username) lock (e.g. advisory lock) on first-time login to avoid the duplicate work entirely | Improve | LMS team | 💡 Backlog |

## Appendix A — The original error

```
Could not find or create user shahana.k@xandylearning.com after error: duplicate key value violates unique constraint "zerver_usergroupmembersh_user_group_id_user_profi_5b32ea4b_uniq"
DETAIL:  Key (user_group_id, user_profile_id)=(14, 23194) already exists.

Django Version: 5.2.5
Server time: Tue, 12 May 2026 14:20:43 +0000
Installed Applications include: 'lms_integration.apps.LmsIntegrationConfig', 'zulip_calls_plugin'
```

## Appendix B — How to confirm an affected user is healthy

```python
python manage.py shell
>>> from zerver.models import UserProfile, Realm
>>> from zerver.models.users import ExternalAuthID
>>> realm = Realm.objects.get(string_id="your_realm")
>>> u = UserProfile.objects.get(delivery_email__iexact="shahana.k@xandylearning.com", realm=realm)
>>> u.is_active, u.id
>>> # The testpress-username mapping re-attaches automatically on the next login if missing:
>>> ExternalAuthID.objects.filter(user=u, external_auth_method_name="testpress-username").exists()
```
