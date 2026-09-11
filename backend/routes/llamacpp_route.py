import json
import subprocess
import os
import platform
import re
import time
from pathlib import Path
from typing import Dict

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_IS_WINDOWS = platform.system() == "Windows"

# Base dir dinamico — funciona em qualquer unidade (C:, G:, D:, etc.)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if _IS_WINDOWS:
    LLAMA_SERVER_EXE = BASE_DIR / "bin" / "vulkan" / "llama-server.exe"
    _CURL = "curl.exe"
    _KILL_CMD = ["taskkill", "/f", "/t", "/im", "llama-server.exe"]
else:
    LLAMA_SERVER_EXE = BASE_DIR / "bin" / "llama-server"
    _CURL = "curl"
    _KILL_CMD = ["pkill", "-f", "llama-server"]
LLAMA_SERVER_PORT = 8080

MODELS_DIR = BASE_DIR / "models"
CONFIG_PATH = BASE_DIR / "backend" / "config.yaml"


def _read_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def _get_gpu_config() -> dict:
    """Le configuracao GPU do config.yaml."""
    config = _read_config()
    llamacpp_cfg = config.get("llamacpp", {})
    ollama_cfg = config.get("ollama", {})
    return {
        "gpu_enabled": llamacpp_cfg.get("gpu_enabled", ollama_cfg.get("gpu_enabled", True)),
        "gpu_layers": llamacpp_cfg.get("gpu_layers", ollama_cfg.get("gpu_layers", -1)),
    }

# Context sizes padrao por "familia" do modelo (chave lowercase parcial)
_DEFAULT_CTX = {
    "bonsai": 32768,
    "ternary": 32768,
    "llama-3.2": 16384,
    "qwen": 16384,
    "nemomix": 16384,
}


def _guess_ctx(filename: str) -> int:
    """Tenta inferir context size baseado no nome do arquivo."""
    name_lower = filename.lower()
    for family, ctx in _DEFAULT_CTX.items():
        if family in name_lower:
            return ctx
    return 8192  # fallback conservador


def _make_model_id(filename: str) -> str:
    """Gera um ID amigavel a partir do nome do arquivo GGUF.
    Ex: 'Qwen2.5-7B-Instruct-Q4_K_M.gguf' -> 'qwen2.5-7b-instruct-q4_k_m'
    """
    stem = Path(filename).stem
    # Remover quantizacao do final para ID mais limpo, mas manter no ID completo
    return re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')


def _make_label(filename: str) -> str:
    """Gera um label legivel a partir do nome do arquivo.
    Ex: 'Qwen2.5-7B-Instruct-Q4_K_M.gguf' -> 'Qwen 2.5 7B Instruct Q4_K_M'
    """
    stem = Path(filename).stem
    # Separar por tokens camelCase e numeros
    label = re.sub(r'([a-z])([A-Z])', r'\1 \2', stem)
    label = re.sub(r'([A-Za-z])(\d)', r'\1 \2', label)
    label = re.sub(r'(\d)([A-Za-z])', r'\1 \2', label)
    label = label.replace("-", " ").replace("_", " ")
    # Capitalizar palavras, mas manter tokens de quantizacao em maiusculo
    parts = []
    for word in label.split():
        if re.match(r'^[QIQBF]\d', word) or word.upper() in ("Q4", "Q5", "Q6", "Q8", "Q2", "Q1", "FP16", "BF16", "F16"):
            parts.append(word.upper())
        elif word.lower() in ("k", "s", "m", "xs", "xxs"):
            parts.append(word.upper())
        else:
            parts.append(word.capitalize())
    return " ".join(parts)


def _find_mmproj(gguf_file: Path) -> str | None:
    """Busca mmproj correspondente ao modelo na mesma pasta ou pasta pai."""
    stem = gguf_file.stem  # ex: Ternary-Bonsai-27B-Q2_0
    parent = gguf_file.parent

    # Buscar mmproj na mesma pasta com nome similar
    for candidate in parent.glob("*mmproj*.gguf"):
        # Associar se o nome base do modelo esta no nome do mmproj
        base_name = stem.split("-Q")[0].split("-q")[0]  # ex: Ternary-Bonsai-27B
        if base_name.lower() in candidate.stem.lower():
            # Preferir Q8_0 sobre BF16 (melhor qualidade)
            if "q8_0" in candidate.stem.lower():
                return str(candidate)

    # Se nao encontrou Q8_0, pegar qualquer mmproj com o mesmo base
    for candidate in parent.glob("*mmproj*.gguf"):
        base_name = stem.split("-Q")[0].split("-q")[0]
        if base_name.lower() in candidate.stem.lower():
            return str(candidate)

    return None


