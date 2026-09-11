"""Dashboard de Monitoramento — CPU, RAM, VRAM (GPU), logs."""
import os
import re
import subprocess
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

_BASE = Path(__file__).resolve().parent.parent.parent
_LOG_FILE = _BASE / "server_stdout.log"
_FALLBACK_LOG = _BASE / "logs" / "inicializacao.log"

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)


def coletar_cpu() -> float:
    if psutil is None:
        return 0.0
    return psutil.cpu_percent(interval=0.3)


def coletar_ram() -> dict:
    if psutil is None:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}
    m = psutil.virtual_memory()
    return {
        "total_gb": round(m.total / (1024**3), 1),
        "used_gb": round(m.used / (1024**3), 1),
        "percent": m.percent,
    }


def coletar_vram() -> dict:
    """Coleta uso de VRAM via nvidia-smi. Fallback silencioso se não houver GPU NVIDIA."""
    # Caminhos possíveis do nvidia-smi
    nvidia_smi_paths = [
        r"C:\Windows\System32\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        "nvidia-smi",
    ]
    nvidia_smi = None
    for p in nvidia_smi_paths:
        if os.path.exists(p):
            nvidia_smi = p
            break
    if not nvidia_smi:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {"total_gb": 0, "used_gb": 0, "percent": 0}
        line = strip_ansi(result.stdout.strip())
        if not line:
            return {"total_gb": 0, "used_gb": 0, "percent": 0}
        parts = line.split(",")
        if len(parts) < 2:
            return {"total_gb": 0, "used_gb": 0, "percent": 0}
        used_mib = float(parts[0].strip())
        total_mib = float(parts[1].strip())
        if total_mib == 0:
            return {"total_gb": 0, "used_gb": 0, "percent": 0}
        return {
            "total_gb": round(total_mib / 1024, 1),
            "used_gb": round(used_mib / 1024, 1),
            "percent": round((used_mib / total_mib) * 100, 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}


def ler_logs(linhas: int = 20) -> list[str]:
    for p in [_LOG_FILE, _FALLBACK_LOG]:
        if p.exists() and p.stat().st_size > 0:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                lines = text.strip().split("\n")
                return [strip_ansi(l) for l in lines[-linhas:]]
            except Exception:
                pass
    return ["(sem logs)"]


def coletar_dashboard() -> dict:
    return {
        "cpu": coletar_cpu(),
        "ram": coletar_ram(),
        "vram": coletar_vram(),
        "logs": ler_logs(),
        "timestamp": time.time(),
    }
