"""
Download Image — baixa imagem de URL e salva localmente.
"""
import os
import re
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote

import httpx


DOWNLOADS_DIR = Path("C:/DEEP-OS/docs/downloads")
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    return name[:100] or "image"


def _guess_ext(url: str, content_type: str = "") -> str:
    # Tenta pela URL
    path = urlparse(url).path
    if "." in path.split("/")[-1]:
        ext = "." + path.split("/")[-1].rsplit(".", 1)[-1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tiff"):
            return ext
    # Tenta pelo content-type
    ct_map = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "image/webp": ".webp", "image/bmp": ".bmp", "image/svg+xml": ".svg",
        "image/x-icon": ".ico", "image/tiff": ".tiff",
    }
    for ct, ext in ct_map.items():
        if ct in content_type:
            return ext
    return ".jpg"


def download_image(url: str, save_path: str = "", filename: str = "") -> str:
    """
    Baixa imagem de uma URL.
    Retorna JSON com status, caminho do arquivo, tamanho e tipo.
    """
    if not url:
        return "Erro: forneça uma URL válida."

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            return f"Erro: a URL retornou HTML, não uma imagem. Content-Type: {content_type}"

        data = resp.content
        if len(data) < 100:
            return "Erro: resposta muito pequena, provavelmente não é uma imagem válida."

        ext = _guess_ext(url, content_type)

        # Define caminho de destino
        if save_path:
            dest = Path(save_path)
            if dest.is_dir():
                if filename:
                    dest = dest / _sanitize_filename(filename) + ext
                else:
                    hash_short = hashlib.md5(data).hexdigest()[:8]
                    dest = dest / f"img_{hash_short}{ext}"
            elif not dest.suffix:
                dest = dest.with_suffix(ext)
            dest.parent.mkdir(parents=True, exist_ok=True)
        else:
            if filename:
                fname = _sanitize_filename(filename) + ext
            else:
                hash_short = hashlib.md5(data).hexdigest()[:8]
                fname = f"img_{hash_short}{ext}"
            dest = DOWNLOADS_DIR / fname

        dest.write_bytes(data)
        size_kb = len(data) / 1024

        result = (
            f"Imagem baixada com sucesso!\n"
            f"Caminho: {dest}\n"
            f"Tamanho: {size_kb:.1f} KB\n"
            f"Tipo: {content_type or ext}"
        )
        print(f"[DownloadImage] OK: {dest} ({size_kb:.1f} KB)")
        return result

    except httpx.HTTPStatusError as e:
        return f"Erro HTTP {e.response.status_code} ao baixar imagem."
    except httpx.ConnectError:
        return "Erro: não foi possível conectar ao servidor."
    except httpx.TimeoutException:
        return "Erro: timeout (30s) ao baixar imagem."
    except Exception as e:
        return f"Erro ao baixar imagem: {str(e)[:200]}"
