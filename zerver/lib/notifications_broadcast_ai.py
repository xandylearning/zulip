"""AI compose helper for broadcast notifications using LangGraph agent architecture."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List, TypedDict, Annotated, Literal
import logging
import json
import re
import uuid

from django.conf import settings
import tenacity

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from zerver.lib.ai_agent_core import PortkeyConfig, PortkeyLLMClient
from zerver.models import NotificationTemplate, Realm, UserProfile

logger = logging.getLogger(__name__)

# ============================================================================
# Agent State Definition
# ============================================================================

class TemplateAgentState(TypedDict):
    """State for template generation agent workflow."""
    
    # Core conversation
    messages: List[dict]
    
    # Template building
    template_draft: Optional[dict]
    template_type: Optional[Literal["text_only", "rich_media"]]
    
    # Planning & approval
    plan_description: Optional[dict]
    plan_approved: bool
    plan_feedback: Optional[str]
    
    # Validation & refinement
    validation_errors: List[str]
    followup_questions: List[str]
    user_answers: Dict[str, str]
    
    # Context
    realm_id: str
    user_id: int
    original_prompt: str
    subject_hint: Optional[str]
    media_hints: Dict[str, bool]
    
    # Workflow control
    iteration_count: int
    status: Literal["planning", "plan_ready", "generating", "validating", "needs_input", "refining", "complete", "error"]
    max_iterations: int
    conversation_id: str


# ============================================================================
# Utility Functions
# ============================================================================

def _extract_json_from_fences(raw: str) -> str:
    """Extract JSON payload from optional ```json ... ``` fences."""
    s = raw.strip()
    try:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return s


def _summarize_template(template: NotificationTemplate) -> str:
    """Return a compact description of the template structure for prompting."""
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


def log_node_execution(node_name: str, state: TemplateAgentState) -> None:
    """Log agent node execution with state snapshot."""
    logger.info(
        f"agent_node node={node_name} status={state.get('status', 'unknown')} "
        f"iteration={state.get('iteration_count', 0)} "
        f"validation_errors={len(state.get('validation_errors', []))} "
        f"realm={state.get('realm_id', 'unknown')} user={state.get('user_id', 0)}"
    )


# ============================================================================
# Validation Functions (Tools)
# ============================================================================

def _validate_block(block: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a single block structure."""
    errors: List[str] = []
    btype = block.get("type")
    
    if btype not in {"text", "image", "video", "audio", "button", "svg"}:
        errors.append(f"unsupported block type: {btype}")
        
    if btype == "text":
        if not isinstance(block.get("content", ""), str):
            errors.append("text block requires string 'content'")
    elif btype in {"image", "video", "audio", "svg"}:
        url = block.get("url")
        if url is not None and not isinstance(url, str):
            errors.append(f"{btype} block 'url' must be string if provided")
    elif btype == "button":
        if not isinstance(block.get("text", ""), str):
            errors.append("button block requires string 'text'")
        href = block.get("href")
        if href is not None and not isinstance(href, str):
            errors.append("button 'href' must be string if provided")
            
    if "id" in block and not isinstance(block.get("id"), str):
        errors.append("block 'id' must be string if provided")
        
    return (len(errors) == 0, errors)


