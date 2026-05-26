from src.hub.hub_config import HUB_AGENT_NAME


def should_post_coordination_followup(
    sender: str,
    content: str,
    active_group_task: bool,
) -> bool:
    """
    Decide if the agent should post a small coordinator follow-up
    after another agent posts progress during an active group task.

    This is intentionally conservative to avoid spam and duplicate work.
    """

    if not active_group_task:
        return False

    if sender == HUB_AGENT_NAME:
        return False

    if not content:
        return False

    text = content.lower()

    result_markers = [
        "result:",
        "klar med",
        "deliverable",
        "done with:",
    ]

    return any(marker in text for marker in result_markers)


def build_coordination_followup_response(sender: str, content: str) -> str:
    """
    Build a short coordinator follow-up after another agent reports progress.
    """

    return (
        "COORDINATION UPDATE\n\n"
        f"Observed contribution from: {sender}\n\n"
        "Suggested next step:\n"
        "- Identify what is now completed.\n"
        "- Pick the next unclaimed task.\n"
        "- Avoid duplicating the same file or module.\n\n"
        "I will not duplicate this work. "
        "I can help with README/demo instructions, review, testing, "
        "or a small assigned task after local approval."
    )