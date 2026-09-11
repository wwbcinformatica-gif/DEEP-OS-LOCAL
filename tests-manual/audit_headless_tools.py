"""
Auditoria: quais tools do Charon funcionam num VPS headless?

Simula o ambiente do VPS (sem DISPLAY) e verifica, para cada arquivo de
action, se o import funciona e se a tool tem como operar. Isso evita que o
Charon ofereça ao usuario ferramentas que so vao falhar.
"""
import importlib
import os
import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "actions"))

# Simula VPS Linux headless
os.environ.pop("DISPLAY", None)
os.environ.pop("WAYLAND_DISPLAY", None)

# Nomes de arquivo de action (o que o Charon expoe como tool)
ACTIONS = [
    "background_monitor", "browser_control", "code_helper", "computer_control",
    "computer_settings", "desktop", "dev_agent", "download_image",
    "file_controller", "file_processor", "flight_finder", "game_updater",
    "open_app", "proactive", "reminder", "screen_processor", "send_message",
    "system_monitor", "weather_report", "web_search", "youtube_video",
]

print(f"Python {sys.version.split()[0]} | DISPLAY={os.environ.get('DISPLAY')!r}")
print("=" * 74)

resultado = {}

for nome in ACTIONS:
    try:
        mod = importlib.import_module(nome)
        # Procura a funcao principal (mesmo nome do modulo, ou a 1a callable publica)
        fn = getattr(mod, nome, None)
        if fn is None:
            pubs = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))]
            fn = getattr(mod, pubs[0], None) if pubs else None
        resultado[nome] = ("import OK", fn is not None)
    except Exception as e:
        resultado[nome] = (f"IMPORT FALHOU: {type(e).__name__}: {e}", False)

for nome in ACTIONS:
    status, tem_fn = resultado[nome]
    marca = "OK " if status == "import OK" and tem_fn else "!! "
    print(f"{marca}{nome:<22} {status}")

print("=" * 74)
falhas = [n for n, (s, f) in resultado.items() if s != "import OK" or not f]
print(f"\nActions que NAO importam/carregam: {len(falhas)}")
for n in falhas:
    print(f"  - {n}: {resultado[n][0]}")

# Verifica se os modulos de GUI realmente falham ao usar (sem display)
print("\n" + "=" * 74)
print("Teste real: pyautogui / mss conseguem operar sem display?")
for modname in ("pyautogui", "mss"):
    try:
        m = importlib.import_module(modname)
        print(f"  {modname}: import OK", end="")
        if modname == "mss":
            try:
                with m.mss() as sct:
                    print(" | captura OK")
            except Exception as e:
                print(f" | CAPTURA FALHA: {type(e).__name__}: {str(e)[:70]}")
        else:
            try:
                print(f" | size={m.size()}")
            except Exception as e:
                print(f" | USO FALHA: {type(e).__name__}: {str(e)[:70]}")
    except Exception as e:
        print(f"  {modname}: import FALHOU: {type(e).__name__}: {str(e)[:70]}")
