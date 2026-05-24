import time

from requests import RequestException

from src.hub.hub_client import fetch_messages, post_message
from src.hub.hub_config import (
    HUB_AGENT_NAME,
    HUB_POLL_INTERVAL_SECONDS,
    validate_hub_config,
)


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

    existing_messages = fetch_messages(since=0)

    last_seen = 0
    for message in existing_messages:
        seq = message.get("seq")
        if isinstance(seq, int):
            last_seen = max(last_seen, seq)

    print(f"Starting from latest existing seq: {last_seen}")
    print(f"Starting hub loop as: {HUB_AGENT_NAME}")
    print("Safe hub mode is enabled.")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            messages = fetch_messages(since=last_seen)

            for message in messages:
                seq = message.get("seq")

                if isinstance(seq, int):
                    last_seen = max(last_seen, seq)

                if not should_respond_to_message(message):
                    continue

                sender = message.get("agent_name", "unknown-agent")
                content = message.get("content", "")

                print(f"Received mention from {sender}: {content}")

                response = build_simple_response(message)
                posted_seq = post_message(response)

                print(f"Posted response with seq: {posted_seq}")

                # Extra sleep after posting because POST is also a request.
                time.sleep(HUB_POLL_INTERVAL_SECONDS)

            time.sleep(HUB_POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\nHub loop stopped by user.")
            break

        except RequestException as error:
            print(f"Hub request failed: {error}")
            time.sleep(HUB_POLL_INTERVAL_SECONDS)

        except Exception as error:
            print(f"Unexpected hub loop error: {error}")
            time.sleep(HUB_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_hub_loop()