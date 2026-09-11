"""
Logs Viewer — leitura e analise estruturada dos logs do backend.
"""
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

_log = logging.getLogger("wbc.logs")

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "wbc-backend.log"

# Padroes de parsing de log
LOG_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},?\d{0,3})\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<logger>[\w.]+)\s*[-:]\s*"
    r"(?P<message>.+)"
)

LEVEL_MAP = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}


def _parse_log_line(line: str) -> dict | None:
    """Parseia uma linha de log em dict estruturado."""
    m = LOG_PATTERN.match(line.strip())
    if not m:
        return None
    return {
        "timestamp": m.group("timestamp"),
        "level": m.group("level"),
        "logger": m.group("logger"),
        "message": m.group("message"),
        "raw": line.strip(),
    }


async def logs_read(
    lines: int = 100,
    level: str | None = None,
    search: str | None = None,
    since: str | None = None,
    logger_filter: str | None = None,
) -> dict:
    """Le e filtra logs do arquivo."""
    if not LOG_FILE.exists():
        return {"logs": [], "count": 0, "total_lines": 0, "file": str(LOG_FILE)}

    # Le ultimas N linhas
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return {"logs": [], "count": 0, "error": str(e)}

    total = len(all_lines)
    recent = all_lines[-min(lines * 3, len(all_lines)):]  # Le mais para compensar filtros

    parsed = []
    for line in recent:
        entry = _parse_log_line(line)
        if not entry:
            continue

        # Filtro por nivel
        if level:
            req_level = LEVEL_MAP.get(level.upper(), 0)
            entry_level = LEVEL_MAP.get(entry["level"], 0)
            if entry_level < req_level:
                continue

        # Filtro por texto
        if search and search.lower() not in entry["message"].lower():
            continue

        # Filtro por logger
        if logger_filter and logger_filter not in entry["logger"]:
            continue

        # Filtro por data
        if since:
            try:
                since_dt = datetime.strptime(since, "%Y-%m-%d %H:%M")
                entry_dt = datetime.strptime(entry["timestamp"].replace(",", "."), "%Y-%m-%d %H:%M:%S.%f")
                if entry_dt < since_dt:
                    continue
            except ValueError:
                pass

        parsed.append(entry)

    # Retorna as ultimas N depois do filtro
    result = parsed[-lines:]

    return {
        "logs": result,
        "count": len(result),
        "total_lines": total,
        "file": str(LOG_FILE),
        "filters": {"level": level, "search": search, "since": since, "logger": logger_filter},
    }


async def logs_stats() -> dict:
    """Retorna estatisticas dos logs."""
    if not LOG_FILE.exists():
        return {"total": 0, "by_level": {}, "file_size": 0}

    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return {"total": 0, "by_level": {}, "file_size": 0}

    by_level = {}
    by_logger = {}
    errors = []

    for line in lines:
        entry = _parse_log_line(line)
        if not entry:
            continue

        level = entry["level"]
        by_level[level] = by_level.get(level, 0) + 1

        logger = entry["logger"]
        by_logger[logger] = by_logger.get(logger, 0) + 1

        if level in ("ERROR", "CRITICAL") and len(errors) < 10:
            errors.append({
                "timestamp": entry["timestamp"],
                "logger": logger,
                "message": entry["message"][:200],
            })

    return {
        "total": len(lines),
        "by_level": by_level,
        "by_logger": by_logger,
        "recent_errors": errors,
        "file_size": LOG_FILE.stat().st_size,
        "file": str(LOG_FILE),
    }


async def logs_clear() -> dict:
    """Limpa o arquivo de log."""
    if LOG_FILE.exists():
        LOG_FILE.write_text("", encoding="utf-8")
        _log.info("Logs limpos")
        return {"cleared": True, "file": str(LOG_FILE)}
    return {"cleared": False, "file": str(LOG_FILE)}
