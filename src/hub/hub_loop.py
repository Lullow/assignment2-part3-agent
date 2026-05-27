import time
from collections import deque

from requests import RequestException

from src.hub.hub_responder import build_llm_collaboration_response
from src.hub.hub_response_guard import sanitize_hub_response
from src.hub.hub_client import fetch_messages, post_message, get_stats
from src.hub.hub_intent import detect_hub_intent, should_handle_intent
from src.hub.hub_message_classifier import classify_hub_message
from src.hub.hub_task_proposal import build_task_proposal
from src.hub.hub_delegation import build_delegation_proposal
from src.hub.hub_task_queue import HubTaskQueue
from src.hub.hub_group_response import build_group_coordination_response
from src.hub.hub_collaboration_role import choose_collaboration_role

from src.hub.hub_coordination_followup import (
    should_post_coordination_followup,
    build_coordination_followup_response,
)

from src.hub.hub_config import (
    HUB_AGENT_NAME,
    HUB_DRY_RUN,
    HUB_MAX_RESPONSES_PER_RUN,
    HUB_POLL_INTERVAL_SECONDS,
    HUB_USE_LLM_RESPONDER,
    HUB_RESPONDER_MAX_TOKENS,
    HUB_EXECUTION_MODE,
    HUB_APPROVED_TASK_RUNNER,
    HUB_APPROVED_TASK_TOOL_MODE,
    HUB_ENABLE_GROUP_MENTIONS,
    HUB_CONSOLE_QUIET,
    validate_hub_config,
)

from src.hub.hub_runtime_controls import (
    HubRuntimeControls,
    start_console_control_thread,
)

from src.hub.hub_assignment_guard import (
    build_chat_collaboration_response,
    build_unclear_assignment_response,
    build_workflow_role_ack_response,
    is_agent_status_noise,
    is_chat_collaboration_task,
    is_clear_assignment_to_agent,
    is_clear_assignment_to_other_agent,
    is_manager_assignment_to_other_agent,
    is_workflow_role_assignment_to_agent,
)

GROUP_MENTION_KEYWORDS = [
    "@all",
    "@agents",
    "@bots",
    "@all-agents",
    "@all-bots",
    "@alla",
    "@alla-bottar",
    "alla bottar",
    "alla agenter",
    "alla agents",
    "all agent",
    "all agents",
    "all bots",
    "everyone",
]

AGENT_IDENTIFICATION_REQUESTS = [
    "agents, identify yourselves",
    "agents identify yourselves",
    "other agents, identify yourselves",
    "other agents identify yourselves",
    "agents, please identify yourselves",
    "agents please identify yourselves",
    "agents, introduce yourselves",
    "agents introduce yourselves",
    "agents: reply with your name",
    "agents reply with your name",
    "all agents: reply with your name",
    "all agents reply with your name",
    "all agents, identify yourselves",
    "all agents identify yourselves",
    "identify yourselves",
    "introduce yourselves",
    "reply with your name",
]

BROAD_COLLABORATION_CANDIDATE_TERMS = [
    "agents",
    "other agents",
    "all agents",
    "team",
    "remaining tasks",
    "workflow",
    "role",
    "review",
    "tests",
    "readme",
    "cli",
    "post your code",
]

RECENT_CONTEXT_LIMIT = 10
MAX_CONTEXT_MESSAGE_CHARS = 800


def hub_log(message: str) -> None:
    """
    Print hub-loop logs only when quiet console mode is disabled.

    This keeps the local control console usable during busy multi-agent tests.
    """
    if not HUB_CONSOLE_QUIET:
        print(message)


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


def format_recent_context(recent_context) -> str:
    """
    Format recent hub messages for semantic routing context.

    This stays bounded and trimmed so classifier context remains small.
    """

    if not recent_context:
        return "No recent context."

    entries = []

    for item in recent_context:
        content = item["content"]

        if len(content) > MAX_CONTEXT_MESSAGE_CHARS:
            content = content[:MAX_CONTEXT_MESSAGE_CHARS].rstrip() + "..."

        entries.append(
            f"seq={item['seq']} sender={item['sender']}:\n"
            f"{content}"
        )

    return "\n\n".join(entries)


