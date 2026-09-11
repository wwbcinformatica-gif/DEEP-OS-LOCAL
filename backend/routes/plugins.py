from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from plugins.mcp_bridge import (
    MCP_TOOL_REGISTRY,
    call_mcp_tool,
    get_all_mcp_servers,
    initialize_mcp_server,
    shutdown_mcp_servers,
)
from plugins.mcp_loader import get_plugin_info, scan_mcp_plugins

router = APIRouter()

class McpToolCallPayload(BaseModel):
    server_key: str
    tool_name: str
    arguments: dict = {}

@router.get("/plugins")
async def list_plugins():
    plugins = scan_mcp_plugins()
    result = []
    for name, info in plugins.items():
        result.append({
            "name": name,
            "description": info["description"],
            "author": info["author"],
            "type": info["type"],
            "servers": list(info["mcp_servers"].keys()),
        })
    return {"plugins": result}

@router.post("/plugins/{plugin_name}/init")
async def init_plugin(plugin_name: str):
    info = get_plugin_info(plugin_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")

    from tools.executor import register_mcp_tool, unregister_mcp_tools
    unregister_mcp_tools(plugin_name)

    server_keys = []
    total_tools = 0
    for server_name in info["mcp_servers"]:
        key = await initialize_mcp_server(plugin_name, server_name)
        if key:
            server_keys.append(key)
            entry = MCP_TOOL_REGISTRY.get(key, {})
            tools = entry.get("tools", [])
            for tool_def in tools:
                register_mcp_tool(plugin_name, key, tool_def)
                total_tools += 1

    if not server_keys:
        raise HTTPException(status_code=500, detail=f"Failed to initialize any MCP server for '{plugin_name}'")

    from tools.executor import TOOL_REGISTRY
    registered = [k for k in TOOL_REGISTRY if k.startswith(f"{plugin_name}__")]
    return {
        "status": "ok",
        "plugin": plugin_name,
        "servers": server_keys,
        "tools_registered": total_tools,
        "available_tools": registered,
    }

@router.get("/plugins/servers")
async def list_mcp_servers():
    servers = get_all_mcp_servers()
    return {"servers": servers}

@router.get("/plugins/servers/{server_key}/tools")
async def list_mcp_tools(server_key: str):
    entry = MCP_TOOL_REGISTRY.get(server_key)
    if not entry:
        raise HTTPException(status_code=404, detail="MCP server not initialized")
    from plugins.mcp_bridge import refresh_tools_list
    tools = await refresh_tools_list(server_key)
    return {"server_key": server_key, "tools": tools}

@router.post("/plugins/call")
async def call_tool(payload: McpToolCallPayload):
    result = await call_mcp_tool(payload.server_key, payload.tool_name, payload.arguments)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/plugins/shutdown")
async def shutdown():
    shutdown_mcp_servers()
    return {"status": "ok", "message": "All MCP servers shut down"}
