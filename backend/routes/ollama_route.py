import json
import subprocess
from pathlib import Path
from typing import List

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def _read_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def _write_config(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)


def _fetch_ollama_models() -> dict:
    """Chama a API local do Ollama e retorna status + lista de modelos."""
    import platform
    curl = "curl.exe" if platform.system() == "Windows" else "curl"
    try:
        r = subprocess.run(
            [curl, "-s", "--max-time", "5", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=6,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {"running": False, "models": []}
        data = json.loads(r.stdout)
        models = [m["name"] for m in data.get("models", [])]
        return {"running": True, "models": models}
    except Exception as e:
        return {"running": False, "models": [], "error": str(e)}


def _fetch_local_gguf_models() -> List[dict]:
    """Busca modelos GGUF na pasta models/ e retorna lista de {name, path, size}."""
    models = []
    if not MODELS_DIR.exists():
        return models
    
    # Buscar arquivos GGUF recursivamente
    for gguf_file in MODELS_DIR.rglob("*.gguf"):
        # Ignorar arquivos de projeção (mmproj)
        if "mmproj" in gguf_file.name.lower():
            continue
        
        try:
            size_bytes = gguf_file.stat().st_size
            size_gb = size_bytes / (1024 ** 3)
            
            # Criar nome amigável baseado no nome do arquivo
            name = gguf_file.stem
            # Remover padrões comuns de quantização para melhorar legibilidade
            for suffix in ["-Q4_K_M", "-Q4_K_S", "-Q4_0", "-Q4_1", "-Q5_K_M", "-Q5_K_S", 
                          "-Q5_0", "-Q5_1", "-Q6_K", "-Q8_0", "-Q2_0", "-Q2_K", "-IQ4_XS",
                          "-IQ3_M", "-IQ3_S", "-IQ3_XS", "-IQ2_M", "-IQ2_S", "-IQ2_XS",
                          "-FP16", "-BF16", "-F16"]:
                name = name.replace(suffix, "")
            
            # Limpar separadores e capitalizar
            name = name.replace("-", " ").replace("_", " ").strip()
            name = " ".join(word.capitalize() for word in name.split())
            
            models.append({
                "name": name,
                "path": str(gguf_file),
                "filename": gguf_file.name,
                "size_gb": round(size_gb, 2),
                "source": "local_gguf"
            })
        except Exception:
            continue
    
    return models


def get_gpu_config() -> dict:
    config = _read_config()
    ollama_cfg = config.get("ollama", {})
    return {
        "gpu_enabled": ollama_cfg.get("gpu_enabled", True),
        "gpu_layers": ollama_cfg.get("gpu_layers", -1),
    }


def set_gpu_config(gpu_enabled: bool, gpu_layers: int = -1):
    config = _read_config()
    if "ollama" not in config:
        config["ollama"] = {}
    config["ollama"]["gpu_enabled"] = gpu_enabled
    config["ollama"]["gpu_layers"] = gpu_layers
    _write_config(config)


class GpuConfigPayload(BaseModel):
    gpu_enabled: bool
    gpu_layers: int = -1


@router.get("/ollama/status")
async def ollama_status():
    result = _fetch_ollama_models()
    return {
        "running": result.get("running", False),
        "models": result.get("models", []),
    }


@router.get("/ollama/models")
async def ollama_models():
    """Retorna apenas modelos instalados no Ollama (sem GGUF locais)."""
    result = _fetch_ollama_models()
    return {
        "running": result.get("running", False),
        "models": result.get("models", []),
    }


@router.get("/ollama/local-models")
async def ollama_local_models():
    """Retorna apenas os modelos GGUF locais da pasta models/."""
    return {
        "models": _fetch_local_gguf_models(),
        "models_dir": str(MODELS_DIR),
    }


@router.get("/ollama/gpu")
async def ollama_get_gpu():
    return get_gpu_config()


@router.post("/ollama/gpu")
async def ollama_set_gpu(payload: GpuConfigPayload):
    set_gpu_config(payload.gpu_enabled, payload.gpu_layers)
    return {"status": "ok", "gpu_enabled": payload.gpu_enabled, "gpu_layers": payload.gpu_layers}
