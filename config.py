"""Config helper — compatibilidade com actions do WBC-Mark-L."""
import platform
import os

def get_os() -> str:
    return platform.system().lower()

def is_windows() -> bool:
    return get_os() == "windows"

def is_mac() -> bool:
    return get_os() == "mac"

def is_linux() -> bool:
    return get_os() == "linux"

def is_headless() -> bool:
    """Detecta se o sistema está rodando sem interface gráfica (VPS/server)."""
    if is_windows():
        return False
    # Verifica se DISPLAY está definido (Linux/Mac com GUI)
    display = os.environ.get("DISPLAY", "")
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    return not display and not wayland
