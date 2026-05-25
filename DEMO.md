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
/quit
```

## Expected Behavior

- The agent connects to the hub when the hub is available.
- If the hub is down, the agent logs errors and keeps running.
- The agent only responds to direct mentions.
- In dry-run mode, responses are printed locally instead of posted to the hub.
- The hub-facing agent does not expose local bash or file-editing tools.