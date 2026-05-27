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
    "make",
    "generate",
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

COLLABORATION_ASSIGNMENT_PHRASES = [
    "work together",
    "collaborate",
    "you are the only two agents",
    "you are the only agents",
    "split the work",
    "share code in chat",
    "decide between yourselves",
    "decide who",
    "do not duplicate work",
    "avoid duplicate work",
    "collaboration rules",
    "local files are not automatically visible",
    "distribute roles",
    "agree who takes",
    "first agree",
]

MENTION_PATTERN = re.compile(r"@[a-z0-9][a-z0-9_-]*")


def is_agent_status_noise(content: str) -> bool:
    """
    Detect low-value status messages from other agents.

    These messages often quote earlier requests or report internal state.
    They should usually not trigger new task proposals.
    """

    if not content:
        return False

    text = content.lower().strip()

    return (
        text.startswith("taking on:")
        or text.startswith("done:")
        or text.startswith("status:")
        or text.startswith("[auto-summary]")
    )


def _agent_mention() -> str:
    return f"@{HUB_AGENT_NAME.lower()}"


def _mentions_this_agent(text: str) -> bool:
    return _agent_mention() in text


def _mentioned_agents(text: str) -> list[str]:
    return MENTION_PATTERN.findall(text)


def _starts_with_assignment(text: str) -> bool:
    """
    Check whether text after a mention starts like a direct task assignment.

    Examples that should match:
    - create tmp/file.py ...
    - please create tmp/file.py ...
    - can you review calculator.py ...
    """

    normalized = text.strip(" \t\n\r,.:;-")

    for prefix in ASSIGNMENT_PREFIXES:
        for verb in ASSIGNMENT_VERBS:
            phrase = f"{prefix} {verb}".strip()

            if normalized == phrase or normalized.startswith(f"{phrase} "):
                return True

    return False


def is_chat_collaboration_task(content: str) -> bool:
    """
    Detect multi-agent collaboration prompts that should stay text-only.

    These messages can include implementation words like "build" or "create",
    but they ask agents to coordinate in chat rather than run local execution.
    """

    if not content:
        return False

    text = content.lower()

    if not _mentions_this_agent(text):
        return False

    has_collaboration_phrase = any(
        phrase in text for phrase in COLLABORATION_ASSIGNMENT_PHRASES
    )

    return has_collaboration_phrase


def is_collaboration_assignment_to_agent(content: str) -> bool:
    """
    Detect broad collaboration assignments involving this agent.

    This is different from a direct local execution task. For example:
    '@lullo-swe-agent @josef-agent work together to create greeting.py'

    This should let the hub loop route the message to a text-only collaboration
    response instead of local execution.
    """

    if not content:
        return False

    text = content.lower()

    if not _mentions_this_agent(text):
        return False

    return is_chat_collaboration_task(content)


def is_clear_assignment_to_agent(content: str) -> bool:
    """
    Decide whether a direct mention is a clear assignment to this agent.

    Mentions alone are not enough. In group collaboration, agents often mention
    each other in status updates, thanks, or planning messages.

    This returns True for direct local execution tasks only.
    Chat collaboration prompts are handled separately.
    """

    if not content:
        return False

    text = content.lower()
    mention = _agent_mention()

    if mention not in text:
        return False

    # Chat collaboration tasks are not clear local execution assignments.
    if is_collaboration_assignment_to_agent(content):
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

    This helps the agent avoid answering for someone else.
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


def is_unclear_assignment_to_agent(content: str) -> bool:
    """
    Detect mentions of this agent that are not clear assignments.

    Useful when the hub loop wants to acknowledge availability without queueing
    local execution.
    """

    if not content:
        return False

    text = content.lower()

    return _mentions_this_agent(text) and not is_clear_assignment_to_agent(content)


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


def build_chat_collaboration_response(content: str) -> str:
    """
    Build a short text-only response for collaboration prompts.
    """

    text = content.lower()
    other_agents = [
        mention.lstrip("@")
        for mention in _mentioned_agents(text)
        if mention != _agent_mention()
    ]

    if other_agents:
        other_agent_text = ", ".join(other_agents)
        role_suggestion = f"{other_agent_text} can take implementation."
    else:
        role_suggestion = "Another agent can take implementation."

    return (
        "I can take review/demo instructions. "
        f"{role_suggestion} "
        "Please share proposed code in chat so I can review it and suggest run/test steps. "
        "I will not create files locally or queue local execution unless I receive a specific local task."
    )