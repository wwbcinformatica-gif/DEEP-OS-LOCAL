import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.config import DATA_DIR
from memory.engine import memory_write
from memory.vector_memory import vector_memory_add

OPENCLAUDE_DIR = Path(__file__).resolve().parent.parent.parent / "openclaude"
HISTORY_FILE = OPENCLAUDE_DIR / "history.jsonl"
PROJECTS_DIR = OPENCLAUDE_DIR / "projects"

async def import_openclaude_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"status": "error", "message": "OpenClaude history.jsonl not found"}

    imported = 0
    sessions_found = set()
    db_path = DATA_DIR / "interactions.db"

    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                display_text = entry.get("display", "")
                session_id = entry.get("sessionId", "")
                timestamp = entry.get("timestamp", 0)
                if display_text and session_id:
                    sessions_found.add(session_id)
                    conn = sqlite3.connect(str(db_path))
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO history (question, answer, created_at) VALUES (?, ?, ?)",
                        (display_text, "(importado do OpenClaude)", datetime.fromtimestamp(timestamp / 1000).isoformat()),
                    )
                    conn.commit()
                    conn.close()
                    imported += 1
            except (json.JSONDecodeError, Exception):
                pass

    return {
        "status": "ok",
        "imported": imported,
        "sessions_found": len(sessions_found),
    }

async def import_openclaude_sessions() -> dict:
    if not PROJECTS_DIR.exists():
        return {"status": "error", "message": "OpenClaude projects dir not found"}

    total_imported = 0
    total_sessions = 0

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for session_file in project_dir.glob("*.jsonl"):
            total_sessions += 1
            session_id = session_file.stem
            conversation = []
            with open(session_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        msg_type = entry.get("type", "")
                        msg_data = entry.get("message", {})

                        if msg_type == "user":
                            content = msg_data.get("content", "")
                            if content and not content.startswith("<"):
                                conversation.append({"role": "user", "content": content})
                        elif msg_type == "assistant":
                            content_list = msg_data.get("content", [])
                            text = ""
                            if isinstance(content_list, list):
                                for c in content_list:
                                    if c.get("type") == "text":
                                        text = c.get("text", "")
                            elif isinstance(content_list, str):
                                text = content_list

                            if text and "error" not in text.lower():
                                conversation.append({"role": "assistant", "content": text})
                    except (json.JSONDecodeError, Exception):
                        pass

            if len(conversation) >= 2:
                combined = "\n".join(
                    f"{m['role']}: {m['content']}" for m in conversation
                )
                await memory_write(
                    "conversations", f"openclaude_{session_id}", combined
                )
                await vector_memory_add(
                    "openclaude",
                    combined[:1000],
                    {"source": "openclaude", "session_id": session_id}
                )
                total_imported += 1

    return {
        "status": "ok",
        "sessions_processed": total_sessions,
        "conversations_imported": total_imported,
    }

async def export_to_openclaude_memory(conversation_text: str, session_id: str = "") -> dict:
    openclaude_memory_dir = OPENCLAUDE_DIR / "projects"
    if not openclaude_memory_dir.exists():
        return {"status": "error", "message": "OpenClaude projects dir not found"}

    project_dirs = list(openclaude_memory_dir.iterdir())
    if not project_dirs:
        return {"status": "error", "message": "No OpenClaude projects found"}

    target_dir = project_dirs[0] / "memory" / "conversations"
    target_dir.mkdir(parents=True, exist_ok=True)

    if not session_id:
        session_id = f"wbc_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    filepath = target_dir / f"{session_id}.json"
    entry = {
        "session_id": session_id,
        "source": "wbc_zero_g",
        "content": conversation_text[:5000],
        "timestamp": datetime.now().isoformat(),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "path": str(filepath), "session_id": session_id}
