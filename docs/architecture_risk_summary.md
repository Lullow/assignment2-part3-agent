# Architecture & Risk Summary

Assignment 2 Part 3 adds a safe hub collaboration layer on top of the existing Part 2 local SWE-agent. The design is deliberately split: hub messages never directly invoke tools; local execution only happens after console approval and through the Part 2 loop.

## Architecture Overview

```text
Part 3 Hub Layer
python -m src.hub.hub_loop

hub_loop.py
-> hub_client / intent / responder / guard
-> task queue + runtime controls
-> optional execution bridge
-> Part 2 SWE-agent only after /approve + config

Part 2 SWE-Agent
python src/main.py

main.py
-> agent_loop.py
-> llm_client + tool_registry
-> bash / read_file / edit_file_section / create_file
```

## Layer Breakdown

### Local Part 2 SWE-Agent

| Piece | Location | Role |
| --- | --- | --- |
| Entry | `src/main.py` | Reads a task, loads the system prompt, and calls `run_agent()` |
| Loop | `src/agent_loop.py` | Runs up to `MAX_STEPS=7`, handles structured decisions, and executes tools |
| LLM | `src/llm_client.py` | Calls an OpenAI-compatible model and returns structured output |
| Schema | `src/schemas.py` | Defines `AgentDecision`, `ToolCall`, and `ToolResult` |
| Prompt | `config/system_prompt.md` | Defines SWE-only behavior, refusal policy, and tool constraints |

Flow:

```text
user task
-> model decision
-> tool call or final answer
-> session history
-> repeat until yield or MAX_STEPS
```

### Hub-Agent Layer

| Piece | Location | Role |
| --- | --- | --- |
| Main loop | `src/hub/hub_loop.py` | Polls hub, filters messages, builds responses, and posts or dry-runs |
| HTTP client | `src/hub/hub_client.py` | Fetches messages, posts messages, and reads stats |
| Config | `src/hub/hub_config.py` | Loads and validates environment-driven modes |
| Intent | `src/hub/hub_intent.py` | Classifies hub messages into supported collaboration intents |
| Responses | `src/hub/hub_responder.py`, `src/hub/hub_task_proposal.py`, `src/hub/hub_delegation.py`, `src/hub/hub_group_response.py` | Builds text-only collaboration responses |
| Guard | `src/hub/hub_response_guard.py` | Trims responses, caps length, and blocks obvious secret-related content |
| Roles | `src/hub/hub_collaboration_role.py` | Chooses temporary collaboration roles |
| Follow-up | `src/hub/hub_coordination_followup.py` | Builds conservative coordination follow-ups |

Hub message flow:

```text
fetch
-> sequence tracking
-> mention filter
-> intent filter
-> group or direct response path
-> sanitize
-> dry-run print or live post
```

### Tools

The tools are available to the local Part 2 SWE-agent, not directly to hub messages.

| Tool | File | Safety |
| --- | --- | --- |
| `bash` | `src/tools/bash_tool.py` | Uses `src/safety.py` to block destructive commands and shell operators |
| `read_file` | `src/tools/file_reader.py` | Uses project-root and sensitive-path checks |
| `edit_file_section` | `src/tools/file_editor.py` | Requires exact text match and blocks sensitive paths |
| `create_file` | `src/tools/file_writer.py` | Creates only new files, blocks sensitive paths, refuses overwrites |
| Tool router | `src/tool_registry.py` | Dispatches validated tool calls |
| Output cap | `src/output_limiter.py` | Limits tool output size |

### Approval Queue

| Piece | Location | Behavior |
| --- | --- | --- |
| Queue | `src/hub/hub_task_queue.py` | Stores pending hub tasks in memory |
| Trigger | `src/hub/hub_loop.py` | Queues `execute_task` messages when `HUB_EXECUTION_MODE=manual_approval` |
| Console controls | `src/hub/hub_runtime_controls.py` | Supports `/tasks`, `/approve TASK_ID`, and `/reject TASK_ID` |
| Bridge | `src/hub/hub_execution_bridge.py` | Runs approved tasks through `placeholder` or `part2_agent` mode |
| Report | `src/hub/hub_result_report.py` | Builds a concise approved task report |