def is_human_sender(sender: str) -> bool:
    """
    Check whether a hub message came from a human sender.

    The hub may represent humans in slightly different ways, for example:
    - "human"
    - "human:Lullo"
    - "Lullo (human)"
    """

    normalized = sender.lower().strip()

    return (
        normalized == "human"
        or normalized.startswith("human:")
        or normalized.endswith("(human)")
        or "(human)" in normalized
    )


def is_direct_mention_for_agent(content: str) -> bool:
    """
    Check if a message directly addresses this agent with @agent-name.

    Direct mentions require @ so passive references like
    "lullo-swe-agent can do README" do not trigger unnecessary replies.
    """

    normalized_content = content.lower()
    normalized_agent_name = HUB_AGENT_NAME.lower()

    return f"@{normalized_agent_name}" in normalized_content


def is_agent_identification_request(content: str) -> bool:
    """
    Detect narrow group requests for agents to identify themselves.
    """

    normalized = " ".join(content.lower().replace("\n", " ").split())

    return any(request in normalized for request in AGENT_IDENTIFICATION_REQUESTS)


def is_broad_collaboration_candidate(content: str) -> bool:
    """
    Broad gate for semantic classification fallback.

    Deterministic guards still handle hard safety. The LLM classifier only sees
    likely collaboration messages and cannot execute tools or approve local work.
    """

    normalized = content.lower()

    return any(term in normalized for term in BROAD_COLLABORATION_CANDIDATE_TERMS)


def can_answer_identification_request(sender: str) -> bool:
    """
    Allow identification replies for humans, agents, or explicit coordinators.

    Own messages are always ignored to prevent feedback loops.
    """

    normalized_sender = sender.lower().strip()

    if normalized_sender == HUB_AGENT_NAME.lower():
        return False

    return (
        is_human_sender(sender)
        or normalized_sender.endswith("-agent")
        or "coordinator" in normalized_sender
    )


def should_respond_to_message(message: dict) -> bool:
    """
    Decide whether this agent should respond to a hub message.

    The agent should:
    - ignore its own messages
    - ignore empty messages
    - respond to direct mentions
    - optionally respond to human group mentions when enabled
    """

    sender = message.get("agent_name", "")
    content = message.get("content", "")

    # Avoid responding to our own messages and creating a feedback loop.
    if sender == HUB_AGENT_NAME:
        return False

    # Ignore empty messages because there is nothing meaningful to process.
    if not content:
        return False

    # Passive references to this agent are ignored unless they use @agent-name.
    mentions_this_agent = is_direct_mention_for_agent(content)

    # Group mentions are limited to humans to avoid agent-to-agent broadcast loops.
    mentions_group = (
        HUB_ENABLE_GROUP_MENTIONS
        and is_human_sender(sender)
        and is_group_mention(content)
    )

    identification_request = (
        HUB_ENABLE_GROUP_MENTIONS
        and can_answer_identification_request(sender)
        and is_agent_identification_request(content)
    )

    return mentions_this_agent or mentions_group or identification_request


def build_agent_identification_response(content: str = "") -> str:
    """
    Build a safe, text-only identity response for hub coordination.
    """

    normalized = content.lower()

    if "reply with your name" in normalized or "remaining open tasks" in normalized:
        return (
            "IDENTIFIED\n\n"
            f"{HUB_AGENT_NAME} is online. I can take the README/demo instructions task: "
            "usage steps, examples, and a short run/demo section. I will keep the "
            "contribution chat-only unless I receive a clear local task for approval."
        )

    return (
        "IDENTIFIED\n\n"
        f"{HUB_AGENT_NAME} is online. I can help with planning, review, testing, "
        "README/demo instructions, or one small assigned task after local approval."
    )


def build_classifier_identify_response(content: str) -> str:
    return build_agent_identification_response(content)


