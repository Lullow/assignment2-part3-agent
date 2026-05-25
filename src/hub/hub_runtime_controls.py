from dataclasses import dataclass
import threading
from src.hub.hub_task_queue import HubTaskQueue
from src.hub.hub_execution_bridge import run_approved_task_placeholder

@dataclass
class HubRuntimeControls:
    """
    Runtime controls for the hub agent.

    These values can be changed while the agent is running through
    local console commands.
    """

    # When paused, the agent stays online but does not post responses.
    paused: bool

    # Shared stop flag used by the console thread and the hub loop.
    should_stop: bool

    # Runtime safety cap for how many responses the agent may post in one run.
    max_responses_per_run: int

    # Runtime token limit for LLM-generated hub responses.
    max_tokens: int


def start_console_control_thread(
    controls: HubRuntimeControls,
    task_queue: HubTaskQueue | None = None,
) -> threading.Thread:
    """
    Start a background thread for local runtime control commands.

    Supported commands:
    - /status
    - /pause
    - /resume
    - /tokens N
    - /responses N
    - /quit
    - /tasks
    - /approve TASK_ID
    - /reject TASK_ID
    """

    def console_loop() -> None:
        # Keep listening for local commands until the hub loop is asked to stop.
        while not controls.should_stop:
            try:
                command = input().strip()
            except EOFError:
                # Allows clean shutdown in environments where stdin is closed.
                break

            # Ignore empty input so blank lines do not produce errors.
            if not command:
                continue

            if command == "/status":
                # Print current runtime limits without changing anything.
                print(
                    "[control] "
                    f"paused={controls.paused}, "
                    f"max_responses_per_run={controls.max_responses_per_run}, "
                    f"max_tokens={controls.max_tokens}"
                )
                continue

            if command == "/pause":
                # Pause posting while keeping the process alive and polling.
                controls.paused = True
                print("[control] Agent paused. It will not post responses.")
                continue

            if command == "/resume":
                # Re-enable posting after a pause.
                controls.paused = False
                print("[control] Agent resumed.")
                continue

            if command.startswith("/tokens "):
                value = command.removeprefix("/tokens ").strip()

                # Only allow positive integer token limits.
                if value.isdigit() and int(value) > 0:
                    controls.max_tokens = int(value)
                    print(f"[control] max_tokens set to {controls.max_tokens}")
                else:
                    print("[control] Usage: /tokens 200")
                continue

            if command.startswith("/responses "):
                value = command.removeprefix("/responses ").strip()

                # Allow 0 so the agent can be kept online without posting responses.
                if value.isdigit() and int(value) >= 0:
                    controls.max_responses_per_run = int(value)
                    print(
                        "[control] max_responses_per_run set to "
                        f"{controls.max_responses_per_run}"
                    )
                else:
                    print("[control] Usage: /responses 3")
                continue

            if command == "/quit":
                # Ask the main hub loop to stop cleanly.
                controls.should_stop = True
                print("[control] Stopping hub loop...")
                continue

            if command == "/tasks":
                if task_queue is None:
                    print("[control] No task queue is available.")
                    continue

                tasks = task_queue.list_tasks()

                if not tasks:
                    print("[control] No pending hub tasks.")
                    continue

                print("[control] Pending hub tasks:")
                for task in tasks:
                    print(
                        f"  #{task.task_id} from {task.sender} "
                        f"intent={task.intent} created_at={task.created_at}"
                    )
                    print(f"     {task.content}")
                continue

            if command.startswith("/approve "):
                if task_queue is None:
                    print("[control] No task queue is available.")
                    continue

                value = command.removeprefix("/approve ").strip()

                if not value.isdigit():
                    print("[control] Usage: /approve TASK_ID")
                    continue

                task = task_queue.remove_task(int(value))

                if task is None:
                    print(f"[control] No pending task found with id {value}.")
                    continue

                print(f"[control] Approved task #{task.task_id}.")
                print()
                print("[control] Task package for future SWE-agent bridge:")
                print(run_approved_task_placeholder(task))
                continue

            if command.startswith("/reject "):
                if task_queue is None:
                    print("[control] No task queue is available.")
                    continue

                value = command.removeprefix("/reject ").strip()

                if not value.isdigit():
                    print("[control] Usage: /reject TASK_ID")
                    continue

                task = task_queue.remove_task(int(value))

                if task is None:
                    print(f"[control] No pending task found with id {value}.")
                    continue

                print(f"[control] Rejected task #{task.task_id}.")
                continue

            print(
                "[control] Unknown command. Available commands: "
                "/status, /pause, /resume, /tokens N, /responses N, "
                "/tasks, /approve TASK_ID, /reject TASK_ID, /quit"
            )

    # Run console input in a daemon thread so it does not block the hub polling loop.
    thread = threading.Thread(target=console_loop, daemon=True)
    thread.start()

    return thread