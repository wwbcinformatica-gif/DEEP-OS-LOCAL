import io
import re
import subprocess
import sys
import textwrap
from pathlib import Path

from core.config import get_base_dir

ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[?\??[0-9;]*[a-zA-Z]')

def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub('', text)


async def tool_read(path: str, root: str = "", offset: int = 0, limit: int = 0) -> dict:
    from tools.explorer import resolve_path
    target = resolve_path(path, root)
    if not target.exists():
        return {"error": "Arquivo/diretorio nao encontrado"}
    if target.is_dir():
        items = [
            {"name": c.name, "type": "directory" if c.is_dir() else "file"}
            for c in sorted(target.iterdir()) if not c.name.startswith(".")
        ]
        return {"type": "directory", "items": items}

    # Arquivos binarios que nao podem ser lidos como texto
    ext = target.suffix.lower()
    binary_exts = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
                   '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
                   '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.webp', '.svg',
                   '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.flac', '.ogg',
                   '.zip', '.rar', '.7z', '.tar', '.gz',
                   '.db', '.sqlite', '.sqlite3'}

    if ext in binary_exts:
        # Tenta extrair texto de PDFs
        if ext == '.pdf':
            try:
                import subprocess
                result = subprocess.run(
                    ['python', '-c', f'''
import fitz
doc = fitz.open(r"{target}")
text = ""
for page in doc:
    text += page.get_text()
print(text)
'''],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    full_text = result.stdout
                    total = len(full_text)
                    if limit > 0:
                        start = offset * limit
                        chunk = full_text[start:start + limit]
                        return {"type": "file", "content": chunk, "total_chars": total, "offset": start, "has_more": start + limit < total, "note": "Texto extraido do PDF"}
                    return {"type": "file", "content": full_text, "total_chars": total, "note": "Texto extraido do PDF (completo)"}
            except Exception:
                pass

        return {
            "type": "binary",
            "error": f"Arquivo {ext} e binario e nao pode ser lido como texto.",
            "suggestion": f"Para visualizar este arquivo, use bash('start {target.name}') para abrir no programa padrao.",
            "file": target.name,
            "size": target.stat().st_size,
        }

    content = target.read_text("utf-8", errors="replace")
    total = len(content)
    total_lines = content.count('\n') + 1

    # Se limit > 0, retorna apenas o trecho solicitado (paginação)
    if limit > 0:
        start = offset * limit
        chunk = content[start:start + limit]
        return {
            "type": "file",
            "content": chunk,
            "total_chars": total,
            "total_lines": total_lines,
            "offset_chars": start,
            "has_more": start + limit < total,
        }

    # Retorna o conteudo completo
    return {"type": "file", "content": content, "total_chars": total, "total_lines": total_lines}

async def tool_write(path: str, content: str, root: str = "") -> dict:
    from tools.explorer import resolve_path
    target = resolve_path(path, root)
    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)
    return {"status": "ok", "path": str(target), "action": "overwritten" if existed else "created"}

async def tool_bash(command: str, workdir: str = "") -> dict:
    """Executa qualquer comando — com verificação de Modo Restrito."""
    if not command.strip():
        return {"error": "Comando vazio"}
    # ── Verifica Modo Restrito (Sandbox) ──────────────────────────────
    # Sandbox desativado — acesso total ao sistema
    # ───────────────────────────────────────────────────────────────────
    try:
        wd = workdir or str(get_base_dir())
        # Garantir que o workdir existe
        from pathlib import Path as _P
        if not _P(wd).exists():
            wd = str(get_base_dir())
        # No Windows, usar cmd /c para melhor compatibilidade com comandos multi-linha
        r = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=120, cwd=wd,
            encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
        )
        stdout = strip_ansi(r.stdout[-5000:])
        stderr = strip_ansi(r.stderr[-2000:])
        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Timeout 60s"}
    except Exception as e:
        return {"error": str(e)}

