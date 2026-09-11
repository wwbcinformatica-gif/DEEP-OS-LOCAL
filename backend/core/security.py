import re
from pathlib import Path

PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[\\/]")
MAX_MESSAGE_LENGTH = 50000


def sanitize_path(user_path: str, root: str) -> str | None:
    resolved = Path(root).resolve() / user_path
    resolved = resolved.resolve()

    root_resolved = Path(root).resolve()
    if not str(resolved).startswith(str(root_resolved)):
        return None
    return str(resolved)


def prevent_path_traversal(path: str) -> bool:
    if PATH_TRAVERSAL_PATTERN.search(path):
        return False
    return True


def validate_message_length(message: str) -> bool:
    return len(message) <= MAX_MESSAGE_LENGTH


def sanitize_shell_command(cmd: str) -> str:
    dangerous = ["rm -rf", "format", "del /f /s", "rd /s /q", "shutdown"]
    for d in dangerous:
        if d.lower() in cmd.lower():
            return cmd.replace(d, f"echo 'blocked: {d}'")
    return cmd