def validate_template_structure(struct: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate template structure (agent tool)."""
    errors: List[str] = []
    
    if not isinstance(struct, dict):
        return False, ["template_structure must be an object"]
        
    blocks = struct.get("blocks", [])
    if not isinstance(blocks, list):
        return False, ["template_structure.blocks must be a list"]
        
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            errors.append(f"block[{i}] must be an object")
            continue
        ok, berrs = _validate_block(b)
        if not ok:
            for e in berrs:
                errors.append(f"block[{i}]: {e}")
                
    return (len(errors) == 0, errors)


def generate_placeholder_url(block_type: str, context: str = "") -> str:
    """Generate contextual placeholder URL for attachment blocks (agent tool)."""
    context_clean = context.lower().replace(" ", "-")[:30] if context else block_type
    return f"placeholder://{context_clean}-{block_type}"


# ============================================================================
# LLM Integration with Retry
# ============================================================================

@tenacity.retry(
    wait=tenacity.wait_exponential(min=1, max=10),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type((RuntimeError, ConnectionError))
)
def call_llm_with_retry(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> dict:
    """Call LLM with automatic retry on failure."""
    api_key = getattr(settings, "PORTKEY_API_KEY", None)
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY not configured")
    
    config = PortkeyConfig(api_key=api_key, timeout=15, max_retries=3)
    client = PortkeyLLMClient(config)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    result = client.chat_completion(messages, max_tokens=max_tokens, temperature=0.4)
    
    if not result.get("success") or not result.get("content"):
        raise RuntimeError(result.get("error", "LLM call failed"))
    
    return result


# ============================================================================
# System Prompts for Each Node
# ============================================================================

def _build_planning_prompt() -> str:
    """System prompt for planning phase."""
    return """You are a notification template planner. Analyze the user's request and create a detailed plan.

Your task:
1. Determine template type (text_only for simple text, or rich_media for structured content)
2. Generate a clear template name
3. Plan the structure with specific blocks
4. Provide reasoning for your choices

Return ONLY JSON:
{
  "template_type": "text_only" or "rich_media",
  "template_name": "Clear, descriptive name for the template",
  "structure": {
    "blocks": [
      {"type": "text", "description": "What this text block will contain"},
      {"type": "image", "description": "What this image will show"},
      {"type": "button", "description": "What this button will do"}
    ]
  },
  "reasoning": "2-3 sentences explaining why this structure will work well"
}

Rules:
- Use text_only for simple announcements
- Use rich_media when images, buttons, videos, or structured layouts are needed
- Be specific in block descriptions (not generic)
- Generate a professional, clear template name
- Reasoning should explain why this structure serves the user's goal
- Do NOT ask for URLs or files"""


def _build_generation_prompt() -> str:
    """System prompt for template generation phase."""
    return """You generate complete broadcast notification templates as strict JSON.

Return ONLY JSON with keys: name, template_type, content, template_structure

Template Types:
- text_only: Simple text content in Markdown
- rich_media: Structured blocks with images, buttons, videos, etc.

For text_only:
- Provide concise Markdown in 'content'
- Set template_structure to {}

For rich_media:
- template_structure must be: {"blocks":[{...block objects...}]}
- Block types: text, image, video, audio, button, svg

AUTOMATIC ATTACHMENT GENERATION:
- For image blocks: use placeholder URLs like 'placeholder://welcome-image' or 'placeholder://hero-image'
- For video blocks: use placeholder URLs like 'placeholder://intro-video'  
- For audio blocks: use placeholder URLs like 'placeholder://welcome-audio'
- For button blocks: generate contextual text like 'Get Started', 'Learn More', 'Sign Up'
- For SVG blocks: use placeholder URLs like 'placeholder://logo-svg'

Generate contextual content and button labels from the prompt.
NEVER ask for URLs or file uploads.
No prose, no code fences, ONLY JSON."""


def _build_followup_prompt(validation_errors: List[str]) -> str:
    """System prompt for generating follow-up questions."""
    errors_text = "\n".join(f"- {e}" for e in validation_errors)
    return f"""The template has validation issues:
{errors_text}

Generate 1-3 specific clarification questions to resolve these issues.
Focus on content and structure, NOT on URLs or file uploads.

Return ONLY JSON:
{{
  "questions": ["question 1", "question 2", "question 3"]
}}

Keep questions specific, actionable, and focused on missing content."""


def _build_refinement_prompt() -> str:
    """System prompt for template refinement phase."""
    return """You are refining a notification template based on user answers to follow-up questions.

Incorporate the new information provided by the user and regenerate the complete template.

Return ONLY JSON with keys: name, template_type, content, template_structure

Follow the same rules as initial generation:
- Use placeholder URLs for attachments
- Generate contextual content
- Validate all required fields are present
- No prose, ONLY JSON"""


# ============================================================================
# Agent Node Functions
# ============================================================================

def plan_node(state: TemplateAgentState) -> TemplateAgentState:
    """Analyze prompt and create detailed plan for user approval."""
    log_node_execution("plan", state)

    # Ensure required collections exist to avoid KeyErrors when resuming
    state.setdefault("messages", [])

    # If user approved but there's no stored plan (e.g., empty checkpoint), just proceed
    if state.get("plan_approved") is True and not state.get("plan_description"):
        state["status"] = "generating"
        return state

    # Check if we already have a plan and are processing approval/feedback
    if state.get("plan_description") and state.get("plan_approved"):
        # Plan was already created and approved, move to generating
        logger.info(f"Plan already approved, proceeding to generation conversation_id={state.get('conversation_id', 'unknown')}")
        state["status"] = "generating"
        return state

    # Clear any previous feedback after processing
    if state.get("plan_approved") is False and state.get("plan_feedback"):
        logger.info(f"Reprocessing plan with feedback: {state.get('plan_feedback')}")
        # Keep the feedback for this iteration, will be cleared after

    try:
        # If user provided feedback, incorporate it
        context = f"""User Request: {state.get('original_prompt', '')}
Subject Hint: {state.get('subject_hint') or 'None'}
Media Hints: {state.get('media_hints', {})}"""

        if state.get("plan_feedback"):
            context += f"\n\nUser Feedback on Previous Plan: {state['plan_feedback']}"

        system_prompt = _build_planning_prompt()

        result = call_llm_with_retry(system_prompt, context, max_tokens=500)
        raw = _extract_json_from_fences(result["content"])
        plan = json.loads(raw)

        # Store detailed plan
        state["plan_description"] = plan
        state["template_type"] = plan.get("template_type", "text_only")
        state["status"] = "plan_ready"

        # Clear feedback after incorporating
        state["plan_feedback"] = None

        state["messages"].append({
            "role": "assistant",
            "content": f"I've created a plan for '{plan.get('template_name', 'your template')}'"
        })
    except Exception as e:
        # Real error - log and continue
        logger.error(f"Planning failed: {e}")
        state["status"] = "generating"  # Proceed with best effort
        return state

    # Log that plan is ready for approval
    # The graph will automatically interrupt after this node completes (interrupt_after=["plan"])
    logger.info(f"Plan ready for approval: {state['plan_description'].get('template_name', 'Unknown') if state.get('plan_description') else 'Unknown'}")

    return state


def generate_node(state: TemplateAgentState) -> TemplateAgentState:
    """Generate template draft using LLM based on approved plan."""
    log_node_execution("generate", state)
    
    try:
        system_prompt = _build_generation_prompt()
        
        # Build context with approved plan
        context_parts = [
            f"Prompt: {state.get('original_prompt', '')}",
            f"Subject hint: {state.get('subject_hint') or '(none)'}",
        ]

        # Include approved plan if available
        if state.get("plan_description"):
            plan = state["plan_description"]
            context_parts.append(f"Approved Plan:")
            context_parts.append(f"- Template Name: {plan.get('template_name', '')}")
            context_parts.append(f"- Template Type: {plan.get('template_type', '')}")
            if plan.get("structure"):
                blocks_desc = "\n".join(
                    f"  * {b['type']}: {b.get('description', '')}"
                    for b in plan['structure'].get('blocks', [])
                )
                context_parts.append(f"- Structure:\n{blocks_desc}")
        else:
            context_parts.append(f"Template type: {state.get('template_type') or 'auto-detect'}")

        # Add user answers if refinement
        if state.get("user_answers"):
            answers_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in state["user_answers"].items())
            context_parts.append(f"User answers:\n{answers_text}")
        
        user_prompt = "\n\n".join(context_parts)
        
        result = call_llm_with_retry(system_prompt, user_prompt, max_tokens=800)
        raw = _extract_json_from_fences(result["content"])
        
        try:
            template_data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            template_data = {}
        
        # Validate template_data is a dictionary
        if not isinstance(template_data, dict):
            logger.warning("LLM response is not a valid dictionary, using empty template")
            template_data = {}
        
        # Create template draft (use plan name if available)
        name = (state.get("plan_description") or {}).get("template_name") or \
               template_data.get("name") or \
               state.get("subject_hint") or \
               (state.get("original_prompt", "")).split("\n")[0][:60] or "AI Template"
        name = name.strip()

        # Use template_type from state (set by plan) if available, otherwise from LLM response
        template_type = state.get("template_type") or template_data.get("template_type", "text_only")
        content = (template_data.get("content") or "").strip()
        template_structure = template_data.get("template_structure", {})

        if template_type == "text_only":
            template_structure = {}
        elif not template_structure.get("blocks"):
            template_structure = {"blocks": []}

        state["template_draft"] = {
            "name": name[:100],
            "template_type": template_type,
            "content": content[:8000],
            "template_structure": template_structure,
            "ai_generated": True,
            "ai_prompt": state.get("original_prompt", "")
        }
        
        state["status"] = "validating"
        state["messages"].append({
            "role": "assistant",
            "content": f"Generated template: {name}"
        })
        
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        state["validation_errors"].append(f"Generation error: {str(e)}")
        state["status"] = "error"
    
    return state


def validate_node(state: TemplateAgentState) -> TemplateAgentState:
    """Validate template structure."""
    log_node_execution("validate", state)
    
    state["validation_errors"] = []
    
    template = state["template_draft"]
    if not template:
        state["validation_errors"].append("No template generated")
        state["status"] = "error"
        return state
    
    template_type = template.get("template_type")
    if template_type not in {"text_only", "rich_media"}:
        state["validation_errors"].append("Invalid template_type")
    
    if template_type == "rich_media":
        structure = template.get("template_structure", {})
        ok, errors = validate_template_structure(structure)
        if not ok:
            state["validation_errors"].extend(errors)
    
    # Update status based on validation
    if state["validation_errors"]:
        state["status"] = "needs_input" if state["iteration_count"] < state["max_iterations"] else "complete"
    else:
        state["status"] = "complete"
    
    return state


def decision_node(state: TemplateAgentState) -> str:
    """Decide next step based on validation results."""
    if not state.get("validation_errors"):
        return "format"

    if state.get("iteration_count", 0) >= state.get("max_iterations", 3):
        logger.warning(f"Max iterations reached for conversation {state.get('conversation_id', 'unknown')}")
        return "format"  # Return best effort

    return "followup"


def followup_node(state: TemplateAgentState) -> TemplateAgentState:
    """Generate clarification questions and wait for human input."""
    log_node_execution("followup", state)
    
    try:
        system_prompt = _build_followup_prompt(state.get("validation_errors", []))
        template_draft_json = json.dumps(state.get('template_draft'), indent=2) if state.get('template_draft') else "None"
        user_prompt = f"""Template Draft: {template_draft_json}
Original Prompt: {state.get('original_prompt', '')}

Generate clarification questions to fix the validation errors."""
        
        result = call_llm_with_retry(system_prompt, user_prompt, max_tokens=300)
        raw = _extract_json_from_fences(result["content"])
        data = json.loads(raw)
        
        questions = data.get("questions", [])
        state["followup_questions"] = questions[:3]  # Max 3 questions
        state["status"] = "needs_input"
    except Exception as e:
        # Real error - log and continue
        logger.error(f"Followup generation failed: {e}")
        state["status"] = "complete"  # Proceed with what we have
        return state

    # Interrupt execution - wait for human input (outside try/except)
    response = interrupt({
        "action": "request_followup_answers",
        "questions": state["followup_questions"],
        "template_draft": state["template_draft"],
        "validation_errors": state["validation_errors"]
    })
    
    # When resumed, process answers
    if response and isinstance(response, dict):
        answers = response.get("answers", {})
        state["user_answers"].update(answers)
        state["status"] = "refining"
    
    return state


def refine_node(state: TemplateAgentState) -> TemplateAgentState:
    """Refine template based on user answers."""
    log_node_execution("refine", state)
    
    state["iteration_count"] += 1
    
    try:
        system_prompt = _build_refinement_prompt()
        
        # Build refinement context
        answers_text = "\n".join(
            f"Q: {q}\nA: {state.get('user_answers', {}).get(q, 'No answer')}"
            for q in state.get("followup_questions", [])
        )

        template_draft_json = json.dumps(state.get('template_draft'), indent=2) if state.get('template_draft') else "None"
        user_prompt = f"""Original Prompt: {state.get('original_prompt', '')}

User Answers to Follow-up Questions:
{answers_text}

Previous Template: {template_draft_json}

Regenerate the complete template incorporating the user's answers."""

        result = call_llm_with_retry(system_prompt, user_prompt, max_tokens=800)
        raw = _extract_json_from_fences(result["content"])
        template_data = json.loads(raw)

        # Update template draft (create new if None)
        if state.get("template_draft") is None:
            # Create new template draft
            state["template_draft"] = {
                "name": template_data.get("name", "Refined Template")[:100],
                "template_type": template_data.get("template_type", "text_only"),
                "content": template_data.get("content", "")[:8000],
                "template_structure": template_data.get("template_structure", {}),
                "ai_generated": True,
                "ai_prompt": state.get("original_prompt", "")
            }
        else:
            # Update existing template draft
            state["template_draft"].update({
                "name": template_data.get("name", state["template_draft"]["name"])[:100],
                "template_type": template_data.get("template_type", state["template_draft"]["template_type"]),
                "content": template_data.get("content", "")[:8000],
                "template_structure": template_data.get("template_structure", state["template_draft"]["template_structure"])
            })
        
        state["status"] = "validating"
        state["messages"].append({
            "role": "assistant",
            "content": f"Refined template (iteration {state['iteration_count']})"
        })
        
    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        state["status"] = "complete"  # Use existing template
    
    return state


def format_node(state: TemplateAgentState) -> TemplateAgentState:
    """Final formatting and cleanup."""
    log_node_execution("format", state)
    
    # Ensure all placeholders are properly formatted
    if state.get("template_draft") and state["template_draft"].get("template_type") == "rich_media":
        structure = state["template_draft"].get("template_structure", {})
        blocks = structure.get("blocks", [])

        for block in blocks:
            btype = block.get("type")
            # Ensure placeholder URLs are set
            if btype in {"image", "video", "audio", "svg"} and not block.get("url"):
                context = state.get("original_prompt", "").split()[0] if state.get("original_prompt") else ""
                block["url"] = generate_placeholder_url(btype, context)

    state["status"] = "complete"
    logger.info(
        f"Template generation complete conversation_id={state.get('conversation_id', 'unknown')} "
        f"iterations={state.get('iteration_count', 0)} realm={state.get('realm_id', 'unknown')}"
    )
    
    return state


# ============================================================================
# Build LangGraph Agent
# ============================================================================

def plan_approval_decision_node(state: TemplateAgentState) -> str:
    """Decide whether to proceed to generation or loop back to planning based on approval."""
    conversation_id = state.get('conversation_id', 'unknown')
    if state.get("plan_approved"):
        logger.info(f"Plan approved, proceeding to generation conversation_id={conversation_id}")
        return "generate"
    elif state.get("plan_feedback"):
        logger.info(f"Plan rejected with feedback, restarting planning conversation_id={conversation_id}")
        return "plan"
    else:
        # Still waiting for approval - stay in plan_ready state
        logger.info(f"Plan ready, waiting for approval conversation_id={conversation_id}")
        return "generate"  # Default to proceed


def build_template_agent(interrupt_on_plan: bool = True) -> StateGraph:
    """Build and return compiled LangGraph agent.

    interrupt_on_plan: If True, compilation will interrupt after the planning
    node to allow explicit user approval. If False, the agent will run through
    generation and formatting without stopping at the planning boundary. This
    is used for resume flows after an explicit approval/feedback is provided.
    """

    # Initialize graph
    workflow = StateGraph(TemplateAgentState)

    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("followup", followup_node)
    workflow.add_node("refine", refine_node)
    workflow.add_node("format", format_node)

    # Set entry point
    workflow.add_edge(START, "plan")

    # Conditional edge from plan (handles approval/rejection after interrupt)
    workflow.add_conditional_edges(
        "plan",
        plan_approval_decision_node,
        {
            "generate": "generate",
            "plan": "plan"
        }
    )

    workflow.add_edge("generate", "validate")

    # Conditional routing from validation
    workflow.add_conditional_edges(
        "validate",
        decision_node,
        {
            "followup": "followup",
            "format": "format"
        }
    )

    # Loop edges
    workflow.add_edge("followup", "refine")
    workflow.add_edge("refine", "validate")

    # Terminal edge
    workflow.add_edge("format", END)

    # Compile with checkpointing; optionally disable interrupt on resume flows
    memory = MemorySaver()
    if interrupt_on_plan:
        return workflow.compile(checkpointer=memory, interrupt_after=["plan"])
    return workflow.compile(checkpointer=memory)


# ============================================================================
# Main API Function
# ============================================================================

def generate_template_with_ai(
    *,
    realm: Realm,
    user: UserProfile,
    prompt: str,
    subject: Optional[str] = None,
    prior_context: Optional[Dict[str, Any]] = None,
    selected_template: Optional[NotificationTemplate] = None,
    media_hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate template using LangGraph agent with stateful workflow."""

    logger.info(
        f"generate_template_with_ai:start realm={realm.string_id} "
        f"user_id={user.id} has_api_key={bool(getattr(settings, 'PORTKEY_API_KEY', None))}"
    )

    # Check API key
    api_key = getattr(settings, "PORTKEY_API_KEY", None)
    if not api_key:
        # Fallback to simple generation
        logger.warning("No PORTKEY_API_KEY, using fallback")
        return _fallback_generate_template(prompt, subject, realm, user)

    try:
        # Build agent
        agent = build_template_agent()

        # Get or create conversation ID
        conversation_id = (prior_context or {}).get("conversation_id") or str(uuid.uuid4())

        # Configure with conversation_id for checkpointing
        config = {
            "configurable": {
                "thread_id": conversation_id
            }
        }

        # Check if we're resuming from an interrupt
        plan_approved = (prior_context or {}).get("plan_approved")
        plan_feedback = (prior_context or {}).get("plan_feedback")
        answers = (prior_context or {}).get("answers")

        # If resuming with approval/feedback or answers, update state and continue
        if plan_approved is not None or plan_feedback is not None or answers:
            logger.info(f"Resuming agent with plan_approved={plan_approved}, has_feedback={bool(plan_feedback)}, has_answers={bool(answers)}")

            # Get current state from checkpoint
            # Use a non-interrupting agent for resume to avoid stopping after plan again
            agent = build_template_agent(interrupt_on_plan=False)
            snapshot = agent.get_state(config)
            current_state = snapshot.values

            # If checkpoint is empty (e.g., new server process), seed a baseline state
            if not current_state:
                current_state = {
                    "messages": [],
                    "template_draft": None,
                    "template_type": None,
                    "plan_description": None,
                    "plan_approved": False,
                    "plan_feedback": None,
                    "validation_errors": [],
                    "followup_questions": [],
                    "user_answers": {},
                    "realm_id": realm.string_id,
                    "user_id": user.id,
                    "original_prompt": prompt,
                    "subject_hint": subject,
                    "media_hints": media_hints or {},
                    "iteration_count": 0,
                    "status": "planning",
                    "max_iterations": 3,
                    "conversation_id": conversation_id,
                }
                agent.update_state(config, current_state)

            # Update state with approval/feedback/answers
            if plan_approved is True:
                current_state["plan_approved"] = True
                current_state["status"] = "generating"
            elif plan_feedback:
                current_state["plan_approved"] = False
                current_state["plan_feedback"] = plan_feedback
                current_state["status"] = "planning"  # Will replan
            elif answers:
                current_state["user_answers"].update(answers)
                current_state["status"] = "refining"

            # Update the state in the checkpoint
            agent.update_state(config, current_state)

            # Stream events and handle interrupts
            result = None
            for event in agent.stream(None, config, stream_mode="values"):
                result = event

            if result is None:
                raise RuntimeError("Agent did not produce any result")

        else:
            # Initial invocation - create initial state
            initial_state: TemplateAgentState = {
                "messages": [],
                "template_draft": None,
                "template_type": None,
                "plan_description": None,
                "plan_approved": False,
                "plan_feedback": None,
                "validation_errors": [],
                "followup_questions": [],
                "user_answers": {},
                "realm_id": realm.string_id,
                "user_id": user.id,
                "original_prompt": prompt,
                "subject_hint": subject,
                "media_hints": media_hints or {},
                "iteration_count": 0,
                "status": "planning",
                "max_iterations": 3,
                "conversation_id": conversation_id
            }

            logger.info(f"Starting new agent invocation conversation_id={conversation_id}")

            # Invoke agent and handle interrupts
            result = None
            for event in agent.stream(initial_state, config, stream_mode="values"):
                result = event

            if result is None:
                raise RuntimeError("Agent did not produce any result")

        # Check if execution was interrupted
        if result.get("status") == "plan_ready" and result.get("plan_description"):
            # Agent interrupted for plan approval
            return {
                "status": "plan_ready",
                "plan": result["plan_description"],
                "conversation_context": {"conversation_id": conversation_id}
            }
        elif result.get("status") == "needs_input" and result.get("followup_questions"):
            # Agent interrupted for followup questions
            return {
                "status": "needs_input",
                "followups": result["followup_questions"],
                "conversation_context": {"conversation_id": conversation_id}
            }

        # Otherwise, format normal response
        return _format_agent_response(result, conversation_id)

    except Exception as e:
        # Real error occurred
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return _fallback_generate_template(prompt, subject, realm, user)


def _fallback_generate_template(
    prompt: str, 
    subject: Optional[str], 
    realm: Realm, 
    user: UserProfile
) -> Dict[str, Any]:
    """Fallback template generation without LangGraph."""
    name = (subject or prompt.split("\n", 1)[0][:40] or "AI Template").strip()
    content = prompt.strip()[:2000]
    
    template = {
        "name": name,
        "template_type": "text_only",
        "content": content,
        "template_structure": {},
        "ai_generated": True,
        "ai_prompt": prompt
    }
    
    logger.info(f"generate_template_with_ai:fallback realm={realm.string_id} user_id={user.id}")
    return {"template": template, "conversation_context": {}}


def _format_agent_response(result: TemplateAgentState, conversation_id: str) -> Dict[str, Any]:
    """Format agent result for API response."""
    response: Dict[str, Any] = {
        "template": result.get("template_draft"),  # Use .get() to handle None
        "conversation_context": {"conversation_id": conversation_id}
    }

    # Add plan if agent is waiting for approval
    if result.get("status") == "plan_ready" and result.get("plan_description"):
        response["plan"] = result["plan_description"]
        response["status"] = "plan_ready"

    # Add follow-up questions if agent is waiting for input
    if result.get("status") == "needs_input" and result.get("followup_questions"):
        response["followups"] = result["followup_questions"]
        response["status"] = "needs_input"

    # Add validation errors if any
    if result.get("validation_errors"):
        response["validation_errors"] = result["validation_errors"]

    # Always include a status for client logic; default to 'complete' if missing
    response["status"] = result.get("status", "complete")

    return response


# ============================================================================
# Legacy compose_broadcast_with_ai (kept for backward compatibility)
# ============================================================================

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
        content_fallback = (prompt or "").strip()[:800]
        subject_fallback = (subject or content_fallback.split("\n", 1)[0][:80] or "Announcement").strip()
        return {"subject": subject_fallback, "content": content_fallback, "media_content": {}}

    config = PortkeyConfig(api_key=api_key, timeout=8, max_retries=2)
    client = PortkeyLLMClient(config)

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
        try:
            data = json.loads(raw)
            subj = (data.get("subject") or "").strip()
            body = (data.get("content") or "").strip()
            media_map = data.get("media_content") or {}
            if not subj:
                subj = (subject or body.split("\n", 1)[0][:80] or "Announcement").strip()
            return {"subject": subj[:80], "content": body[:4000], "media_content": media_map}
        except Exception:
            body = raw[:4000]
            subj = (subject or body.split("\n", 1)[0][:80] or "Announcement").strip()
            return {"subject": subj[:80], "content": body, "media_content": {}}

    content_fallback = (prompt or "").strip()[:800]
    subject_fallback = (subject or content_fallback.split("\n", 1)[0][:80] or "Announcement").strip()
    return {"subject": subject_fallback, "content": content_fallback, "media_content": {}}
