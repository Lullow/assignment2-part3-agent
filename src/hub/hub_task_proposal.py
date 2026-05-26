from src.hub.hub_config import HUB_AGENT_NAME

from src.hub.hub_config import HUB_AGENT_NAME, HUB_EXECUTION_MODE


def build_task_proposal(message: dict, intent: str) -> str:
    """
    Build a safe task proposal for hub task requests.

    This does not execute tools, edit files, or run bash.
    It only turns a hub request into a reviewable task plan.
    """

    sender = message.get("agent_name", "unknown-agent")
    content = message.get("content", "").strip()

    return (
        "TASK PROPOSAL\n\n"
        f"Requested by: {sender}\n"
        f"Assigned agent: {HUB_AGENT_NAME}\n"
        f"Detected intent: {intent}\n\n"
        "Requested task:\n"
        f"{content}\n\n"
        "Safe plan:\n"
        "1. Clarify the goal and expected output.\n"
        "2. Identify the smallest safe change or contribution.\n"
        "3. Share a text-only patch or implementation proposal in the hub.\n"
        "4. Wait for local approval before any file edits or command execution.\n\n"
        f"Current execution mode: {HUB_EXECUTION_MODE}\n"
        "I will not run bash, edit files, or execute hub-provided code automatically."
    )