"""
Shim de compatibilidade para as actions do Charon.

Por que este arquivo existe
---------------------------
Existe um DIRETORIO `backend/config/` (com `api_keys.json` e `permissions.json`)
que nao tem `__init__.py`. O Python o trata como *namespace package*, e isso
sombreava o `config.py` real da raiz do projeto:

    >>> import config
    >>> config.__file__          # None! pacote vazio, sem get_os/is_headless

Consequencia: `actions/youtube_video.py`, `actions/game_updater.py` e
`actions/flight_finder.py` faziam

    from config import get_os, is_windows, is_linux, is_headless,

e estouravam com `ImportError: cannot import name 'get_os' from 'config'`.
A tool `youtube_video` era oferecida ao Charon mas NUNCA carregava.

Este modulo — um arquivo real chamado `config.py` dentro de `backend/` —
tem precedencia sobre o diretorio e restaura os helpers, delegando para o
`config.py` verdadeiro da raiz. Nao mover nem renomear: a posicao e o que
faz o shim funcionar.
"""
import importlib.util
import sys
from pathlib import Path

# backend/config.py -> backend/ -> raiz do projeto
_ROOT_CONFIG = Path(__file__).resolve().parent.parent / "config.py"

_impl = None

if _ROOT_CONFIG.exists():
    try:
        _spec = importlib.util.spec_from_file_location("_deepos_root_config", _ROOT_CONFIG)
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules["_deepos_root_config"] = _mod
            _spec.loader.exec_module(_mod)
            _impl = _mod
    except Exception as e:  # nunca derrubar o import por causa do helper
        print(f"[config] Falha ao carregar {_ROOT_CONFIG}: {e}")

if _impl is not None:
    from _deepos_root_config import (  # noqa: F401
        get_os,
        is_headless,
        is_linux,
        is_mac,
        is_windows,
    )
else:
    # Fallback independente — mesmo contrato, sem depender do arquivo da raiz.
    import os
    import platform

    def get_os() -> str:
        return platform.system().lower()

    def is_windows() -> bool:
        return get_os() == "windows"

    def is_mac() -> bool:
        return get_os() == "mac"

    def is_linux() -> bool:
        return get_os() == "linux"

    def is_headless() -> bool:
        """Sem interface grafica? (VPS/servidor)"""
        if is_windows():
            return False
        return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


__all__ = ["get_os", "is_windows", "is_mac", "is_linux", "is_headless"]
