from typing import Literal


# Allowed intent labels for hub messages.
# Literal makes the return type stricter than a plain string.
HubIntent = Literal[
    "review",
    "plan",
    "status",
    "help",
    "question",
    "ignore",
]


# Keywords that indicate the sender wants code or work reviewed.
REVIEW_KEYWORDS = [
    "review",
    "code review",
    "check this",
    "feedback",
    "look over",
    "granska",
    "kolla igenom",
]


# Keywords that indicate planning or coordination work.
PLAN_KEYWORDS = [
    "plan",
    "next step",
    "coordinate",
    "roadmap",
    "what should we do",
    "nästa steg",
    "planera",
]


# Keywords for simple availability or status checks.
STATUS_KEYWORDS = [
    "status",
    "are you online",
    "ping",
    "report",
    "available",
    "online",
]


# Keywords that indicate the sender is asking for assistance.
HELP_KEYWORDS = [
    "help",
    "assist",
    "support",
    "can you help",
    "hjälp",
]


# General question indicators in both English and Swedish.
QUESTION_KEYWORDS = [
    "?",
    "what",
    "why",
    "how",
    "when",
    "where",
    "vad",
    "varför",
    "hur",
    "när",
]


def detect_hub_intent(content: str) -> HubIntent:
    """
    Detect the collaboration intent of a hub message.

    This is a lightweight keyword-based filter.
    It helps the agent avoid responding too broadly in the shared hub.
    """

    # Normalize casing so keyword matching works regardless of capitalization.
    normalized = content.lower()

    # The order matters: more specific intents are checked before generic questions.
    if any(keyword in normalized for keyword in REVIEW_KEYWORDS):
        return "review"

    if any(keyword in normalized for keyword in PLAN_KEYWORDS):
        return "plan"

    if any(keyword in normalized for keyword in STATUS_KEYWORDS):
        return "status"

    if any(keyword in normalized for keyword in HELP_KEYWORDS):
        return "help"

    # Questions are checked late because many other intents can also contain questions.
    if any(keyword in normalized for keyword in QUESTION_KEYWORDS):
        return "question"

    # Ignore messages that do not clearly match a supported collaboration intent.
    return "ignore"


def should_handle_intent(intent: HubIntent) -> bool:
    """
    Decide whether this agent should handle a detected intent.
    """

    # Keep this as an explicit allowlist so new intent types are ignored by default.
    return intent in {
        "review",
        "plan",
        "status",
        "help",
        "question",
    }