# Assignment 2 Part 3 Hub Agent

This project is a Python hub agent for Assignment 2 Part 3. It connects to a shared RunPod hub, reads group-chat messages from other agents, decides whether it should respond, and posts safe collaboration replies.

The project builds on my Part 2 local SWE-agent, but the hub layer is intentionally separate. Hub messages are treated as untrusted input. They must not directly run bash, edit files, apply patches, or start the local Part 2 agent.

## What The Agent Does

- Connects to the shared RunPod/HTTP hub.
- Fetches only new messages.
- Uses a response decision gate to decide whether to respond or ignore.
- Generates short, safe collaboration replies.
- Runs every response through a final guard before posting.
- Avoids spam, duplicate work, and taking over other agents' tasks.
- Can queue direct implementation requests for local manual approval.

The default collaboration role is:

- reviewer
- tester
- integration-support agent
- lightweight coordinator when the team has no clear structure

## Main Hub Flow

```text
RunPod hub message
-> src/hub/hub_loop.py
-> src/hub/hub_response_decision.py
-> src/hub/hub_responder.py
-> src/hub/hub_response_guard.py
-> src/hub/hub_client.py posts response
```

The Python code stays in control of polling, rate limits, response caps, dry-run mode, sanitization, posting, and local approval.

## Manual Approval Flow

Direct implementation-style hub requests can be queued locally, but they are not executed automatically.

```text
direct implementation request
-> local task queue
-> /tasks
-> /approve TASK_ID
-> src/hub/hub_execution_bridge.py
-> Part 2 agent/tools
```

This keeps remote hub input separated from local tool execution.

## Important Files

| File | Purpose |
| --- | --- |
| `src/hub/hub_client.py` | Talks to the RunPod hub API |
| `src/hub/hub_config.py` | Loads and validates hub settings |
| `src/hub/hub_loop.py` | Main polling/responding loop |
| `src/hub/hub_response_decision.py` | Decides respond vs ignore |
| `src/hub/hub_responder.py` | Writes safe collaboration responses |
| `src/hub/hub_response_guard.py` | Final safety filter before posting |
| `src/hub/hub_task_queue.py` | Stores pending local approval tasks |
| `src/hub/hub_runtime_controls.py` | Handles local live control commands |
| `src/hub/hub_execution_bridge.py` | Approved bridge to Part 2/tools |
| `config/system_prompt.md` | System prompt for the Part 2/tool-agent flow |

`config/system_prompt.md` is not the main prompt for normal hub chat replies. Normal hub chat behavior is mainly controlled by `src/hub/hub_response_decision.py` and `src/hub/hub_responder.py`.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

The code uses OpenAI-compatible API clients. I tested with OpenRouter and:

```env
MODEL_NAME=anthropic/claude-sonnet-4.6
```

GPT-4o can also be used as a fallback with an OpenAI-compatible configuration.

## Hub Configuration

Important `.env` values:

```env
OPENAI_API_KEY=your_openrouter_or_openai_key
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=anthropic/claude-sonnet-4.6

HUB_AGENT_NAME=lullo-swe-agent
HUB_BASE_URL=https://your-runpod-hub-url
HUB_PASSWORD=your-hub-password

HUB_DRY_RUN=true
HUB_USE_LLM_RESPONDER=true
HUB_USE_LLM_RESPONSE_DECISION=true
HUB_MAX_RESPONSES_PER_RUN=10
HUB_POLL_INTERVAL_SECONDS=5
HUB_DECISION_MAX_TOKENS=180
HUB_RESPONDER_MAX_TOKENS=500

HUB_EXECUTION_MODE=manual_approval
HUB_APPROVED_TASK_RUNNER=part2_agent
HUB_APPROVED_TASK_TOOL_MODE=local_tools
```

Use `HUB_DRY_RUN=true` for the first demo so the agent prints what it would post without sending messages to the hub.

## Run The Hub Agent

Local run:

```bash
python -m src.hub.hub_loop
```

Docker:

```bash
docker build -t assignment2-part3-agent .
docker run --env-file .env assignment2-part3-agent
```

## Runtime Controls

While the hub loop is running, type these commands in the local console:

| Command | Effect |
| --- | --- |
| `/status` | Show pause state and response/token limits |
| `/pause` | Keep polling but stop posting |
| `/resume` | Allow posting again |
| `/tokens N` | Set response token limit |
| `/responses N` | Set max responses for this run |
| `/tasks` | List pending local approval tasks |
| `/approve TASK_ID` | Approve a queued task |
| `/reject TASK_ID` | Reject a queued task |
| `/quit` | Stop the hub loop |

## Safety Design

Hub messages are untrusted. The hub layer does not directly expose tools.

Safety decisions:

- No direct bash execution from hub messages.
- No direct file edits from hub messages.
- No automatic patch application from other agents.
- Manual approval is required before local tool execution.
- A response guard runs before anything is posted.
- Response caps and pause mode help avoid spam.
- Secrets and `.env` values must never be shared.

## Local Part 2 Tools

The Part 2 agent can use controlled tools after local approval, depending on configuration:

- `bash`
- `read_file`
- `edit_file_section`

These tools still pass through Part 2 safety checks such as command blocking, path safety, output limiting, and max step limits.

## Demo

See `DEMO.md` for a short walkthrough with Docker commands, hub test prompts, expected behavior, and manual approval testing.

## Known Limitations

- The agent does not have full long-term memory of the entire hub.
- Multi-agent behavior is unpredictable because other agents may behave differently.
- Tool execution results are local after approval unless manually shared back to the hub.
- The response decision and responder prompts can still be tuned further.
