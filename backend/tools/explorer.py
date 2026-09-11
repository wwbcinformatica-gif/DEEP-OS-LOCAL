from pathlib import Path

from fastapi import HTTPException

from core.config import get_explorer_root


def resolve_path(path: str, root: str = "") -> Path:
    if root:
        base = Path(root).resolve()
    elif path and len(path) >= 2 and path[1] == ':':
        # Path absoluto (C:/, D:/, etc) — usa direto sem base
        return Path(path).resolve()
    else:
        base = get_explorer_root()
    target = (base / path).resolve()
    return target

async def explorer_list(path: str = "", root: str = ""):
    try:
        if root:
            root_path = Path(root).resolve()
            if not root_path.exists() or not root_path.is_dir():
                raise HTTPException(status_code=400, detail="Diretório raiz não encontrado")
            target = (root_path / path).resolve() if path else root_path
        elif path and len(path) >= 2 and path[1] == ':':
            # Path absoluto (C:\Users, etc) — acessa direto
            target = Path(path).resolve()
            root_path = target.parent if target.is_file() else target
        else:
            _root = get_explorer_root()
            target = (_root / path).resolve() if path else _root
            root_path = _root
        if not target.exists():
            raise HTTPException(status_code=404, detail="Caminho não encontrado")
        if target.is_file():
            rel = root_path if root else get_explorer_root()
            return {
                "type": "file",
                "name": target.name,
                "path": str(target.relative_to(rel)).replace("\\", "/"),
                "size": target.stat().st_size,
            }
        items = []
        rel_base = root_path if root else (target if (path and len(path) >= 2 and path[1] == ':') else get_explorer_root())
        for child in sorted(target.iterdir()):
            try:
                rel = str(child.relative_to(rel_base)).replace("\\", "/")
            except ValueError:
                rel = str(child).replace("\\", "/")
            items.append({
                "name": child.name,
                "path": rel,
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else 0,
            })
        return {"type": "directory", "name": target.name, "path": path, "items": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def explorer_read(path: str, root: str = ""):
    try:
        if root:
            root_path = Path(root).resolve()
            target = (root_path / path).resolve()
        elif path and len(path) >= 2 and path[1] == ':':
            # Path absoluto — acessa direto
            target = Path(path).resolve()
        else:
            _root = get_explorer_root()
            target = (_root / path).resolve()
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        ext = target.suffix.lower()
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            return {"type": "text", "content": content, "language": ext.lstrip(".")}
        except Exception:
            return {"type": "binary", "content": None, "language": ext.lstrip(".")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
