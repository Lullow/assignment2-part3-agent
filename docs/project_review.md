# Project Review

This review summarizes the current Assignment 2 Part 3 multi-agent hub/SWE-agent project.

## 1. Project Overview

The project has two main layers:

- The local Part 2 SWE-agent can use controlled tools for software engineering tasks.
- The Part 3 hub-agent communicates with a shared HTTP/RunPod hub and treats hub messages as untrusted input.

The important safety boundary is that hub messages do not directly execute local tools. A hub task must first become a proposal, then optionally enter the local approval queue, and only then can it be approved from the local console.

### Local SWE-Agent Layer

- `src/main.py` starts the local agent.
- `src/agent_loop.py` runs the structured tool-calling loop.
- `src/schemas.py` defines `AgentDecision`, `ToolCall`, and `ToolResult`.
- `src/tool_registry.py` routes validated tool calls.
- `config/system_prompt.md` describes the local agent rules.

The local agent can request one of these tools:

| Tool | Purpose |
| --- | --- |
| `bash` | Runs conservative commands inside the project root |
| `read_file` | Reads safe project files |
| `edit_file_section` | Replaces one exact section in an existing safe file |
| `create_file` | Creates a new safe project file and refuses overwrites |

### Hub-Agent Layer

- `src/hub/hub_loop.py` polls the hub, filters messages, detects intents, and posts or dry-runs responses.
- `src/hub/hub_client.py` wraps hub API calls.
- `src/hub/hub_config.py` loads and validates hub settings.
- `src/hub/hub_intent.py` classifies collaboration intent.
- `src/hub/hub_response_guard.py` sanitizes responses before printing or posting.

### Approval Queue And Runtime Controls

- `src/hub/hub_task_queue.py` stores pending hub tasks in memory.
- `src/hub/hub_runtime_controls.py` supports local commands such as `/tasks`, `/approve TASK_ID`, and `/reject TASK_ID`.
- `src/hub/hub_execution_bridge.py` decides what happens after local approval.

The approval flow is:

```text
Hub message
-> detect intent
-> create task proposal
-> optionally queue task for local approval
-> user reviews with /tasks
-> user approves with /approve TASK_ID
-> approved task goes through configured runner
-> result is printed locally
```

### Collaboration Behavior

The hub layer supports:

- task proposals,
- delegation proposals,
- group coordination responses,
- temporary collaboration roles,
- task claim suggestions,
- bounded coordination follow-ups,
- result report formatting.

The agent is designed to be useful in a team without taking over leadership or duplicating work.

## 2. Strong Points

- The project has a clear trust boundary between hub messages and local tool execution.
- Manual approval protects local execution through `/approve TASK_ID`.
- Safe defaults are used: dry-run mode, review-only mode, placeholder runner, read-only approved task mode, and group mentions disabled by default.
- Local tools are centralized through `src/tool_registry.py`.
- File tools use project-root and sensitive-path checks.
- `create_file` refuses overwrites and creates parent directories only after path safety checks.
- Bash execution is conservative and blocks destructive commands and shell operators.
- Hub responses pass through a response guard before printing or posting.
- Group collaboration is coordination-first, not implementation-first.
- Temporary roles make the agent more flexible than a fixed “coder bot”.
- Documentation and demo files explain the main operating modes.
- `python3 -m compileall src` currently passes.

## 3. Weak Points And Risks

- `src/hub/hub_loop.py` has many responsibilities: polling, filtering, group state, follow-ups, intent handling, queue setup, and posting.
- `read_only` approved task mode is mostly prompt-based. The tool registry does not enforce read-only behavior at the tool layer.
- Approved task reports are printed locally, but not automatically posted back to the hub.
- Intent detection is keyword-based and may misclassify mixed or unusual messages.
- Mention matching can be broad because it checks for the agent name inside message content.
- `active_group_task` is a simple boolean and does not track which task is active or when it ends.
- The approval queue is in-memory only, so pending tasks are lost on restart.
- There are no automated tests for intent detection, task queue behavior, response guard, or tool safety.
- Some modules have small cleanup issues, such as duplicate imports and uneven formatting.
- The mode matrix can be confusing during a demo unless explained clearly.

## 4. Improvement Areas

### Must Fix Before Demo

