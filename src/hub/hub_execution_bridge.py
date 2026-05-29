import sys
from pathlib import Path

from src.hub.hub_result_report import build_approved_task_report
from src.hub.hub_config import (
    HUB_APPROVED_TASK_RUNNER,
    HUB_APPROVED_TASK_TOOL_MODE,
)
from src.hub.hub_task_queue import QueuedHubTask

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def prepare_task_for_local_agent(task: QueuedHubTask) -> str:
    """
    Prepare a hub-approved task for local Part 2 handling.

    This function does not execute tools, run bash, edit files, or start
    the Part 2 agent loop by itself. It only returns the safe execution prompt.
    """

    return task.to_execution_prompt()


def run_approved_task_placeholder(task: QueuedHubTask) -> str:
    """
    Placeholder for a safe bridge to the Part 2 SWE-agent.

    The bridge is intentionally not active in placeholder mode.
    """

    prompt = prepare_task_for_local_agent(task)

    return (
        "APPROVED TASK READY FOR FUTURE EXECUTION BRIDGE\n\n"
        f"{prompt}\n"
        "Bridge status: placeholder mode.\n"
        "No bash commands, file edits, or Part 2 tools were run."
    )


def run_approved_task_with_part2_agent(task: QueuedHubTask) -> str:
    """
    Run an approved hub task through the local Part 2 SWE-agent.

    This should only be called after explicit local approval.
    The Part 2 agent's existing tool safety checks still apply.
    """

    # The Part 2 files currently use script-style imports like:
    # from agent_loop import ...
    # from llm_client import ...
    # Therefore we add src/ to sys.path here instead of refactoring Part 2 now.
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from agent_loop import run_agent
    from config_loader import load_system_prompt

    system_prompt = load_system_prompt()
    user_task = (
        f"{task.to_execution_prompt()}\n\n"
        f"{build_tool_mode_instructions()}"
    )
    final_answer = run_agent(
        user_task=user_task,
        system_prompt=system_prompt,
    )

    return build_approved_task_report(
        task_id=task.task_id,
        sender=task.sender,
        intent=task.intent,
        tool_mode=HUB_APPROVED_TASK_TOOL_MODE,
        final_answer=final_answer,
    )


def run_approved_task(task: QueuedHubTask) -> str:
    """
    Run an approved task according to HUB_APPROVED_TASK_RUNNER.

    Supported modes:
    - placeholder: do not execute anything
    - part2_agent: run the local Part 2 SWE-agent after approval
    """

    if HUB_APPROVED_TASK_RUNNER == "placeholder":
        return run_approved_task_placeholder(task)

    if HUB_APPROVED_TASK_RUNNER == "part2_agent":
        return run_approved_task_with_part2_agent(task)

    return (
        "Unsupported approved task runner mode. "
        "No bash commands, file edits, or Part 2 tools were run."
    )


def build_tool_mode_instructions() -> str:
    """
    Build safety instructions for approved hub task execution.

    This controls how the local Part 2 SWE-agent should treat the task.
    """

    if HUB_APPROVED_TASK_TOOL_MODE == "read_only":
        return (
            "Approved task tool mode: read_only\n"
            "- Do not edit files.\n"
            "- Do not use edit_file_section.\n"
            "- Do not run bash commands that modify files or environment state.\n"
            "- Prefer read_file or safe inspection commands only.\n"
            "- Return a plan, analysis, or text-only patch proposal.\n"
        )

    if HUB_APPROVED_TASK_TOOL_MODE == "local_tools":
        return (
            "Approved task tool mode: local_tools\n"
            "- You may use the existing Part 2 tools if needed.\n"
            "- All tool calls must still pass bash safety, path safety, and output limits.\n"
            "- Prefer the smallest safe change.\n"
            "- Do not access secrets or private configuration.\n"
        )

    return "Approved task tool mode: unknown. Prefer safe read-only behavior.\n"