Default safe configuration:

```text
HUB_DRY_RUN=true
HUB_EXECUTION_MODE=review_only
HUB_APPROVED_TASK_RUNNER=placeholder
HUB_APPROVED_TASK_TOOL_MODE=read_only
HUB_USE_LLM_RESPONDER=false
```

### Runtime Controls

`src/hub/hub_runtime_controls.py` supports:

- `/status`
- `/pause`
- `/resume`
- `/tokens N`
- `/responses N`
- `/tasks`
- `/approve TASK_ID`
- `/reject TASK_ID`
- `/quit`

These controls are local only and do not expose tools to hub messages.

### Collaboration Behavior

The hub agent supports:

- intent routing for review, plan, status, help, question, code request, execute task, and delegation,
- delegation proposals with known agents from hub stats,
- group coordination when group mentions are enabled,
- temporary role selection such as planner, implementer, reviewer, tester, coordinator, clarifier, or observer,
- task claim suggestions that avoid permanent ownership claims,
- conservative coordination follow-up after other agents report progress.

## Strong Points

- Clear trust boundary: hub messages cannot directly execute local tools.
- Safe defaults: dry-run, review-only, placeholder runner, read-only tool mode, and LLM responder disabled.
- Manual approval flow before local execution.
- Separate local SWE-agent and hub collaboration layers.
- Conservative bash and path safety checks.
- `create_file` adds safer file creation without overwriting existing files.
- Response guard reduces risk of empty, overlong, or obvious secret-related hub output.
- Runtime controls make the hub loop adjustable without restart.
- Collaboration-first group behavior helps avoid duplicate work.
- Documentation and demo files explain the major modes and safety decisions.

## Weak Points & Risks

| Risk | Severity | Detail |
| --- | --- | --- |
| `read_only` is prompt-only | Medium | Tool registry does not enforce read-only mode; the Part 2 agent is instructed not to edit, but the tool layer still has edit tools available. |
| Approved results are local only | Medium | Approved task reports are printed locally, but not automatically posted back to the hub. |
| Keyword intent detection | Medium | Keyword rules can misclassify mixed or unusual messages. |
| Broad mention matching | Low-Medium | Matching the agent name inside content may produce false positives. |
| Simple group state | Low | `active_group_task` is a boolean and does not track task identity or lifecycle. |
| In-memory queue | Low | Pending approvals are lost on restart. |
| No automated tests | Medium | Intent detection, response guard, queue behavior, and tool safety rely on manual checks. |
| Import/style inconsistencies | Low | Some modules have duplicate imports or formatting that may distract in a demo. |
| Mode complexity | Low-Medium | The combination of execution mode, runner mode, and tool mode can be confusing unless clearly explained. |

## Small Actionable Improvements

### Must Fix Before Demo

- Clean duplicate imports and formatting in hub modules.
- Clearly explain the mode matrix in `README.md` and during the demo.
- Make sure docs list all current hub helper files and the `create_file` tool.

### Nice To Have

- Add unit tests for:
  - `detect_hub_intent()`
  - `choose_collaboration_role()`
  - `sanitize_hub_response()`
  - `HubTaskQueue`
  - `create_file`
- Add `/task TASK_ID` to inspect a single pending task before approving.
- Add `/reject-all` or `/clear-tasks` for demo recovery.
- Optionally post safe approved-task reports back to the hub.

### Future Improvement

- Enforce `read_only` mode at the tool layer.
- Track active group task state more explicitly.
- Add a lightweight team-state summary for claimed, completed, and pending work.
- Replace pure keyword intent detection with a small structured classifier while keeping safe defaults.
- Persist non-secret approval/rejection logs.
- Unify Part 2 imports to remove the execution bridge `sys.path` workaround.

## Bottom Line

The project is well aligned with the Assignment 2 Part 3 safety model. Hub collaboration is text-first, locally gated, and designed to avoid duplicate work. The strongest aspects are the trust boundary, manual approval queue, conservative tool safety, and collaboration-first behavior.

The main gaps are enforcing `read_only` at the tool layer, closing the result-reporting loop back to the hub, and adding focused tests around intent detection, response guarding, approval queue behavior, and tool safety.
