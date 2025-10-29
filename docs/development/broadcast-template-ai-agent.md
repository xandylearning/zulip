# Broadcast Template AI Agent (LangGraph) - Developer Deep Dive

This guide explains the internals of the Template AI agent used by `POST /json/notification_templates/ai_generate`.

- Audience: Backend/platform developers
- Overview link: See `docs/subsystems/broadcast-notifications.md` → “Agent architecture overview”

## Purpose

Convert a natural-language prompt into a validated notification template (`text_only` or `rich_media`) using a controlled, resumable workflow that plans, generates, validates, and optionally asks follow-ups.

## Architecture

```
User -> ai_generate endpoint -> LangGraph Agent (StateGraph)
           |                     | nodes: plan -> generate -> validate -> (followup <-> refine)* -> format -> END
           |                     | checkpointing: MemorySaver with conversation_id
           +---------------------+--------------------------------------------------------------
```

- Implementation: `zerver/lib/notifications_broadcast_ai.py`
- LLM client: `PortkeyLLMClient` (retry/backoff via tenacity)
- Checkpointing: LangGraph `MemorySaver` keyed by `conversation_id`
- Feature flag: `BROADCAST_AI_TEMPLATES_ENABLED`
- Fallback: Missing `PORTKEY_API_KEY` -> deterministic `text_only` template

## TemplateAgentState (key fields)

- messages: trace of agent messages
- template_draft: `{name, template_type, content, template_structure, ai_generated, ai_prompt}`
- template_type: `"text_only" | "rich_media"`
- plan_description, plan_approved, plan_feedback
- validation_errors, followup_questions, user_answers
- realm_id, user_id, original_prompt, subject_hint, media_hints
- iteration_count, max_iterations, status, conversation_id

## Nodes

- plan: Analyze prompt, propose plan (type, name, block descriptions) -> `plan_ready` interrupt
- generate: Produce concrete draft (name/type/content/structure)
- validate: Enforce `template_type` and `template_structure` rules; errors -> `needs_input`
- followup: Create up to 3 questions from validation errors -> interrupt
- refine: Incorporate answers and regenerate; loop back to validate
- format: Final consistency pass (e.g., placeholder URLs) -> `complete`

## Prompts (intent only)

- Planning: choose type, outline blocks, name, brief reasoning
- Generation: strict JSON output; `rich_media` requires `{"blocks": [...]}` (text, image, video, audio, button, svg)
- Followup: turn validation errors into 1–3 actionable questions
- Refinement: incorporate answers and regenerate strict JSON

## Validation rules (server-side)

- Root: `{ "blocks": Block[] }`
- Types: `text | image | video | audio | button | svg`
- text: `content: string` required
- image|video|audio|svg: optional `url: string` must be string if present
- button: `text: string` required; optional `href: string`
- Optional `id: string` for any block

Errors are reported as `validation_errors` with index, e.g., `block[2]: unsupported block type`.

## Statuses and resume

- `plan_ready`: includes `plan`; client answers with `approve_plan` or `plan_feedback`
- `needs_input`: includes `followups`; client answers with `answers`
- `complete`: includes `template` (and optional `validation_errors` if best-effort)

Always send `conversation_id` on subsequent calls to resume from checkpoint.

## Endpoint contract

- Request fields: `prompt`, `conversation_id?`, `approve_plan?` (Json[bool]), `plan_feedback?`, `answers?`, plus optional `subject`, `template_id`, `media_hints`
- Response: includes `conversation_id`, `status`, and one of `plan` | `followups` | `template` (+ optional `validation_errors`)

## Persistence, logging, reliability

- Checkpointing: `MemorySaver` for state
- Logging: `log_node_execution()` with realm/user/iteration counts
- Retries: LLM calls use tenacity exponential backoff

## Error handling and fallback

- If the agent fails or API key missing, return deterministic `text_only` fallback; log details

## Security

- Admin-only endpoint (`@require_realm_admin`)
- Input length checks and output validation

## Tests

See `zerver/tests/test_notifications_ai.py` for:
- Permission enforcement
- Fallback without API key
- Conversation tracking
- `approve_plan` JSON boolean parsing

## Minimal client flows

Approve a plan:

```bash
curl -X POST \
  -d 'prompt=Create a birthday card' \
  -d "conversation_id=$CONV" \
  -d 'approve_plan=true' \
  /json/notification_templates/ai_generate
```

Answer follow-ups:

```bash
curl -X POST \
  -d 'prompt=Create a birthday card' \
  -d "conversation_id=$CONV" \
  -d 'answers={"headline":"Happy Birthday!","cta":"Celebrate"}' \
  /json/notification_templates/ai_generate
```

---

Start with `docs/subsystems/broadcast-notifications.md` → “Agent architecture overview” for a concise overview.
