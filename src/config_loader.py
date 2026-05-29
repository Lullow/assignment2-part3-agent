from pathlib import Path


# Finds the project root from src/config_loader.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "config" / "system_prompt.md"



def load_system_prompt() -> str:
  """
  Load the system prompt from the config directory.

  The system prompt is kept outside the Python code so it can be edited
  without changing the agent implementation.
  """

  if not SYSTEM_PROMPT_PATH.exists():
    raise FileNotFoundError(f"System prompt file was not found: {SYSTEM_PROMPT_PATH}")

  prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf8").strip()

  if not prompt:
    raise ValueError("System prompt file is empty.")

  return prompt