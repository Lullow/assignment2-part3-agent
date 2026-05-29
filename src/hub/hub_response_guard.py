from src.hub.hub_config import HUB_AGENT_NAME


# Maximum length for a message posted to the shared hub.
# This prevents the agent from posting overly long responses.
MAX_HUB_RESPONSE_LENGTH = 3500


# Simple denylist for obviously sensitive content.
# This is not a complete secret scanner, but it catches common mistakes.
BLOCKED_RESPONSE_PATTERNS = [
    "OPENAI_API_KEY",
    "HUB_PASSWORD",
    "API_KEY",
    "password=",
    "BEGIN PRIVATE KEY",
    ".env",
]


def sanitize_hub_response(response: str, fallback_sender: str = "unknown-agent") -> str:
    """
    Sanitize a response before posting it to the shared hub.

    This is a defensive layer between the LLM responder and the public group chat.
    It prevents empty, overly long, or obviously sensitive responses from being posted.
    """

    # Remove leading/trailing whitespace before validation and posting.
    cleaned = response.strip()

    # Never post an empty response to the hub.
    if not cleaned:
        return (
            f"Hi {fallback_sender}, this is {HUB_AGENT_NAME}. "
            "I received your message, but I could not generate a safe response."
        )

    # Use uppercase comparison so pattern matching is case-insensitive.
    upper_cleaned = cleaned.upper()

    for pattern in BLOCKED_RESPONSE_PATTERNS:
        # Block responses that appear to contain secrets or secret-related config names.
        if pattern.upper() in upper_cleaned:
            return (
                f"Hi {fallback_sender}, this is {HUB_AGENT_NAME}. "
                "I received your message, but I will not share sensitive configuration or secret-related content."
            )

    # Trim very long responses so the agent does not spam the shared hub.
    if len(cleaned) > MAX_HUB_RESPONSE_LENGTH:
        cleaned = cleaned[:MAX_HUB_RESPONSE_LENGTH].rstrip()
        cleaned += "..."

    return cleaned