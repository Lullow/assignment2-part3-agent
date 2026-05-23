import os
from dotenv import load_dotenv


load_dotenv()


HUB_BASE_URL = os.getenv("HUB_BASE_URL", "").rstrip("/")
HUB_PASSWORD = os.getenv("HUB_PASSWORD", "")
HUB_AGENT_NAME = os.getenv("HUB_AGENT_NAME", "lullo-swe-agent")
HUB_POLL_INTERVAL_SECONDS = float(os.getenv("HUB_POLL_INTERVAL_SECONDS", "1.2"))


def validate_hub_config() -> None:
    """
    Validate required hub configuration.

    The real hub password should be stored in .env, never hardcoded in source code.
    """

    if not HUB_BASE_URL:
        raise ValueError("Missing HUB_BASE_URL in environment.")

    if not HUB_PASSWORD:
        raise ValueError("Missing HUB_PASSWORD in environment.")

    if not HUB_AGENT_NAME:
        raise ValueError("Missing HUB_AGENT_NAME in environment.")

    if HUB_POLL_INTERVAL_SECONDS < 1.0:
        raise ValueError("HUB_POLL_INTERVAL_SECONDS must be at least 1.0 due to hub rate limit.")