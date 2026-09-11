"""
OpenCode Agents & Skills Loader
================================
Carrega agentes e skills da pasta .opencode/ do projeto DEEP-OS.

Agentes sao arquivos .md com frontmatter YAML:
  - description, mode (primary/subagent), model, permission
  - Corpo com instrucoes do system prompt

Skills sao pastas com SKILL.md:
  - name, description, allowed-tools
  - Corpo com padroes e instrucoes especializadas
"""

import os
import re
from pathlib import Path
from typing import Optional

OPENCODE_DIR = Path(__file__).resolve().parent.parent.parent / ".opencode"
AGENTS_DIR = OPENCODE_DIR / "agent"
SKILLS_DIR = OPENCODE_DIR / "skills"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extrai frontmatter YAML e corpo de um arquivo .md."""
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not fm_match:
        return {}, content

    fm_text = fm_match.group(1)
    body = fm_match.group(2).strip()

    fm = {}
    current_key = None
    current_list = None

    for line in fm_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("- ") and current_key:
            if current_list is None:
                current_list = []
            val = stripped[2:].strip()
            if ":" in val and " " in val.split(":")[0]:
                parts = val.split(":", 1)
                current_list.append({parts[0].strip(): parts[1].strip()})
            else:
                current_list.append(val)
            continue

        if ":" in stripped and not stripped.startswith("-"):
            if current_list is not None:
                fm[current_key] = current_list
                current_list = None
            parts = stripped.split(":", 1)
            current_key = parts[0].strip()
            val = parts[1].strip()
            if val and val != ">" and val != ">-":
                fm[current_key] = val
            elif val in (">", ">-"):
                current_key = current_key
            continue

    if current_list is not None:
        fm[current_key] = current_list

    return fm, body


def load_opencode_agents() -> dict:
    """
    Carrega todos os agentes da pasta .opencode/agent/.
    Retorna dict: {name: {description, model, mode, permission, prompt}}
    """
    agents = {}
    if not AGENTS_DIR.exists():
        return agents

    for agent_file in AGENTS_DIR.glob("*.md"):
        try:
            content = agent_file.read_text(encoding="utf-8", errors="replace")
            fm, body = _parse_frontmatter(content)
            name = agent_file.stem
            agents[name] = {
                "name": name,
                "description": fm.get("description", ""),
                "model": fm.get("model", ""),
                "mode": fm.get("mode", "subagent"),
                "permission": fm.get("permission", {}),
                "prompt": body,
                "file": str(agent_file),
            }
        except Exception:
            pass

    return agents


def load_opencode_skills() -> dict:
    """
    Carrega todas as skills da pasta .opencode/skills/.
    Retorna dict: {name: {description, allowed_tools, content}}
    """
    skills = {}
    if not SKILLS_DIR.exists():
        return skills

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            if skill_dir.suffix == ".md":
                try:
                    content = skill_dir.read_text(encoding="utf-8", errors="replace")
                    fm, body = _parse_frontmatter(content)
                    name = fm.get("name", skill_dir.stem)
                    skills[name] = {
                        "name": name,
                        "description": fm.get("description", ""),
                        "allowed_tools": fm.get("allowed-tools", ""),
                        "content": body,
                        "file": str(skill_dir),
                    }
                except Exception:
                    pass
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            fm, body = _parse_frontmatter(content)
            name = fm.get("name", skill_dir.name)
            skills[name] = {
                "name": name,
                "description": fm.get("description", ""),
                "allowed_tools": fm.get("allowed-tools", ""),
                "content": body,
                "file": str(skill_file),
            }
        except Exception:
            pass

    return skills


def get_agent_prompt(agent_name: str) -> Optional[str]:
    """Retorna o system prompt de um agente especifico."""
    agents = load_opencode_agents()
    agent = agents.get(agent_name)
    if agent:
        return agent["prompt"]
    return None


def get_skill_content(skill_name: str) -> Optional[str]:
    """Retorna o conteudo de uma skill especifica."""
    skills = load_opencode_skills()
    skill = skills.get(skill_name)
    if skill:
        return skill["content"]
    return None


def build_agent_enhanced_prompt(base_prompt: str, agent_name: str = "") -> str:
    """
    Combina o system prompt base com o prompt de um agente .opencode.
    Se agent_name estiver vazio, usa apenas o base_prompt.
    """
    if not agent_name:
        return base_prompt

    agent_prompt = get_agent_prompt(agent_name)
    if not agent_prompt:
        return base_prompt

    return f"{base_prompt}\n\n[AGENTE: {agent_name.upper()}]\n{agent_prompt}"


def inject_skill_context(prompt: str, skill_names: list[str]) -> str:
    """
    Injeta conteudo de skills no system prompt.
    """
    if not skill_names:
        return prompt

    skills = load_opencode_skills()
    skill_parts = []
    for name in skill_names:
        skill = skills.get(name)
        if skill:
            skill_parts.append(f"[SKILL: {name}]\n{skill['content'][:2000]}")

    if skill_parts:
        return f"{prompt}\n\n" + "\n\n".join(skill_parts)

    return prompt


def list_available_agents() -> list[dict]:
    """Lista agentes disponiveis para o frontend."""
    agents = load_opencode_agents()
    return [
        {
            "name": a["name"],
            "description": a["description"],
            "model": a["model"],
            "mode": a["mode"],
        }
        for a in agents.values()
    ]


def list_available_skills() -> list[dict]:
    """Lista skills disponiveis para o frontend."""
    skills = load_opencode_skills()
    return [
        {
            "name": s["name"],
            "description": s["description"],
            "allowed_tools": s["allowed_tools"],
        }
        for s in skills.values()
    ]