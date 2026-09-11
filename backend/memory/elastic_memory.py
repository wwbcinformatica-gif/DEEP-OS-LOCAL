"""
DEEP-OS â€” Memória Humana Elástica
==========================================
Sistema de memória curto/longo prazo com busca semÃ¢ntica zero-dependência.

- Memória de Trabalho (Curto Prazo): gerenciada pelo lifecycle (janela de contexto)
- Memória de Longo Prazo: embeddings locais + JSON persistido + cosine similarity

No estado FINAL: indexa resumo estruturado (Problema, Solução, Ferramentas, Lições).
No estado START: busca semÃ¢ntica para injetar insights passados no prompt inicial.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import MEMORY_DIR

_log = logging.getLogger("wbc.elastic_memory")

LONG_TERM_DIR = MEMORY_DIR / "long_term"
LONG_TERM_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = LONG_TERM_DIR / "index.json"
_MAX_LONG_TERM_ENTRIES = 500
SIMILARITY_THRESHOLD = 0.15
TOP_K_RECALL = 5

# Async lock para serializar escritas concorrentes no index.json
_write_lock = asyncio.Lock()

# â”€â”€â”€ Tokenizer simplificado (zero dependência) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_STOPWORDS = frozenset({
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com",
    "sem", "sob", "entre", "que", "se", "ao", "aos", "as", "os",
    "isso", "este", "esta", "esses", "essas", "aquele", "aquela",
    "eu", "tu", "ele", "ela", "nos", "vos", "eles", "elas", "meu",
    "teu", "seu", "minha", "tua", "sua", "meus", "teus", "seus",
    "minhas", "tuas", "suas", "foi", "ser", "estar", "ter", "fazer",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some", "such",
    "than", "too", "very", "just", "about", "also", "it", "its", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "they", "them", "their", "what",
    "which", "who", "whom", "when", "where", "why", "how", "if", "then",
    "else", "because", "while", "although", "though", "since", "until",
    "unless", "except", "instead", "rather", "however", "therefore",
    "furthermore", "moreover", "nevertheless", "meanwhile", "otherwise",
    "func", "def", "class", "import", "from", "return", "if", "else",
    "elif", "for", "while", "try", "except", "finally", "with", "as",
    "lambda", "yield", "async", "await", "self", "cls", "true", "false",
    "null", "none", "undefined", "var", "let", "const", "function",
    "const", "let", "var", "new", "delete", "typeof", "instanceof",
    "print", "log", "error", "warn", "info", "debug", "none", "type",
})


def _tokenize(text: str) -> list[str]:
    """Tokeniza texto em minúsculas, remove stopwords, retorna tokens únicos."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _term_frequency(tokens: list[str]) -> dict[str, float]:
    """Calcula TF normalizado para uma lista de tokens."""
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    max_count = max(counts.values())
    return {t: c / max_count for t, c in counts.items()}


