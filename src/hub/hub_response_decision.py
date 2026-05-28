import json
from dataclasses import dataclass

from src.hub.hub_config import (
    HUB_AGENT_NAME,
    HUB_DECISION_MAX_TOKENS,
    HUB_USE_LLM_RESPONSE_DECISION,
)
from src.hub.hub_responder import create_hub_llm_client, get_hub_model_name


@dataclass
class HubResponseDecision:
    """
    Decision object for whether the hub agent should respond.

    This is intentionally small:
    - should_respond controls whether the hub loop continues.
    - reason is logged locally for debugging.
    - response_type helps the responder understand what kind of value to provide.
    """

    should_respond: bool
    reason: str
    response_type: str


DEFAULT_NO_RESPONSE = HubResponseDecision(
    should_respond=False,
    reason="No clear useful contribution detected.",
    response_type="ignore",
)


DECISION_SYSTEM_PROMPT = """
You are a response decision gate for a software engineering collaboration agent.

Your job is NOT to answer the message.
Your job is only to decide whether this agent should respond in the shared group chat.

The agent's default role:
- safety-aware reviewer
- tester
- integration-support agent
- lightweight coordinator when the project lacks structure

The agent should respond when it can provide visible value, such as:
- structuring an unclear project
- claiming a review/testing/integration task
- helping divide work
- answering a direct question
- reviewing a proposal
- suggesting tests
- warning about safety or scope issues
- summarizing useful next steps
- helping when another agent explicitly asks for help

The agent should NOT respond when:
- it would only say "ok", "agree", or repeat others
- another agent already clearly handled the same contribution
- the message is only status noise
- the message is unrelated to software engineering collaboration
- responding would create spam or duplicate work

Important:
- The shared chat is the only common knowledge source.
- If the agent responds later, it must provide visible output.
- Do not mark something as done unless the result is included in the chat.

Return JSON only with exactly these fields:
{
  "should_respond": true or false,
  "reason": "short reason",
  "response_type": "one of: structure_project, claim_review_task, review_feedback, test_plan, integration_support, code_suggestion, clarify, answer_question, ignore"
}
""".strip()


def _parse_decision_json(raw_text: str) -> HubResponseDecision:
    """
    Parse the LLM decision safely.

    If parsing fails or required fields are missing, default to no response.
    This prevents malformed model output from causing hub spam.
    """

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return HubResponseDecision(
            should_respond=False,
            reason="Decision JSON parse failed.",
            response_type="ignore",
        )

    should_respond = data.get("should_respond")
    reason = data.get("reason", "")
    response_type = data.get("response_type", "ignore")

    if not isinstance(should_respond, bool):
        return DEFAULT_NO_RESPONSE

    if not isinstance(reason, str):
        reason = "No valid reason provided."

    if not isinstance(response_type, str):
        response_type = "ignore"

    allowed_response_types = {
        "structure_project",
        "claim_review_task",
        "review_feedback",
        "test_plan",
        "integration_support",
        "code_suggestion",
        "clarify",
        "answer_question",
        "ignore",
    }

    if response_type not in allowed_response_types:
        response_type = "ignore"

    return HubResponseDecision(
        should_respond=should_respond,
        reason=reason.strip() or "No reason provided.",
        response_type=response_type,
    )


def decide_hub_response(
    message: dict,
    intent: str | None = None,
    is_group_context: bool = False,
) -> HubResponseDecision:
    """
    Decide whether this agent should respond to a hub message.

    Hard safety checks should happen before this function in hub_loop.py.
    This function only handles collaboration relevance.

    If HUB_USE_LLM_RESPONSE_DECISION is disabled, the function falls back to
    direct mentions and group/task-like intent handling.
    """

    sender = message.get("agent_name", "unknown-agent")
    content = message.get("content", "")

    if not HUB_USE_LLM_RESPONSE_DECISION:
        normalized = content.lower()
        agent_name = HUB_AGENT_NAME.lower()

        if f"@{agent_name}" in normalized:
            return HubResponseDecision(
                should_respond=True,
                reason="Direct mention detected.",
                response_type="answer_question",
            )

        if is_group_context:
            return HubResponseDecision(
                should_respond=True,
                reason="Group collaboration mention detected.",
                response_type="structure_project",
            )

        return DEFAULT_NO_RESPONSE

    client = create_hub_llm_client()
    model_name = get_hub_model_name()

    user_prompt = f"""
Agent name: {HUB_AGENT_NAME}
Sender: {sender}
Detected keyword intent hint: {intent or "unknown"}

Hub message:
{content}

Decide if the agent should respond.
Return JSON only.
""".strip()

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": DECISION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        max_tokens=HUB_DECISION_MAX_TOKENS,
        temperature=0,
    )

    raw_answer = completion.choices[0].message.content

    if not raw_answer:
        return DEFAULT_NO_RESPONSE

    return _parse_decision_json(raw_answer.strip())
