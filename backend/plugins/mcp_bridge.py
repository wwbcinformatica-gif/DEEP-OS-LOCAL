import asyncio
import json
import subprocess
import uuid

import httpx

from plugins.mcp_loader import get_mcp_server_config, get_plugin_info, resolve_path_var

MCP_SERVER_PROCESSES: dict[str, subprocess.Popen] = {}
MCP_TOOL_REGISTRY: dict[str, dict] = {}
MCP_PLUGIN_TO_SERVERS: dict[str, list[str]] = {}

async def _call_http_server(url: str, method: str, params: dict = None, headers: dict = None) -> dict:
    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

async def _call_stdio_server(process: subprocess.Popen, method: str, params: dict = None) -> dict:
    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    request_str = json.dumps(payload) + "\n"
    process.stdin.write(request_str)
    process.stdin.flush()

    try:
        response_line = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, process.stdout.readline),
            timeout=20.0,
        )
        if not response_line:
            return {"error": {"message": "MCP server returned no response"}}
        return json.loads(response_line)
    except asyncio.TimeoutError:
        return {"error": {"message": "Timeout waiting for MCP server response"}}

def _start_stdio_server(command: str, args: list, cwd: str) -> subprocess.Popen | None:
    try:
        cmd_line = " ".join([command] + args)
        process = subprocess.Popen(
            cmd_line,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return process
    except FileNotFoundError:
        return None

async def initialize_mcp_server(plugin_name: str, server_name: str = "") -> str | None:
    config = get_mcp_server_config(plugin_name, server_name)
    if not config:
        return None

    plugin_info = get_plugin_info(plugin_name)
    if not plugin_info:
        return None

    server_key = f"{plugin_name}:{server_name or list(get_plugin_info(plugin_name)['mcp_servers'].keys())[0]}"
    if plugin_name not in MCP_PLUGIN_TO_SERVERS:
        MCP_PLUGIN_TO_SERVERS[plugin_name] = []
    MCP_PLUGIN_TO_SERVERS[plugin_name].append(server_key)

    server_type = config.get("type", "stdio")

    if server_type == "http":
        MCP_SERVER_PROCESSES[server_key] = None
        MCP_TOOL_REGISTRY[server_key] = {"type": "http", "config": config}
        await refresh_tools_list(server_key)
        return server_key

    command = config.get("command", "")
    args = config.get("args", [])
    plugin_root = plugin_info["path"]

    resolved_args = [resolve_path_var(a, plugin_root) for a in args]

    process = _start_stdio_server(command, resolved_args, plugin_root)
    if not process:
        return None

    MCP_SERVER_PROCESSES[server_key] = process
    MCP_TOOL_REGISTRY[server_key] = {"type": "stdio", "config": config, "process": process}

    try:
        init_result = await _call_stdio_server(process, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "wbc-agent", "version": "2.0"},
        })
        if "error" in init_result:
            return None
        await _call_stdio_server(process, "notifications/initialized")
        await refresh_tools_list(server_key)
        return server_key
    except Exception:
        return None

async def refresh_tools_list(server_key: str) -> list[dict]:
    entry = MCP_TOOL_REGISTRY.get(server_key)
    if not entry:
        return []

    try:
        if entry["type"] == "http":
            url = entry["config"].get("url", "")
            headers = entry["config"].get("headers", {})
            result = await _call_http_server(url, "tools/list", headers=headers)
        else:
            process = entry.get("process")
            if not process:
                return []
            result = await _call_stdio_server(process, "tools/list")

        tools = result.get("result", {}).get("tools", [])
        entry["tools"] = tools
        return tools
    except Exception:
        entry["tools"] = []
        return []

async def call_mcp_tool(server_key: str, tool_name: str, arguments: dict = None) -> dict:
    entry = MCP_TOOL_REGISTRY.get(server_key)
    if not entry:
        return {"error": f"MCP server '{server_key}' not initialized"}

    try:
        if entry["type"] == "http":
            url = entry["config"].get("url", "")
            headers = entry["config"].get("headers", {})
            result = await _call_http_server(url, "tools/call", {
                "name": tool_name,
                "arguments": arguments or {},
            }, headers)
        else:
            process = entry.get("process")
            if not process:
                return {"error": "MCP server process not running"}
            result = await _call_stdio_server(process, "tools/call", {
                "name": tool_name,
                "arguments": arguments or {},
            })

        if "error" in result:
            return {"error": result["error"].get("message", str(result["error"]))}
        tool_result = result.get("result", {})
        content = tool_result.get("content", [])
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "resource":
                text_parts.append(str(item.get("resource", {})))
        return {
            "status": "ok",
            "content": "\n".join(text_parts),
            "isError": tool_result.get("isError", False),
        }
    except Exception as e:
        return {"error": str(e)}

def get_all_mcp_servers() -> dict[str, list[dict]]:
    result = {}
    for server_key, entry in MCP_TOOL_REGISTRY.items():
        tools = entry.get("tools", [])
        result[server_key] = tools
    return result

def shutdown_mcp_servers():
    for plugin_name in list(MCP_PLUGIN_TO_SERVERS.keys()):
        try:
            from tools.executor import unregister_mcp_tools
            unregister_mcp_tools(plugin_name)
        except Exception:
            pass
    for server_key, process in MCP_SERVER_PROCESSES.items():
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                pass
    MCP_SERVER_PROCESSES.clear()
    MCP_TOOL_REGISTRY.clear()
    MCP_PLUGIN_TO_SERVERS.clear()
