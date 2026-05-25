import time

from requests import RequestException

from src.hub.hub_responder import build_llm_collaboration_response
from src.hub.hub_response_guard import sanitize_hub_response
from src.hub.hub_client import fetch_messages, post_message, get_stats
from src.hub.hub_intent import detect_hub_intent, should_handle_intent
from src.hub.hub_task_proposal import build_task_proposal
from src.hub.hub_delegation import build_delegation_proposal
from src.hub.hub_task_queue import HubTaskQueue
from src.hub.hub_config import (
    HUB_AGENT_NAME,
    HUB_DRY_RUN,
    HUB_MAX_RESPONSES_PER_RUN,
    HUB_POLL_INTERVAL_SECONDS,
    HUB_USE_LLM_RESPONDER,
    HUB_RESPONDER_MAX_TOKENS,
    HUB_EXECUTION_MODE,
    HUB_APPROVED_TASK_RUNNER,
    HUB_APPROVED_TASK_TOOL_MODE,
    validate_hub_config,
)
from src.hub.hub_runtime_controls import (
    HubRuntimeControls,
    start_console_control_thread,
)


def get_message_seq(message: dict) -> int | None:
    """
    Extract message sequence number safely.

    The hub should return seq as an integer, but this also handles
    numeric strings defensively.
    """

    seq = message.get("seq")

    if isinstance(seq, int):
        return seq

    if isinstance(seq, str) and seq.isdigit():
        return int(seq)

    return None


def is_mention_for_agent(content: str) -> bool:
    """
    Check if a message mentions this agent.

    A message counts as a mention if it contains:
    - @agent-name
    - agent-name
    """

    normalized_content = content.lower()
    normalized_agent_name = HUB_AGENT_NAME.lower()

    return (
        f"@{normalized_agent_name}" in normalized_content
        or normalized_agent_name in normalized_content
    )


def should_respond_to_message(message: dict) -> bool:
    """
    Decide whether this agent should respond to a hub message.

    The agent should:
    - ignore its own messages
    - only respond when mentioned
    """

    sender = message.get("agent_name", "")
    content = message.get("content", "")

    # Avoid responding to our own messages and creating a feedback loop.
    if sender == HUB_AGENT_NAME:
        return False

    # Ignore empty messages because there is nothing meaningful to process.
    if not content:
        return False

    # Only respond when the message explicitly mentions this agent.
    return is_mention_for_agent(content)


def build_simple_response(message: dict) -> str:
    """
    Build a safe minimal response.

    This version does not call the SWE-agent or any tools.
    """

    sender = message.get("agent_name", "unknown-agent")

    return (
        f"Hi {sender}, this is {HUB_AGENT_NAME}. "
        "I received your message. I am currently running in safe hub mode, "
        "so I can acknowledge mentions but I am not executing code or editing files yet."
    )


