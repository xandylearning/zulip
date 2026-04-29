# Play Store Demo Account Filtering

This note documents the custom filtering added for the Google Play review demo account.

## Goal

For the demo account `xandybooks@gmail.com`, the endpoint `GET /api/v1/lms/users/for-chat`
should not expose other mentors/admins/owners. It should only return:

- the demo user itself
- students directly assigned to that mentor

## Where the logic is implemented

File: `lms_integration/lib/user_filtering.py`

### Configured demo email list

Look for:

- `DEMO_MENTOR_ONLY_STUDENTS_EMAILS`

This is a `frozenset` of restricted demo emails.

### Email matching helper

Look for:

- `is_demo_mentor_restricted_account(user_profile)`

It checks both:

- `user_profile.email`
- `user_profile.delivery_email`

and matches case-insensitively.

### Filtering behavior

In `get_mentor_filtered_user_ids(...)`:

- If requester is in `DEMO_MENTOR_ONLY_STUDENTS_EMAILS`:
  - include self
  - include only direct mentor->student mappings from `Mentortostudent`
  - do **not** include admins/owners
  - do **not** include other mentors
  - do **not** include batch-expanded students
- Otherwise, existing mentor behavior is unchanged.

## How to change later

### Change demo account email

Edit:

- `DEMO_MENTOR_ONLY_STUDENTS_EMAILS` in `lms_integration/lib/user_filtering.py`

Example:

```python
DEMO_MENTOR_ONLY_STUDENTS_EMAILS = frozenset(
    {
        "new-demo-email@example.com",
    }
)
```

### Disable this custom behavior completely

Either:

- remove the email from `DEMO_MENTOR_ONLY_STUDENTS_EMAILS`, or
- remove the `demo_restricted_account` branch in `get_mentor_filtered_user_ids(...)`.

## Important scope note

This customization currently affects LMS endpoint filtering (`/api/v1/lms/users/for-chat`).
It does not globally change every user-list endpoint.

## Quick verification checklist

1. Login as demo account.
2. Call `GET /api/v1/lms/users/for-chat`.
3. Confirm response `members` includes only self + assigned students.
4. Confirm no admins, owners, or other mentors appear.

