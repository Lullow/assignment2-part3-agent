# Assignment 2 Part 2 Agent

This project implements a Python-based software engineering agent for Assignment 2 Part 2.

The goal of this project is to build a stronger version of the Part 1 ReAct agent using structured output, while still keeping full control over the agent loop, context handling, tool routing, safety checks, and tool execution in custom Python code.


## What This Agent Can Do

The agent can:

- Receive a software engineering task from the user
- Ask a local or OpenAI-compatible model for a structured decision
- Choose between calling a tool or yielding a final answer
- Run multiple tool-calling rounds before answering
- Read files in the project
- Edit specific sections of files
- Run safe bash commands
- Send tool results back to the model as observations
- Stop safely after a maximum number of steps
- Write logs for each agent run

## Main Difference From Part 1

In Part 1, the agent used raw text output from the model and custom string parsing.

In Part 2, the agent uses structured output with Pydantic schemas. The model returns an `AgentDecision`, but the Python code still controls:

- The agent loop
- Session history
- Tool routing
- Safety checks
- Tool execution
- Output limiting
- Logging

This makes the agent more robust and closer to how real agent systems are built.

## Project Structure

```text
assignment2-part2-agent/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   └── system_prompt.md
├── logs/
└── src/
    ├── main.py
    ├── agent_loop.py
    ├── llm_client.py
    ├── schemas.py
    ├── tool_registry.py
    ├── safety.py
    ├── session.py
    ├── output_limiter.py
    ├── path_safety.py
    ├── logger.py
    ├── config_loader.py
    └── tools/
        ├── bash_tool.py
        ├── file_reader.py
        └── file_editor.py
```

## Tools

The agent currently supports these tools:

| Tool | Purpose |
| --- | --- |
| `bash` | Runs safe bash commands inside the project root |
| `read_file` | Reads a file from the project |
| `edit_file_section` | Replaces one exact section of a file |

The model does not execute tools directly. It only requests a tool call. The Python program validates and executes the tool through `tool_registry.py`.

## Structured Output

The model must return an `AgentDecision`.

There are two possible decisions:

- `tool_call`
- `yield_to_user`

Example tool call:

```json
{
  "decision": "tool_call",
  "reason": "I need to inspect the README file first.",
  "tool_call": {
    "tool_name": "read_file",
    "path": "README.md"
  },
  "yield_to_user": null
}
```

Example final answer:

```json
{
  "decision": "yield_to_user",
  "reason": "The task is complete.",
  "tool_call": null,
  "yield_to_user": {
    "final_answer": "README.md has been updated and verified."
  }
}
```

## Agent Loop

The agent loop works like this:

```text
User task
↓
LLM returns structured AgentDecision
↓
If decision is tool_call:
    run tool through tool_registry
    save tool result as OBSERVATION
    send observation back to model
↓
If decision is yield_to_user:
    return final answer
↓
Stop if MAX_STEPS is reached
```

The maximum number of steps is controlled by:

```python
MAX_STEPS = 7
```

This prevents infinite loops and unnecessary API/model usage.


## Security Note

This project uses guardrails such as command blocking, path validation, output limiting, and safe subprocess execution. However, it is not a full sandbox.

The file tools also block sensitive or ignored project paths such as `.env`, `.git`, `.venv`, `logs`, and `__pycache__`.

For stronger isolation, the agent should be run inside a container or another restricted environment.


## Safety

The bash tool has a safety layer that blocks dangerous commands and shell operators.

Examples of blocked commands:

- `rm`
- `sudo`
- `shutdown`
- `reboot`
- `mkfs`
- `dd`
- `chmod`
- `chown`
- `curl`
- `wget`
- `ssh`
- `scp`
- `mv`
- `cp`
- `find`
- `python`
- `python3`
- `pip`
- `git`


Examples of blocked shell operators:

- `|`
- `&&`
- `;`
- `>`
- `<`
- `$()`
- Backticks

The bash tool also uses:

- `subprocess.run`
- `shell=False`
- `shlex.split`
- Timeout
- Project-root working directory

## File Editing Safety

The `edit_file_section` tool only edits a file if `old_text` exists exactly once.

This avoids ambiguous edits.

The tool refuses to edit if:

- The file does not exist
- The path is outside the project root
- `old_text` is missing
- `old_text` appears more than once

For indentation-sensitive files such as Python code, the agent is instructed to match complete lines or complete code blocks including leading whitespace. This reduces the risk of moving statements into the wrong scope during partial edits.

After code edits, the agent should verify the change with a syntax check, test command, or by reading the edited file again.

## Output Limiting

Tool outputs are limited to avoid sending too much data back to the model.

If output is too long, it is truncated and marked with:

```text
[OUTPUT TRUNCATED]
```

Only the first 4000 characters are shown.

## Logging

Each agent run creates a timestamped log file in `logs/`.

The logs include:

- User task
- Each step
- Model decisions
- Tool executions
- Tool results
- Final answer
- Stop reason if `MAX_STEPS` is reached

The `logs/` directory is ignored by git.

## System Prompt

The system prompt is stored in:

```text
config/system_prompt.md
```

It tells the agent to:

- Only work with software engineering tasks
- Avoid unsafe commands
- Avoid leaking sensitive information
- Use tools carefully
- Read files before editing them
- Verify edits after making them
- Yield to the user when the task is complete

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env`:

```bash
cp .env.example .env
```

Example `.env` for LM Studio:

```env
OPENAI_API_KEY=lm-studio
OPENAI_BASE_URL=http://YOUR_LM_STUDIO_ADDRESS:1234/v1
MODEL_NAME=qwen3-32b
```

## Run

```bash
python src/main.py
```

Example task:

```text
List the files in this project and summarize what you see.
```

Another example:

```text
Read README.md, improve the introduction slightly, then verify the change.
```

## Requirement Checklist

| Requirement | Status | Where |
| --- | --- | --- |
| Bash calls with safety checks | Done | `bash_tool.py`, `safety.py` |
| Edit specific file sections | Done | `file_editor.py` |
| Multiple tool-calling rounds before yield | Done | `agent_loop.py`, `session.py` |
| Model decides tool-call or yield | Done | `schemas.py`, `llm_client.py` |
| Session history during runtime | Done | `session.py` |
| System prompt from config file | Done | `config/system_prompt.md`, `config_loader.py` |
| SWE-only behavior | Done | `config/system_prompt.md` |
| Tool output limits | Done | `output_limiter.py` |
| Agent knows tool output may be truncated | Done | `config/system_prompt.md` |
| Logging for debugging | Done | `logger.py`, `agent_loop.py` |

## Known Limitations

- The agent is conservative and may block commands that could be safe in some contexts.
- Local models may sometimes fill unused structured output fields.
- The project currently stores session history only during one program run.
- The agent does not yet support multi-session memory.
- The agent should still be run in a controlled environment when testing tool execution.