def _cosine_similarity(tf1: dict[str, float], tf2: dict[str, float]) -> float:
    """Calcula similaridade coseno entre dois vetores TF esparsos."""
    if not tf1 or not tf2:
        return 0.0
    keys = set(tf1.keys()) & set(tf2.keys())
    if not keys:
        return 0.0
    dot = sum(tf1[k] * tf2[k] for k in keys)
    mag1 = math.sqrt(sum(v * v for v in tf1.values()))
    mag2 = math.sqrt(sum(v * v for v in tf2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# â”€â”€â”€ Ãndice persistido em JSON (com atomic write) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    try:
        with open(INDEX_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def _save_index(entries: list[dict]):
    """Escrita atÃ´mica: grava em tmp e renomeia para evitar corrupção."""
    entries = entries[-_MAX_LONG_TERM_ENTRIES:]
    dir_path = INDEX_FILE.parent
    # Cria arquivo temporário no mesmo diretório (rename é atÃ´mico no mesmo FS)
    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=str(dir_path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        # Rename atÃ´mico â€” no Windows pode falhar se o destino existe
        try:
            os.replace(tmp_path, str(INDEX_FILE))
        except OSError:
            # Windows fallback: remove destino, depois renomeia
            if INDEX_FILE.exists():
                INDEX_FILE.unlink()
            os.rename(tmp_path, str(INDEX_FILE))
    except Exception:
        # Limpa temp em caso de falha
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _compute_entry_hash(task: str, solution_summary: str) -> str:
    """Gera hash único para evitar duplicatas exatas."""
    raw = f"{task.strip().lower()}|{solution_summary.strip().lower()[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# â”€â”€â”€ API pública â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def index_task_memory(
    task: str,
    solution_summary: str,
    tools_used: list[str],
    lessons_learned: str,
    provider: str = "",
    model: str = "",
) -> dict:
    """
    Armazena uma experiência de tarefa na memória de longo prazo.
    Chamado quando o estado FINAL é atingido com sucesso.
    Usa asyncio.Lock para serializar escritas concorrentes.
    """
    entry_hash = _compute_entry_hash(task, solution_summary)

    async with _write_lock:
        # Verifica duplicata
        entries = _load_index()
        for e in entries:
            if e.get("hash") == entry_hash:
                _log.info("[ELASTIC-MEMORY] Entrada duplicada ignorada: %s", entry_hash)
                return {"status": "duplicate", "hash": entry_hash}

        entry = {
            "hash": entry_hash,
            "task": task[:500],
            "solution_summary": solution_summary[:1000],
            "tools_used": tools_used[:20],
            "lessons_learned": lessons_learned[:500],
            "timestamp": datetime.now().isoformat(),
            "tokens": _tokenize(f"{task} {solution_summary} {lessons_learned}"),
        }
        entries.append(entry)
        _save_index(entries)

    _log.info(
        "[ELASTIC-MEMORY] ðŸ§  Indexada experiência: %s (total: %d)",
        task[:60], len(entries),
    )
    return {"status": "indexed", "hash": entry_hash, "total": len(entries)}


async def recall_relevant_memories(query: str, top_k: int = TOP_K_RECALL) -> list[dict]:
    """
    Busca semÃ¢ntica (TF-cosine) na memória de longo prazo.
    Chamado no START de qualquer nova tarefa para injetar insights passados.
    """
    entries = _load_index()
    if not entries:
        _log.info("[ELASTIC-MEMORY] Memória de longo prazo vazia.")
        return []

    query_tokens = _tokenize(query)
    query_tf = _term_frequency(query_tokens)

    scored: list[tuple[float, dict]] = []
    for entry in entries:
        entry_tf = _term_frequency(entry.get("tokens", []))
        sim = _cosine_similarity(query_tf, entry_tf)
        if sim >= SIMILARITY_THRESHOLD:
            scored.append((sim, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for sim, entry in scored[:top_k]:
        results.append({
            "relevance": round(sim, 3),
            "task": entry["task"],
            "solution_summary": entry["solution_summary"],
            "tools_used": entry.get("tools_used", []),
            "lessons_learned": entry.get("lessons_learned", ""),
            "timestamp": entry.get("timestamp", ""),
        })

    if results:
        _log.info(
            "[ELASTIC-MEMORY] ðŸ” Recuperadas %d memórias relevantes de %d (query: %s...)",
            len(results), len(entries), query[:40],
        )
    else:
        _log.info("[ELASTIC-MEMORY] ðŸ” Nenhuma memória relevante encontrada para: %s...", query[:40])

    return results


def format_memories_for_prompt(memories: list[dict]) -> str:
    """Formata memórias recuperadas para injeção no system prompt.
    Trata memórias de falha (FAILURE_LESSON) com formato de aviso."""
    if not memories:
        return ""

    success_mems = [m for m in memories if not m.get("is_failure")]
    failure_mems = [m for m in memories if m.get("is_failure")]

    lines = []

    # Avisos de falha (Anti-Padrao) â€” SEMPRE primeiro para impacto maximo
    if failure_mems:
        lines.append("\n\n## âš ï¸ ANTI-PADROES DETECTADOS (NAO REPITA ESTES ERROS)\n")
        for i, mem in enumerate(failure_mems, 1):
            lines.append(f"### Anti-Padrao {i} (relevancia: {mem['relevance']})")
            lines.append(f"- **Tarefa que FALHOU:** {mem['task'][:200]}")
            lines.append(f"- **Motivo da falha:** {mem['solution_summary'][:200]}")
            if mem.get("tools_used"):
                lines.append(f"- **Ferramentas que causaram impasse:** {', '.join(mem['tools_used'][:5])}")
            if mem.get("lessons_learned"):
                lines.append(f"- **Licao:** {mem['lessons_learned'][:200]}")
            lines.append("")
        lines.append("IMPORTANTE: NAO repita as estrategias acima. Tente uma abordagem completamente diferente.\n")

    # Memorias de sucesso
    if success_mems:
        lines.append("\n## MEMÃ“RIAS PASSADAS RELEVANTES (RAG)\n")
        for i, mem in enumerate(success_mems, 1):
            lines.append(f"### Experiência {i} (relevÃ¢ncia: {mem['relevance']})")
            lines.append(f"- **Problema:** {mem['task'][:200]}")
            lines.append(f"- **Solução:** {mem['solution_summary'][:200]}")
            if mem.get("tools_used"):
                lines.append(f"- **Ferramentas:** {', '.join(mem['tools_used'][:5])}")
            if mem.get("lessons_learned"):
                lines.append(f"- **Lição:** {mem['lessons_learned'][:200]}")
            lines.append("")

    if success_mems:
        lines.append("Use essas experiências como referência, mas adapte Ã  nova tarefa.")
    return "\n".join(lines)


# â”€â”€â”€ Anti-Padrão SemÃ¢ntico (Failure Lessons) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

FAILURE_LESSON_PREFIX = "[FAILURE_LESSON]"

async def index_failure_lesson(
    task: str,
    failure_reason: str,
    tools_attempted: list[str],
    error_summary: str,
) -> dict:
    """
    Registra um anti-padrao semantico apos falha de circuito.
    Salva no index.json com tag [FAILURE_LESSON] para que o recall
    future injete um aviso de "nao repita esse erro".
    """
    entry_hash = _compute_entry_hash(task, failure_reason)

    async with _write_lock:
        entries = _load_index()
        for e in entries:
            if e.get("hash") == entry_hash:
                _log.info("[ELASTIC-MEMORY] Anti-padrao duplicado ignorado: %s", entry_hash)
                return {"status": "duplicate", "hash": entry_hash}

        solution_tagged = f"{FAILURE_LESSON_PREFIX} FALHOU ao tentar: {failure_reason[:500]}"
        entry = {
            "hash": entry_hash,
            "task": task[:500],
            "solution_summary": solution_tagged,
            "tools_used": tools_attempted[:20],
            "lessons_learned": f"ERRO: {error_summary[:500]}. Ferramentas que falharam: {', '.join(tools_attempted[:5])}",
            "timestamp": datetime.now().isoformat(),
            "tokens": _tokenize(f"{task} {failure_reason} {error_summary}"),
            "is_failure": True,
        }
        entries.append(entry)
        _save_index(entries)

    _log.info(
        "[ELASTIC-MEMORY] ðŸš« Anti-padrao registrado: %s (total: %d)",
        task[:60], len(entries),
    )
    return {"status": "indexed", "hash": entry_hash, "total": len(entries)}


async def get_memory_stats() -> dict:
    """Retorna estatísticas da memória de longo prazo."""
    entries = _load_index()
    return {
        "total_entries": len(entries),
        "max_capacity": _MAX_LONG_TERM_ENTRIES,
        "index_file": str(INDEX_FILE),
        "oldest": entries[0]["timestamp"] if entries else None,
        "newest": entries[-1]["timestamp"] if entries else None,
    }


async def clear_long_term_memory():
    """Limpa toda a memória de longo prazo (uso manual)."""
    async with _write_lock:
        _save_index([])
    _log.info("[ELASTIC-MEMORY] ðŸ—‘ï¸ Memória de longo prazo limpa.")
    return {"status": "cleared"}
