"""AI compose helper for broadcast notifications (low-token configuration)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.conf import settings

from zerver.lib.ai_agent_core import PortkeyConfig, PortkeyLLMClient
from zerver.models import NotificationTemplate, Realm, UserProfile


def _summarize_template(template: NotificationTemplate) -> str:
    """Return a compact description of the template structure for prompting.

    Avoid large payloads; include only block types and minimal labels/text.
    """
    try:
        structure = template.template_structure or {}
        blocks = structure.get("blocks", [])
    except Exception:
        blocks = []

    parts: list[str] = []
    for b in blocks:
        btype = b.get("type")
        if btype == "text":
            text_preview = (b.get("content") or "").strip()[:40]
            parts.append(f"text('{text_preview}')")
        elif btype == "button":
            parts.append(f"button(text='{(b.get('text') or '').strip()[:30]}')")
        elif btype in {"image", "video", "audio", "svg"}:
            parts.append(btype)
        else:
            if btype:
                parts.append(btype)

    return ", ".join(parts) if parts else "(no blocks)"


def _extract_json_from_fences(raw: str) -> str:
    """Extract JSON payload from optional ```json ... ``` fences, if present."""
    s = raw.strip()
    # Common case: fenced block with optional language tag
    try:
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return s


def compose_broadcast_with_ai(
    *,
    realm: Realm,
    user: UserProfile,
    subject: str | None,
    prompt: str,
    template: Optional[NotificationTemplate] = None,
    media_content: Optional[Dict[str, str]] = None,
) -> dict[str, Any]:
    """Generate concise subject, content, and block-wise media_content for a broadcast.

    Uses Portkey with a small token budget and compact prompt.
    """
    api_key = getattr(settings, "PORTKEY_API_KEY", None)
    if not api_key:
        # Fallback: derive a minimal subject and return prompt as content
        content_fallback = (prompt or "").strip()[:800]
        subject_fallback = (subject or content_fallback.split("\n", 1)[0][:80] or "Announcement").strip()
        return {"subject": subject_fallback, "content": content_fallback, "media_content": {}}

    config = PortkeyConfig(api_key=api_key, timeout=8, max_retries=2)
    client = PortkeyLLMClient(config)

    # Build compact system and user messages
    system_msg = {
        "role": "system",
        "content": (
            "You generate short, clear broadcast announcements. Respond ONLY as compact JSON with keys "
            "'subject', 'content', and 'media_content'. Subject should be <= 80 chars. Content should be "
            "concise Markdown (3-6 sentences), no front matter, no code fences. If template blocks exist, "
            "media_content should map block IDs to their values (text content for text blocks, button text "
            "for button blocks, URLs for buttons)."
        ),
    }

    tmpl_desc = _summarize_template(template) if template else "none"
    media_hint = ", ".join(sorted((media_content or {}).keys()))[:120]

    user_fields = [
        f"Subject: {subject or '(none)'}",
        f"Template blocks: {tmpl_desc}",
        f"Media fields present: {media_hint or '(none)'}",
        f"Prompt: {prompt[:400]}",
    ]

    user_msg = {
        "role": "user",
        "content": "\n".join(user_fields) + "\n\nReturn JSON: {\"subject\": \"...\", \"content\": \"...\", \"media_content\": {\"blockId\": \"value\"}}",
    }

    result = client.chat_completion(
        [system_msg, user_msg],
        max_tokens=256,
        temperature=0.5,
    )

    if result.get("success") and result.get("content"):
        raw = str(result["content"]).strip()
        raw = _extract_json_from_fences(raw)
        # Try to parse JSON
        try:
            import json
            data = json.loads(raw)
            subj = (data.get("subject") or "").strip()
            body = (data.get("content") or "").strip()
            media_map = data.get("media_content") or {}
            if not subj:
                subj = (subject or body.split("\n", 1)[0][:80] or "Announcement").strip()
            return {"subject": subj[:80], "content": body[:4000], "media_content": media_map}
        except Exception:
            # Fallback: derive subject from first line
            body = raw[:4000]
            subj = (subject or body.split("\n", 1)[0][:80] or "Announcement").strip()
            return {"subject": subj[:80], "content": body, "media_content": {}}

    # Fallback on failure
    content_fallback = (prompt or "").strip()[:800]
    subject_fallback = (subject or content_fallback.split("\n", 1)[0][:80] or "Announcement").strip()
    return {"subject": subject_fallback, "content": content_fallback, "media_content": {}}


