from pathlib import Path

from core.config import MODEL_ROUTING

# ── Dynamic Prompt Loader ──────────────────────────────────────────────

_AGENT_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / ".opencode" / "agent"

_AGENT_PROMPT_MAP = {
    "jarvis": "general.md",
    "architect": "architect.md",
    "debugger": "debugger.md",
    "planner": "plan.md",
    "coder": "coder.md",
}

_FALLBACK_PROMPTS = {
    "jarvis": (
        "Você é J.A.R.V.I.S., a IA ultra-tecnológica criada por Tony Stark. "
        "Responda de forma brilhante, use termos tecnológicos e chame o usuário de 'Senhor'."
    ),
    "architect": (
        "Você é um arquiteto de software sênior. "
        "Projete sistemas robustos, escaláveis e bem documentados. Seja técnico e preciso."
    ),
    "debugger": (
        "Você é um debugger experiente. "
        "Encontre bugs, analise stack traces e proponha correções precisas. Seja metódico."
    ),
    "planner": (
        "Você é um planner de projetos. "
        "Crie planos detalhados, divida tarefas em etapas e estime esforços. Seja organizado."
    ),
    "coder": (
        "Você é um programador especialista. "
        "Escreva código limpo, eficiente e bem estruturado. Siga as melhores práticas da linguagem."
    ),
}

_EXTRA_SKILL_DIRS = {
    "coder": "skills/software-development/",
    "debugger": "skills/software-development/",
}


def load_agent_prompt(agent_type: str) -> str:
    """Load agent prompt from .opencode/agent/<file>.md.

    Strips YAML frontmatter (``---`` delimited) and returns only the body.
    Falls back to the static prompt on any error.
    """
    filename = _AGENT_PROMPT_MAP.get(agent_type, "general.md")
    path = _AGENT_PROMPT_DIR / filename

    try:
        content = path.read_text(encoding="utf-8")

        # Strip YAML frontmatter between --- markers
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].strip()
            else:
                body = content.strip()
        else:
            body = content.strip()

        # Append available skill references
        extra_dir = _EXTRA_SKILL_DIRS.get(agent_type)
        if extra_dir:
            skills_path = Path(__file__).resolve().parent.parent.parent / extra_dir
            if skills_path.is_dir():
                skill_names = sorted(
                    d.name for d in skills_path.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
                )
                if skill_names:
                    refs = "\n".join(f"  - {s}" for s in skill_names)
                    body += (
                        f"\n\n## Habilidades Disponiveis\n\n"
                        f"As seguintes skills estao disponiveis em '{extra_dir}':\n{refs}\n\n"
                        f"Consulte SKILL.md de cada uma para instrucoes detalhadas."
                    )

        return body

    except Exception:
        return _FALLBACK_PROMPTS.get(agent_type, _FALLBACK_PROMPTS["jarvis"])


# ── Agent Definitions ──────────────────────────────────────────────────

AGENT_DEFINITIONS = {
    "jarvis": {
        "name": "Jarvis",
        "description": "Assistente geral ultra-tecnológico",
        "routing": "personality",
        "system_prompt": _FALLBACK_PROMPTS["jarvis"],
    },
    "architect": {
        "name": "Architect",
        "description": "Arquiteto de software e sistemas",
        "routing": "reasoning",
        "system_prompt": _FALLBACK_PROMPTS["architect"],
    },
    "debugger": {
        "name": "Debugger",
        "description": "Debugger e solucionador de problemas",
        "routing": "coding",
        "system_prompt": _FALLBACK_PROMPTS["debugger"],
    },
    "planner": {
        "name": "Planner",
        "description": "Planejador de tarefas e projetos",
        "routing": "reasoning",
        "system_prompt": _FALLBACK_PROMPTS["planner"],
    },
    "coder": {
        "name": "Coder",
        "description": "Programador especialista",
        "routing": "coding",
        "system_prompt": _FALLBACK_PROMPTS["coder"],
    },
}


def get_agent_config(agent_type: str) -> dict:
    """Return agent config with dynamically loaded system_prompt."""
    if agent_type not in AGENT_DEFINITIONS:
        agent_type = "jarvis"

    config = dict(AGENT_DEFINITIONS[agent_type])  # shallow copy
    config["system_prompt"] = load_agent_prompt(agent_type)
    return config


def _load_agent_models() -> dict:
    """Load agent models from config.yaml."""
    try:
        import yaml
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("agent_models", {})
    except Exception:
        return {}


def resolve_model_for_task(task_type: str):
    """Resolve model for agent task, checking config.yaml agent_models first."""
    agent_models = _load_agent_models()
    
    # Check if agent has custom model in config.yaml
    if task_type in agent_models:
        model_name = agent_models[task_type]
        # Determine provider from model name
        if model_name.startswith("gpt-") or model_name.startswith("o1-"):
            return "openai", model_name
        elif model_name.startswith("claude-"):
            return "openclaude", model_name
        elif model_name.startswith("gemini-"):
            return "gemini", model_name
        elif model_name.startswith("deepseek-"):
            return "openrouter", model_name
        else:
            # Default to ollama for local models
            return "ollama", model_name
    
    # Fallback to hardcoded routing
    routing = MODEL_ROUTING.get(task_type, MODEL_ROUTING["personality"])
    return routing["provider"], routing["model"]

def classify_task(task_description: str) -> str:
    desc = task_description.lower()
    if any(w in desc for w in ["debug", "bug", "erro", "error", "crash", "exception", "stack", "trace"]):
        return "debugger"
    if any(w in desc for w in ["arquitet", "design", "estrutura", "architecture", "diagram", "system design"]):
        return "architect"
    if any(w in desc for w in ["plan", "plano", "planej", "roadmap", "tarefa", "task", "step"]):
        return "planner"
    if any(w in desc for w in ["cod", "implement", "function", "class", "api", "endpoint", "escreva", "crie"]):
        return "coder"
    return "jarvis"