def build_classifier_task_claim_response(
    task_to_claim: str | None,
    content: str,
) -> str:
    if task_to_claim:
        return (
            "TASK CLAIM\n\n"
            f"{HUB_AGENT_NAME} can take: {task_to_claim}. I will keep the contribution "
            "chat-only unless I receive a clear local task for approval."
        )

    return (
        "TASK CLAIM\n\n"
        f"{HUB_AGENT_NAME} can take one small remaining task, preferably README/demo "
        "instructions, review, or tests. I will keep the contribution chat-only unless "
        "I receive a clear local task for approval."
    )


def build_classifier_already_claimed_response(claimed_task: str) -> str:
    return (
        "ACKNOWLEDGED\n\n"
        f"{HUB_AGENT_NAME} already claimed: {claimed_task}. I will avoid duplicate "
        "claims and wait for the relevant handoff or code/context before contributing further."
    )


def build_classifier_clarify_response() -> str:
    return (
        "CLARIFICATION NEEDED\n\n"
        "I saw the message, but I need a clearer task or handoff before contributing. "
        "Please assign me one small role such as planning, review, tests, README/demo, "
        "or final refinement."
    )


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


def build_unclear_collaboration_request_response() -> str:
    """
    Build a short clarification response for unsupported direct mentions.
    """

    return (
        "ACKNOWLEDGED\n\n"
        "I saw the mention, but I need a clearer collaboration task. "
        "Please ask me to plan, review, test, suggest code, or take one small assigned role."
    )


def build_response(
    message: dict,
    intent: str | None = None,
    max_tokens: int | None = None,
    known_context: str | None = None,
) -> str:
    """
    Build a response for a hub message.

    By default, this uses the simple safe response.
    If HUB_USE_LLM_RESPONDER is enabled, it tries to use the LLM-based responder.

    If the LLM responder fails, the agent falls back to the simple safe response
    instead of crashing the hub loop.
    """

    if HUB_USE_LLM_RESPONDER:
        try:
            # Use the LLM responder only when explicitly enabled in config.
            return build_llm_collaboration_response(
                message,
                intent=intent,
                max_tokens=max_tokens,
                known_context=known_context,
            )
        except Exception as error:
            # Keep the hub loop alive even if the LLM provider fails.
            print(f"LLM responder failed, falling back to simple response: {error}")
            return build_simple_response(message)

    # Default safe mode: acknowledge mentions without calling the LLM.
    return build_simple_response(message)


def get_known_agents_from_hub() -> list[str]:
    """
    Fetch known agent names from the hub stats endpoint.

    If the hub stats request fails, return an empty list so delegation
    can still work without active agent information.
    """

    try:
        stats = get_stats()
    except RequestException as error:
        print(f"Could not fetch hub stats for delegation: {error}")
        return []

    per_agent = stats.get("per_agent", {})

    if not isinstance(per_agent, dict):
        return []

    return sorted(per_agent.keys())


def build_task_aware_response(
    message: dict,
    intent: str,
    max_tokens: int | None = None,
    task_queue: HubTaskQueue | None = None,
    known_context: str | None = None,
) -> str:
    """
    Build a response based on the detected hub intent.

    Task execution requests are converted into safe task proposals.
    Delegation requests are converted into safe delegation proposals.

    The agent does not execute hub tasks automatically.
    """

    if intent == "execute_task":
        proposal = build_task_proposal(message, intent)

        if HUB_EXECUTION_MODE == "manual_approval" and task_queue is not None:
            sender = message.get("agent_name", "unknown-agent")
            content = message.get("content", "")

            queued_task = task_queue.add_task(
                sender=sender,
                content=content,
                intent=intent,
            )

            proposal += (
                "\n\n"
                f"Queued locally for manual approval as task #{queued_task.task_id}.\n"
                "Use `/tasks` in the local console to view pending tasks.\n"
                f"Use `/approve {queued_task.task_id}` or `/reject {queued_task.task_id}`."
            )

        return proposal

    if intent == "delegate_task":
        known_agents = get_known_agents_from_hub()
        return build_delegation_proposal(message, known_agents=known_agents)

    return build_response(
        message,
        intent=intent,
        max_tokens=max_tokens,
        known_context=known_context,
    )


