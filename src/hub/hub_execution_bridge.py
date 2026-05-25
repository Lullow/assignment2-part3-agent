from src.hub.hub_task_queue import QueuedHubTask


def prepare_task_for_local_agent(task: QueuedHubTask) -> str:
    """
    Prepare a hub-approved task for a future local SWE-agent bridge.

    This function does not execute tools, run bash, edit files, or start
    the Part 2 agent loop. It only returns the safe execution prompt.
    """

    # Convert the approved queued task into a prompt format the local agent can use later.
    return task.to_execution_prompt()


def run_approved_task_placeholder(task: QueuedHubTask) -> str:
    """
    Placeholder for a future safe bridge to the Part 2 SWE-agent.

    The bridge is intentionally not active yet.
    """

    # Prepare the prompt, but do not pass it into any tool-running agent yet.
    prompt = prepare_task_for_local_agent(task)

    # Return a clear status message proving that no execution happened.
    return (
        "APPROVED TASK READY FOR FUTURE EXECUTION BRIDGE\n\n"
        f"{prompt}\n"
        "Bridge status: not enabled.\n"
        "No bash commands, file edits, or Part 2 tools were run."
    )