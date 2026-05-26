from schemas import ToolCall, ToolResult
from tools.bash_tool import run_bash
from tools.file_editor import edit_file_section
from tools.file_reader import read_file
from tools.file_writer import create_file


def execute_tool_call(tool_call: ToolCall) -> ToolResult:
  """
  Route a structured ToolCall to the correct Python tool.

  The model only requests tool calls. This registry decides which actual
  Python function should run
  """

  # Bash requires a command before it can be executed.
  if tool_call.tool_name == "bash":
    if tool_call.command is None:
      return ToolResult(
        success=False,
        tool_name="bash",
        output="",
        error="Missing command for bash tool.",
     )

    return run_bash(tool_call.command)

  # Read_file requires a path to know which file should be read.
  if tool_call.tool_name == "read_file":
    if tool_call.path is None:
      return ToolResult(
        success=False,
        tool_name="read_file",
        output="",
        error="Missing path for read_file tool.",
    )

    return read_file(tool_call.path)

  # Edit_file_section requires all edit fields to avoid vague or partial file edits.
  if tool_call.tool_name == "edit_file_section":
    if tool_call.path is None or tool_call.old_text is None or tool_call.new_text is None:
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error="Missing path, old_text, or new_text for edit_file_section tool."
      )

    return edit_file_section(
      path=tool_call.path,
      old_text=tool_call.old_text,
      new_text=tool_call.new_text,
    )

  # Create_file requires a path and file content. It refuses to overwrite existing files.
  if tool_call.tool_name == "create_file":
    if tool_call.path is None or tool_call.new_text is None:
      return ToolResult(
        success=False,
        tool_name="create_file",
        output="",
        error="Missing path or new_text for create_file tool."
      )

    return create_file(
      path=tool_call.path,
      content=tool_call.new_text,
    )

  # Unknown tools are rejected instead of being executed or ignored silently.
  return ToolResult(
    success=False,
    tool_name=tool_call.tool_name,
    output="",
    error=f"Unknown tool: {tool_call.tool_name}"
  )