def is_group_mention(content: str) -> bool:
    """
    Check whether a message appears to address all agents/bots.

    Group mentions are optional because responding to broad messages can create
    coordination noise if every agent replies at once.
    """

    normalized = content.lower()

    return any(keyword in normalized for keyword in GROUP_MENTION_KEYWORDS)


def contains_code_block(content: str) -> bool:
    """
    Detect whether a hub message contains shared code.
    """

    return "```" in content


def build_collaboration_stall_response() -> str:
    """
    Build a bounded follow-up for stalled chat collaboration.

    This does not claim ownership or queue local execution.
    """

    return (
        "COLLABORATION CHECK\n\n"
        "The collaboration may be waiting for a clear handoff. "
        "The assigned implementation agent should share code in chat. "
        "If no code is shared, I can provide a small chat-only scaffold, "
        "review checklist, or test plan. "
        "I will not create files locally unless I receive a specific local task."
    )


def build_active_chat_task_response(content: str, sender: str) -> str:
    """
    Build a concrete chat-only contribution during active collaboration.

    This keeps role handoffs useful without queueing local execution.
    """

    text = content.lower()
    contributions = []

    if "cli" in text or "command" in text or "flow" in text:
        contributions.append("define the CLI flow: inputs, commands, output format, and error cases")

    if "test" in text or "testing" in text:
        contributions.append("write a chat-only test plan with key cases and expected results")

    if "review" in text:
        contributions.append("review the shared code for correctness, safety, and duplicate work")

    if not contributions:
        contributions.append("provide a small chat-only plan, scaffold, or review checklist")

    contribution_text = "; ".join(contributions)

    return (
        f"Accepted, {sender}. I can handle this as a chat-only role: {contribution_text}. "
        "Expected handoff: please share the implementation code, public function names, "
        "and any intended CLI entrypoint in chat.\n\n"
        "Initial plan from my side:\n"
        "- I will review the shared code for correctness and simple structure.\n"
        "- I will suggest CLI steps or test cases once the implementation is posted.\n"
        "- I will keep everything in chat and will not queue local execution unless I receive a specific local task."
    )


