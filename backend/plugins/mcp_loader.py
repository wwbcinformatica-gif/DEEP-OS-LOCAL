import json
from pathlib import Path

OPENCLAUDE_DIR = Path(__file__).resolve().parent.parent.parent / "openclaude"
PLUGINS_DIR = OPENCLAUDE_DIR / "plugins" / "marketplaces" / "claude-plugins-official"
KNOWN_MARKETPLACES_FILE = OPENCLAUDE_DIR / "plugins" / "known_marketplaces.json"

MCP_CACHE: dict[str, dict] = {}
PLUGIN_REGISTRY: dict[str, dict] = {}

def scan_mcp_plugins() -> dict[str, dict]:
    plugins = {}
    if not PLUGINS_DIR.exists():
        return plugins

    external_plugins_dir = PLUGINS_DIR / "external_plugins"
    if external_plugins_dir.exists():
        for plugin_dir in external_plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            mcp_file = plugin_dir / ".mcp.json"
            plugin_json_file = plugin_dir / ".claude-plugin" / "plugin.json"
            if mcp_file.exists():
                try:
                    config = json.loads(mcp_file.read_text("utf-8"))
                    name = plugin_dir.name
                    meta = {}
                    if plugin_json_file.exists():
                        meta = json.loads(plugin_json_file.read_text("utf-8"))
                    plugins[name] = {
                        "name": name,
                        "path": str(plugin_dir),
                        "mcp_servers": config.get("mcpServers", config),
                        "description": meta.get("description", ""),
                        "author": meta.get("author", {}).get("name", ""),
                        "type": "external",
                    }
                except (json.JSONDecodeError, OSError):
                    pass

    builtin_plugins_dir = PLUGINS_DIR / "plugins"
    if builtin_plugins_dir.exists():
        for plugin_dir in builtin_plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            mcp_file = plugin_dir / ".mcp.json"
            if mcp_file.exists():
                try:
                    config = json.loads(mcp_file.read_text("utf-8"))
                    name = plugin_dir.name
                    plugins[name] = {
                        "name": name,
                        "path": str(plugin_dir),
                        "mcp_servers": config.get("mcpServers", config),
                        "description": "",
                        "author": "",
                        "type": "builtin",
                    }
                except (json.JSONDecodeError, OSError):
                    pass

    PLUGIN_REGISTRY.clear()
    PLUGIN_REGISTRY.update(plugins)
    return plugins

def get_plugin_info(plugin_name: str) -> dict | None:
    if not PLUGIN_REGISTRY:
        scan_mcp_plugins()
    return PLUGIN_REGISTRY.get(plugin_name)

def get_mcp_server_config(plugin_name: str, server_name: str = "") -> dict | None:
    plugin = get_plugin_info(plugin_name)
    if not plugin:
        return None
    servers = plugin["mcp_servers"]
    if not server_name:
        all_names = list(servers.keys())
        if not all_names:
            return None
        server_name = all_names[0]
    return servers.get(server_name)

def resolve_path_var(value: str, plugin_root: str) -> str:
    return value.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)
