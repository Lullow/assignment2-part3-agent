from agent_loop import run_agent
from config_loader import load_system_prompt


def main() -> None:
  # Load the system prompt that defines the agent's rules and behavior.
  system_prompt = load_system_prompt()

  print("Assignment 2 Part 2 Agent")
  print("Type a software engineering task for the agent.")
  print()

  # Read the user's task from the terminal.
  # strip() removes extra whitespace before and after the input.
  user_task = input("Task: ").strip()

  # Stop early if the user did not enter anything.
  if not user_task:
    print("No task provided.")
    return

  # Start the agent loop with the user's task and the loaded system prompt.
  final_answer = run_agent(
    user_task=user_task,
    system_prompt=system_prompt,
  )

  print()
  print("--------- FINAL ANSWER ---------")
  print(final_answer)


if __name__ == "__main__":
    main()
