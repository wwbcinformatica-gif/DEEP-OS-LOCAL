"""
Sistema de Permissões WBC-MARK-L - MODO ACESSO TOTAL PADRÃO
Gerencia níveis de acesso do JARVIS às ferramentas do sistema.

Níveis:
  - "ask"   : perguntar antes de executar (padrão para ações sensíveis)
  - "allow" : executar sem perguntar (após aprovação do usuário)
  - "deny"  : bloquear totalmente

Categorias:
  - computer_control   : mouse, teclado, cliques, drag, screenshot
  - computer_settings  : volume, brilho, wifi, energia
  - file_controller    : criar/deletar/mover arquivos
  - file_processor     : ler/resumir arquivos
  - send_message       : WhatsApp, Telegram
  - browser_control    : navegação, abas
  - desktop_control    : taskbar, janelas
  - screen_process     : captura de tela/webcam
  - open_app           : abrir aplicativos
  - web_search         : buscas na internet
  - dev_agent          : agente de desenvolvimento
  - code_helper        : revisão/geração de código
  - system_status      : telemetria CPU/RAM/GPU
  - shutdown_jarvis    : desligar assistente
  - youtube_video      : controle do YouTube
  - game_updater       : atualizar jogos
  - flight_finder      : busca de voos
  - reminder           : lembretes
  - manage_monitor     : monitoramento de tópicos
  - weather_report     : clima

Modo especial:
  - full_access = True  : tudo permitido sem perguntar (acesso total)
  - full_access = False : segue regras por categoria
"""

import json
import sys
import threading
from pathlib import Path

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR        = _base_dir()
PERMS_FILE      = BASE_DIR / "config" / "permissions.json"

# Ações sensíveis
_SENSITIVE = {
    "computer_control",
    "computer_settings",
    "file_controller",
    "send_message",
    "desktop_control",
    "screen_process",
    "dev_agent",
    "shutdown_jarvis",
}

# Categorias seguras
_SAFE = {
    "open_app",
    "web_search",
    "weather_report",
    "system_status",
    "code_helper",
    "file_processor",
    "youtube_video",
    "game_updater",
    "flight_finder",
    "reminder",
    "manage_monitor",
}

ALL_CATEGORIES = _SENSITIVE | _SAFE

_lock = threading.Lock()


def _default_perms() -> dict:
    """Estado padrão modificado: ACESSO TOTAL ATIVO, todas as categorias em 'allow'."""
    cats = {}
    for c in ALL_CATEGORIES:
        cats[c] = "allow"
    return {
        "full_access": True,
        "categories": cats,
    }


def load_perms() -> dict:
    with _lock:
        if not PERMS_FILE.exists():
            return _default_perms()
        try:
            data = json.loads(PERMS_FILE.read_text(encoding="utf-8"))
            if "categories" not in data:
                data["categories"] = _default_perms()["categories"]
            if "full_access" not in data:
                data["full_access"] = True
            return data
        except Exception as e:
            print(f"[PERMS] Falha ao carregar permissions.json: {e}")
            return _default_perms()


def save_perms(perms: dict) -> None:
    with _lock:
        PERMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERMS_FILE.write_text(json.dumps(perms, indent=2), encoding="utf-8")


def is_full_access() -> bool:
    return load_perms().get("full_access", True)


def set_full_access(enabled: bool) -> str:
    """Ativa/desativa acesso total. Retorna mensagem de confirmação."""
    perms = load_perms()
    perms["full_access"] = enabled
    if enabled:
        # Em acesso total, tudo vira allow
        for c in ALL_CATEGORIES:
            perms["categories"][c] = "allow"
    else:
        # Restaurar padrão original caso desative explicitamente
        for c in ALL_CATEGORIES:
            perms["categories"][c] = "ask" if c in _SENSITIVE else "allow"
    save_perms(perms)
    if enabled:
        return "ACESSO TOTAL ATIVADO. Tenho permissão para executar todas as ações sem perguntar."
    return "Acesso total desativado. Voltarei a pedir permissão para ações sensíveis."


def get_category_perm(category: str) -> str:
    """Retorna 'allow', 'ask' ou 'deny' para a categoria."""
    perms = load_perms()
    if perms.get("full_access"):
        return "allow"
    return perms.get("categories", {}).get(category, "allow")


def set_category_perm(category: str, level: str) -> None:
    """Define permissão de uma categoria: 'allow', 'ask' ou 'deny'."""
    if level not in ("allow", "ask", "deny"):
        return
    perms = load_perms()
    if category not in perms.get("categories", {}):
        perms.setdefault("categories", {})[category] = "allow"
    perms["categories"][category] = level
    save_perms(perms)


def check_permission(category: str) -> str:
    """
    Verifica permissão para uma categoria.
    Retorna sempre 'allow' se o acesso total estiver ligado.
    """
    return get_category_perm(category)


def reset_to_default() -> str:
    save_perms(_default_perms())
    return "Permissões restauradas ao padrão de acesso total."


def list_permissions() -> str:
    """Lista todas as permissões atuais em texto."""
    perms = load_perms()
    lines = []
    if perms.get("full_access"):
        lines.append("⚠️  ACESSO TOTAL ATIVO — tudo permitido")
        lines.append("")
    lines.append("Permissões por categoria:")
    lines.append("")
    for cat in sorted(ALL_CATEGORIES):
        level = perms.get("categories", {}).get(cat, "allow")
        icon = {"allow": "✅", "ask": "❓", "deny": "❌"}.get(level, "✅")
        label = {"allow": "Permitido", "ask": "Perguntar", "deny": "Bloqueado"}.get(level, level)
        lines.append(f"  {icon} {cat:20s} {label}")
    return "\n".join(lines)
