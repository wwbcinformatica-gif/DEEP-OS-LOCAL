"""
Skill Loader — carrega skills dos diretórios do projeto e injeta no system prompt.
Escaneia .opencode/skills/, skills/browser-harness/, skills/software-development/
"""
import re
from pathlib import Path
from functools import lru_cache

_BASE = Path(__file__).resolve().parent.parent.parent

_SKILL_DIRS = [
    _BASE / ".opencode" / "skills",
    _BASE / "skills" / "browser-harness",
    _BASE / "skills" / "software-development",
]

# Palavras-chave para matching de skills por categoria
_CATEGORY_KEYWORDS = {
    "web": ["web", "browser", "http", "url", "site", "navegador", "pesquisar", "buscar", "scraping"],
    "file": ["arquivo", "file", "pasta", "directory", "ler", "escrever", "editar", "deletar", "mover", "copiar"],
    "code": ["codigo", "code", "programar", "desenvolver", "python", "javascript", "typescript", "rust", "node"],
    "debug": ["debug", "erro", "error", "bug", "problema", "diagnostico", "investigar"],
    "test": ["teste", "test", "tdd", "unittest", "pytest", "verificar"],
    "deploy": ["deploy", "publicar", "servidor", "docker", "ci/cd", "producao"],
    "design": ["design", "ui", "ux", "frontend", "css", "layout", "interface", "visual"],
    "database": ["banco", "database", "sql", "sqlite", "mysql", "postgres", "mongodb"],
    "api": ["api", "rest", "graphql", "endpoint", "rotas", "fastapi"],
    "security": ["seguranca", "security", "vulnerabilidade", "permissao", "auth"],
    "performance": ["performance", "otimizacao", "lento", "rapido", "cache", "memoria"],
    "mobile": ["mobile", "android", "ios", "react native", "flutter"],
    "game": ["game", "jogo", "unity", "godot", "sprite", "2d", "3d"],
    "devops": ["devops", "docker", "kubernetes", "ci", "cd", "pipeline"],
    "ai": ["ia", "ai", "machine learning", "ml", "llm", "modelo", "treinar"],
    "voice": ["voz", "voice", "audio", "tts", "stt", "charon", "microfone"],
    "browser_automation": ["automacao", "automation", "click", "preencher", "scroll", "screenshot"],
    "system": ["sistema", "system", "computador", "windows", "linux", "macos", "configuracao"],
    "memory": ["memoria", "memory", "lembrar", "salvar", "persistir"],
    "planning": ["plano", "plan", "tarefa", "task", "organizar", "estruturar"],
}


