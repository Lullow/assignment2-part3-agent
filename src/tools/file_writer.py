from pathlib import Path

from output_limiter import limit_output
from path_safety import is_inside_project, is_sensitive_path
from schemas import ToolResult

# Resolve the project root so file creation can be restricted to this project.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def create_file(path: str, content: str) -> ToolResult:
  """
  Create a new text file inside the current project.

  The path must stay inside the project root, must not point to sensitive
  files or directories, and must not already exist.
  """

  try:
    # Convert the user-provided path into an absolute resolved path.
    # This handles things like "../" before safety checks are applied.
    requested_path = (PROJECT_ROOT / path).resolve()

    # Block attempts to create files outside the project directory.
    if not is_inside_project(requested_path, PROJECT_ROOT):
      return ToolResult(
        success=False,
        tool_name="create_file",
        output="",
        error="Access denied: path is outside the project root.",
      )

    # Block sensitive files and folders such as .env, .git, .venv, and logs.
    if is_sensitive_path(requested_path, PROJECT_ROOT):
      return ToolResult(
        success=False,
        tool_name="create_file",
        output="",
        error="Access denied: path points to a sensitive or ignored project file.",
      )

    # This tool only creates new files. Existing files must be edited explicitly.
    if requested_path.exists():
      return ToolResult(
        success=False,
        tool_name="create_file",
        output="",
        error=f"File already exists, refusing to overwrite: {path}",
      )

    # Do not allow creating directories through the file creation tool.
    if path.endswith("/") or requested_path.name == "":
      return ToolResult(
        success=False,
        tool_name="create_file",
        output="",
        error=f"Path does not point to a file: {path}",
      )

    # Create parent directories if needed, after the target path has passed safety checks.
    requested_path.parent.mkdir(parents=True, exist_ok=True)

    # Write text content using UTF-8.
    requested_path.write_text(content, encoding="utf-8")

    output = (
      f"Successfully created file: {path}\n\n"
      f"Content:\n{content}"
    )

    return ToolResult(
      success=True,
      tool_name="create_file",
      output=limit_output(output),
      error=None,
    )

  except Exception as exc:
    # Return errors as ToolResult instead of crashing the agent loop.
    return ToolResult(
      success=False,
      tool_name="create_file",
      output="",
      error=str(exc),
    )
