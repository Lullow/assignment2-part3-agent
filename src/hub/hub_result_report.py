from src.hub.hub_config import HUB_AGENT_NAME


def build_approved_task_report(
    task_id: int,
    sender: str,
    intent: str,
    tool_mode: str,
    final_answer: str,
) -> str:
    """
    Build a concise team-friendly report after an approved local task run.

    This report is safe to print locally and can later be posted to the hub.
    """

    # Build a structured summary that other agents or humans can quickly review.
    # This avoids posting raw logs, command output, or unnecessary implementation details.
    return (
        "APPROVED LOCAL TASK REPORT\n\n"
        f"Reporting agent: {HUB_AGENT_NAME}\n"
        f"Task #{task_id}\n"
        f"Requested by: {sender}\n"
        f"Intent: {intent}\n"
        f"Tool mode: {tool_mode}\n"
        "Status: completed\n\n"
        "Summary:\n"
        f"{final_answer}\n\n"
        "Collaboration note:\n"
        "This task was executed locally after approval. "
        "Local files are not automatically visible to other agents, "
        "so relevant created or edited code/content is included above when available. "
        "Another agent can review the result, suggest follow-up tests, "
        "or continue from this output if needed."
    )