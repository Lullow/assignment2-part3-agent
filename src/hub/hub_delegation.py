from src.hub.hub_config import HUB_AGENT_NAME


def build_delegation_proposal(message: dict, known_agents: list[str] | None = None) -> str:
    """
    Build a safe delegation proposal for a hub collaboration task.

    This does not assign work permanently or execute tools.
    It only suggests a safe task split that other agents can accept or modify.
    """

    sender = message.get("agent_name", "unknown-agent")
    content = message.get("content", "").strip()

    agents = known_agents or []

    if agents:
        agent_list = ", ".join(agents)
    else:
        agent_list = "No active agent list available."

    return (
        "DELEGATION PROPOSAL\n\n"
        f"Requested by: {sender}\n"
        f"Coordinator: {HUB_AGENT_NAME}\n\n"
        "Original request:\n"
        f"{content}\n\n"
        "Known agents:\n"
        f"{agent_list}\n\n"
        "Suggested task split:\n"
        "1. Planning: clarify the goal, constraints, and expected output.\n"
        "2. Implementation proposal: suggest the smallest safe code or design change.\n"
        "3. Review: check correctness, safety, and alignment with the task.\n"
        "4. Testing: propose or run safe tests where appropriate.\n"
        "5. Reporting: summarize results back to the hub.\n\n"
        f"My suggested role as {HUB_AGENT_NAME}:\n"
        "I can help with planning, safe code proposals, review, and coordination. "
        "I will not execute commands or edit files from hub messages automatically."
    )