import os
from dotenv import load_dotenv


# Load local environment variables from .env during development.
# In production, these values can instead come from the runtime environment.
load_dotenv()

# When enabled, the hub loop prints planned responses instead of posting them.
HUB_DRY_RUN = os.getenv("HUB_DRY_RUN", "true").lower() == "true"

# Safety cap for how many hub messages the agent may answer in one run.
HUB_MAX_RESPONSES_PER_RUN = int(os.getenv("HUB_MAX_RESPONSES_PER_RUN", "3"))

# Remove trailing slash so endpoint paths can be joined consistently.
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "").rstrip("/")

# Secrets should be read from environment variables, never hardcoded.
HUB_PASSWORD = os.getenv("HUB_PASSWORD", "")

# Default agent name used when no custom name is provided.
HUB_AGENT_NAME = os.getenv("HUB_AGENT_NAME", "lullo-swe-agent")

# How often the agent polls the hub for new tasks.
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