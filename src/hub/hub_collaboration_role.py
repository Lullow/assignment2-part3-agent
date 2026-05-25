from typing import Literal


# Allowed temporary collaboration roles for the hub agent.
# Literal gives stricter type hints than using a plain string.
HubCollaborationRole = Literal[
    "planner",
    "implementer",
    "reviewer",
    "tester",
    "coordinator",
    "clarifier",
    "observer",
]


def choose_collaboration_role(
    content: str,
    intent: str,
    is_group_context: bool = False,
) -> HubCollaborationRole:
    """
    Choose a temporary collaboration role for this message.

    This is not a fixed identity for the agent.
    It is a context-aware suggestion for how the agent can be useful
    in the current hub conversation.
    """

    # Normalize casing so keyword checks work regardless of capitalization.
    normalized = content.lower()

    # In group context, coordination is preferred over immediate implementation
    # to avoid duplicate work or multiple agents claiming the same task.
    if is_group_context:
        if intent == "execute_task":
            return "coordinator"

        if intent == "delegate_task":
            return "coordinator"

        # Testing-related messages should be handled as verification work.
        if "test" in normalized or "verify" in normalized:
            return "tester"

        # Review-related messages should focus on checking work, not changing it.
        if "review" in normalized or "granska" in normalized:
            return "reviewer"

        # Unclear group messages should trigger clarification before action.
        if "unclear" in normalized or "?" in normalized:
            return "clarifier"

        # Default group behavior is planning, because broad group mentions need structure.
        return "planner"

    # Outside group context, direct task requests can be treated as implementation candidates.
    # Actual execution still depends on later safety checks and local approval.
    if intent == "execute_task":
        return "implementer"

    if intent == "delegate_task":
        return "coordinator"

    if intent == "review":
        return "reviewer"

    # Testing can be detected from keywords even if the broader intent was not "test".
    if "test" in normalized or "verify" in normalized or "testa" in normalized:
        return "tester"

    if intent == "plan":
        return "planner"

    if intent == "question":
        return "clarifier"

    # Safe fallback: avoid adding noise when the agent has no clear useful role.
    return "observer"


def describe_role(role: HubCollaborationRole) -> str:
    """
    Explain what the temporary role means in practical collaboration terms.
    """

    # Human-readable descriptions used in hub responses or logs.
    descriptions = {
        "planner": (
            "help define scope, break down the work, and identify a safe next step"
        ),
        "implementer": (
            "take one clear assigned task and implement it after local approval"
        ),
        "reviewer": (
            "review proposed code, plans, or task splits for correctness and safety"
        ),
        "tester": (
            "suggest or run safe verification steps and report the result"
        ),
        "coordinator": (
            "reduce duplicate work by helping the team agree on task ownership"
        ),
        "clarifier": (
            "ask focused questions when the goal, scope, or ownership is unclear"
        ),
        "observer": (
            "avoid unnecessary noise unless a useful contribution is clear"
        ),
    }

    return descriptions[role]