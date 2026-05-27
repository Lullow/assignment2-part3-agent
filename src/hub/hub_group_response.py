from src.hub.hub_config import HUB_AGENT_NAME
from src.hub.hub_collaboration_role import describe_role


def build_group_coordination_response(
    message: dict,
    intent: str,
    suggested_role: str,
) -> str:
    """
    Build a coordination-first response for broad group mentions.

    The goal is to avoid duplicate work, leadership collisions, and premature
    execution when many agents are addressed at the same time.
    """

    sender = message.get("agent_name", "unknown-agent")

    role_description = describe_role(suggested_role)

    # This response does not execute the task.
    # It suggests coordination without taking over leadership.
    return (
        f"Hi {sender}, {HUB_AGENT_NAME} can contribute.\n\n"
        f"Temporary role: {suggested_role} - I can {role_description}.\n\n"
        "To avoid duplicate work, I suggest small task ownership: one agent implements, "
        "one reviews/tests, and results are shared back in chat.\n\n"
        "I will wait for a clear assigned task before any local execution."
    )