def _scan_gguf_models() -> Dict[str, dict]:
    """Escaneia MODELS_DIR recursivamente e monta o dict de modelos GGUF automaticamente."""
    models = {}
    if not MODELS_DIR.exists():
        return models

    for gguf_file in MODELS_DIR.rglob("*.gguf"):
        # Ignorar mmproj — serao associados aos modelos principais
        if "mmproj" in gguf_file.name.lower():
            continue

        try:
            size_bytes = gguf_file.stat().st_size
            size_gb = size_bytes / (1024 ** 3)
        except OSError:
            continue

        model_id = _make_model_id(gguf_file.name)
        label = _make_label(gguf_file.name)
        ctx = _guess_ctx(gguf_file.name)

        # Buscar mmproj correspondente para visao
        mmproj_path = _find_mmproj(gguf_file)
        has_vision = mmproj_path is not None

        models[model_id] = {
            "file": str(gguf_file),
            "label": label,
            "ctx": ctx,
            "size_gb": round(size_gb, 2),
            "mmproj": mmproj_path,
            "has_vision": has_vision,
        }

    return models


GGUF_MODELS = _scan_gguf_models()


def _check_llama_server() -> dict:
    try:
        r = subprocess.run(
            [_CURL, "-s", "--max-time", "3", f"http://localhost:{LLAMA_SERVER_PORT}/health"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            return {"running": data.get("status") == "ok", "port": LLAMA_SERVER_PORT}
    except Exception:
        pass
    return {"running": False, "port": LLAMA_SERVER_PORT}


def _current_loaded_model() -> str | None:
    """Tenta descobrir qual modelo o llama-server carregou via /props."""
    try:
        r = subprocess.run(
            [_CURL, "-s", "--max-time", "3", f"http://localhost:{LLAMA_SERVER_PORT}/props"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            path = data.get("default_generation_settings", {}).get("model") or data.get("model_path", "")
            if path:
                return Path(path).name
    except Exception:
        pass
    return None


def _start_llama_server(model_id: str) -> dict:
    info = GGUF_MODELS[model_id]
    gpu = _get_gpu_config()
    template_file = str(LLAMA_SERVER_EXE.parent.parent / "models" / "chat-template.txt")
    cmd = [
        str(LLAMA_SERVER_EXE),
        "--model", info["file"],
        "--port", str(LLAMA_SERVER_PORT),
        "--ctx-size", str(info["ctx"]),
        "--host", "0.0.0.0",
    ]
    # GPU: -ngl 999 = todos os layers na GPU, 0 = CPU only
    if gpu["gpu_enabled"]:
        cmd.extend(["--n-gpu-layers", str(gpu["gpu_layers"])])
    # Adicionar mmproj para suporte a visao (imagens)
    if info.get("mmproj") and Path(info["mmproj"]).exists():
        cmd.extend(["--mmproj", info["mmproj"]])
    if Path(template_file).exists():
        cmd.extend(["--chat-template", f"file://{template_file}"])
    else:
        cmd.extend(["--chat-template", "chatml"])
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {"status": "starting", "model": model_id, "port": LLAMA_SERVER_PORT, "vision": bool(info.get("mmproj")), "gpu": gpu["gpu_enabled"]}


def ensure_llamacpp_model(model_id: str, max_wait: int = 60) -> dict:
    """Garante que o llama-server esteja rodando o modelo GGUF correto."""
    if model_id not in GGUF_MODELS:
        return {"error": f"Modelo '{model_id}' desconhecido"}

    info = GGUF_MODELS[model_id]
    if not Path(info["file"]).exists():
        return {"error": f"Arquivo GGUF nao encontrado: {info['file']}"}

    if not LLAMA_SERVER_EXE.exists():
        return {"error": f"llama-server nao encontrado: {LLAMA_SERVER_EXE}"}

    status = _check_llama_server()
    target_filename = Path(info["file"]).name

    # Se estiver rodando outro modelo, para e reinicia
    if status["running"]:
        current = _current_loaded_model()
        if current and current != target_filename:
            subprocess.run(_KILL_CMD, capture_output=True)
            time.sleep(1)

    # Se nao estiver rodando, inicia
    if not _check_llama_server()["running"]:
        _start_llama_server(model_id)
        # Aguarda subir
        for _ in range(max_wait):
            if _check_llama_server()["running"]:
                return {"ok": True, "model": model_id}
            time.sleep(1)
        return {"error": "llama-server nao respondeu a tempo"}

    return {"ok": True, "model": model_id, "already_running": True}


class StartGGUFPayload(BaseModel):
    model_id: str


@router.get("/llamacpp/status")
async def llamacpp_status():
    status = _check_llama_server()
    current = _current_loaded_model()
    return {
        "running": status["running"],
        "port": status["port"],
        "current_model": current,
        "models": list(GGUF_MODELS.keys()),
    }


@router.get("/llamacpp/models")
async def llamacpp_models():
    """Retorna todos os modelos GGUF detectados automaticamente na pasta models/."""
    global GGUF_MODELS
    GGUF_MODELS = _scan_gguf_models()  # re-escaneia sempre para pegar novos arquivos
    status = _check_llama_server()
    current = _current_loaded_model()
    result = []
    for mid, info in GGUF_MODELS.items():
        exists = Path(info["file"]).exists()
        loaded = status["running"] and current and current == Path(info["file"]).name
        result.append({
            "id": mid,
            "label": info["label"],
            "file": info["file"],
            "size_gb": info.get("size_gb", 0),
            "ctx": info["ctx"],
            "available": exists,
            "loaded": loaded,
            "has_vision": info.get("has_vision", False),
            "mmproj": info.get("mmproj"),
        })
    return {"running": status["running"], "current_model": current, "models": result}


@router.post("/llamacpp/refresh")
async def llamacpp_refresh():
    """Forca re-escaneamento da pasta de modelos."""
    global GGUF_MODELS
    GGUF_MODELS = _scan_gguf_models()
    return {"status": "ok", "count": len(GGUF_MODELS), "models": list(GGUF_MODELS.keys())}


class GpuConfigPayload(BaseModel):
    gpu_enabled: bool
    gpu_layers: int = -1


@router.get("/llamacpp/gpu")
async def llamacpp_get_gpu():
    """Retorna configuracao GPU atual."""
    return _get_gpu_config()


@router.post("/llamacpp/gpu")
async def llamacpp_set_gpu(payload: GpuConfigPayload):
    """Salva configuracao GPU no config.yaml."""
    config = _read_config()
    if "llamacpp" not in config:
        config["llamacpp"] = {}
    config["llamacpp"]["gpu_enabled"] = payload.gpu_enabled
    config["llamacpp"]["gpu_layers"] = payload.gpu_layers
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
    return {"status": "ok", "gpu_enabled": payload.gpu_enabled, "gpu_layers": payload.gpu_layers}


@router.post("/llamacpp/start")
async def llamacpp_start(payload: StartGGUFPayload):
    return ensure_llamacpp_model(payload.model_id)


@router.post("/llamacpp/stop")
async def llamacpp_stop():
    """Para o llama-server e todos os processos filhos."""
    import ctypes
    # Método 1: taskkill com tree kill
    result = subprocess.run(
        ["taskkill", "/f", "/t", "/im", "llama-server.exe"],
        capture_output=True, text=True,
    )
    # Método 2: se ainda existir, mata por PID
    if result.returncode != 0:
        try:
            result2 = subprocess.run(
                ["wmic", "process", "where", "name='llama-server.exe'", "get", "processid"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result2.stdout.strip().split('\n'):
                pid = line.strip()
                if pid.isdigit():
                    subprocess.run(["taskkill", "/f", "/pid", pid], capture_output=True)
        except Exception:
            pass
    return {"status": "stopped", "detail": result.stdout.strip() or "ok"}

