from typing import Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
  """
  Represents a tool call requested by the model.

  The model does not execute tools directly.
  It only returns a structured request, and our Python agent loop decides
  weather the tool is valid and safe to run.
  """

  tool_name: Literal[
    "bash",
    "read_file",
    "edit_file_section",
    "create_file",
  ] = Field(
    description="The name of the tool the model wants to call"
  )


  # Used when tool_name = "bash"
  command: str | None = Field(
    default=None,
    description="Bash command to run when using the bash tool"
  )

  # Used when tool_name == "read_file", "edit_file_section", or "create_file"
  path: str | None = Field(
    default=None,
    description="Path to the file that should be read, edited, or created."
  )

  # Used when tool_name == "edit_file_section"
  old_text: str | None = Field(
    default=None,
    description="Exact text section that should be replaced."
  )

  # Used when tool_name == "edit_file_section" or "create_file"
  new_text: str | None = Field(
    default=None,
    description="New text that should replace old_text or become the new file content."
  )


class YieldToUser(BaseModel):
  """
  Represents a final response to the user.

  This is used when the agent is done with its work and should stop
  the tool-calling loop.
  """

  final_answer: str = Field(
    description="The final answer that should be shown to the user."
  )



class AgentDecision(BaseModel):
  """
  Struvtured decision returned by the model.

  Instead of parsing raw text like in Part 1, Part 2 uses a structured schema.

  The model must either:

  1. request a tool call:
    The agent wants to use a tool, such as "bash" or "read_file"

  2. yield a final answer to the user:
    The agent is finished and wants to respond to the user.

  Our own Python code still controls the agent loop, validation,
  safety checks, and actual tool execution
  """

  decision: Literal["tool_call", "yield_to_user"] = Field(
    description="Whether the model wants to call a tool or respond to the user."
  )

  # A short explanation is usefor for logging and debugging.
  # It lets us understand why the model made the decision.
  reason: str = Field(
    descritption="Brief explanation of why this decision was made."
  )

  # This should only be provided when decision == "tool_call"
  tool_call: ToolCall | None = Field(
    default=None,
    description="Tool call details. Required when decision is tool_call."
  )

  # This shuld only be provided when decision == "yield_to_user"
  yield_to_user: YieldToUser | None = Field(
    default=None,
    description="Final response detals. Required when decision is yield_to_user"
  )



class ToolResult(BaseModel):
  """
  Standard result returned by all tools.

  This makes it easier for the agent loop to handle tool outputs
  in one consistent format, no matter which tool was used.
  """

  success: bool = Field(
    description="Weather the tool call succeeded."
  )

  tool_name: str = Field(
    description="Name of the tool that was executed."
  )

  output: str = Field(
    description="Tool output that can be sent back to the model."
  )

  error: str | None = Field(
    default=None,
    description="Error message if the tool failed."
  )


def normalize_agent_decision(decision: AgentDecision) -> AgentDecision:
  """
  Clean up extra fields from the model response.

  Some models may fill both tool_call and yield_to_user even though only one
  should be used. We trust the decision field and remove the irrelevant part
  before validation.
  """

  # If the model chose a tool call, remove any final-answer data.
  # The agent should execute the tool first and continue after the observation.
  if decision.decision == "tool_call":
    return decision.model_copy(update={"yield_to_user": None})

  # If the model chose to yield to the user, remove any tool-call data.
  # This makes the final answer the only active action.
  if decision.decision == "yield_to_user":
    return decision.model_copy(update={"tool_call": None})

  # Return unchanged if the decision type is unknown.
  # The validator can handle invalid decision values later.
  return decision


def validate_agent_decision(decision: AgentDecision) -> None:
  """
  Validate that the structured decision is internally consistent.

  Pydantic validates the general shape of the object, but this function
  checks the relationship between fields and tool-specific requirements.
  """

  if decision.decision == "tool_call":
    if decision.tool_call is None:
      raise ValueError("Decision is 'tool_call', but tool_call is missing.")

    if decision.yield_to_user is not None:
        raise ValueError("Decision is 'tool_call', but yield_to_user was also provided.")

    tool_call = decision.tool_call

    if tool_call.tool_name == "bash":
      if not tool_call.command:
        raise ValueError("bash tool requires command.")
      return

    if tool_call.tool_name == "read_file":
      if not tool_call.path:
        raise ValueError("read_file tool requires path.")
      return

    if tool_call.tool_name == "edit_file_section":
      if not tool_call.path:
        raise ValueError("edit_file_section tool requires path.")
      if not tool_call.old_text:
        raise ValueError("edit_file_section tool requires old_text.")
      if tool_call.new_text is None:
        raise ValueError("edit_file_section tool requires new_text.")
      return

    if tool_call.tool_name == "create_file":
      if not tool_call.path:
        raise ValueError("create_file tool requires path.")
      if tool_call.new_text is None:
        raise ValueError("create_file tool requires new_text.")
      return

    raise ValueError(f"Unknown tool name: {tool_call.tool_name}")

  if decision.decision == "yield_to_user":
    if decision.yield_to_user is None:
      raise ValueError("Decision is 'yield_to_user', but yield_to_user is missing.")

    if decision.tool_call is not None:
      raise ValueError("Decision is 'yield_to_user', but tool_call was also provided.")

    return

  raise ValueError(f"Unknown decision type: {decision.decision}")