def _parse_frontmatter(content: str) -> dict:
    """Extrai frontmatter YAML de um SKILL.md."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {"body": content.strip()}
    fm_text = match.group(1)
    body = content[match.end():].strip()
    meta = {}
    for line in fm_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            meta[key.strip()] = val.strip().strip('"').strip("'")
    meta["body"] = body
    return meta


@lru_cache(maxsize=1)
def _load_all_skills() -> dict:
    """Carrega todas as skills de todos os diretórios. Cacheado."""
    skills = {}
    for skill_dir in _SKILL_DIRS:
        if not skill_dir.exists():
            continue
        # Skills em subdiretórios (cada pasta tem SKILL.md)
        for child in sorted(skill_dir.iterdir()):
            if child.is_dir():
                skill_file = child / "SKILL.md"
                if skill_file.exists():
                    try:
                        content = skill_file.read_text(encoding="utf-8", errors="replace")
                        meta = _parse_frontmatter(content)
                        name = meta.get("name", child.name)
                        skills[name] = {
                            "name": name,
                            "description": meta.get("description", ""),
                            "body": meta.get("body", content)[:4000],  # limita a 4000 chars
                            "path": str(child),
                            "category": _classify_skill(name, meta.get("description", ""), meta.get("body", "")),
                        }
                    except Exception:
                        pass
            elif child.suffix == ".md" and child.name != "SKILL.md":
                # Skills soltas (ex: doc.md)
                try:
                    content = child.read_text(encoding="utf-8", errors="replace")
                    meta = _parse_frontmatter(content)
                    name = meta.get("name", child.stem)
                    if name not in skills:
                        skills[name] = {
                            "name": name,
                            "description": meta.get("description", ""),
                            "body": meta.get("body", content)[:4000],
                            "path": str(child),
                            "category": _classify_skill(name, meta.get("description", ""), meta.get("body", "")),
                        }
                except Exception:
                    pass
    return skills


def _classify_skill(name: str, description: str, body: str) -> str:
    """Classifica uma skill em uma categoria baseada em palavras-chave."""
    text = f"{name} {description} {body}".lower()
    scores = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


def get_relevant_skills(user_message: str, max_skills: int = 5, max_tokens: int = 3000) -> str:
    """
    Retorna as skills mais relevantes para a mensagem do usuário.
    Formato: bloco de texto para injetar no system prompt.
    """
    skills = _load_all_skills()
    if not skills:
        return ""

    msg_lower = user_message.lower()
    msg_words = set(msg_lower.split())

    # Pontua cada skill
    scored = []
    for name, skill in skills.items():
        score = 0

        # Match EXATO por nome da skill (maior peso)
        name_lower = name.lower().replace("-", " ").replace("_", " ")
        if name_lower in msg_lower or msg_lower in name_lower:
            score += 20

        # Match por palavras do nome
        name_words = set(name_lower.split())
        common_name = msg_words & name_words
        score += len(common_name) * 8

        # Match por categoria (apenas se palavras-chave específicas aparecerem)
        cat = skill["category"]
        cat_keywords = _CATEGORY_KEYWORDS.get(cat, [])
        cat_matches = sum(1 for kw in cat_keywords if kw in msg_lower and len(kw) > 3)
        score += cat_matches * 2

        # Match por descrição (penaliza terms muito genéricos)
        desc_lower = skill["description"].lower()
        desc_words = set(desc_lower.split())
        common_desc = msg_words & desc_words
        # Remove palavras genéricas da pontuação
        generic = {"use", "para", "com", "the", "and", "that", "this", "from", "with", "when"}
        specific_desc = common_desc - generic
        score += len(specific_desc) * 3

        # Bonus: se a skill é sobre o tópico exato da mensagem
        if any(kw in msg_lower for kw in ["navegador", "browser", "chrome", "edge", "firefox"]):
            if "web" in name_lower or "browser" in name_lower or "browse" in name_lower:
                score += 15
        if any(kw in msg_lower for kw in ["configuração", "settings", "sistema"]):
            if "system" in name_lower or "config" in name_lower:
                score += 15
        if any(kw in msg_lower for kw in ["código", "code", "programar", "python"]):
            if "code" in name_lower or "python" in name_lower or "develop" in name_lower:
                score += 15

        if score > 3:  # threshold mínimo
            scored.append((score, name, skill))

    # Ordena por pontuação e pega as top N
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_skills]

    if not top:
        return ""

    # Monta o bloco de texto (resumido para não explode o contexto)
    parts = ["--- SKILLS RELEVANTES DISPONIVEIS ---"]
    total_len = 0
    for score, name, skill in top:
        # Pega apenas os primeiros 500 chars do body (resumo)
        body_summary = skill["body"][:500].split('\n')[0:5]  # primeiras 5 linhas
        body_text = '\n'.join(body_summary)
        block = f"\n## {name}\n{skill['description']}\n{body_text}"
        if total_len + len(block) > max_tokens * 4:  # ~4 chars por token
            break
        parts.append(block)
        total_len += len(block)

    return "\n".join(parts)


def list_all_skills() -> list:
    """Retorna lista de todas as skills disponíveis."""
    skills = _load_all_skills()
    return [{"name": s["name"], "description": s["description"], "category": s["category"]}
            for s in skills.values()]


def get_skill_count() -> int:
    """Retorna o total de skills carregadas."""
    return len(_load_all_skills())


# Para uso no voice_ws.py (Charon)
def get_charon_skills_context(user_message: str) -> str:
    """Retorna contexto de skills otimizado para o Charon (mais curto)."""
    return get_relevant_skills(user_message, max_skills=3, max_tokens=1000)


# Para uso no chat.py (Ollama/llamacpp/cloud)
def get_chat_skills_context(user_message: str, provider: str = "cloud") -> str:
    """Retorna contexto de skills otimizado para o chat."""
    if provider in ("ollama", "llamacpp"):
        # Modelos locais: menos skills, menos tokens
        return get_relevant_skills(user_message, max_skills=3, max_tokens=1500)
    else:
        # Modelos cloud: mais skills
        return get_relevant_skills(user_message, max_skills=5, max_tokens=3000)