def run_hub_loop() -> None:
    """
    Run the hub polling loop.

    This loop fetches new messages, responds only to mentions,
    and respects the hub rate limit by sleeping between requests.
    """

    validate_hub_config()

    # Runtime controls can be changed while the loop is running through console commands.
    controls = HubRuntimeControls(
        paused=False,
        should_stop=False,
        max_responses_per_run=HUB_MAX_RESPONSES_PER_RUN,
        max_tokens=HUB_RESPONDER_MAX_TOKENS,
    )

    task_queue = HubTaskQueue()

    # Start local console controls in the background without blocking hub polling.
    start_console_control_thread(controls, task_queue=task_queue)

    responses_sent = 0
    last_seen = 0
    active_group_task = False
    coordination_followups_sent = 0
    MAX_COORDINATION_FOLLOWUPS_PER_RUN = 3
    active_chat_collaboration = False
    last_collaboration_activity_at = time.monotonic()
    collaboration_stall_followups_sent = 0
    MAX_COLLABORATION_STALL_FOLLOWUPS = 1
    COLLABORATION_STALL_SECONDS = 45
    recent_context = deque(maxlen=RECENT_CONTEXT_LIMIT)
    claimed_task = None

    try:
        # Load existing messages once so the agent does not reply to old hub history.
        existing_messages = fetch_messages(since=0)

        for message in existing_messages:
            seq = get_message_seq(message)

            if seq is not None:
                last_seen = max(last_seen, seq)

    except RequestException as error:
        print(f"Could not fetch existing hub messages at startup: {error}")
        print("Starting with last_seen = 0. The loop will retry.")

    print(f"Starting from latest existing seq: {last_seen}")
    print(f"Starting hub loop as: {HUB_AGENT_NAME}")
    print("Safe hub mode is enabled.")
    print(f"Dry run: {HUB_DRY_RUN}")
    print(f"Execution mode: {HUB_EXECUTION_MODE}")
    print(f"Approved task runner: {HUB_APPROVED_TASK_RUNNER}")
    print(f"LLM responder: {HUB_USE_LLM_RESPONDER}")
    print(f"Approved task tool mode: {HUB_APPROVED_TASK_TOOL_MODE}")
    print(f"Group mentions: {HUB_ENABLE_GROUP_MENTIONS}")
    print(f"Max responses per run: {controls.max_responses_per_run}")
    print(f"Max tokens: {controls.max_tokens}")
    print(f"Poll interval: {HUB_POLL_INTERVAL_SECONDS} seconds")
    print("Press Ctrl+C to stop.\n")

    try:
        while not controls.should_stop:
            try:
                # Fetch only messages newer than the latest sequence number we have seen.
                messages = fetch_messages(since=last_seen)
            except RequestException as error:
                print(f"Could not fetch hub messages: {error}")
                time.sleep(HUB_POLL_INTERVAL_SECONDS)
                continue

            for message in messages:
                seq = get_message_seq(message)

                # Update last_seen even for ignored messages so they are not processed again.
                if seq is not None:
                    last_seen = max(last_seen, seq)

                sender = message.get("agent_name", "unknown-agent")
                content = message.get("content", "")

                normalized_sender = sender.lower().strip()
                is_own_message = normalized_sender == HUB_AGENT_NAME.lower()

                # Hard safety guard: never process our own hub messages.
                # This must run before manager guards, status-noise checks,
                # deterministic routing, classifier fallback, and response building.
                if is_own_message:
                    hub_log("Ignoring own message.")
                    continue

                # Store recent context from other senders only.
                # This gives the semantic classifier current hub context without
                # letting the agent respond to itself or build loops from its own replies.
                if content:
                    recent_context.append(
                        {
                            "seq": seq,
                            "sender": sender,
                            "content": content,
                        }
                    )

                if is_human_sender(sender) and is_manager_assignment_to_other_agent(content):
                    hub_log("Another agent was assigned as manager/coordinator. Staying silent.")
                    continue

                if not sender.startswith("human:") and is_agent_status_noise(content):
                    hub_log(f"Ignoring agent status noise from {sender}.")
                    continue

                was_active_chat_collaboration = active_chat_collaboration

                if active_chat_collaboration and sender != HUB_AGENT_NAME and content:
                    last_collaboration_activity_at = time.monotonic()

                    if not sender.startswith("human:") and contains_code_block(content):
                        active_chat_collaboration = False
                        hub_log("Code block shared during chat collaboration. Stopping stall watchdog.")

                if should_post_coordination_followup(
                    sender=sender,
                    content=content,
                    active_group_task=active_group_task,
                ):
                    if coordination_followups_sent >= MAX_COORDINATION_FOLLOWUPS_PER_RUN:
                        continue

                    if controls.paused:
                        hub_log(f"Agent is paused. Ignoring coordination follow-up from {sender}.")
                        continue

                    if responses_sent >= controls.max_responses_per_run:
                        hub_log("Max responses reached. Skipping coordination follow-up.")
                        continue

                    response = build_coordination_followup_response(
                        sender=sender,
                        content=content,
                    )

                    response = sanitize_hub_response(response, fallback_sender=sender)

                    if HUB_DRY_RUN:
                        responses_sent += 1
                        coordination_followups_sent += 1
                        hub_log("Dry run enabled. Would post coordination follow-up:")
                        hub_log(response)
                        hub_log(f"Dry-run responses this run: {responses_sent}/{controls.max_responses_per_run}")
                    else:
                        try:
                            posted_seq = post_message(response)
                        except RequestException as error:
                            print(f"Could not post coordination follow-up: {error}")
                            time.sleep(HUB_POLL_INTERVAL_SECONDS)
                            continue

                        responses_sent += 1
                        coordination_followups_sent += 1
                        hub_log(f"Posted coordination follow-up with seq: {posted_seq}")
                        hub_log(f"Responses sent this run: {responses_sent}/{controls.max_responses_per_run}")
                        time.sleep(HUB_POLL_INTERVAL_SECONDS)

                    continue

                classifier_decision = None
                deterministic_should_respond = should_respond_to_message(message)
                known_context = (
                    f"Current claimed task by {HUB_AGENT_NAME}: {claimed_task or 'none'}\n\n"
                    f"Recent hub messages:\n{format_recent_context(recent_context)}"
                )

                if not deterministic_should_respond:
                    if not (
                        HUB_ENABLE_GROUP_MENTIONS
                        and is_broad_collaboration_candidate(content)
                    ):
                        continue

                    if controls.paused:
                        hub_log(f"Agent is paused. Ignoring classifier candidate from {sender}.")
                        continue

                    if responses_sent >= controls.max_responses_per_run:
                        hub_log("Max responses reached. Skipping classifier candidate.")
                        continue

                    # Deterministic guards handle hard safety. The classifier only makes
                    # a semantic routing suggestion; Python still controls all actions.
                    classifier_decision = classify_hub_message(
                        sender=sender,
                        content=content,
                        agent_name=HUB_AGENT_NAME,
                        known_context=known_context,
                    )

                    if not classifier_decision.should_respond:
                        continue

                    if (
                        classifier_decision.confidence < 0.55
                        and not is_direct_mention_for_agent(content)
                    ):
                        hub_log("Classifier confidence too low. Staying silent.")
                        continue

                mentions_group = HUB_ENABLE_GROUP_MENTIONS and is_group_mention(content)

                if mentions_group:
                    active_group_task = True

                # Detect intent before responding so the agent only handles relevant messages.
                intent = detect_hub_intent(content)

                suggested_role = choose_collaboration_role(
                    content=content,
                    intent=intent,
                    is_group_context=mentions_group,
                )

                if (
                    intent == "execute_task"
                    and not is_chat_collaboration_task(content)
                    and is_clear_assignment_to_other_agent(content)
                    and not is_clear_assignment_to_agent(content)
                ):
                    hub_log("Task appears assigned to another agent. Staying silent.")
                    continue

                # Pause mode keeps the agent online but prevents it from posting.
                if controls.paused:
                    hub_log(f"Agent is paused. Ignoring mention from {sender}.")
                    continue

                # Safety cap to avoid spamming the hub or using too many LLM calls.
                if responses_sent >= controls.max_responses_per_run:
                    hub_log("Max responses reached for this run. Staying online but not posting more responses.")
                    continue

                hub_log(f"Received mention from {sender}: {content}")
                hub_log(f"Detected intent: {intent}")
                hub_log(f"Suggested temporary role: {suggested_role}")

                response = None

                if classifier_decision is not None:
                    if classifier_decision.response_type == "identify":
                        response = build_classifier_identify_response(content)
                    elif classifier_decision.response_type == "acknowledge_workflow_role":
                        response = build_workflow_role_ack_response(content)
                    elif classifier_decision.response_type == "claim_task":
                        if claimed_task:
                            response = build_classifier_already_claimed_response(claimed_task)
                        else:
                            response = build_classifier_task_claim_response(
                                classifier_decision.task_to_claim,
                                content,
                            )

                            if classifier_decision.task_to_claim:
                                claimed_task = classifier_decision.task_to_claim
                    elif classifier_decision.response_type in {
                        "answer_question",
                        "review",
                        "plan",
                    }:
                        classifier_intent = {
                            "answer_question": "question",
                            "review": "review",
                            "plan": "plan",
                        }.get(classifier_decision.response_type, intent)

                        response = build_response(
                            message,
                            intent=classifier_intent,
                            max_tokens=controls.max_tokens,
                            known_context=known_context,
                        )
                    elif classifier_decision.response_type == "clarify":
                        response = build_classifier_clarify_response()
                    else:
                        continue

                elif is_agent_identification_request(content):
                    response = build_agent_identification_response(content)

                elif is_workflow_role_assignment_to_agent(content):
                    response = build_workflow_role_ack_response(content)

                # A direct @mention with unclear intent should get one safe clarification,
                # not silence and not local execution.
                elif not should_handle_intent(intent):
                    if is_direct_mention_for_agent(content):
                        response = build_unclear_collaboration_request_response()
                    else:
                        hub_log(f"Ignoring mention from {sender} with unsupported intent: {intent}")
                        continue

                if response is None:
                    if mentions_group:
                        response = build_group_coordination_response(
                            message,
                            intent,
                            suggested_role=suggested_role,
                        )
                    else:
                        if (
                            was_active_chat_collaboration
                            and not sender.startswith("human:")
                            and sender != HUB_AGENT_NAME
                            and intent == "execute_task"
                        ):
                            response = build_active_chat_task_response(content, sender)
                        elif intent == "execute_task" and is_chat_collaboration_task(content):
                            response = build_chat_collaboration_response(content)
                            active_chat_collaboration = True
                            last_collaboration_activity_at = time.monotonic()
                            collaboration_stall_followups_sent = 0
                        elif intent == "execute_task" and not is_clear_assignment_to_agent(content):
                            response = build_unclear_assignment_response()
                        else:
                            response = build_task_aware_response(
                                message,
                                intent=intent,
                                max_tokens=controls.max_tokens,
                                task_queue=task_queue,
                                known_context=known_context,
                            )

                # Final safety layer before anything is printed or posted to the shared hub.
                response = sanitize_hub_response(response, fallback_sender=sender)

                if HUB_DRY_RUN:
                    # Dry-run mode shows what would be posted without sending it to the hub.
                    responses_sent += 1
                    hub_log("Dry run enabled. Would post response:")
                    hub_log(response)
                    hub_log(f"Dry-run responses this run: {responses_sent}/{controls.max_responses_per_run}")
                else:
                    try:
                        posted_seq = post_message(response)
                    except RequestException as error:
                        print(f"Could not post hub response: {error}")
                        time.sleep(HUB_POLL_INTERVAL_SECONDS)
                        continue

                    responses_sent += 1

                    hub_log(f"Posted response with seq: {posted_seq}")
                    hub_log(f"Responses sent this run: {responses_sent}/{controls.max_responses_per_run}")

                    # Extra sleep after posting because POST is also a request.
                    time.sleep(HUB_POLL_INTERVAL_SECONDS)

            if (
                active_chat_collaboration
                and not controls.paused
                and responses_sent < controls.max_responses_per_run
                and collaboration_stall_followups_sent < MAX_COLLABORATION_STALL_FOLLOWUPS
                and time.monotonic() - last_collaboration_activity_at >= COLLABORATION_STALL_SECONDS
            ):
                response = build_collaboration_stall_response()
                response = sanitize_hub_response(response, fallback_sender="collaboration-stall")

                if HUB_DRY_RUN:
                    responses_sent += 1
                    collaboration_stall_followups_sent += 1
                    last_collaboration_activity_at = time.monotonic()
                    hub_log("Dry run enabled. Would post collaboration check:")
                    hub_log(response)
                    hub_log(f"Dry-run responses this run: {responses_sent}/{controls.max_responses_per_run}")
                else:
                    try:
                        posted_seq = post_message(response)
                    except RequestException as error:
                        print(f"Could not post collaboration check: {error}")
                        time.sleep(HUB_POLL_INTERVAL_SECONDS)
                        continue

                    responses_sent += 1
                    collaboration_stall_followups_sent += 1
                    last_collaboration_activity_at = time.monotonic()
                    hub_log(f"Posted collaboration check with seq: {posted_seq}")
                    hub_log(f"Responses sent this run: {responses_sent}/{controls.max_responses_per_run}")
                    time.sleep(HUB_POLL_INTERVAL_SECONDS)

            # Sleep after every successful polling cycle.
            time.sleep(HUB_POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        controls.should_stop = True
        print("\nHub loop stopped by user.")


if __name__ == "__main__":
    run_hub_loop()
