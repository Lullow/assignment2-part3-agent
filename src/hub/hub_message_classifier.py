import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


RoutingResponseType = Literal[
    "identify",
    "acknowledge_workflow_role",
    "claim_task",
    "answer_question",
    "review",
    "plan",
    "clarify",
    "ignore",
]


class HubRoutingDecision(BaseModel):
    should_respond: bool
    response_type: RoutingResponseType
    assigned_role: str | None = None
    task_to_claim: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


def _fallback_decision() -> HubRoutingDecision:
    return HubRoutingDecision(
        should_respond=False,
        response_type="ignore",
        assigned_role=None,
        task_to_claim=None,
        confidence=0.0,
        reason="classifier_failed",
    )


def _create_classifier_client() -> OpenAI:
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError(f"OPENAI_API_KEY is missing in .env at: {ENV_PATH}")

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)

    return OpenAI(api_key=api_key)


def _get_classifier_model_name() -> str:
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    return os.getenv("MODEL_NAME", "gpt-4o-mini")


def classify_hub_message(
    sender: str,
    content: str,
    agent_name: str,
    known_context: str | None = None,
    max_tokens: int = 300,
) -> HubRoutingDecision:
    """
    Classify a hub message into a safe routing decision.

    The classifier does not execute tools, approve work, or post messages.
    Python code remains responsible for all actions and safety checks.
    """

    system_prompt = """
You are only a semantic routing classifier for a safe hub agent.
You do not execute tools.
You do not edit files.
You do not run bash.
You do not approve local execution.
You only decide whether the agent should respond and what safe response category fits.

Classify based on:
- direct mentions of this agent
- group/broadcast requests to agents
- coordinator task assignment messages
- requests to identify yourself
- staged workflow role assignments
- requests to claim one open task
- review/planning/question requests
- whether another agent is clearly assigned the task
- whether responding would cause duplicate work or spam

Rules:
- If the message is clearly for another named agent only, should_respond=false.
- If another agent has been appointed coordinator by a human, do not compete for coordinator.
- If the message asks all/other agents to identify themselves, response_type="identify".
- If the message assigns this agent a staged workflow role, response_type="acknowledge_workflow_role".
- If a coordinator asks agents/remaining agents to pick up open tasks and this agent has not already claimed a task, response_type="claim_task".
- Prefer claiming at most one small task.
- If multiple tasks are available and no task is assigned specifically, prefer README/demo, tests, or review over taking the whole implementation.
- If the message asks for review, response_type="review".
- If the message asks for planning or coordination help, response_type="plan".

Return only valid JSON with these keys:
should_respond, response_type, assigned_role, task_to_claim, confidence, reason.
""".strip()

    user_prompt = f"""
Agent name: {agent_name}
Sender: {sender}
Known context: {known_context or "none"}

Hub message:
{content}
""".strip()

    try:
        client = _create_classifier_client()
        model_name = _get_classifier_model_name()

        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw_content = completion.choices[0].message.content

        if not raw_content:
            return _fallback_decision()

        data = json.loads(raw_content)
        return HubRoutingDecision.model_validate(data)

    except (ValidationError, json.JSONDecodeError, ValueError, OSError) as error:
        return _fallback_decision()
