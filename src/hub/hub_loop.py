import time

from requests import RequestException

from src.hub.hub_client import fetch_messages, post_message
from src.hub.hub_config import (
    HUB_AGENT_NAME,
    HUB_POLL_INTERVAL_SECONDS,
    HUB_DRY_RUN,
    HUB_MAX_RESPONSES_PER_RUN,
    validate_hub_config,
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

    if sender == HUB_AGENT_NAME:
        return False

    if not content:
        return False

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


def run_hub_loop() -> None:
    """
    Run the hub polling loop.

    This loop fetches new messages, responds only to mentions,
    and respects the hub rate limit by sleeping between requests.
    """

    validate_hub_config()

    responses_sent = 0

    existing_messages = fetch_messages(since=0)

    last_seen = 0
    for message in existing_messages:
        seq = get_message_seq(message)

        if seq is not None:
            last_seen = max(last_seen, seq)

    print(f"Starting from latest existing seq: {last_seen}")
    print(f"Starting hub loop as: {HUB_AGENT_NAME}")
    print("Safe hub mode is enabled.")
    print(f"Dry run: {HUB_DRY_RUN}")
    print(f"Max responses per run: {HUB_MAX_RESPONSES_PER_RUN}")
    print(f"Poll interval: {HUB_POLL_INTERVAL_SECONDS} seconds")
    print("Press Ctrl+C to stop.\n")

    while True:
        messages = fetch_messages(since=last_seen)

        for message in messages:
            seq = get_message_seq(message)

            if seq is not None:
                last_seen = max(last_seen, seq)

            if not should_respond_to_message(message):
                continue

            if responses_sent >= HUB_MAX_RESPONSES_PER_RUN:
                print("Max responses reached for this run. Staying online but not posting more responses.")
                continue

            sender = message.get("agent_name", "unknown-agent")
            content = message.get("content", "")

            print(f"Received mention from {sender}: {content}")

            response = build_simple_response(message)

            if HUB_DRY_RUN:
                responses_sent += 1
                print("Dry run enabled. Would post response:")
                print(response)
                print(f"Dry-run responses this run: {responses_sent}/{HUB_MAX_RESPONSES_PER_RUN}")
            else:
                posted_seq = post_message(response)
                responses_sent += 1

                print(f"Posted response with seq: {posted_seq}")
                print(f"Responses sent this run: {responses_sent}/{HUB_MAX_RESPONSES_PER_RUN}")

                # Extra sleep after posting because POST is also a request.
                time.sleep(HUB_POLL_INTERVAL_SECONDS)

        time.sleep(HUB_POLL_INTERVAL_SECONDS)



if __name__ == "__main__":
    run_hub_loop()