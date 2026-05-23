import requests

from src.hub.hub_config import HUB_AGENT_NAME, HUB_BASE_URL, HUB_PASSWORD


# Avoid hanging forever if the hub does not respond.
REQUEST_TIMEOUT_SECONDS = 10


def fetch_messages(since: int = 0) -> list[dict]:
    """
    Fetch messages from the hub after a given sequence number.

    Args:
        since: Fetch messages with seq greater than this number.

    Returns:
        A list of message dictionaries from the hub.
    """

    response = requests.get(
        f"{HUB_BASE_URL}/api/messages",
        params={
            # The hub uses "since" so the agent only receives new messages.
            "since": since,

            # Password is read from environment config, not hardcoded here.
            "password": HUB_PASSWORD,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    # Raise an exception for HTTP errors instead of silently continuing.
    response.raise_for_status()
    data = response.json()

    return data.get("messages", [])


def post_message(content: str) -> int | None:
    """
    Send a message to the hub.

    Args:
        content: Message content to send.

    Returns:
        The sequence number of the posted message if available.
    """

    response = requests.post(
        f"{HUB_BASE_URL}/api/message",
        json={
            "agent_name": HUB_AGENT_NAME,
            "content": content,

            # The password authenticates the agent against the hub.
            "password": HUB_PASSWORD,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()
    data = response.json()

    return data.get("seq")


def get_stats() -> dict:
    """
    Fetch hub statistics such as message counts and caps.

    Returns:
        Hub stats as a dictionary.
    """

    response = requests.get(
        f"{HUB_BASE_URL}/api/stats",
        params={
            "password": HUB_PASSWORD,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    # Small manual smoke test for checking hub connectivity.
    stats = get_stats()
    print("Hub stats:")
    print(stats)

    messages = fetch_messages(since=0)
    print(f"\nFetched {len(messages)} messages.")