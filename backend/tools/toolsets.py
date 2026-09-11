"""
DEEP-OS Toolset System
==========================
Adapted from Hermes Agent's toolset composition system.

Toolsets group tools into logical bundles that can be enabled/disabled
per agent profile or platform. Each toolset maps to tool names in the
TOOL_REGISTRY (executor.py) and their OpenAI function definitions
(function_defs.py).
"""


# ---------------------------------------------------------------------------
# Toolset Definitions
# ---------------------------------------------------------------------------
# Each toolset is a dict with:
#   description  â€“ human-readable label
#   tools        â€“ list of tool names (must exist in TOOL_REGISTRY)
#   includes     â€“ list of other toolsets to inherit (optional)

_TOOLSETS: dict[str, dict] = {
    # â”€â”€ Core â€” always available â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "core": {
        "description": "Core system tools",
        "tools": [
            "tool_search",
            "monitor_dashboard",
        ],
    },

    # â”€â”€ File Operations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "file": {
        "description": "File read, write, edit, and directory management",
        "tools": [
            "read",
            "write",
            "delete",
            "rename",
            "create_directory",
            "file_edit",
            "glob",
            "explorer",
            "explorer_read",
        ],
    },

    # â”€â”€ Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "search": {
        "description": "Text and file pattern search",
        "tools": [
            "search",
            "grep",
        ],
    },

    # â”€â”€ Terminal / Shell â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "terminal": {
        "description": "Shell command execution and scripting",
        "tools": [
            "bash",
            "execute_python",
            "install_package",
        ],
    },

    # â”€â”€ Web â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "web": {
        "description": "Web search and content fetching",
        "tools": [
            "web_search",
            "web_fetch",
        ],
    },

    # â”€â”€ Task Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "tasks": {
        "description": "Persistent task tracking and management",
        "tools": [
            "task_create",
            "task_get",
            "task_update",
            "task_list",
            "task_stop",
        ],
    },

    # â”€â”€ Agent Delegation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "delegation": {
        "description": "Subagent forking and team coordination",
        "tools": [
            "fork_subagent",
            "get_subagent_result",
            "team_create",
            "team_delete",
            "send_message",
        ],
    },

    # â”€â”€ Cron / Scheduling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "cron": {
        "description": "Scheduled job management",
        "tools": [
            "cron_create",
            "cron_delete",
            "cron_list",
        ],
    },

    # â”€â”€ MCP Plugins â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "mcp": {
        "description": "MCP server plugin management",
        "tools": [
            "list_mcp_servers",
            "init_mcp_plugin",
        ],
    },

    # â”€â”€ Memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    "memory": {
        "description": "Agent memory and reflection",
        "tools": [
            "memory_write",
            "memory_read",
            "memory_list",
            "memory_delete",
        ],
    },

    # â”€â”€ Composed Toolsets (include other toolsets) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    "developer": {
        "description": "Full development toolset: file ops + terminal + search + web",
        "includes": ["file", "search", "terminal", "web"],
    },

    "agent": {
        "description": "Full agent toolset: all autonomous capabilities",
        "includes": ["developer", "tasks", "delegation", "planning", "cron", "memory", "mcp"],
    },

    "readonly": {
        "description": "Read-only inspection: no mutations",
        "tools": [
            "read",
            "explorer",
            "explorer_read",
            "search",
            "grep",
            "glob",
            "tool_search",
            "web_search",
            "web_fetch",
        ],
    },
}


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def get_toolset(name: str) -> dict | None:
    """Return raw toolset definition by name, or None."""
    return _TOOLSETS.get(name)


def get_all_toolsets() -> dict[str, dict]:
    """Return all registered toolset definitions."""
    return dict(_TOOLSETS)


def get_toolset_names() -> list[str]:
    """Return list of all toolset names."""
    return list(_TOOLSETS.keys())


def resolve_toolset(name: str, _visited: set | None = None) -> list[str]:
    """Recursively resolve a toolset name to a flat list of tool names.

    Handles ``includes`` with cycle detection.
    """
    if _visited is None:
        _visited = set()

    if name in _visited:
        return []  # cycle detected

    ts = _TOOLSETS.get(name)
    if ts is None:
        return []

    _visited.add(name)
    result: list[str] = []

    # Tools defined directly on this toolset
    result.extend(ts.get("tools", []))

    # Recursively resolve included toolsets
    for included_name in ts.get("includes", []):
        result.extend(resolve_toolset(included_name, _visited))

    return result


def resolve_multiple_toolsets(names: list[str]) -> list[str]:
    """Resolve multiple toolset names into a single deduplicated tool list."""
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        for tool_name in resolve_toolset(name):
            if tool_name not in seen:
                seen.add(tool_name)
                result.append(tool_name)
    return result


# ---------------------------------------------------------------------------
# Integration helpers for function_defs.py
# ---------------------------------------------------------------------------

def filter_function_defs(function_defs: list[dict], allowed_tools: list[str]) -> list[dict]:
    """Filter a list of OpenAI function definitions to only include allowed tools.

    Args:
        function_defs: Full list from function_defs.TOOLS
        allowed_tools: List of tool names to allow (from resolve_toolset)

    Returns:
        Filtered list matching only allowed tools.
    """
    allowed_set = set(allowed_tools)
    return [
        fd for fd in function_defs
        if fd.get("function", {}).get("name") in allowed_set
    ]


def toolset_has(name: str, tool: str) -> bool:
    """Check if a toolset (resolved) contains a given tool."""
    return tool in resolve_toolset(name)
