import json
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to load api_keys.json: {e}")
        return {}

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def _get_root_config_path() -> Path:
    """Retorna caminho do config.yaml raiz (C:\\DEEP-OS\\config.yaml)."""
    return Path(__file__).resolve().parent.parent.parent / "config.yaml"


def get_assistant_name() -> str:
    """Return the configured assistant name from root config.yaml."""
    try:
        cfg_path = _get_root_config_path()
        if cfg_path.exists():
            import yaml
            with open(cfg_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            name = data.get("identity", {}).get("assistant_name", "")
            if name:
                return name
    except Exception:
        pass
    return load_api_keys().get("assistant_name", "DEEP-OS") or "DEEP-OS"


def get_user_name() -> str:
    """Return the configured user name from root config.yaml."""
    try:
        cfg_path = _get_root_config_path()
        if cfg_path.exists():
            import yaml
            with open(cfg_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            name = data.get("identity", {}).get("user_name", "")
            if name:
                return name
    except Exception:
        pass
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to root config.yaml."""
    try:
        import yaml
        cfg_path = _get_root_config_path()
        data: dict = {}
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        if "identity" not in data:
            data["identity"] = {}
        data["identity"]["assistant_name"] = assistant_name.strip() or "DEEP-OS"
        data["identity"]["user_name"] = user_name.strip()
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        print(f"Failed to save identity to config.yaml: {e}")
    # Tambem mantem api_keys.json atualizado (compatibilidade)
    ensure_config_dir()
    data_ak: dict = {}
    if CONFIG_FILE.exists():
        try:
            data_ak = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data_ak = {}
    data_ak["assistant_name"] = assistant_name.strip() or "DEEP-OS"
    data_ak["user_name"] = user_name.strip()
    CONFIG_FILE.write_text(json.dumps(data_ak, indent=4), encoding="utf-8")


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["morning_brief_enabled"] = enabled
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
