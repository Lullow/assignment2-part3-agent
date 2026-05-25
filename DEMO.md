# Demo Guide

This guide shows how to run the Assignment 2 Part 3 hub agent locally or in Docker.

## Before Running

Create a `.env` file from `.env.example` and fill in the hub and model settings:

```bash
cp .env.example .env
```

At minimum, check these values:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `MODEL_NAME`
- `HUB_BASE_URL`
- `HUB_PASSWORD`
- `HUB_AGENT_NAME`

For a safe first demo, keep:

```env
HUB_DRY_RUN=true
HUB_MAX_RESPONSES_PER_RUN=3
HUB_USE_LLM_RESPONDER=false
HUB_EXECUTION_MODE=review_only
HUB_APPROVED_TASK_RUNNER=placeholder
HUB_APPROVED_TASK_TOOL_MODE=read_only
```

## Local Run

Install dependencies, then start the hub loop:

```bash
pip install -r requirements.txt
python -m src.hub.hub_loop
```

## Docker Run

Build and run the container:

```bash
docker build -t assignment2-part3-agent .
docker run -it --rm --env-file .env assignment2-part3-agent
```

## Runtime Controls

While the hub loop is running, type commands into the local console:

```text
/status
/pause
/resume
/tokens 100
/responses 1
/tasks
/approve 1
/reject 1
/quit
```

## Expected Behavior

- The agent connects to the hub when the hub is available.
- If the hub is down, the agent logs errors and keeps running.
- The agent only responds to direct mentions.
- In dry-run mode, responses are printed locally instead of posted to the hub.
- The hub-facing agent does not expose local bash or file-editing tools.

## Approved Local Edit Test

This optional test verifies that an approved hub task can run through the local Part 2 SWE-agent and make a controlled file edit.

Before running it, set:

```env
HUB_EXECUTION_MODE=manual_approval
HUB_APPROVED_TASK_RUNNER=part2_agent
HUB_APPROVED_TASK_TOOL_MODE=local_tools
```

Create a temporary test file:

```bash
mkdir -p tmp
cat > tmp/bridge_test.md <<'EOF'
# Bridge Test

Status: TODO
EOF
```

Run an approved local task:

```bash
python3 - <<'PY'
from src.hub.hub_task_queue import HubTaskQueue
from src.hub.hub_execution_bridge import run_approved_task

queue = HubTaskQueue()
task = queue.add_task(
    sender="human",
    content=(
        "Update tmp/bridge_test.md by replacing 'Status: TODO' "
        "with 'Status: completed by approved Part 2 agent'. "
        "Use the smallest safe edit."
    ),
    intent="execute_task",
)

print(run_approved_task(task))
PY
```

Verify the file:

```bash
cat tmp/bridge_test.md
```

Expected result:

```text
# Bridge Test

Status: completed by approved Part 2 agent
```

Clean up:

```bash
rm -f tmp/bridge_test.md
```

This test demonstrates that the agent can perform a real local edit, but only through the approved bridge and existing Part 2 safety checks.



## Dynamic Group Collaboration Test

This test does not require the hub to be online.

```bash
python - <<'PY'
from src.hub.hub_intent import detect_hub_intent
from src.hub.hub_collaboration_role import choose_collaboration_role
from src.hub.hub_group_response import build_group_coordination_response

message = {
    "agent_name": "human",
    "content": "@all agents build a small todo CLI app together",
}

intent = detect_hub_intent(message["content"])
role = choose_collaboration_role(
    content=message["content"],
    intent=intent,
    is_group_context=True,
)

print("Intent:", intent)
print("Role:", role)
print()
print(build_group_coordination_response(message, intent, role))
PY
```

## Expected Behavior

- The message is detected as a broad task.
- The agent chooses a temporary role.
- The response suggests scope and task ownership first.
- The agent does not immediately execute the full group task.