def build_response(
    message: dict,
    intent: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    Build a response for a hub message.

    By default, this uses the simple safe response.
    If HUB_USE_LLM_RESPONDER is enabled, it tries to use the LLM-based responder.

    If the LLM responder fails, the agent falls back to the simple safe response
    instead of crashing the hub loop.
    """

    if HUB_USE_LLM_RESPONDER:
        try:
            # Use the LLM responder only when explicitly enabled in config.
            return build_llm_collaboration_response(
                message,
                intent=intent,
                max_tokens=max_tokens,
            )
        except Exception as error:
            # Keep the hub loop alive even if the LLM provider fails.
            print(f"LLM responder failed, falling back to simple response: {error}")
            return build_simple_response(message)

    # Default safe mode: acknowledge mentions without calling the LLM.
    return build_simple_response(message)


def get_known_agents_from_hub() -> list[str]:
    """
    Fetch known agent names from the hub stats endpoint.

    If the hub stats request fails, return an empty list so delegation
    can still work without active agent information.
    """

    try:
        stats = get_stats()
    except RequestException as error:
        print(f"Could not fetch hub stats for delegation: {error}")
        return []

    per_agent = stats.get("per_agent", {})

    if not isinstance(per_agent, dict):
        return []

    return sorted(per_agent.keys())


def build_task_aware_response(
    message: dict,
    intent: str,
    max_tokens: int | None = None,
    task_queue: HubTaskQueue | None = None,
) -> str:
    """
    Build a response based on the detected hub intent.

    Task execution requests are converted into safe task proposals.
    Delegation requests are converted into safe delegation proposals.

    The agent does not execute hub tasks automatically.
    """

    if intent == "execute_task":
        proposal = build_task_proposal(message, intent)

        if HUB_EXECUTION_MODE == "manual_approval" and task_queue is not None:
            sender = message.get("agent_name", "unknown-agent")
            content = message.get("content", "")
            queued_task = task_queue.add_task(
                sender=sender,
                content=content,
                intent=intent,
            )

            proposal += (
                "\n\n"
                f"Queued locally for manual approval as task #{queued_task.task_id}.\n"
                "Use `/tasks` in the local console to view pending tasks.\n"
                f"Use `/approve {queued_task.task_id}` or `/reject {queued_task.task_id}`."
            )

        return proposal

    if intent == "delegate_task":
        known_agents = get_known_agents_from_hub()
        return build_delegation_proposal(message, known_agents=known_agents)

    return build_response(
        message,
        intent=intent,
        max_tokens=max_tokens,
    )


def run_hub_loop() -> None:
    """
    Run the hub polling loop.

    This loop fetches new messages, responds only to mentions,
    and respects the hub rate limit by sleeping between requests.
    """

    validate_hub_config()

    # Runtime controls can be changed while the loop is running through console commands.
    controls = HubRuntimeControls(
        paused=False,
        should_stop=False,
        max_responses_per_run=HUB_MAX_RESPONSES_PER_RUN,
        max_tokens=HUB_RESPONDER_MAX_TOKENS,
    )

    task_queue = HubTaskQueue()

    # Start local console controls in the background without blocking hub polling.
    start_console_control_thread(controls, task_queue=task_queue)

    responses_sent = 0
    last_seen = 0

    try:
        # Load existing messages once so the agent does not reply to old hub history.
        existing_messages = fetch_messages(since=0)

        for message in existing_messages:
            seq = get_message_seq(message)

            if seq is not None:
                last_seen = max(last_seen, seq)

    except RequestException as error:
        print(f"Could not fetch existing hub messages at startup: {error}")
        print("Starting with last_seen = 0. The loop will retry.")

    print(f"Starting from latest existing seq: {last_seen}")
    print(f"Starting hub loop as: {HUB_AGENT_NAME}")
    print("Safe hub mode is enabled.")
    print(f"Dry run: {HUB_DRY_RUN}")
    print(f"Execution mode: {HUB_EXECUTION_MODE}")
    print(f"Approved task runner: {HUB_APPROVED_TASK_RUNNER}")
    print(f"LLM responder: {HUB_USE_LLM_RESPONDER}")
    print(f"Approved task tool mode: {HUB_APPROVED_TASK_TOOL_MODE}")
    print(f"Max responses per run: {controls.max_responses_per_run}")
    print(f"Max tokens: {controls.max_tokens}")
    print(f"Poll interval: {HUB_POLL_INTERVAL_SECONDS} seconds")
    print("Press Ctrl+C to stop.\n")

    try:
        while not controls.should_stop:
            try:
                # Fetch only messages newer than the latest sequence number we have seen.
                messages = fetch_messages(since=last_seen)
            except RequestException as error:
                print(f"Could not fetch hub messages: {error}")
                time.sleep(HUB_POLL_INTERVAL_SECONDS)
                continue

            for message in messages:
                seq = get_message_seq(message)

                # Update last_seen even for ignored messages so they are not processed again.
                if seq is not None:
                    last_seen = max(last_seen, seq)

                if not should_respond_to_message(message):
                    continue

                sender = message.get("agent_name", "unknown-agent")
                content = message.get("content", "")

                # Detect intent before responding so the agent only handles relevant messages.
                intent = detect_hub_intent(content)

                # Ignore mentions that do not match supported collaboration intents.
                if not should_handle_intent(intent):
                    print(f"Ignoring mention from {sender} with unsupported intent: {intent}")
                    continue

                # Pause mode keeps the agent online but prevents it from posting.
                if controls.paused:
                    print(f"Agent is paused. Ignoring mention from {sender}.")
                    continue

                # Safety cap to avoid spamming the hub or using too many LLM calls.
                if responses_sent >= controls.max_responses_per_run:
                    print("Max responses reached for this run. Staying online but not posting more responses.")
                    continue

                print(f"Received mention from {sender}: {content}")
                print(f"Detected intent: {intent}")

                response = build_task_aware_response(
                    message,
                    intent=intent,
                    max_tokens=controls.max_tokens,
                    task_queue=task_queue,
                )

                # Final safety layer before anything is printed or posted to the shared hub.
                response = sanitize_hub_response(response, fallback_sender=sender)

                if HUB_DRY_RUN:
                    # Dry-run mode shows what would be posted without sending it to the hub.
                    responses_sent += 1
                    print("Dry run enabled. Would post response:")
                    print(response)
                    print(f"Dry-run responses this run: {responses_sent}/{controls.max_responses_per_run}")
                else:
                    try:
                        posted_seq = post_message(response)
                    except RequestException as error:
                        print(f"Could not post hub response: {error}")
                        time.sleep(HUB_POLL_INTERVAL_SECONDS)
                        continue

                    responses_sent += 1

                    print(f"Posted response with seq: {posted_seq}")
                    print(f"Responses sent this run: {responses_sent}/{controls.max_responses_per_run}")

                    # Extra sleep after posting because POST is also a request.
                    time.sleep(HUB_POLL_INTERVAL_SECONDS)

            # Sleep after every successful polling cycle.
            time.sleep(HUB_POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        controls.should_stop = True
        print("\nHub loop stopped by user.")



if __name__ == "__main__":
    run_hub_loop()