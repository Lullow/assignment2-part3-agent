import re

from src.hub.hub_config import HUB_AGENT_NAME


ASSIGNMENT_VERBS = [
    "create",
    "write",
    "update",
    "edit",
    "inspect",
    "review",
    "test",
    "implement",
    "add",
    "fix",
    "build",
    "summarize",
    "analyze",
]

NON_ASSIGNMENT_PHRASES = [
    "thanks",
    "thank you",
    "tack",
    "available",
    "ready",
    "if you are ready",
    "if you're ready",
    "om du är redo",
    "kommer att",
    "will create",
    "will work on",
    "can help",
    "finns tillgänglig",
]

ASSIGNMENT_PREFIXES = [
    "",
    "please",
    "can you",
    "could you",
    "would you",
    "kan du",
]

MENTION_PATTERN = re.compile(r"@[a-z0-9][a-z0-9_-]*")


def _agent_mention() -> str:
    return f"@{HUB_AGENT_NAME.lower()}"


def _starts_with_assignment(text: str) -> bool:
    """
    Check whether text after a mention starts like a direct task assignment.
    """

    normalized = text.strip(" \t\n\r,.:;-")

    for prefix in ASSIGNMENT_PREFIXES:
        for verb in ASSIGNMENT_VERBS:
            phrase = f"{prefix} {verb}".strip()

            if normalized == phrase or normalized.startswith(f"{phrase} "):
                return True

    return False


def is_clear_assignment_to_agent(content: str) -> bool:
    """
    Decide whether a direct mention is a clear task assignment to this agent.

    Mentions alone are not enough. In group collaboration, agents often mention
    each other in status updates, thanks, or planning messages. This guard helps
    prevent queue spam by requiring a clear action verb near the agent mention.
    """

    if not content:
        return False

    text = content.lower()
    mention = _agent_mention()

    if mention not in text:
        return False

    # Avoid turning thanks/status chatter into queued execution tasks.
    if any(phrase in text for phrase in NON_ASSIGNMENT_PHRASES):
        return False

    mention_index = text.find(mention)
    after_mention = text[mention_index + len(mention):]

    return _starts_with_assignment(after_mention)


def is_clear_assignment_to_other_agent(content: str) -> bool:
    """
    Detect clear task assignments to another mentioned agent.
    """

    if not content:
        return False

    text = content.lower()
    this_agent = _agent_mention()

    for match in MENTION_PATTERN.finditer(text):
        mentioned_agent = match.group()

        if mentioned_agent == this_agent:
            continue

        after_mention = text[match.end():]

        if _starts_with_assignment(after_mention):
            return True

    return False


def build_unclear_assignment_response() -> str:
    """
    Build a short response when the agent is mentioned but not clearly assigned a task.
    """

    return (
        "ACKNOWLEDGED\n\n"
        "I am available, but I will wait for a clear assigned task before queueing "
        "local execution.\n\n"
        "Please assign me a specific task like:\n"
        f"`@{HUB_AGENT_NAME} create test_calculator.py with tests for add, subtract, and multiply.`"
    )