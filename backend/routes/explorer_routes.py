from pathlib import Path
import mimetypes

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from tools.explorer import explorer_list, explorer_read

router = APIRouter()

# ── Media Streaming Endpoint ────────────────────────────────
@router.get("/api/media/stream")
async def stream_media(path: str, root: str = ""):
    """Serve local media file for browser playback."""
    try:
        import os
        target = Path(path).resolve()
        # Se o caminho absoluto existe, usa direto
        if not target.exists() and root:
            from tools.explorer import resolve_path
            target = resolve_path(path, root)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
        mime_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        return FileResponse(
            path=str(target),
            media_type=mime_type,
            filename=target.name,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class WriteRequest(BaseModel):
    path: str
    content: str
    root: str = ""

@router.get("/explorer")
async def api_explorer_list(path: str = "", root: str = ""):
    return await explorer_list(path, root)

@router.get("/explorer/read")
async def api_explorer_read(path: str, root: str = ""):
    return await explorer_read(path, root)

@router.post("/explorer/write")
async def api_explorer_write(req: WriteRequest):
    try:
        from core.config import get_explorer_root
        base = Path(req.root).resolve() if req.root else get_explorer_root()
        target = (base / req.path).resolve()
        if not str(target).startswith(str(base)):
            raise HTTPException(status_code=403, detail="Acesso negado")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(req.content)
        return {"status": "ok", "path": req.path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RenameRequest(BaseModel):
    path: str
    new_name: str
    root: str = ""

@router.post("/api/files/rename")
async def api_file_rename(req: RenameRequest):
    try:
        from tools.explorer import resolve_path
        target = resolve_path(req.path, req.root)
        if not target.exists():
            raise HTTPException(404, "Arquivo/pasta nao encontrado")
        new_path = target.parent / req.new_name
        if new_path.exists():
            raise HTTPException(409, "Ja existe um arquivo/pasta com esse nome")
        target.rename(new_path)
        return {"status": "ok", "old": req.path, "new": str(new_path.relative_to(target.parent.parent if req.root else target.parent))}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


class DeleteRequest(BaseModel):
    path: str
    root: str = ""

@router.post("/api/files/delete")
async def api_file_delete(req: DeleteRequest):
    try:
        from tools.explorer import resolve_path
        target = resolve_path(req.path, req.root)
        if not target.exists():
            raise HTTPException(404, "Arquivo/pasta nao encontrado")
        if target.is_dir():
            import shutil
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"status": "ok", "path": req.path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


class RevealRequest(BaseModel):
    path: str
    root: str = ""

@router.post("/api/files/reveal")
async def api_file_reveal(req: RevealRequest):
    try:
        from tools.explorer import resolve_path
        target = resolve_path(req.path, req.root)
        if not target.exists():
            raise HTTPException(404, "Arquivo/pasta nao encontrado")
        import subprocess
        subprocess.Popen(['explorer', '/select,', str(target)])
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


class OpenExternalRequest(BaseModel):
    path: str
    root: str = ""

@router.get("/api/explorer/open-external")
async def api_open_external(path: str, root: str = ""):
    """
    Abre o arquivo nativamente no Windows usando o programa padrao.
    Para .docx abre no Word, para .pdf no Edge/Acrobat, etc.
    """
    try:
        from tools.explorer import resolve_path
        target = resolve_path(path, root)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
        import os
        os.startfile(str(target))
        return {"status": "success", "message": "Arquivo aberto no Windows"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateRequest(BaseModel):
    path: str
    root: str = ""
    type: str = "file"

@router.post("/api/files/create")
async def api_file_create(req: CreateRequest):
    try:
        from tools.explorer import resolve_path
        target = resolve_path(req.path, req.root)
        if target.exists():
            raise HTTPException(409, "Ja existe um arquivo/pasta com esse caminho")
        if req.type == "directory":
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("")
        return {"status": "ok", "path": req.path, "type": req.type}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.get("/api/explorer/pick-folder")
async def api_pick_folder():
    """
    Abre o diálogo nativo do Windows para o usuário escolher uma pasta
    e retorna o caminho absoluto completo.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        folder_path = filedialog.askdirectory(title="Selecione a Pasta do Projeto")
        root.destroy()

        if not folder_path:
            return {"status": "cancelled", "path": ""}

        return {"status": "ok", "path": folder_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
