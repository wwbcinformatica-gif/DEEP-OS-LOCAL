"""
WorkspaceManager
================
Singleton central que gerencia o workspace ativo.
Todos os componentes consultam este manager em vez de acessar BASE_DIR diretamente.

Arquitetura preparada para futuro suporte multi-workspace:
  - list_workspaces()   → retornar todos os workspaces conhecidos
  - add_workspace()     → registrar novo workspace nomeado
  - remove_workspace()  → remover workspace da lista
  - switch_workspace()  → trocar entre workspaces nomeados
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

_log = logging.getLogger("wbc.workspace")


def _resolve_proj_root() -> Path:
    """Resolve a raiz do projeto DEEP-OS (3 níveis acima de core/)."""
    return Path(__file__).resolve().parent.parent.parent


_DEFAULT_PROJECT_ROOT = _resolve_proj_root()
_DEFAULT_CONFIG_PATH = _DEFAULT_PROJECT_ROOT / "config.yaml"


class WorkspaceEntry:
    """Representa um workspace registrado (preparação multi-workspace)."""

    def __init__(self, name: str, path: str, last_opened: str | None = None):
        self.name = name
        self.path = path
        self.last_opened = last_opened or ""

    def to_dict(self) -> dict:
        return {"name": self.name, "path": self.path, "last_opened": self.last_opened}

    @classmethod
    def from_dict(cls, d: dict) -> WorkspaceEntry:
        return cls(d.get("name", ""), d.get("path", ""), d.get("last_opened", ""))


class WorkspaceManager:
    """Gerencia o workspace ativo e prepara o terreno para múltiplos projetos."""

    _instance: WorkspaceManager | None = None

    def __init__(self, config_path: str | None = None):
        self._config_path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self._workspace: Path = _DEFAULT_PROJECT_ROOT
        self._workspace_name: str = "default"
        self._workspaces: list[WorkspaceEntry] = []
        self._config_loaded = False

    # ─── Singleton ────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls, config_path: str | None = None) -> WorkspaceManager:
        if cls._instance is None:
            cls._instance = cls(config_path=config_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    # ─── Leitura/Escrita do config.yaml ───────────────────────────────

    def _read_config(self) -> dict:
        try:
            if self._config_path.exists():
                with open(self._config_path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            _log.warning("Erro ao ler config.yaml: %s", e)
        return {}

    def _write_config(self, data: dict):
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            _log.error("Erro ao escrever config.yaml: %s", e)

    # ─── API Pública ──────────────────────────────────────────────────

    def load_workspace(self) -> Path:
        """
        Carrega o workspace do config.yaml.
        Se não configurado, usa o diretório do projeto como padrão.
        """
        if self._config_loaded:
            return self._workspace

        config = self._read_config()

        # Carrega workspaces conhecidos (futuro: multi-workspace)
        ws_list = config.get("workspaces", [])
        self._workspaces = [WorkspaceEntry.from_dict(w) for w in ws_list]

        # Carrega workspace ativo
        ws_config = config.get("workspace") or {}
        root_str = ws_config.get("root", "")
        if root_str:
            p = Path(root_str).resolve()
            if p.exists() and p.is_dir():
                self._workspace = p
                self._workspace_name = ws_config.get("name", "default")

        self._config_loaded = True
        return self._workspace

    def get_workspace(self) -> Path:
        """Retorna o Path do workspace ativo (sempre carregado)."""
        if not self._config_loaded:
            self.load_workspace()
        return self._workspace

    def get_workspace_str(self) -> str:
        """Retorna o workspace como string."""
        return str(self.get_workspace())

    def get_workspace_name(self) -> str:
        return self._workspace_name

    def validate_workspace(self, path: str) -> dict:
        """
        Valida se um caminho é um workspace válido.
        Retorna {"valid": bool, "error": str | None, "resolved": str | None}.
        """
        try:
            clean_path = path.strip(' "\'')
            p = Path(clean_path).resolve()
            if not p.exists():
                return {"valid": False, "error": "Caminho não existe", "resolved": str(p)}
            if not p.is_dir():
                return {"valid": False, "error": "Caminho não é um diretório", "resolved": str(p)}
            # Verifica permissão de leitura
            try:
                next(p.iterdir(), None)
            except PermissionError:
                return {"valid": False, "error": "Sem permissão de leitura", "resolved": str(p)}
            # Verifica se não é um diretório de sistema protegido
            system_dirs = {
                "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
                "C:\\System32", "C:\\System Volume Information",
                "C:\\$Recycle.Bin", "C:\\Recovery",
            }
            if str(p).rstrip("\\") in system_dirs:
                return {"valid": False, "error": "Diretório de sistema protegido", "resolved": str(p)}
            return {"valid": True, "error": None, "resolved": str(p)}
        except Exception as e:
            return {"valid": False, "error": str(e), "resolved": None}

    def set_workspace(self, path: str) -> dict:
        """
        Define o workspace ativo.
        Valida o caminho, persiste no config.yaml e retorna resultado.

        Retorna {"success": bool, "error": str | None, "workspace": str | None}.
        """
        validation = self.validate_workspace(path)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"], "workspace": None}

        resolved = validation["resolved"]
        self._workspace = Path(resolved)
        self._workspace_name = self._workspace.name
        self._config_loaded = True

        self.persist_workspace()

        # Invalida cache do agent_config para recarregar config.yaml na proxima chamada
        try:
            from core.agent_config import reset_config_cache
            reset_config_cache()
        except ImportError:
            pass

        return {"success": True, "error": None, "workspace": resolved}

    def persist_workspace(self):
        """
        Persiste o workspace ativo no config.yaml.
        Também atualiza a lista de workspaces conhecidos (preparação multi-workspace).
        """
        config = self._read_config()

        # Atualiza workspace ativo
        config["workspace"] = {
            "root": self.get_workspace_str(),
            "name": self._workspace_name,
        }

        # Atualiza terminal.cwd para o novo workspace
        config.setdefault("terminal", {})["cwd"] = self.get_workspace_str()

        # Atualiza lista de workspaces conhecidos (futuro)
        ws_key = self.get_workspace_str()
        existing_names = {w.name for w in self._workspaces}
        if self._workspace_name not in existing_names:
            self._workspaces.append(WorkspaceEntry(
                name=self._workspace_name,
                path=ws_key,
            ))
        else:
            for w in self._workspaces:
                if w.name == self._workspace_name:
                    w.path = ws_key
                    break
        config["workspaces"] = [w.to_dict() for w in self._workspaces]

        self._write_config(config)

    # ─── Futuro: multi-workspace ──────────────────────────────────────

    def list_workspaces(self) -> list[WorkspaceEntry]:
        """Retorna a lista de workspaces conhecidos (preparação multi-workspace)."""
        if not self._config_loaded:
            self.load_workspace()
        return self._workspaces.copy()

    def add_workspace(self, name: str, path: str) -> dict:
        """
        Registra um novo workspace na lista (não ativa).
        Preparação para suporte multi-workspace.
        """
        validation = self.validate_workspace(path)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"]}
        if name in {w.name for w in self._workspaces}:
            return {"success": False, "error": f"Workspace '{name}' já existe"}
        self._workspaces.append(WorkspaceEntry(name=name, path=validation["resolved"]))
        self.persist_workspace()
        return {"success": True, "error": None}

    def remove_workspace(self, name: str) -> dict:
        """Remove um workspace da lista (preparação multi-workspace)."""
        before = len(self._workspaces)
        self._workspaces = [w for w in self._workspaces if w.name != name]
        if len(self._workspaces) == before:
            return {"success": False, "error": f"Workspace '{name}' não encontrado"}
        if self._workspace_name == name:
            fallback = self._workspaces[0] if self._workspaces else WorkspaceEntry("default", str(_DEFAULT_PROJECT_ROOT))
            self._workspace = Path(fallback.path)
            self._workspace_name = fallback.name
        self.persist_workspace()
        return {"success": True, "error": None}

    def switch_workspace(self, name: str) -> dict:
        """Troca para um workspace registrado pelo nome (preparação multi-workspace)."""
        for w in self._workspaces:
            if w.name == name:
                return self.set_workspace(w.path)
        return {"success": False, "error": f"Workspace '{name}' não encontrado"}