async def tool_search(pattern: str, path: str = "", include: str = "") -> dict:
    try:
        _base = get_base_dir()
        if path:
            # Se o path é absoluto (C:/, D:/, etc), usa direto
            if len(path) >= 2 and path[1] == ':':
                search_root = Path(path).resolve()
            else:
                search_root = Path(_base / path).resolve()
        else:
            search_root = _base
        # Garante que o path existe
        if not search_root.exists():
            return {"error": f"Caminho nao encontrado: {search_root}"}
        import subprocess
        cmd = ["rg", "-n", pattern, str(search_root)]
        if include:
            cmd.extend(["-g", include])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        lines = [l for l in r.stdout.split("\n") if l.strip()][:50]
        return {"matches": len(lines), "results": lines[:30]}
    except FileNotFoundError:
        # fallback to pure python search
        matches = []
        for f in sorted(search_root.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                try:
                    content = f.read_text("utf-8", errors="replace")
                    for i, line in enumerate(content.split("\n"), 1):
                        if pattern in line:
                            rel = f.relative_to(get_base_dir())
                            matches.append(f"{rel}:{i}: {line.strip()[:120]}")
                            if len(matches) >= 30:
                                break
                except Exception:
                    pass
            if len(matches) >= 30:
                break
        return {"matches": len(matches), "results": matches[:30]}
    except Exception as e:
        return {"error": str(e)}

async def tool_grep(pattern: str, path: str = "", include: str = "") -> dict:
    return await tool_search(pattern, path, include)

async def tool_execute_python(code: str) -> dict:
    try:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        clean_code = textwrap.dedent(code)
        exec_globals = {"__builtins__": __builtins__}
        exec(clean_code, exec_globals)
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        return {"stdout": output[-3000:], "status": "ok"}
    except Exception as e:
        sys.stdout = old_stdout
        return {"error": str(e), "status": "error"}

async def tool_create_directory(path: str, root: str = "") -> dict:
    from tools.explorer import resolve_path
    try:
        target = resolve_path(path, root)
        target.mkdir(parents=True, exist_ok=True)
        return {"status": "ok", "path": str(target), "created": target.exists()}
    except Exception as e:
        return {"error": str(e)}

async def tool_delete(path: str, root: str = "") -> dict:
    from tools.explorer import resolve_path
    try:
        target = resolve_path(path, root)
        if not target.exists():
            return {"error": "Caminho não encontrado"}
        if target.is_dir():
            import shutil
            shutil.rmtree(target)
            return {"status": "ok", "action": "deleted_dir", "path": str(target)}
        else:
            target.unlink()
            return {"status": "ok", "action": "deleted_file", "path": str(target)}
    except Exception as e:
        return {"error": str(e)}

async def tool_rename(old_path: str, new_path: str, root: str = "") -> dict:
    from tools.explorer import resolve_path
    try:
        old_target = resolve_path(old_path, root)
        new_target = resolve_path(new_path, root)
        if not old_target.exists():
            return {"error": "Caminho original não encontrado"}
        old_target.rename(new_target)
        return {"status": "ok", "from": str(old_target), "to": str(new_target)}
    except Exception as e:
        return {"error": str(e)}

async def tool_install_package(package: str) -> dict:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True, timeout=120
        )
        return {
            "stdout": r.stdout[-2000:],
            "stderr": r.stderr[-1000:],
            "returncode": r.returncode,
        }
    except Exception as e:
        return {"error": str(e)}


