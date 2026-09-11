"""
File Edit Tool — edição precisa via find-and-replace (FileEditTool do OpenClaude).
Usa resolve_path() para prevenir path traversal.
"""
from tools.explorer import resolve_path


async def tool_file_edit(path: str, old_string: str, new_string: str, root: str = "") -> dict:
    try:
        target = resolve_path(path, root)
    except Exception as e:
        return {"success": False, "message": f"Acesso negado: {e}"}
    if not target.exists():
        return {"success": False, "message": f"Arquivo não encontrado: {target}"}
    if not target.is_file():
        return {"success": False, "message": f"Não é arquivo: {target}"}
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"success": False, "message": f"Erro ao ler: {e}"}
    count = content.count(old_string)
    if count == 0:
        return {"success": False, "message": "String não encontrada no arquivo"}
    if count > 1:
        return {"success": False, "message": f"'{old_string[:40]}...' aparece {count}x. Forneça contexto único."}
    try:
        new_content = content.replace(old_string, new_string, 1)
        target.write_text(new_content, encoding="utf-8", newline="\r\n")
        return {"success": True, "message": f"Editado: {target.name}"}
    except Exception as e:
        return {"success": False, "message": f"Erro ao escrever: {e}"}