- Clean duplicate imports and formatting in `hub_execution_bridge.py`, `hub_task_proposal.py`, `hub_config.py`, and the role-selection block in `hub_loop.py`.
- Update documentation if new files are added, especially hub helper modules and `tools/file_writer.py`.
- Prepare a short explanation of the mode matrix:
  - `review_only`: proposals only.
  - `manual_approval + placeholder`: queue and approve, but no execution.
  - `manual_approval + part2_agent + read_only`: approved local analysis only.
  - `manual_approval + part2_agent + local_tools`: approved local tool use.

### Nice To Have

- Add unit tests for `detect_hub_intent()`, `choose_collaboration_role()`, `sanitize_hub_response()`, `HubTaskQueue`, and `create_file`.
- Add `/task TASK_ID` to inspect one queued task before approval.
- Add `/reject-all` or `/clear-tasks` for demo recovery.
- Add a per-group-task follow-up limit instead of one global coordination follow-up.
- Make approved local result reporting optionally post a safe summary back to the hub.

### Future Improvement

- Add a lightweight team-state tracker for active task, claimed work, completed work, and pending follow-ups.
- Make “what should we do next?” summarize current team state before suggesting a next action.
- Replace pure keyword intent detection with a small structured classifier while keeping safe defaults.
- Add persistent non-secret logs for approved and rejected hub tasks.
- Unify Part 2 imports so the bridge does not need to adjust `sys.path`.

## 5. Commenting And Docstrings

The project already has many helpful comments. The best additions would be targeted comments that help explain demo behavior:

- In `src/hub/hub_loop.py`, add a short comment explaining that `active_group_task` is simple runtime state, not full task tracking.
- In `src/hub/hub_coordination_followup.py`, explain why only result-like messages trigger follow-up.
- In `src/hub/hub_execution_bridge.py`, clarify the difference between runner mode and tool mode.
- In `src/hub/hub_task_queue.py`, update `to_execution_prompt()` to say it can feed the real Part 2 agent after approval.
- Avoid adding comments to obvious console command branches such as `/pause` or `/resume`.

## 6. Structure Cleanup

Small, low-risk structure improvements:

- Keep `hub_loop.py` focused on polling and posting over time.
- Move mention/group-message filtering into a helper module if it grows.
- Move response dispatch into a helper if direct, group, follow-up, and task responses keep expanding.
- Keep all mode documentation centralized near `hub_config.py` and the README Hub Configuration section.
- Consider renaming user-facing `placeholder` to `no_execution` or `approval_preview` later for clarity.

## Project Explanation Summary For ChatGPT

This project has two main parts.

The local Part 2 SWE-agent is the tool-using layer. It uses structured Pydantic decisions, a custom loop, session history, a tool registry, and controlled tools. The tools are `bash`, `read_file`, `edit_file_section`, and `create_file`. Bash is checked by a conservative safety layer. File tools check that paths stay inside the project root and avoid sensitive paths such as `.env`, `.git`, `.venv`, `logs`, and `__pycache__`. Tool outputs are limited before being sent back to the model.

The Part 3 hub-agent is the collaboration layer. It polls a shared HTTP/RunPod hub, ignores old messages and its own messages, detects mentions, classifies message intent, and creates safe collaboration responses. It can produce task proposals, delegation proposals, group coordination responses, task claim suggestions, and local result reports.

The full task flow is:

```text
Hub message
-> intent detection
-> task proposal
-> local approval queue
-> user approves with /approve TASK_ID
-> approved task goes through placeholder or Part 2 runner
-> Part 2 agent may use controlled tools depending on mode
-> result report is produced locally
```

The main safety decisions are:

- hub input is untrusted,
- hub messages cannot directly run tools,
- local approval is required before execution,
- safe defaults avoid execution,
- sensitive paths are blocked,
- outputs are limited,
- responses are sanitized before hub posting,
- group mentions are optional to avoid spam.

The main collaboration decisions are:

- the agent should coordinate before implementing broad group tasks,
- it should avoid duplicate work,
- it should suggest clear task ownership,
- it can switch temporary roles such as planner, coordinator, reviewer, tester, clarifier, implementer, or observer,
- it should report concise results when work is completed.

For a quiz or demo, be ready to explain the difference between `review_only`, `manual_approval`, `placeholder`, `part2_agent`, `read_only`, and `local_tools`. Also be ready to show why `/tasks` and `/approve TASK_ID` are the safety gate between hub collaboration and local execution.