async def tool_open_app(app_name: str, path: str = "", args: str = "") -> dict:
    """Abre um programa/executável no sistema.

    Procura em:
      1. Caminho fornecido (se path for informado)
      2. PATH do sistema (where/which)
      3. C:\\Program Files\\*, C:\\Program Files (x86)\\*
      4. %LOCALAPPDATA%\\Programs\\*
      5. Start Menu (atalhos .lnk)
      6. Apps do Windows (calc, notepad, explorer, etc.)
    """
    import os
    import shutil

    app = app_name.strip()
    if not app:
        return {"error": "Nome do app não fornecido"}

    # Se path fornecido, tenta abrir direto
    if path:
        try:
            full = path.strip('"')
            if args:
                subprocess.Popen([full, args], shell=False)
            else:
                subprocess.Popen(full, shell=True)
            return {"status": "ok", "app": app, "path": full}
        except Exception as e:
            return {"error": f"Não foi possível abrir {path}: {e}"}

    # 1. Procura no PATH do sistema
    found = shutil.which(app)
    if found:
        try:
            if args:
                subprocess.Popen([found, args])
            else:
                subprocess.Popen(found)
            return {"status": "ok", "app": app, "path": found}
        except Exception as e:
            return {"error": f"Encontrei {found} mas não consegui abrir: {e}"}

    # 2. Procura com where no Windows
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                f"where {app}", shell=True, capture_output=True,
                text=True, timeout=5, encoding="utf-8", errors="replace",
            )
            if r.returncode == 0 and r.stdout.strip():
                found_path = r.stdout.strip().split("\n")[0].strip()
                if args:
                    subprocess.Popen([found_path, args])
                else:
                    subprocess.Popen(found_path, shell=True)
                return {"status": "ok", "app": app, "path": found_path}
        except Exception:
            pass

    # 3. Procura em Program Files
    search_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
    ]

    # Variações de extensão
    exts = [".exe", ".lnk", ".bat", ".cmd", ""] if sys.platform == "win32" else [""]

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        try:
            for root, dirs, files in os.walk(search_dir, topdown=True):
                # Limita profundidade
                depth = root[len(search_dir):].count(os.sep)
                if depth > 2:
                    dirs.clear()
                    continue
                for f in files:
                    fname_lower = f.lower()
                    app_lower = app.lower()
                    # Match por nome (com ou sem extensão)
                    for ext in exts:
                        if fname_lower == app_lower + ext.lower():
                            full_path = os.path.join(root, f)
                            try:
                                if args:
                                    subprocess.Popen([full_path, args])
                                else:
                                    subprocess.Popen(full_path, shell=True)
                                return {"status": "ok", "app": app, "path": full_path}
                            except Exception as e:
                                return {"error": f"Encontrei {full_path} mas não consegui abrir: {e}"}
                    # Match parcial (nome contém o app)
                    if app_lower in fname_lower and any(fname_lower.endswith(e) for e in [".exe", ".lnk"]):
                        full_path = os.path.join(root, f)
                        try:
                            if args:
                                subprocess.Popen([full_path, args])
                            else:
                                subprocess.Popen(full_path, shell=True)
                            return {"status": "ok", "app": app, "path": full_path}
                        except Exception:
                            pass
        except (PermissionError, OSError):
            continue

    # 4. Apps nativos do Windows
    win_apps = {
        "calc": "calc",
        "calculadora": "calc",
        "notepad": "notepad",
        "bloco de notas": "notepad",
        "explorer": "explorer",
        "gerenciador de arquivos": "explorer",
        "taskmgr": "taskmgr",
        "gerenciador de tarefas": "taskmgr",
        "cmd": "cmd",
        "prompt de comando": "cmd",
        "powershell": "powershell",
        "paint": "mspaint",
        "snipping": "snippingtool",
        "config": "ms-settings:",
        "configurações": "ms-settings:",
        "control": "control",
        "painel de controle": "control",
        "magnifier": "magnify",
        "lupa": "magnify",
        "narrator": "narrator",
        "wordpad": "write",
    }
    cmd = win_apps.get(app.lower())
    if cmd:
        try:
            subprocess.Popen(cmd, shell=True)
            return {"status": "ok", "app": app, "path": cmd}
        except Exception as e:
            return {"error": f"Não consegui abrir {cmd}: {e}"}

    return {"error": f"Não encontrei '{app}' no sistema. Tente informar o caminho completo com o parâmetro path."}
