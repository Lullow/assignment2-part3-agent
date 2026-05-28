# Del 3 Agent Design

## Goal

This agent is built for Assignment 2 Part 3. It participates in a shared multi-agent software engineering hub where several student agents communicate through a common group chat.

The goal is not to make the agent take over the project. The goal is to make it a safe, useful, and collaborative participant.

## Agent role

The agent's default role is:

- safety-aware reviewer
- tester
- integration-support agent
- lightweight coordinator when the team lacks structure

The agent can suggest small code snippets or patches when useful, but it should not act as the main implementation agent unless directly asked.

## Current architecture

The simplified hub flow is:

1. Fetch new messages from the hub.
2. Ignore old messages, empty messages, and the agent's own messages.
3. Detect a lightweight keyword intent as a hint.
4. Use an LLM-based response decision gate to decide whether the agent should respond.
5. Generate a short, safe, text-only response.
6. Sanitize the response before printing or posting.
7. Respect runtime limits such as pause mode, max responses, token limits, and hub rate limits.

## Response decision gate

The response decision gate decides whether the agent should respond to a message.

It returns:

- `should_respond`
- `reason`
- `response_type`

Example response types:

- `structure_project`
- `claim_review_task`
- `review_feedback`
- `test_plan`
- `integration_support`
- `code_suggestion`
- `clarify`
- `answer_question`
- `ignore`

This makes the agent more flexible than hardcoded mention-only routing, while still keeping the behavior controlled.

## Responder behavior

When the agent responds, it should provide visible value in the shared chat.

Useful contributions include:

- task breakdowns
- lightweight collaboration protocol suggestions
- review notes
- test ideas
- integration risks
- concrete mismatch detection
- minimal code suggestions
- clear next steps

The agent should avoid generic replies, duplicate work, and unnecessary restructuring once code already exists.

## Collaboration protocol

For broad all-agent kickoff messages, the agent may suggest a lightweight protocol:

- `[CLAIM]` before starting work
- `[OUTPUT]` when sharing code, tests, or concrete results
- `[REVIEW]` when giving feedback
- avoid duplicate work
- prefer one minimal shared file structure
- switch from planning to integration review when code already exists

## Safety design

The agent is text-only in the hub by default.

It must not:

- reveal secrets, API keys, passwords, private URLs, or environment variables
- claim that it executed code unless it actually did
- claim that it edited files unless it actually did
- run local commands automatically from hub messages
- instruct other agents to run destructive commands
- spam the group chat

Local command execution, if used, must happen through local console/manual approval.

## Runtime controls

The agent supports runtime controls such as:

- pause mode
- stop mode
- max responses per run
- max response tokens

This helps control cost, prevent spam, and keep the agent safe during live group-chat tests.

## Known limitations

The agent still has limitations:

- It does not have full shared memory of the whole project beyond the messages it sees.
- It can miss some context if other agents only create local files and do not share their output.
- It may still respond too often if the max response limit is set too high.
- It may need prompt tuning to better detect concrete integration conflicts.
- It cannot verify code unless code or test output is shared in the hub.

## Recommended live settings

For testing:

```env
HUB_DRY_RUN=true
HUB_MAX_RESPONSES_PER_RUN=3
HUB_USE_LLM_RESPONSE_DECISION=true
HUB_USE_LLM_RESPONDER=true

For controlled live use:

HUB_DRY_RUN=false
HUB_MAX_RESPONSES_PER_RUN=3
HUB_USE_LLM_RESPONSE_DECISION=true
HUB_USE_LLM_RESPONDER=true
