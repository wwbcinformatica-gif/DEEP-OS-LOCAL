from fastapi import APIRouter, HTTPException

from core.models import MemoryPayload
from memory.engine import memory_delete, memory_list, memory_read, memory_write
from memory.reflection import get_reflections
from memory.vector_memory import (
    list_vector_namespaces,
    vector_memory_add,
    vector_memory_search,
)
from memory.elastic_memory import (
    index_task_memory,
    recall_relevant_memories,
    get_memory_stats,
    clear_long_term_memory,
)

router = APIRouter()

@router.post("/memory")
async def api_memory_write(payload: MemoryPayload):
    result = await memory_write(payload.namespace, payload.key, payload.content)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/memory")
async def api_memory_read(namespace: str = "conversations", key: str = ""):
    if key:
        result = await memory_read(namespace, key)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    return await memory_list(namespace)

@router.delete("/memory")
async def api_memory_delete(namespace: str = "conversations", key: str = ""):
    return await memory_delete(namespace, key)

@router.post("/memory/vector")
async def api_vector_add(namespace: str, text: str):
    await vector_memory_add(namespace, text)
    return {"status": "ok"}

@router.get("/memory/vector/search")
async def api_vector_search(namespace: str = "default", query: str = "", k: int = 5):
    results = await vector_memory_search(namespace, query, k)
    return {"results": results}

@router.get("/memory/vector/namespaces")
async def api_vector_namespaces():
    return {"namespaces": list_vector_namespaces()}

@router.get("/memory/reflections")
async def api_reflections(category: str = "", limit: int = 20):
    cat = category if category else None
    reflections = await get_reflections(cat, limit)
    return {"reflections": reflections}

# ── Elastic Memory (Long-Term RAG) ──

@router.get("/memory/elastic/stats")
async def api_elastic_stats():
    return await get_memory_stats()

@router.get("/memory/elastic/recall")
async def api_elastic_recall(query: str, top_k: int = 5):
    results = await recall_relevant_memories(query, top_k)
    return {"memories": results, "count": len(results)}

@router.post("/memory/elastic/index")
async def api_elastic_index(
    task: str,
    solution_summary: str,
    tools_used: str = "",
    lessons_learned: str = "",
):
    tools = [t.strip() for t in tools_used.split(",") if t.strip()] if tools_used else []
    result = await index_task_memory(task, solution_summary, tools, lessons_learned)
    return result

@router.delete("/memory/elastic")
async def api_elastic_clear():
    return await clear_long_term_memory()
