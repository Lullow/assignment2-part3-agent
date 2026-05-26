from typing import Literal


# Allowed intent labels for hub messages.
# Literal makes the return type stricter than using a plain string.
HubIntent = Literal[
    "review",
    "plan",
    "status",
    "help",
    "question",
    "code_request",
    "execute_task",
    "delegate_task",
    "ignore",
]


# Keywords that indicate the sender wants this agent to perform or implement work.
# This does not mean the agent will execute tools automatically; it only detects intent.
EXECUTE_TASK_KEYWORDS = [
    "implement",
    "build",
    "create",
    "add",
    "fix",
    "update",
    "modify",
    "change",
    "write code",
    "make this",
    "do this",
    "inspect",
    "inspect your repo",
    "analyze",
    "analyse",
    "investigate",
    "check your repo",
    "utför",
    "bygg",
    "skapa",
    "lägg till",
    "fixa",
    "ändra",
    "uppdatera",
    "analysera",
    "undersök",
    "kolla ditt repo",
]


# Keywords that indicate the sender wants a code suggestion, not direct execution.
CODE_REQUEST_KEYWORDS = [
    "suggest a patch",
    "code suggestion",
    "code snippet",
    "patch",
    "implementation help",
    "can you suggest code",
    "föreslå kod",
    "kodförslag",
    "patchförslag",
]


# Keywords that indicate coordination between multiple agents.
DELEGATE_TASK_KEYWORDS = [
    "delegate",
    "assign",
    "split the task",
    "who should do",
    "coordinate agents",
    "ask another agent",
    "delegera",
    "tilldela",
    "dela upp",
]


# Keywords that indicate the sender wants feedback or review.
REVIEW_KEYWORDS = [
    "review",
    "code review",
    "check this",
    "feedback",
    "look over",
    "granska",
    "kolla igenom",
]


# Keywords that indicate planning or next-step coordination.
PLAN_KEYWORDS = [
    "plan",
    "next step",
    "coordinate",
    "roadmap",
    "what should we do",
    "suggest",
    "suggest one safe contribution",
    "safe contribution",
    "team project",
    "contribution",
    "nästa steg",
    "planera",
    "föreslå",
    "bidrag",
    "säkert bidrag",
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

    More specific intents should be checked before broader intents.
    """

    # Normalize casing so keyword matching works regardless of capitalization.
    normalized = content.lower()

    # Order matters: delegation is more specific than a general plan or question.
    if any(keyword in normalized for keyword in DELEGATE_TASK_KEYWORDS):
        return "delegate_task"

    # Code suggestions are separated from execution requests for safety.
    if any(keyword in normalized for keyword in CODE_REQUEST_KEYWORDS):
        return "code_request"

    # Detect requests that sound like implementation work.
    # Later logic can still decide whether the agent is allowed to act on it.
    if any(keyword in normalized for keyword in EXECUTE_TASK_KEYWORDS):
        return "execute_task"

    if any(keyword in normalized for keyword in REVIEW_KEYWORDS):
        return "review"

    if any(keyword in normalized for keyword in PLAN_KEYWORDS):
        return "plan"

    if any(keyword in normalized for keyword in STATUS_KEYWORDS):
        return "status"

    if any(keyword in normalized for keyword in HELP_KEYWORDS):
        return "help"

    # Questions are checked late because many specific intents can also be phrased as questions.
    if any(keyword in normalized for keyword in QUESTION_KEYWORDS):
        return "question"

    # Ignore messages that do not clearly match a supported collaboration intent.
    return "ignore"


def should_handle_intent(intent: HubIntent) -> bool:
    """
    Decide whether this agent should handle a detected intent.
    """

    # Explicit allowlist: unknown or ignored intents are not handled by default.
    return intent in {
        "review",
        "plan",
        "status",
        "help",
        "question",
        "code_request",
        "execute_task",
        "delegate_task",
    }