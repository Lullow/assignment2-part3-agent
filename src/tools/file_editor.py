from pathlib import Path

from output_limiter import limit_output
from path_safety import is_inside_project, is_sensitive_path
from schemas import ToolResult

# Resolve the project root so edits can be restricted to this project only.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def edit_file_section(path: str, old_text: str, new_text: str) -> ToolResult:
  """
  Replace one exact section of a file.

  The edit only runs if old_text exists exactly once in the target file.
  Sensitive paths such as .env, .git, .venv, logs, and __pycache__ are blocked.
  """

  try:

    # Convert the user-provided path into an absolute resolved path.
    # This handles things like "../" before safety checks are applied.
    requested_path = (PROJECT_ROOT / path).resolve()

    # Block edits outside the project directory.
    if not is_inside_project(requested_path, PROJECT_ROOT):
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error="Access denied: path is outside the project root.",
      )

    # Block sensitive files and folders such as .env, .git, .venv, and logs.
    if is_sensitive_path(requested_path, PROJECT_ROOT):
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error="Access denied: path points to a sensitive or ignored project file.",
      )

    # Make sure the target file exists before trying to edit it.
    if not requested_path.exists():
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error=f"File not found: {path}",
      )

    # Only allow editing files, not directories.
    if not requested_path.is_file():
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error=f"Path is not a file: {path}",
      )


    # For Python files, require edits to include complete lines or code blocks.
    # This helps avoid indentation bugs where a small fragment like "return result"
    # is replaced and accidentally moved into the wrong scope.
    if requested_path.suffix == ".py" and "\n" not in old_text:
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error=(
          "Python edits must replace complete lines or code blocks, "
          "including indentation."
        ),
      )


    # Read the file content before replacing text.
    content = requested_path.read_text(encoding="utf-8")

    # Count matches so the edit is safe and not ambiguous.
    occurrences = content.count(old_text)

    # Refuse the edit if the exact text does not exist.
    if occurrences == 0:
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error="old_text was not found in the file.",
      )


    # Refuse the edit if the text appears more than once.
    # This prevents accidentally editing the wrong section.
    if occurrences > 1:
      return ToolResult(
        success=False,
        tool_name="edit_file_section",
        output="",
        error="old_text appears multiple times. Refusing ambiguous edit.",
      )

    # Replace exactly one matching section.
    updated_content = content.replace(old_text, new_text, 1)

    # Write the updated content back to the file.
    requested_path.write_text(updated_content, encoding="utf-8")

    # Return a readable summary of what changed.
    output = (
      f"Successfully edited one section in {path}.\n\n"
      f"Replaced:\n{old_text}\n\n"
      f"With:\n{new_text}"
    )

    # Limit output so large edits do not flood the agent context.
    return ToolResult(
      success=True,
      tool_name="edit_file_section",
      output=limit_output(output),
      error=None,
    )

  except Exception as exc:
    # Return errors as ToolResult instead of crashing the agent loop.
    return ToolResult(
      success=False,
      tool_name="edit_file_section",
      output="",
      error=str(exc),
    )