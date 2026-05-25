from dataclasses import dataclass
import threading


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


def start_console_control_thread(controls: HubRuntimeControls) -> threading.Thread:
    """
    Start a background thread for local runtime control commands.

    Supported commands:
    - /status
    - /pause
    - /resume
    - /tokens N
    - /responses N
    - /quit
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

            print(
                "[control] Unknown command. Available commands: "
                "/status, /pause, /resume, /tokens N, /responses N, /quit"
            )

    # Run console input in a daemon thread so it does not block the hub polling loop.
    thread = threading.Thread(target=console_loop, daemon=True)
    thread.start()

    return thread