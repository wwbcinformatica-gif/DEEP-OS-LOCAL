import asyncio
import json
from datetime import datetime

from core.config import MEMORY_DIR

REFLECTIONS_FILE = MEMORY_DIR / "reflections" / "_reflections_log.json"


def ensure_file():
    if not REFLECTIONS_FILE.exists():
        REFLECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        REFLECTIONS_FILE.write_text("[]", encoding="utf-8")


async def save_reflection(category: str, content: str, metadata: dict = None):
    ensure_file()

    def _sync_save():
        with open(REFLECTIONS_FILE, encoding="utf-8") as f:
            reflections = json.load(f)
        entry = {
            "category": category,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        reflections.append(entry)
        with open(REFLECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(reflections[-100:], f, ensure_ascii=False, indent=2)

    await asyncio.to_thread(_sync_save)


async def get_reflections(category: str = None, limit: int = 20):
    ensure_file()

    def _sync_read():
        with open(REFLECTIONS_FILE, encoding="utf-8") as f:
            reflections = json.load(f)
        if category:
            reflections = [r for r in reflections if r.get("category") == category]
        return reflections[-limit:]

    try:
        return await asyncio.to_thread(_sync_read)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[REFLECTION] Erro ao ler reflexões: {e}")
        return []


async def save_llm_reflection(question: str, answer: str, llm_output: str = ""):
    await save_reflection(
        category="interaction",
        content=f"Pergunta: {question[:200]}\nResposta: {answer[:200]}",
        metadata={"question_len": len(question), "answer_len": len(answer)}
    )
