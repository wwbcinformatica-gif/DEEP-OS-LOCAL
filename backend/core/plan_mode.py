"""
Plan Mode — Geração e gerenciamento de planos de execução.

Modos:
  - AUTO  : executa imediatamente sem validação
  - PLAN  : exige aprovação do usuário antes de executar
  - SAFE  : exige aprovação + backup antes de executar

Níveis inteligentes (usados quando strategy='intelligent'):
  - LOW   : execução automática, apenas resumo
  - MEDIUM: plano resumido + aprovação
  - HIGH  : plano completo + diff + snapshot + aprovação
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

CHANGE_TYPE_CREATE = "CREATE"
CHANGE_TYPE_MODIFY = "MODIFY"
CHANGE_TYPE_DELETE = "DELETE"
CHANGE_TYPE_RENAME = "RENAME"
CHANGE_TYPE_READ = "READ"
CHANGE_TYPE_EXECUTE = "EXECUTE"
CHANGE_TYPE_OTHER = "OTHER"

PLAN_LEVEL_LOW = "LOW"
PLAN_LEVEL_MEDIUM = "MEDIUM"
PLAN_LEVEL_HIGH = "HIGH"

HIGH_RISK_PATTERNS = ["config", ".env", "auth", "login", "password", "secret", "key", "token",
                      "database", "db.sql", "migration", "schema", "credential", "certificate",
                      "firewall", "security", "permission"]


@dataclass
class ChangeInfo:
    """Metadata about a file change."""
    file: str
    change_type: str = CHANGE_TYPE_OTHER
    lines_added: int = 0
    lines_removed: int = 0
    summary: str = ""
    is_config: bool = False
    is_auth: bool = False
    is_database: bool = False


@dataclass
class PlanStep:
    """Uma etapa do plano de execução."""
    order: int
    tool: str
    description: str
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending | running | done | error
    result: str | None = None
    files_affected: list[str] = field(default_factory=list)
    diff: str = ""
    change_info: ChangeInfo | None = None

    def to_dict(self) -> dict:
        d = {
            "order": self.order,
            "tool": self.tool,
            "description": self.description,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "files_affected": self.files_affected,
            "diff": self.diff,
        }
        if self.change_info:
            d["change_info"] = {
                "file": self.change_info.file,
                "change_type": self.change_info.change_type,
                "lines_added": self.change_info.lines_added,
                "lines_removed": self.change_info.lines_removed,
                "summary": self.change_info.summary,
                "is_config": self.change_info.is_config,
                "is_auth": self.change_info.is_auth,
                "is_database": self.change_info.is_database,
            }
        return d


@dataclass
class ExecutionPlan:
    """Plano completo de execução."""
    steps: list[PlanStep] = field(default_factory=list)
    risk: str = "baixo"  # baixo | medio | alto
    files: list[str] = field(default_factory=list)
    backup_needed: bool = False
    dependencies: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: float = 0.0
    approved: bool = False
    executed: bool = False
    total_additions: int = 0
    total_deletions: int = 0
    risk_reason: str = ""
    level: str = PLAN_LEVEL_LOW  # LOW | MEDIUM | HIGH

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "risk": self.risk,
            "files": self.files,
            "backup_needed": self.backup_needed,
            "dependencies": self.dependencies,
            "summary": self.summary,
            "approved": self.approved,
            "executed": self.executed,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "risk_reason": self.risk_reason,
            "created_at": self.created_at,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionPlan:
        plan = cls(
            risk=d.get("risk", "baixo"),
            files=d.get("files", []),
            backup_needed=d.get("backup_needed", False),
            dependencies=d.get("dependencies", []),
            summary=d.get("summary", ""),
            approved=d.get("approved", False),
            executed=d.get("executed", False),
            total_additions=d.get("total_additions", 0),
            total_deletions=d.get("total_deletions", 0),
            risk_reason=d.get("risk_reason", ""),
            created_at=d.get("created_at", 0.0),
            level=d.get("level", PLAN_LEVEL_LOW),
        )
        for s in d.get("steps", []):
            ci = s.get("change_info")
            change_info = None
            if ci:
                change_info = ChangeInfo(
                    file=ci.get("file", ""),
                    change_type=ci.get("change_type", CHANGE_TYPE_OTHER),
                    lines_added=ci.get("lines_added", 0),
                    lines_removed=ci.get("lines_removed", 0),
                    summary=ci.get("summary", ""),
                    is_config=ci.get("is_config", False),
                    is_auth=ci.get("is_auth", False),
                    is_database=ci.get("is_database", False),
                )
            plan.steps.append(PlanStep(
                order=s.get("order", 0),
                tool=s.get("tool", ""),
                description=s.get("description", ""),
                params=s.get("params", {}),
                status=s.get("status", "pending"),
                result=s.get("result"),
                files_affected=s.get("files_affected", []),
                diff=s.get("diff", ""),
                change_info=change_info,
            ))
        return plan


def _detect_change_type(tool: str, params: dict, filepath: str) -> str:
    """Determina o tipo de alteração baseado na tool e parâmetros."""
    if tool == "write":
        return CHANGE_TYPE_CREATE
    if tool == "delete":
        return CHANGE_TYPE_DELETE
    if tool == "rename":
        return CHANGE_TYPE_RENAME
    if tool == "file_edit":
        return CHANGE_TYPE_MODIFY
    if tool == "read" or tool == "explorer_read" or tool == "explorer":
        return CHANGE_TYPE_READ
    if tool == "bash":
        return CHANGE_TYPE_EXECUTE
    return CHANGE_TYPE_OTHER


def _compute_line_counts(diff_text: str) -> tuple[int, int]:
    """Retorna (lines_added, lines_removed) de um diff texto."""
    added = 0
    removed = 0
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


def _is_config_file(filepath: str) -> bool:
    name = os.path.basename(filepath).lower()
    return any(kw in name for kw in ["config", "conf", "settings", ".env", ".ini", ".toml", ".yaml", ".yml"])


def _is_auth_file(filepath: str) -> bool:
    name = os.path.basename(filepath).lower()
    return any(kw in name for kw in ["auth", "login", "password", "secret", "credential", "token", "key", "certificate"])


def _is_database_file(filepath: str) -> bool:
    name = os.path.basename(filepath).lower()
    return any(kw in name for kw in ["database", "db", "migration", "schema", "sql"])


def _generate_summary(tool: str, params: dict, change_type: str) -> str:
    """Gera um resumo legível da mudança."""
    path = params.get("path", params.get("file", ""))
    base = os.path.basename(path) if path else ""

    summaries = {
        "write": lambda: f"Criar arquivo {base}",
        "file_edit": lambda: f"Editar {base}",
        "delete": lambda: f"Excluir {base}",
        "rename": lambda: f"Renomear {base} → {params.get('new_name', '?')}",
        "create_directory": lambda: f"Criar diretório {path}",
        "bash": lambda: f"Executar comando: {params.get('command', '')[:60]}",
        "read": lambda: f"Ler {base}",
        "explorer": lambda: f"Listar {path or 'raiz'}",
        "explorer_read": lambda: f"Ler {base}",
        "grep": lambda: f"Buscar '{params.get('pattern', '')[:40]}'",
        "search": lambda: f"Pesquisar '{params.get('pattern', '')[:40]}'",
    }
    fn = summaries.get(tool, lambda: f"{tool}: {path or json.dumps(params)[:60]}")
    return fn()


def intelligent_assess(steps: list[PlanStep], total_additions: int, total_deletions: int) -> str:
    """
    Determina o nível inteligente (LOW/MEDIUM/HIGH) baseado nos critérios:
    
    HIGH (qualquer um):
      - >10 arquivos
      - DELETE
      - RENAME
      - auth/database/config files
      - bash com comandos críticos

    MEDIUM:
      - 3-10 arquivos
      - refatorações locais

    LOW:
      - até 2 arquivos
      - sem DELETE/RENAME
      - sem auth/database/config global
    """
    num_files = len(set(f for s in steps for f in s.files_affected))
    has_delete = any(s.tool == "delete" for s in steps)
    has_rename = any(s.tool == "rename" for s in steps)
    has_bash = any(s.tool == "bash" for s in steps)
    has_config = any(s.change_info and s.change_info.is_config for s in steps)
    has_auth = any(s.change_info and s.change_info.is_auth for s in steps)
    has_db = any(s.change_info and s.change_info.is_database for s in steps)

    # HIGH triggers
    if num_files > 10:
        return PLAN_LEVEL_HIGH
    if has_delete:
        return PLAN_LEVEL_HIGH
    if has_rename:
        return PLAN_LEVEL_HIGH
    if has_auth:
        return PLAN_LEVEL_HIGH
    if has_db:
        return PLAN_LEVEL_HIGH
    if has_bash:
        return PLAN_LEVEL_HIGH

    # MEDIUM triggers
    if num_files >= 3:
        return PLAN_LEVEL_MEDIUM
    if has_config:
        return PLAN_LEVEL_MEDIUM
    if total_additions > 100 or total_deletions > 50:
        return PLAN_LEVEL_MEDIUM

    # LOW
    return PLAN_LEVEL_LOW


def assess_risk(steps: list[PlanStep], total_additions: int, total_deletions: int) -> tuple[str, str]:
    """
    Avalia o risco considerando:
    - número de arquivos afetados
    - exclusões
    - alterações em config, auth, database
    - magnitude das mudanças (linhas)
    """
    reasons = []
    risk_score = 0

    # Count files and changes
    num_files = len(set(f for s in steps for f in s.files_affected))
    num_deletes = sum(1 for s in steps if s.tool == "delete")
    num_config = sum(1 for s in steps if s.change_info and s.change_info.is_config)
    num_auth = sum(1 for s in steps if s.change_info and s.change_info.is_auth)
    num_db = sum(1 for s in steps if s.change_info and s.change_info.is_database)
    has_bash = any(s.tool == "bash" for s in steps)
    has_rename = any(s.tool == "rename" for s in steps)

    if num_files > 10:
        risk_score += 3
        reasons.append(f"{num_files} arquivos afetados")
    elif num_files > 5:
        risk_score += 2
        reasons.append(f"{num_files} arquivos afetados")
    elif num_files > 2:
        risk_score += 1

    if num_deletes > 0:
        risk_score += 2
        reasons.append(f"{num_deletes} exclusão(ões)")

    if num_config > 0:
        risk_score += 3
        reasons.append("altera arquivos de configuração")

    if num_auth > 0:
        risk_score += 3
        reasons.append("altera arquivos de autenticação")

    if num_db > 0:
        risk_score += 3
        reasons.append("altera arquivos de banco de dados")

    if has_bash:
        risk_score += 2
        reasons.append("executa comandos shell")

    if has_rename:
        risk_score += 1
        reasons.append("renomeia arquivos")

    if total_deletions > 100:
        risk_score += 2
        reasons.append(f"{total_deletions} linhas removidas")
    elif total_deletions > 30:
        risk_score += 1

    if total_additions > 200:
        risk_score += 1
        reasons.append(f"{total_additions} linhas adicionadas")

    if risk_score >= 6:
        return "alto", "; ".join(reasons[:3])
    elif risk_score >= 3:
        return "medio", "; ".join(reasons[:2]) if reasons else "alterações moderadas"
    return "baixo", "alterações simples e seguras"


def needs_backup(steps: list[PlanStep], risk: str) -> bool:
    """Determina se backup é recomendado."""
    write_tools = {"write", "file_edit", "delete", "rename", "bash"}
    for s in steps:
        if s.tool in write_tools:
            return True
    return risk == "alto"


def generate_diff_preview(filepath: str, old_string: str, new_string: str) -> str:
    """
    Gera um diff estilizado (linhas) entre old_string e new_string,
    simulando unified diff sem dependência externa.
    Retorna string formatada para exibição.
    """
    old_lines = old_string.splitlines(True)
    new_lines = new_string.splitlines(True)
    import difflib
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        n=3,
    )
    return "".join(diff)


def compute_plan_diffs(plan: ExecutionPlan, workspace: str) -> dict[int, str]:
    """
    Para cada file_edit do plano, lê o arquivo atual e gera um diff preview.
    Retorna dict {order: diff_text}.
    """
    diffs: dict[int, str] = {}
    for step in plan.steps:
        if step.tool == "file_edit":
            path = step.params.get("path", "")
            full_path = os.path.join(workspace, path) if workspace else path
            old_string = step.params.get("old_string", "")
            new_string = step.params.get("new_string", "")
            if os.path.isfile(full_path) and old_string:
                try:
                    diffs[step.order] = generate_diff_preview(path, old_string, new_string)
                except Exception:
                    pass
    return diffs


def _extract_files_from_params(tool: str, params: dict) -> list[str]:
    """Extrai arquivos afetados dos parâmetros de uma tool."""
    files = []
    if "path" in params and isinstance(params["path"], str):
        files.append(params["path"])
    if "root" in params and isinstance(params["root"], str):
        files.append(params["root"])
    return files


def extract_plan_from_tool_calls(
    collected_tools: list[dict],
    user_message: str,
    full_answer: str = "",
    workspace: str = "",
) -> ExecutionPlan:
    """
    Converte tool_calls do LLM em um ExecutionPlan estruturado.
    """
    plan = ExecutionPlan()
    plan.created_at = time.time()
    plan.summary = full_answer[:500] if full_answer else user_message[:200]

    for i, tc in enumerate(collected_tools):
        tool_name = tc.get("function", {}).get("name", "")
        try:
            tool_params = json.loads(tc.get("function", {}).get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            tool_params = {}

        path = tool_params.get("path", tool_params.get("file", ""))
        change_type = _detect_change_type(tool_name, tool_params, path)
        summary = _generate_summary(tool_name, tool_params, change_type)
        files = _extract_files_from_params(tool_name, tool_params)

        step = PlanStep(
            order=i + 1,
            tool=tool_name,
            description=_describe_tool_call(tool_name, tool_params),
            params=tool_params,
            files_affected=files,
            change_info=ChangeInfo(
                file=path,
                change_type=change_type,
                summary=summary,
                is_config=_is_config_file(path),
                is_auth=_is_auth_file(path),
                is_database=_is_database_file(path),
            ),
        )
        plan.steps.append(step)

    for s in plan.steps:
        plan.files.extend(s.files_affected)
    plan.files = list(set(plan.files))

    # Generate diff previews for file_edit steps
    diffs = compute_plan_diffs(plan, workspace)
    for step in plan.steps:
        if step.order in diffs:
            step.diff = diffs[step.order]
            added, removed = _compute_line_counts(step.diff)
            if step.change_info:
                step.change_info.lines_added = added
                step.change_info.lines_removed = removed
            plan.total_additions += added
            plan.total_deletions += removed

    # Assess risk with new metrics
    plan.risk, plan.risk_reason = assess_risk(plan.steps, plan.total_additions, plan.total_deletions)
    plan.backup_needed = needs_backup(plan.steps, plan.risk)

    # Intelligent level assessment
    plan.level = intelligent_assess(plan.steps, plan.total_additions, plan.total_deletions)

    return plan


def _describe_tool_call(tool: str, params: dict) -> str:
    """Gera descrição legível de uma chamada de ferramenta."""
    descriptions = {
        "read": lambda p: f"Ler arquivo: {p.get('path', '?')}",
        "write": lambda p: f"Escrever arquivo: {p.get('path', '?')}",
        "file_edit": lambda p: f"Editar arquivo: {p.get('path', '?')}",
        "delete": lambda p: f"Excluir: {p.get('path', '?')}",
        "rename": lambda p: f"Renomear: {p.get('path', '?')} para {p.get('new_name', '?')}",
        "create_directory": lambda p: f"Criar diretório: {p.get('path', '?')}",
        "explorer": lambda p: f"Listar diretório: {p.get('path', '?') or '(raiz)'}",
        "explorer_read": lambda p: f"Ler arquivo (explorer): {p.get('path', '?')}",
        "bash": lambda p: f"Executar comando: {p.get('command', '?')[:80]}",
        "search": lambda p: f"Buscar: {p.get('pattern', '?')}",
        "grep": lambda p: f"Grep: {p.get('pattern', '?')} em {p.get('path', '?')}",
    }
    desc = descriptions.get(tool, lambda p: f"Chamar {tool} com params: {json.dumps(p)[:60]}")
    return desc(params)


def create_snapshot(workspace: str, files: list[str]) -> dict:
    """
    Cria snapshot (backup) de uma lista de arquivos antes da execução.
    Mais leve que create_backup — não precisa de um ExecutionPlan completo.
    """
    backup_dir = Path(workspace) / ".wbc-backup" / f"snapshot_{int(time.time())}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backed_up = []
    for f in files:
        src = Path(workspace) / f
        if src.exists() and src.is_file():
            dst = backup_dir / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(src), str(dst))
                backed_up.append(f)
            except Exception:
                pass
    return {
        "success": len(backed_up) > 0,
        "backup_path": str(backup_dir),
        "files_backed_up": backed_up,
        "type": "snapshot",
    }


def create_backup(workspace: str, plan: ExecutionPlan) -> dict:
    """
    Cria backup dos arquivos afetados antes da execução (modo SAFE).
    Retorna {success, backup_path, files_backed_up}.
    """
    backup_dir = Path(workspace) / ".wbc-backup" / f"backup_{int(time.time())}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up = []
    for f in plan.files:
        src = Path(workspace) / f
        if src.exists() and src.is_file():
            dst = backup_dir / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(src), str(dst))
                backed_up.append(f)
            except Exception:
                pass

    return {
        "success": len(backed_up) > 0,
        "backup_path": str(backup_dir),
        "files_backed_up": backed_up,
    }


def restore_backup(backup_path: str, workspace: str) -> dict:
    """Restaura arquivos de um backup anterior."""
    backup_dir = Path(backup_path)
    if not backup_dir.exists():
        return {"success": False, "error": "Backup não encontrado"}
    restored = []
    for f in backup_dir.rglob("*"):
        if f.is_file():
            rel = f.relative_to(backup_dir)
            target = Path(workspace) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(f), str(target))
                restored.append(str(rel))
            except Exception:
                pass
    return {"success": True, "files_restored": restored}
