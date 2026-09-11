"""
Tool Search — busca ferramentas disponíveis (ToolSearchTool do OpenClaude).
Gera índice automaticamente a partir do function_defs.py.
"""
from tools.function_defs import build_tool_index

_SEARCH_INDEX_CACHE: dict[str, str] | None = None

def _get_index() -> dict[str, str]:
    global _SEARCH_INDEX_CACHE
    if _SEARCH_INDEX_CACHE is None:
        _SEARCH_INDEX_CACHE = build_tool_index()
    return _SEARCH_INDEX_CACHE

def _invalidate_index():
    global _SEARCH_INDEX_CACHE
    _SEARCH_INDEX_CACHE = None

async def tool_tool_search(query: str) -> dict:
    q = query.lower()
    index = _get_index()
    results = []
    for name, desc in index.items():
        if q in name.lower() or q in desc.lower():
            results.append({"name": name, "description": desc})
    return {"query": query, "results": results, "total": len(results)}
