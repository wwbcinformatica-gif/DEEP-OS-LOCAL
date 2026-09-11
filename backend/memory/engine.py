import asyncio
import json
from datetime import datetime

from core.config import MEMORY_DIR

MEMORY_NAMESPACES = {
    "conversations": MEMORY_DIR / "conversations",
    "project_knowledge": MEMORY_DIR / "project_knowledge",
    "reflections": MEMORY_DIR / "reflections",
    "preferences": MEMORY_DIR / "preferences",
}


async def memory_write(namespace: str, key: str, content: str) -> dict:
    ns_path = MEMORY_NAMESPACES.get(namespace)
    if not ns_path:
        return {"error": f"Namespace desconhecido: {namespace}"}
    ns_path.mkdir(parents=True, exist_ok=True)
    entry = {
        "key": key,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    safe_key = key.replace("/", "_").replace("\\", "_")
    filepath = ns_path / f"{safe_key}.json"

    def _sync_write():
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

    await asyncio.to_thread(_sync_write)
    return {"status": "ok", "namespace": namespace, "key": key}


async def memory_read(namespace: str, key: str) -> dict:
    ns_path = MEMORY_NAMESPACES.get(namespace)
    if not ns_path:
        return {"error": f"Namespace desconhecido: {namespace}"}
    safe_key = key.replace("/", "_").replace("\\", "_")
    filepath = ns_path / f"{safe_key}.json"
    if not filepath.exists():
        return {"error": "Chave não encontrada na memória"}

    def _sync_read():
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)

    try:
        data = await asyncio.to_thread(_sync_read)
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Erro ao ler arquivo de memória: {e}"}
    return {"status": "ok", "data": data}


async def memory_list(namespace: str) -> dict:
    ns_path = MEMORY_NAMESPACES.get(namespace)
    if not ns_path:
        return {"error": f"Namespace desconhecido: {namespace}"}
    if not ns_path.exists():
        return {"namespace": namespace, "items": []}

    def _sync_list():
        items = []
        for f in sorted(ns_path.glob("*.json"), reverse=True):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                    items.append({"key": data.get("key"), "timestamp": data.get("timestamp")})
            except (json.JSONDecodeError, OSError):
                continue  # Pula arquivos corrompidos
        return items

    items = await asyncio.to_thread(_sync_list)
    return {"namespace": namespace, "items": items}


async def memory_delete(namespace: str, key: str) -> dict:
    ns_path = MEMORY_NAMESPACES.get(namespace)
    if not ns_path:
        return {"error": f"Namespace desconhecido: {namespace}"}
    safe_key = key.replace("/", "_").replace("\\", "_")
    filepath = ns_path / f"{safe_key}.json"
    if filepath.exists():
        filepath.unlink()
    return {"status": "deleted"}
