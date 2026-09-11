"""
File Tools — glob + grep aprimorados (GlobTool do OpenClaude).
"""
import fnmatch
import os
import re


def _extract_path_from_pattern(pattern: str) -> str:
    """Extrai o caminho base de um pattern como 'C:/**/*.mp3' → 'C:\\'."""
    # Match drive letter no início: C:, D:, etc.
    m = re.match(r'^([a-zA-Z]:[\\/]?)(.*)', pattern)
    if m:
        drive = m.group(1)
        rest = m.group(2)
        # Se tem subpastas antes do wildcard, usa como base
        if '*' not in rest and '?' not in rest:
            return os.path.join(drive, rest)
        # Pega a parte antes do primeiro wildcard
        parts = rest.split('/')
        base_parts = []
        for p in parts:
            if '*' in p or '?' in p:
                break
            base_parts.append(p)
        if base_parts:
            return os.path.join(drive, *base_parts)
        return drive
    return ""


async def tool_glob(pattern: str, path: str = "") -> dict:
    # Limpa barras duplas (Gemini envia C:\\ em vez de C:\)
    if path:
        path = path.replace("\\\\", "\\").replace("//", "/")
    if pattern:
        pattern = pattern.replace("\\\\", "\\").replace("//", "/")

    # Se o pattern tem um caminho absoluto (ex: C:/**/*.mp3), extrai o base
    if not path and re.match(r'^[a-zA-Z]:', pattern):
        path = _extract_path_from_pattern(pattern)
        if path:
            rel_pattern = pattern[len(path):].lstrip('\\/').lstrip('/')
            if rel_pattern:
                pattern = rel_pattern

    base = path or os.getcwd()
    if not os.path.isdir(base):
        drive = base[:3] if len(base) >= 3 else base
        if os.path.isdir(drive):
            base = drive
        else:
            return {"pattern": pattern, "path": base, "files": [], "total": 0, "error": "Caminho nao encontrado"}

    matched = []
    try:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ('node_modules', '__pycache__', '.git', '$Recycle.Bin', 'System Volume Information')]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), base)
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(f, pattern):
                    matched.append(os.path.join(root, f))
    except (PermissionError, OSError):
        pass

    matched.sort()
    # Limita resultados para não sobrecarregar
    total = len(matched)
    if total > 200:
        matched = matched[:200]
    return {"pattern": pattern, "path": base, "files": matched, "total": total}