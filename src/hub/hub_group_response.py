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

    # Keep the original request visible in the response for context and traceability.
    content = message.get("content", "").strip()

    role_description = describe_role(suggested_role)

    # This response does not execute the task.
    # It proposes a safe collaboration flow before any agent starts working.
    return (
        f"Hi {sender}, {HUB_AGENT_NAME} can contribute.\n\n"
        f"Suggested temporary role for me: {suggested_role}\n"
        f"In this role, I can {role_description}.\n\n"
        "To avoid duplicate work, I suggest we first agree on scope and task ownership "
        "before agents start implementing.\n\n"
        "Suggested collaboration flow:\n"
        "1. Define the minimal scope and expected output.\n"
        "2. Split the work into small tasks.\n"
        "3. Let agents explicitly claim one task each.\n"
        "4. Implement only assigned tasks.\n"
        "5. Report results back to the hub.\n\n"
        "I can flexibly help with planning, implementation, review, testing, or README/demo work. "
        "If the team assigns me a clear task, I can queue it for local approval and run it through "
        "my local Part 2 SWE-agent.\n\n"
        f"Detected intent: {intent}\n"
        f"Original request: {content}"
    )