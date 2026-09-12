import asyncio
import json
import re
import traceback
import uuid
from typing import Any
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import get_base_dir
from core.lifecycle import LifecycleConfig, run_lifecycle
from core.message_queue import message_queue, QueuedMessage
from core.llm_native import (
    build_conversation_messages,
    build_user_content,
    complete_chat,
    complete_chat_with_tools,
    stream_chat,
    stream_chat_with_tools,
)
from core.models import Message
from core.prompts import MOOD_INSTRUCTIONS, TOOL_SYSTEM_PROMPT, PLANNING_PROTOCOL_REMINDER, build_compact_tool_prompt
from core.rag import get_rag_context
from core.security import validate_message_length
from database.connection import get_conn
from memory.reflection import save_llm_reflection
from tools.executor import execute_tool
from tools.function_defs import TOOLS

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# ── Tools filtradas para modelos locais (reduzir tokens) ────────────────────────
# Modelos locais tem contexto limitado, entao enviamos apenas as tools essenciais
LOCAL_TOOLS = [t for t in TOOLS if t["function"]["name"] in [
    # Arquivos e codigo
    "read", "write", "bash", "explorer", "search", "glob",
    "create_directory", "delete", "rename", "file_edit",
    "read_document", "execute_python", "find_file",
    # Web
    "web_search", "web_fetch",
    # Tarefas
    "task_create", "task_update", "task_list",
    # Sistema e apps
    "open_app", "close_app", "system_status", "computer_settings",
    # Midia
    "media_play",
    # Memoria
    "memory_write", "memory_read", "memory_list",
    # Ferramentas
    "tool_search", "monitor_dashboard", "reminder",
]]

# JSON interno que o modelo gera como parte do protocolo de checklist/planejamento
_INTERNAL_JSON_RE = re.compile(
    r'\{"type"\s*:\s*"(task_plan|task_progress)"[^}]*\}'
)

def strip_internal_json(text: str) -> str:
    """Remove JSON de protocolo interno."""
    if not text:
        return text
    # Remove JSON de protocolo (task_plan, task_progress)
    cleaned = _INTERNAL_JSON_RE.sub("", text)
    cleaned = cleaned.strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned

def assess_tool_risk(tool_name: str, params: dict) -> dict:
    """Analise autonoma de risco. Retorna {needs_confirm, risk_level, reason}."""
    risk_level = "safe"
    needs_confirm = False
    reason = ""

    if tool_name == "delete":
        path = params.get("path", "")
        if any(kw in path.lower() for kw in ["node_modules", ".git", "venv", "system", "windows", "program"]):
            risk_level = "critical"
            needs_confirm = True
            reason = f"Exclusao de diretorio critico detectado: {path}"
        elif path:
            risk_level = "high"
            needs_confirm = True
            reason = f"Exclusao de arquivo/pasta: {path}"

    elif tool_name == "bash":
        cmd = params.get("command", "").lower().strip()
        dangerous_patterns = [
            "rm -rf", "rmdir /s", "del /f /s /q", "format ", "diskpart",
            "shutdown", "reboot", "net user", "net localgroup",
            "reg delete", "reg add", "sc delete", "taskkill /f",
            "chmod 777", "chown", "chattr", ":(){ :|:&", "dd if=",
            "mkfs", "> /dev/sda", "wget", "curl.*|.*sh",
            "pip install --upgrade pip", "npm install -g",
            "winget install", "choco install",
        ]
        if any(p in cmd for p in dangerous_patterns):
            risk_level = "critical"
            needs_confirm = True
            reason = f"Comando bash de alto risco detectado: {cmd[:80]}"
        elif any(kw in cmd for kw in ["rm ", "del ", "rmdir", "kill", "stop", "disable", "remove"]):
            risk_level = "high"
            needs_confirm = True
            reason = f"Comando bash potencialmente destrutivo: {cmd[:80]}"

    elif tool_name == "rename":
        risk_level = "medium"
        needs_confirm = True
        reason = f"Renomear: {params.get('old_path', '?')} -> {params.get('new_path', '?')}"

    elif tool_name == "install_package":
        pkg = params.get("package", "")
        if any(kw in pkg.lower() for kw in ["--global", "-g", "sudo", "system"]):
            risk_level = "high"
            needs_confirm = True
            reason = f"Instalacao global/sistema: {pkg}"

    return {"needs_confirm": needs_confirm, "risk_level": risk_level, "reason": reason}


URGENT_KEYWORDS = [
    "para", "parar", "stop", "cancela", "cancelar", "aborta", "abortar",
    "espera", "esperar", "aguarda", "aguardar",
    "urgente", "urgencia", "rapido", "rapida", "agora", "imediato", "imediatamente",
    "socorro", "ajuda", "erro", "bug", "crash", "travou", "travando",
    "cancele", "interrompe", "interromper",
    "fogo", "emergencia", "emergência",
    "nao faca", "não faça", "nao execute", "não execute", "pare de",
    "esquece", "deixa", "deixa pra la", "deixa pra lá",
    "cancela isso", "cancela tudo", "para tudo",
]

NORMAL_KEYWORDS = [
    "depois", "quando terminar", "no final", "no fim", "pode esperar",
    "nao urgente", "não urgente", "sem pressa", "calma",
    "adicione", "tambem", "lembre", "anote", "guarde",
    "mais tarde", "depois de", "apos",
]


async def assess_urgency(new_message: str, current_task: str = "") -> dict:
    """
    Avalia se uma mensagem nova e urgente (deve interromper) ou normal (pode esperar).
    Usa heuristica rapida primeiro; se incerto, usa LLM para decidir.
    Retorna {urgent: bool, reason: str, method: str}.
    """
    msg_lower = new_message.lower().strip()

    # 1. Heuristica rapida: palavras explicitas de parada/urgencia
    for kw in URGENT_KEYWORDS:
        if kw in msg_lower:
            return {"urgent": True, "reason": f"Palavra de urgencia detectada: '{kw}'", "method": "heuristic"}

    # 2. Heuristica rapida: palavras explicitas de "pode esperar"
    for kw in NORMAL_KEYWORDS:
        if kw in msg_lower:
            return {"urgent": False, "reason": f"Palavra de baixa prioridade: '{kw}'", "method": "heuristic"}

    # 3. Mensagens muito curtas (<15 chars) geralmente sao comandos urgentes
    if len(msg_lower) < 15:
        return {"urgent": True, "reason": "Mensagem curta — provavel comando rapido", "method": "heuristic"}

    # 4. Mensagens longas (>150 chars) geralmente sao detalhamento/continuacao
    if len(msg_lower) > 150:
        return {"urgent": False, "reason": "Mensagem longa — provavel detalhamento ou continuacao", "method": "heuristic"}

    # 5. Se ainda incerto, usa LLM para classificar (rapido, 1 chamada)
    try:
        urgency_prompt = [
            {"role": "system", "content": (
                "Voce e um classificador de urgencia. Avalie se a mensagem do usuario deve "
                "INTERROMPER a tarefa atual do assistente ou se PODE ESPERAR ate o final.\n\n"
                "Responda APENAS com 'URGENT' ou 'NORMAL' seguido de uma breve justificativa.\n"
                "URGENT: erros, pedidos de parada, correcoes criticas, comandos curtos, perguntas diretas.\n"
                "NORMAL: detalhamentos, informacoes adicionais, pedidos nao relacionados a tarefa atual."
            )},
            {"role": "user", "content": (
                f"Tarefa atual em execucao: {current_task[:200] if current_task else '(desconhecida)'}\n\n"
                f"Nova mensagem do usuario: {new_message[:500]}\n\n"
                f"E URGENT ou NORMAL?"
            )},
        ]
        from core.llm_native import complete_chat
        response = await complete_chat("mimo", "mimo-v2.5", urgency_prompt, 0.3, api_key="")
        response_upper = response.upper().strip()
        if response_upper.startswith("URGENT"):
            return {"urgent": True, "reason": f"LLM: {response[:100]}", "method": "llm"}
        else:
            return {"urgent": False, "reason": f"LLM: {response[:100]}", "method": "llm"}
    except Exception as e:
        # Em caso de erro no LLM, default: normal (nao interrompe)
        return {"urgent": False, "reason": f"LLM falhou ({e}), default: normal", "method": "fallback"}


def parse_slash_command(text: str) -> dict | None:
    """Parse /comando, +comando, ou palavras-chave soltas. Retorna {command, args} ou None."""
    t = text.strip()
    if not t:
        return None
    
    # Com prefixo / ou +
    prefix = t[0] if t[0] in ("/", "+") else None
    if prefix:
        parts = t[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        valid_commands = {
            "goal", "run", "clear", "help", "status", "stop", "doctor",
            "model", "provider", "theme", "voice", "debug",
        }
        if cmd in valid_commands:
            return {"command": cmd, "args": args}
        return None
    
    # Sem prefixo — reconhece palavras-chave isoladas
    t_lower = t.lower()
    standalone_commands = {
        "doctor": "doctor",
        "diagnostico": "doctor",
        "diagnóstico": "doctor",
        "diagnostico completo": "doctor",
    }
    for phrase, cmd in standalone_commands.items():
        if t_lower == phrase:
            return {"command": cmd, "args": ""}
    
    return None


# Comandos de voz em portugues que mapeiam para acoes do sistema
VOICE_ACTION_MAP = {
    "novo contexto": "clear",
    "limpar contexto": "clear",
    "limpa contexto": "clear",
    "novo chat": "clear",
    "limpar chat": "clear",
    "limpa tudo": "clear",
    "parar": "stop",
    "para": "stop",
    "cancelar": "stop",
    "cancela": "stop",
    "status": "status",
    "ajuda": "help",
    "help": "help",
    "diagnostico": "doctor",
    "diagnóstico": "doctor",
    "doctor": "doctor",
    "fechar arquivo": "close_file",
    "fechar documento": "close_file",
    "fechar video": "close_file",
    "fechar musica": "media_stop",
    "fechar música": "media_stop",
    "fechar a musica": "media_stop",
    "fechar a música": "media_stop",
    "parar musica": "media_stop",
    "parar música": "media_stop",
    "pausar musica": "media_pause",
    "pausar música": "media_pause",
    "pausa": "media_pause",
    "pausa a musica": "media_pause",
    "retomar": "media_pause",
    "continuar musica": "media_pause",
    "continuar música": "media_pause",
    "tocar musica": "media_resume",
    "tocar música": "media_resume",
    "proxima musica": "media_next",
    "próxima música": "media_next",
    "proximo": "media_next",
    "próximo": "media_next",
    "musica anterior": "media_prev",
    "música anterior": "media_prev",
    "anterior": "media_prev",
    "fechar tudo": "close_all",
    "tocar no media": "media_internal",
    "tocar no MEDIA": "media_internal",
    "player interno": "media_internal",
    "abrir no media": "media_internal",
    "tocar no windows media": "media_external",
    "tocar no windows": "media_external",
    "abrir no windows media": "media_external",
    "abrir no player do windows": "media_external",
    "tocar no sistema": "media_external",
    "abrir no sistema": "media_external",
}


def parse_voice_action(text: str) -> dict | None:
    """Detecta acoes por voz em portugues. Retorna {command, args} ou None."""
    t = text.strip().lower()
    for phrase, action in VOICE_ACTION_MAP.items():
        if t == phrase or t.startswith(phrase):
            return {"command": action, "args": t.replace(phrase, "").strip()}
    return None


def parse_at_mentions(text: str) -> dict:
    """Parse @mencoes. Retorna {agents: [...], skills: [...], clean_text: str}."""
    import re
    agents = []
    skills = []
    clean = text

    # Carrega agentes e skills do .opencode dinamicamente
    from core.opencode_loader import load_opencode_agents, load_opencode_skills
    oc_agents = set(load_opencode_agents().keys())
    oc_skills = set(load_opencode_skills().keys())

    known_agents = {"coder", "writer", "helper", "planner", "reviewer", "debugger", "architect", "analyst",
                    "mimo", "general", "explore", "gemini"}
    known_agents |= oc_agents

    known_skills = {
        "web_search", "file_picker", "terminal_run", "code_review",
        "test_runner", "doc_generator", "refactor", "deploy",
        "memory", "brain", "plan", "explore",
    }
    known_skills |= oc_skills

    for match in re.finditer(r'@(\w[\w-]*)', text):
        tag = match.group(1).lower()
        if tag in known_agents:
            agents.append(tag)
        elif tag in known_skills:
            skills.append(tag)

    return {"agents": agents, "skills": skills, "clean_text": clean}

TASK_KEYWORDS = [
    "crie", "criar", "cria", "criarei", "criou",
    "faca", "fazer", "farei",
    "gere", "gerar", "gerarei",
    "execute", "executar", "executarei",
    "rode", "rodar", "roda",
    "compile", "compilar",
    "inicie", "iniciar", "inicia",
    "instale", "instalar", "instala",
    "baixe", "baixar", "baixa",
    "clica", "clique", "click",
    "abre", "abra", "abrir",
    "mostra", "mostre", "mostrar",
    "veja", "ver", "ve", "exibe", "exiba",
    "navega", "navegue", "navegar",
    "acessa", "acesse", "acessar",
    "entra", "entre", "entrar",
    "lista", "liste", "listar",
    "leia", "ler", "le",
    "procura", "procure", "procurar",
    "busca", "busque", "buscar",
    "encontra", "encontre", "encontrar",
    "edita", "edite", "editar",
    "modifica", "modifique", "modificar",
    "renomeie", "renomear",
    "move", "mover",
    "copia", "copie", "copiar",
    "apaga", "apague", "apagar",
    "deleta", "delete", "deletar",
    "exclui", "exclua", "excluir",
    "remove", "remova", "remover",
    "desenvolva", "desenvolver",
    "implemente", "implementar",
    "configure", "configurar",
    "programa", "codigo", "codigo", "script",
    "quero criar", "preciso criar",
    "quero que voce", "voce pode",
    "crie um arquivo", "crie uma pasta",
    "criar arquivo", "criar pasta",
    "adicionar", "adicione", "coloque", "insira",
    "salve", "salvar", "grave", "gravar",
    "pesquise", "pesquisar", "investigue",
    "teste", "testar", "debug", "debugue",
    "analise", "analisar", "analisa",
    "formate", "formatar", "organize",
    "converta", "converter",
    "atualize", "atualizar",
    "remova", "remove",
    "substitua", "substituir",
    "mescle", "mesclar",
    "baixe", "baixar", "download",
    "upload", "envie", "enviar",
    "verifique", "verificar", "verifica",
    "examine", "examinar",
    "inspecione", "inspecionar",
    "identifique", "identificar",
    "diagnostique", "diagnosticar",
    "monitore", "monitorar",
    "mapeie", "mapear",
    "explore", "explorar",
    "investigue", "investigar",
]

NO_TOOL_MODELS = {"llava", "bakllava", "moondream", "minicpm-v", "qwen-vl", "qwen2-vl", "qwen-vl-plus", "qwen2.5-vl", "qwen2.5vl"}

# Modelos cloud que NAO suportam tool calling
CLOUD_NO_TOOL_MODELS = {
    "nemotron-3-super-free",
    "gpt-5.1-codex", "nemotron-3-super",
    "mixtral-8x7b-32768",
}


def supports_tools(provider: str, model: str) -> bool:
    if provider == "ollama":
        model_lower = model.split(":")[0].lower()
        for ntm in NO_TOOL_MODELS:
            if ntm in model_lower:
                return False
        # Vision models (vl, vision, gemma4) nao suportam tool calling
        if re.search(r'(vl|vision|gemma4)', model_lower):
            return False
        return True
    # Cloud models: verifica lista explicita
    model_clean = model.split("/")[-1].split(":")[0].lower()
    for ntm in CLOUD_NO_TOOL_MODELS:
        if ntm in model_clean:
            return False
    return True


def is_task_message(text: str) -> bool:
    t = text.strip().lower()
    starters = [
        "crie", "cria", "faca", "gere", "execute",
        "quero", "preciso", "clica", "clique", "abre", "abra",
        "mostra", "mostre", "veja", "lista", "liste", "leia",
        "busca", "busque", "encontra", "edita", "edite",
        "apaga", "apague", "deleta", "delete", "exclui",
        "rode", "roda", "compile",
        "adicione", "adicionar", "coloque", "salve", "salvar",
        "pesquise", "pesquisa", "pesquisar", "teste", "analise", "converta",
        "verifique", "verifica", "examine", "explore",
        "identifique", "inspecione", "mapeie", "diagnostique",
        "acesse", "navegue", "va para", "vou para",
        "pode fazer", "faca uma pesquisa", "fazer uma pesquisa",
        "pode pesquisar", "pode buscar", "pode procurar",
    ]
    if any(t.startswith(k) for k in starters):
        return True
    # Detecta comandos de sistema de arquivos (C:\, D:\, caminhos)
    if any(x in t for x in ["c:", "d:", "unidade", "raiz", "diretorio", "pasta", "acessar"]):
        return True
    for kw in TASK_KEYWORDS:
        if kw in t:
            return True
    return False


PROJECT_CREATION_KEYWORDS = [
    "crie um projeto", "criar um projeto", "cria um projeto",
    "crie o projeto", "criar o projeto", "cria o projeto",
    "crie um novo projeto", "criar um novo projeto",
    "crie um app", "criar um app", "cria um app",
    "crie uma aplicacao", "criar uma aplicacao",
    "crie um sistema", "criar um sistema",
    "crie uma api", "criar uma api", "cria uma api",
    "crie uma api rest", "criar uma api rest",
    "crie um backend", "criar um backend",
    "crie um frontend", "criar um frontend",
    "crie um site", "criar um site",
    "crie uma pagina", "criar uma pagina",
    "gere um projeto", "gerar um projeto",
    "gere uma api", "gerar uma api",
    "desenvolva um projeto", "desenvolver um projeto",
    "desenvolva uma api", "desenvolver uma api",
    "faca um projeto", "fazer um projeto",
    "faca uma api", "fazer uma api",
    "quero criar um projeto", "preciso criar um projeto",
    "quero criar uma api", "preciso criar uma api",
    "quero desenvolver um", "preciso desenvolver um",
    "create a project", "create project", "create new project",
    "create an app", "create a app", "create application",
    "create an api", "create a api", "create api",
    "build a project", "build project", "build an app",
    "build an api", "build api",
    "scaffold a project", "scaffold project",
    "new project", "novo projeto",
]

def is_project_creation_request(text: str) -> bool:
    t = text.strip().lower()
    for kw in PROJECT_CREATION_KEYWORDS:
        if kw in t:
            return True
    return False


def extract_tool(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None

    # Helper: normalize any tool format to {"tool": name, "params": {...}}
    def normalize(parsed: dict) -> dict | None:
        if not isinstance(parsed, dict):
            return None
        # Old format: {"tool": "name", "params": {...}}
        if "tool" in parsed:
            return parsed
        # OpenAI format: {"name": "func", "arguments": {...}} or {"name": "func", "arguments": "..."}
        if "name" in parsed:
            args = parsed.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            return {"tool": parsed["name"], "params": args}
        # OpenAI tool_calls array format: [{"function": {"name": "...", "arguments": "..."}}]
        if isinstance(parsed, list) and len(parsed) > 0:
            item = parsed[0]
            if isinstance(item, dict) and "function" in item:
                fn = item["function"]
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                return {"tool": fn.get("name", ""), "params": args}
        return None

    # 1. Try JSON code blocks: ```json ... ```
    for m in re.finditer(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL):
        try:
            parsed = json.loads(m.group(1).strip())
            result = normalize(parsed)
            if result:
                return result
        except json.JSONDecodeError:
            pass

    # 2. Find JSON by brace counting
    i = 0
    while i < len(text):
        idx = text.find('{', i)
        if idx == -1:
            break
        depth = 0
        j = idx
        while j < len(text):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[idx:j+1])
                        result = normalize(parsed)
                        if result:
                            return result
                    except json.JSONDecodeError:
                        pass
                    break
            j += 1
        i = idx + 1

    return None


def _load_config_system_prompt() -> str:
    """Carrega system_prompt do config.yaml como fallback."""
    try:
        import yaml
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return (data.get("agent") or {}).get("system_prompt", "")
    except Exception:
        return ""


_identity_cache = {}
_identity_cache_time = 0

def _load_identity() -> dict:
    """Carrega identity do config.yaml com cache."""
    global _identity_cache, _identity_cache_time
    import time
    now = time.time()
    if _identity_cache and (now - _identity_cache_time) < 5:
        return _identity_cache
    try:
        import yaml
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        result = data.get("identity", {})
        _identity_cache = result
        _identity_cache_time = now
        return result
    except Exception:
        return {}


def build_system_prompt(msg: Message) -> str:
    identity = _load_identity()
    assistant_name = identity.get("assistant_name", "DEEP-OS") or "DEEP-OS"
    user_name = identity.get("user_name", "") or "usuario"
    
    # Identidade sempre vai no inicio - separada do instruction
    identity_block = (
        f"═══════════════════════════════════════════════════════\n"
        f" IDENTIDADE OBRIGATORIA - NAO ALTERE ESTE BLOCO\n"
        f"═══════════════════════════════════════════════════════\n"
        f"Seu nome e EXATAMENTE: {assistant_name}\n"
        f"Nome do usuario: {user_name}\n\n"
        f"REGRAS DE IDENTIDADE (SEMPRE SIGA):\n"
        f"1. Quando perguntado 'qual seu nome', 'quem voce e', etc: responda '{assistant_name}'\n"
        f"2. Chame o usuario por '{user_name}' nas saudacoes e quando apropriado\n"
        f"3. NUNCA diga que voce e 'OpenCode', 'DEEP-OS', 'Jarvis' ou outro nome\n"
        f"4. NUNCA diga 'sou um assistente de IA generico' - voce e {assistant_name}\n"
        f"5. SEMPRE use '{assistant_name}' quando se referir a si mesmo\n"
        f"═══════════════════════════════════════════════════════\n\n"
    )
    
    instruction = msg.system_prompt or _load_config_system_prompt() or MOOD_INSTRUCTIONS.get(msg.mood, MOOD_INSTRUCTIONS["opencode"])
    
    user_root = msg.root.strip() if msg.root else ""
    user_path = msg.path.strip() if msg.path else ""
    if user_root:
        escaped_root = user_root.replace("\\", "\\\\")
        escaped_path = user_path.replace("\\", "\\\\") if user_path else ""
        root_info = f"{escaped_root}{'/' + escaped_path if escaped_path else ''}"
    else:
        from core.config import get_base_dir
        root_info = str(get_base_dir()).replace("\\", "\\\\")

    q = msg.user.strip().lower()
    is_greeting = (
        len(q) < 20
        and not any(w in q for w in ["criar", "fazer", "ler", "buscar", "executar",
            "arquivo", "pasta", "codigo", "mostrar", "explorar", "verificar",
            "analisar", "crie", "liste", "abra", "abrir", "leia", "procure",
            "ferramenta", "sistema", "projeto", "trocar", "mudar", "alterar"])
        and not any(c in q for c in [".py", ".ts", ".js", ".json", ".md", ".html"])
    )

    if is_greeting:
        return identity_block + instruction

    from core.prompts import TASK_CHECKLIST_PROMPT
    prompt_base = TOOL_SYSTEM_PROMPT.format(
        root_info=root_info,
        personality=instruction,
        checklist_prompt=TASK_CHECKLIST_PROMPT,
    )

    if msg.system_prompt:
        prompt_base = msg.system_prompt + "\n\n" + prompt_base

    prompt_base = identity_block + prompt_base
    prompt_base += PLANNING_PROTOCOL_REMINDER

    # Injeta skills relevantes
    from core.skill_loader import get_chat_skills_context
    provider = msg.provider if hasattr(msg, 'provider') else 'cloud'
    skills_ctx = get_chat_skills_context(msg.user, provider)
    if skills_ctx:
        prompt_base += "\n\n" + skills_ctx

    return prompt_base


@router.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, msg: Message):
    if not validate_message_length(msg.user):
        raise HTTPException(400, "Mensagem muito longa")
    if msg.user.startswith("/approve-tool") or msg.user.startswith("/reject-tool"):
        msg.tool_confirmed = True
        msg.user = "continue"

    # Detecta comandos de voz em portugues
    voice_cmd = parse_voice_action(msg.user)
    if voice_cmd and voice_cmd["command"] in ("clear", "stop", "help", "status", "doctor"):
        slash_cmd = {"command": voice_cmd["command"], "args": voice_cmd["args"]}
        events = []
        async for event in handle_slash_command(slash_cmd, msg):
            events.append(json.loads(event))
        answer = next((e.get("answer", "") for e in events if e.get("type") == "done"), "")
        return {"answer": answer, "type": "slash_command"}

    # Comandos de midia por voz
    if voice_cmd and voice_cmd["command"] == "media_stop":
        return {"answer": "Musica parada.", "type": "voice_action", "action": "media_stop"}

    if voice_cmd and voice_cmd["command"] == "media_pause":
        return {"answer": "Musica pausada. Diga 'retomar' para continuar.", "type": "voice_action", "action": "media_pause"}

    if voice_cmd and voice_cmd["command"] == "media_resume":
        return {"answer": "Retomando musica...", "type": "voice_action", "action": "media_pause"}

    if voice_cmd and voice_cmd["command"] == "media_next":
        return {"answer": "Proxima musica.", "type": "voice_action", "action": "media_next"}

    if voice_cmd and voice_cmd["command"] == "media_prev":
        return {"answer": "Musica anterior.", "type": "voice_action", "action": "media_prev"}

    # Fechar arquivo/musica por voz
    if voice_cmd and voice_cmd["command"] == "close_file":
        from tools.executor import execute_tool
        result = await execute_tool("close_app", {"file_path": voice_cmd["args"]})
        return {"answer": f"Arquivo fechado: {result}", "type": "voice_action"}

    if voice_cmd and voice_cmd["command"] == "close_all":
        from tools.executor import execute_tool
        await execute_tool("close_app", {"process_name": "notepad.exe"})
        await execute_tool("close_app", {"process_name": "WINWORD.EXE"})
        return {"answer": "Arquivos fechados.", "type": "voice_action"}

    slash_cmd = parse_slash_command(msg.user)
    if slash_cmd:
        events = []
        async for event in handle_slash_command(slash_cmd, msg):
            events.append(json.loads(event))
        answer = next((e.get("answer", "") for e in events if e.get("type") == "done"), "")
        return {"answer": answer, "type": "slash_command"}
    mentions = parse_at_mentions(msg.user)
    if mentions["agents"] or mentions["skills"]:
        msg = inject_mention_context(msg, mentions)
    if is_task_message(msg.user):
        return await handle_task(msg)
    return await handle_question(msg)


# ─── Persistencia de tarefas (continue) ────────────────────────────────

def save_task_state(task_id: str, messages: list, tool_logs: list,
                    system_prompt: str, step: int, max_steps: int, context: str = ""):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT OR REPLACE INTO task_state
            (task_id, messages, tool_logs, system_prompt, step, max_steps, context, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (task_id, json.dumps(messages), json.dumps(tool_logs),
             system_prompt, step, max_steps, context))
        conn.commit()
        conn.close()
    except Exception:
        pass

def load_task_state(task_id: str) -> dict | None:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM task_state WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "messages": json.loads(row["messages"]),
                "tool_logs": json.loads(row["tool_logs"]),
                "system_prompt": row["system_prompt"],
                "step": row["step"],
                "max_steps": row["max_steps"],
                "context": row["context"],
            }
        return None
    except Exception:
        return None

def delete_task_state(task_id: str):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM task_state WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass

# ─── Sistema de memoria neural (aprendizado) ───────────────────────────

def save_brain_memory(key: str, content: str, category: str = "general", importance: float = 0.5):
    """Salva uma memoria de longo prazo (aprendizado neural)."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT OR REPLACE INTO brain_memories
            (key, content, category, importance, access_count, updated_at)
            VALUES (?, ?, ?, ?, COALESCE((SELECT access_count FROM brain_memories WHERE key = ?), 0) + 1, CURRENT_TIMESTAMP)""",
            (key, content, category, importance, key))
        conn.commit()
        conn.close()
    except Exception:
        pass

def load_brain_memories(category: str = "", limit: int = 20) -> list:
    """Carrega memorias de longo prazo, ordenadas por importancia + acesso."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        if category:
            cur.execute("""SELECT * FROM brain_memories WHERE category = ?
                ORDER BY importance DESC, access_count DESC LIMIT ?""", (category, limit))
        else:
            cur.execute("""SELECT * FROM brain_memories
                ORDER BY importance DESC, access_count DESC LIMIT ?""", (limit,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def learn_from_interaction(question: str, answer: str, tool_logs: list):
    """Apos cada interacao, extrai aprendizado e salva na memoria neural."""
    try:
        # Extrai ferramentas usadas como aprendizado de capacidade
        tools_used = set()
        for log in tool_logs:
            if isinstance(log, dict) and log.get("tool"):
                tools_used.add(log["tool"])
        if tools_used:
            save_brain_memory(
                key=f"tool_capability_{abs(hash(str(tools_used)))}",
                content=f"Ferramentas usadas juntas: {', '.join(sorted(tools_used))}",
                category="tool_patterns",
                importance=0.3
            )

        # Aprende sobre o projeto (palavras-chave)
        keywords = [w for w in question.lower().split() if len(w) > 4]
        if keywords:
            top_kw = max(set(keywords), key=keywords.count)
            save_brain_memory(
                key=f"keyword_{top_kw}",
                content=f"O usuario perguntou sobre '{top_kw}' e recebeu resposta sobre {answer[:100]}",
                category="user_interests",
                importance=0.2
            )
    except Exception:
        pass



PATH_PATTERN = re.compile(
    r'(?:em|na|no|para|dentro de|dentro da|em:|para:)\s*([a-zA-Z]:[\\/](?:[^,\s]*))',
    re.IGNORECASE
)

def _extract_target_dir(user_text: str, msg_root: str) -> str:
    match = PATH_PATTERN.search(user_text)
    if match:
        return match.group(1).rstrip("\\/")
    return msg_root or ""


async def _handle_project_generation(msg: Message) -> AsyncGenerator[dict, None]:
    from core.config import get_base_dir
    from generator.planner import ProjectPlanner
    from generator.scaffolder import ProjectScaffolder

    GENERATED_DIR = get_base_dir() / "generated"
    GENERATED_DIR.mkdir(exist_ok=True)

    user_text = msg.user.strip()
    provider = msg.provider
    model = msg.model
    api_key = msg.api_key

    try:
        target_root = _extract_target_dir(user_text, msg.root)
        if target_root:
            target_dir = Path(target_root)
        else:
            target_dir = GENERATED_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        yield {"type": "thinking", "content": "Planejando projeto..."}
        planner = ProjectPlanner(provider, model, api_key)
        plan = await planner.plan(user_text)

        yield {"type": "thinking", "content": f"Projeto: {plan.project_name} ({plan.language})"}
        yield {"type": "tool_start", "tool": "generate", "params": {"project": plan.project_name, "target": str(target_dir)}}

        project_dir = target_dir / plan.project_name
        scaffolder = ProjectScaffolder(str(target_dir), provider, model, api_key)
        scaffold_result = await scaffolder.scaffold(plan)

        for f in scaffold_result.get("files", []):
            yield {"type": "tool_start", "tool": "write", "params": {"path": f["path"]}}
            yield {"type": "tool_end", "tool": "write", "result": {"path": f["path"], "status": f.get("status", "created")}}

        if scaffold_result.get("errors"):
            for err in scaffold_result["errors"]:
                yield {"type": "thinking", "content": f"[Aviso] {err}"}

        total = len(scaffold_result.get("files", []))
        answer = (
            f"Projeto **{plan.project_name}** criado com sucesso!\n\n"
            f"- **Linguagem:** {plan.language}\n"
            f"- **Arquivos criados:** {total}\n"
            f"- **Diretório:** `{project_dir}`\n"
        )
        if plan.run_command:
            answer += f"- **Executar:** `{plan.run_command}`\n"

        yield {"type": "tool_end", "tool": "generate", "result": {"project": plan.project_name, "path": str(project_dir), "files": total}}
        yield {"type": "done", "answer": answer}
    except Exception as e:
        import traceback as _tb
        _tb.print_exc()
        yield {"type": "thinking", "content": f"[Erro] {str(e)[:200]}"}
        yield {"type": "done", "answer": f"Não foi possível criar o projeto. {str(e)[:200]}"}


async def handle_task_stream(msg: Message) -> AsyncGenerator[dict, None]:
    try:
        # ─── Suporte a continue: carrega estado salvo ────────────────
        task_id = msg.task_id or ""
        if not task_id:
            task_id = f"task_{uuid.uuid4().hex[:12]}"

        saved = load_task_state(task_id) if msg.task_id else None

        # ─── Project creation: redirect to generator ────────────────
        if is_project_creation_request(msg.user) and not saved:
            async for event in _handle_project_generation(msg):
                yield event
            return

        if saved:
            messages = saved["messages"]
            tool_logs = saved["tool_logs"]
            start_step = saved["step"]
            max_steps = saved.get("max_steps", 100)
            system_prompt = saved["system_prompt"]
            if not msg.tool_confirmed:
                messages.append({
                    "role": "user",
                    "content": "[SISTEMA] O usuario REJEITOU a execucao desta ferramenta. Prossiga SEM executar esta acao. Escolha uma alternativa ou pule esta etapa.",
                })
            yield {"type": "thinking", "content": f"[Continuando tarefa {task_id} do passo {start_step + 1}]"}
        else:
            system_prompt = build_system_prompt(msg)
            # Se o modelo nao suporta tool calling, ajusta instrucoes mas MANTER media_play
            if not supports_tools(msg.provider, msg.model):
                system_prompt = system_prompt.replace(
                    "IMPORTANTE: NUNCA diga que nao tem acesso. Voce TEM as ferramentas:",
                    "IMPORTANTE: Responda em texto descrevendo o que voce encontrou."
                )
            tool_logs = []
            start_step = 0
            max_steps = msg.max_steps or 100
            history_pairs = []
            
            # SEMPRE carregar historico completo do banco primeiro
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT question, answer FROM history ORDER BY id DESC LIMIT 50")
                for row in reversed(list(cur.fetchall())):
                    ans = row["answer"]
                    if not ans:
                        continue
                    try:
                        parsed_ans = json.loads(ans)
                        if isinstance(parsed_ans, dict) and ("tool" in parsed_ans or "name" in parsed_ans):
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass
                    history_pairs.append({"role": "user", "content": row["question"]})
                    history_pairs.append({"role": "assistant", "content": ans[:8000]})
                conn.close()
            except Exception:
                pass

            # Se tem contexto anterior (correcao/fila), adicionar ao final
            if msg.previous_context:
                for ctx_msg in msg.previous_context:
                    role = ctx_msg.get("from", "user")
                    content = ctx_msg.get("text", "")
                    if role == "user":
                        history_pairs.append({"role": "user", "content": content})
                    elif role == "bot":
                        history_pairs.append({"role": "assistant", "content": content[:8000]})
            
            messages = [{"role": "system", "content": system_prompt}]
            for hp in history_pairs:
                messages.append(hp)
            messages.append({"role": "user", "content": build_user_content(msg.user, msg.images)})

        # ─── Greeting detection ─────────────────────────────────────
        q = msg.user.strip().lower()
        is_greeting = (
            len(q) < 20
            and not any(w in q for w in ["criar", "fazer", "ler", "buscar", "executar",
                "arquivo", "pasta", "codigo", "mostrar", "explorar", "verificar",
                "analisar", "crie", "liste", "abra", "abrir", "leia", "procure"])
            and not any(c in q for c in [".py", ".ts", ".js", ".json", ".md", ".html"])
        )

        tool_temp = msg.temperature if msg.provider == "ollama" else 0.3
        recent_calls: list[str] = []
        checklist_steps: list[dict] = []

        # ═══════════════════════════════════════════════════════════════
        # MiMo EXECUTOR: provider=mimo usa mimo.exe com tool calling nativo
        # Se mimo.exe nao existe, faz fallback para API MiMo normal
        # ═══════════════════════════════════════════════════════════════
        if msg.provider == "mimo" and not saved:
            from pathlib import Path
            _mimo_exe = Path(str(get_base_dir())) / "bin" / "mimo.exe"
            _mimo_exe2 = Path(__file__).resolve().parent.parent / "bin" / "mimo.exe"
            _mimo_exe3 = Path(__file__).resolve().parent.parent / ".mimocode" / "bin" / "mimo.exe"
            _has_mimo_exe = _mimo_exe.exists() or _mimo_exe2.exists() or _mimo_exe3.exists()

            if _has_mimo_exe:
                from tools.mimo_executor import stream_mimo_task

                mimo_model = f"xiaomi/{msg.model}" if not msg.model.startswith("xiaomi/") else msg.model
                if msg.model in ("mimo-v2.5", "mimo"):
                    mimo_model = "xiaomi/mimo-v2.5"

                root_dir = msg.root or str(get_base_dir())

                yield {"type": "thinking", "content": f"[MiMo Executor] Executando via mimo.exe (model={mimo_model})"}

                full_answer = ""
                tool_logs = []
                step = 0

                # Constroi historico para o mimo.exe
                history_for_mimo = []
                for hp in history_pairs[-20:]:  # ultimas 20 mensagens
                    history_for_mimo.append({"role": hp["role"], "content": hp["content"]})

                async for event in stream_mimo_task(
                    message=msg.user,
                    model=mimo_model,
                    root=root_dir,
                    timeout=120,
                    history=history_for_mimo,
                ):
                    etype = event.get("type", "")

                    if etype == "content":
                        text = event.get("data", "")
                        if text:
                            full_answer += text
                            yield {"type": "token", "content": text}

                    elif etype == "tool_start":
                        tool_name = event.get("tool", "")
                        tool_params = event.get("params", {})
                        step += 1
                        yield {"type": "thinking", "step": step, "content": f"[MiMo] Executando: {tool_name}"}
                        yield {"type": "tool_start", "step": step, "tool": tool_name, "params": tool_params}

                    elif etype == "tool_end":
                        tool_name = event.get("tool", "")
                        tool_result = event.get("result", {})
                        yield {"type": "tool_end", "step": step, "tool": tool_name, "result": tool_result}
                        tool_logs.append({
                            "step": step,
                            "tool": tool_name,
                            "params": event.get("params", {}),
                            "result": tool_result,
                        })

                    elif etype == "error":
                        err_msg = event.get("message", "Erro desconhecido")
                        yield {"type": "thinking", "content": f"[MiMo Erro] {err_msg}"}

                    elif etype == "done":
                        content = event.get("content", "")
                        if content and not full_answer:
                            full_answer = content
                            yield {"type": "token", "content": content}
                        tc_events = event.get("tool_calls", [])
                        if tc_events and not tool_logs:
                            for tc in tc_events:
                                step += 1
                                tool_logs.append({
                                    "step": step,
                                    "tool": tc.get("tool", ""),
                                    "params": tc.get("params", {}),
                                    "result": tc.get("result", {}),
                                })

                if not full_answer:
                    full_answer = "Tarefa executada via MiMo Executor."

                conn = get_conn()
                cur = conn.cursor()
                cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, full_answer))
                conn.commit()
                conn.close()
                await save_llm_reflection(msg.user, full_answer)
                learn_from_interaction(msg.user, full_answer, tool_logs)

                yield {"type": "done", "answer": full_answer, "steps": step, "tool_logs": tool_logs}
                return
            # else: mimo.exe nao encontrado, cai no fluxo normal da API LLM
        checklist_active = -1
        checklist_yielded_plan = False
        model_sends_explicit_progress = False

        # ═══════════════════════════════════════════════════════════════
        # LIFECYCLE ENGINE: state machine-based execution loop
        # ═══════════════════════════════════════════════════════════════

        async def call_model_stream(messages_inner: list) -> AsyncGenerator[dict, None]:
            # Modelos locais usam LOCAL_TOOLS (reduzido) para caber no contexto
            if msg.provider in ("ollama", "llamacpp"):
                effective_tools = [] if is_greeting or not supports_tools(msg.provider, msg.model) else LOCAL_TOOLS
            else:
                effective_tools = [] if is_greeting or not supports_tools(msg.provider, msg.model) else TOOLS
            tool_names = [t["function"]["name"] for t in effective_tools] if effective_tools else []
            print(f"[CHAT] provider={msg.provider} model={msg.model} tools={len(effective_tools)} tool_names={tool_names[:10]}... is_greeting={is_greeting}")
            async for chunk in stream_chat_with_tools(
                msg.provider, msg.model, messages_inner, effective_tools, tool_temp, api_key=msg.api_key
            ):
                yield chunk

        async def execute_tool_fn(tool_name: str, params: dict) -> dict:
            if msg.root:
                root_tools = {"read", "write", "explorer", "explorer_read", "create_directory", "delete", "rename", "file_edit"}
                if tool_name in root_tools and "root" not in params:
                    params["root"] = msg.root
                elif tool_name == "bash" and "workdir" not in params:
                    params["workdir"] = msg.root

            call_sig = f"{tool_name}:{json.dumps(params, sort_keys=True)[:80]}"
            recent_calls.append(call_sig)
            if len(recent_calls) >= 6:
                last_6 = recent_calls[-6:]
                # Loop detection: same EXACT call signature 3x in a row
                if len(set(last_6[-3:])) == 1:
                    return {"error": f"Loop detectado: mesma chamada EXATA '{tool_name}' executada 3x seguidas. Mude de estrategia."}

            risk = assess_tool_risk(tool_name, params)
            if risk["needs_confirm"] and risk["risk_level"] in ("high", "critical") and not getattr(msg, 'tool_confirmed', False):
                return {"error": f"CONFIRM_REQUIRED:{risk['reason']}:{risk['risk_level']}", "_needs_confirm": True, "_risk": risk}

            # Intercepta bash(start...) com midia e converte para media_play
            if tool_name == "bash":
                cmd = (params.get("command") or "").strip()
                media_exts = ('.mp3', '.mp4', '.wav', '.avi', '.mkv', '.flac', '.ogg', '.wma', '.m4a')
                cmd_lower = cmd.lower()
                if cmd_lower.startswith("start ") and any(ext in cmd_lower for ext in media_exts):
                    # Extrai o caminho do arquivo
                    path_match = re.search(r'["\']([^"\']+?)["\']', cmd)
                    if not path_match:
                        path_match = re.search(r'start\s+["\']?(\S+)', cmd)
                    if path_match:
                        file_path = path_match.group(1)
                        import os
                        file_name = os.path.basename(file_path)
                        return await execute_tool("media_play", {"name": file_name, "path": file_path, "isVideo": any(v in cmd_lower for v in ('.mp4', '.avi', '.mkv', '.mov'))})

            # Intercepta browser_control(go_to) com URL de homepage e converte para web_search
            if tool_name == "browser_control" and params.get("action") == "go_to":
                url = (params.get("url") or "").strip().rstrip("/")
                # Detecta se e so o dominio (homepage) sem caminho especifico
                if url and "/" not in url.split("//")[-1] and "?" not in url and "#" not in url:
                    # Converte para web_search usando o dominio como contexto
                    from urllib.parse import urlparse
                    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
                    domain = parsed.netloc.replace("www.", "")
                    return await execute_tool("web_search", {"query": f"site:{domain}"})

            return await execute_tool(tool_name, params)

        def on_tool_start_fn(tool_name: str, params: dict):
            nonlocal checklist_active
            if not checklist_steps:
                return
            # Marca passo anterior como done (se havia um ativo)
            if checklist_active >= 0 and checklist_active < len(checklist_steps):
                if checklist_steps[checklist_active]["status"] != "done":
                    checklist_steps[checklist_active]["status"] = "done"
                    state_ref["yielded"].append({
                        "type": "task_progress",
                        "step_index": checklist_active,
                        "status": "done",
                    })
            # Avanca para proximo passo
            next_idx = checklist_active + 1
            if 0 <= next_idx < len(checklist_steps):
                checklist_steps[next_idx]["status"] = "running"
                checklist_active = next_idx
                state_ref["yielded"].append({
                    "type": "task_progress",
                    "step_index": next_idx,
                    "status": "running",
                })

        def on_tool_end_fn(tool_name: str, result: Any):
            nonlocal checklist_active
            if not checklist_steps or not (0 <= checklist_active < len(checklist_steps)):
                return
            checklist_steps[checklist_active]["status"] = "done"
            state_ref["yielded"].append({
                "type": "task_progress",
                "step_index": checklist_active,
                "status": "done",
            })

        # Track state for callbacks
        state_ref = {"step": 0, "yielded": []}

        lifecycle_config = LifecycleConfig(
            max_tool_steps=max_steps,
            max_api_retries=3,
            max_think_only_loops=3,
            tool_timeout=60.0,
            consecutive_tool_limit=12,
            planning_enforced=False,
        )

        def should_force_final_fn(consecutive: int) -> bool:
            return consecutive >= lifecycle_config.consecutive_tool_limit

        async def lifecycle_stream_wrapper(messages_inner: list) -> AsyncGenerator[dict, None]:
            async for chunk in call_model_stream(messages_inner):
                yield chunk

        async for event in run_lifecycle(
            messages=messages,
            config=lifecycle_config,
            call_model=None,
            call_model_stream=lifecycle_stream_wrapper,
            execute_tool_fn=execute_tool_fn,
            on_stream_token=lambda t: None,
            on_tool_start=on_tool_start_fn,
            on_tool_end=on_tool_end_fn,
            should_force_final=should_force_final_fn,
            supports_streaming=True,
        ):
            state_ref["step"] = event.get("step", state_ref["step"])

            # ═══════════════════════════════════════════════════════════════
            # PLAN_BREAK: Plano foi apresentado e lifecycle retornou.
            # Forcar checkpoint para frontend renderizar checkboxes vazios.
            # ═══════════════════════════════════════════════════════════════
            if event.get("type") == "plan_break":
                # Parse do task_plan do conteudo acumulado
                content_text = event.get("content", "")
                for plan_match in re.finditer(r'\{"type"\s*:\s*"task_plan"[^}]*"steps"\s*:\s*\[([^\]]*)\][^}]*\}', content_text):
                    try:
                        parsed_plan = json.loads(plan_match.group(0))
                        steps_list = parsed_plan.get("steps", [])
                        if steps_list:
                            checklist_steps.clear()
                            checklist_steps.extend([{"label": s, "status": "pending"} for s in steps_list])
                            checklist_yielded_plan = True
                            # checklist_active = -1 para que on_tool_start_fn comece do primeiro passo
                            checklist_active = -1
                            # Emitir checklist IMEDIATAMENTE para o frontend
                            yield {"type": "task_checklist", "steps": checklist_steps}
                            yield {"type": "thinking", "step": state_ref["step"], "content": f"[PLAN] Checklist renderizado com {len(steps_list)} passos"}
                    except (json.JSONDecodeError, IndexError):
                        pass
                # FORCAR YIELD para garantir que o frontend receba antes de continuar
                await asyncio.sleep(0)
                # Re-entrar no lifecycle para proxima iteracao (execucao)
                continue

            # ─── Parse task_plan / task_progress from accumulated content ──
            if event.get("type") == "thinking":
                content_text = event.get("content", "")
                for plan_match in re.finditer(r'\{"type"\s*:\s*"task_plan"[^}]*"steps"\s*:\s*\[([^\]]*)\][^}]*\}', content_text):
                    try:
                        parsed_plan = json.loads(plan_match.group(0))
                        steps_list = parsed_plan.get("steps", [])
                        if steps_list and not checklist_yielded_plan:
                            checklist_steps.clear()
                            checklist_steps.extend([{"label": s, "status": "pending"} for s in steps_list])
                            checklist_yielded_plan = True
                            checklist_active = 0
                            yield {"type": "task_checklist", "steps": checklist_steps}
                    except (json.JSONDecodeError, IndexError):
                        pass
                for prog_match in re.finditer(r'\{"type"\s*:\s*"task_progress"[^}]*\}', content_text):
                    try:
                        parsed_prog = json.loads(prog_match.group(0))
                        idx = parsed_prog.get("step_index", -1)
                        status = parsed_prog.get("status", "running")
                        error_msg = parsed_prog.get("error", "")
                        if 0 <= idx < len(checklist_steps):
                            checklist_steps[idx]["status"] = status
                            if error_msg:
                                checklist_steps[idx]["error"] = error_msg
                            if status == "running":
                                checklist_active = idx
                            model_sends_explicit_progress = True
                            yield {"type": "task_checklist", "steps": checklist_steps}
                    except (json.JSONDecodeError, IndexError):
                        pass

            # ─── Forward lifecycle events to stream ────────────────────
            if event["type"] == "tool_start":
                tool_name_ev = event.get("tool", "")
                tool_params_ev = event.get("params", {})

                # Check for CONFIRM_REQUIRED from execute_tool_fn
                if "CONFIRM_REQUIRED" in json.dumps(event.get("result", {})):
                    pass

                yield {"type": "thinking", "step": event.get("step", 0), "content": f"[Passo {event.get('step', 0)}/{max_steps}] Executando: {tool_name_ev}"}
                yield event
                # Yield accumulated checklist events from callbacks
                for ce in state_ref["yielded"]:
                    yield ce
                state_ref["yielded"].clear()

            elif event["type"] == "tool_end":
                tool_result = event.get("result", {})
                tool_name_ev = event.get("tool", "")

                # Se media_play retornou, emite evento action para o frontend
                if tool_name_ev == "media_play" and isinstance(tool_result, dict) and tool_result.get("action") == "media_play":
                    yield {"type": "action", "action": "media_play", "payload": tool_result.get("payload", {})}

                # Check for CONFIRM_REQUIRED
                if isinstance(tool_result, dict) and tool_result.get("_needs_confirm"):
                    confirm_id = f"tc_{uuid.uuid4().hex[:8]}"
                    save_task_state(task_id, messages, tool_logs, system_prompt, state_ref["step"] - 1, max_steps)
                    risk = tool_result.get("_risk", {})
                    yield {
                        "type": "tool_confirm",
                        "confirm_id": confirm_id,
                        "tool": tool_name_ev,
                        "label": risk.get("reason", ""),
                        "risk_level": risk.get("risk_level", "high"),
                        "params": tool_result.get("_params", {}),
                        "task_id": task_id,
                    }
                    yield {"type": "done", "answer": "", "task_id": task_id, "pending_confirm": True}
                    return

                # Parse task_progress do conteudo acumulado do modelo
                acc_content = event.get("accumulated_content", "")
                if acc_content:
                    for prog_match in re.finditer(r'\{"type"\s*:\s*"task_progress"[^}]*\}', acc_content):
                        try:
                            parsed_prog = json.loads(prog_match.group(0))
                            idx = parsed_prog.get("step_index", -1)
                            status = parsed_prog.get("status", "running")
                            error_msg = parsed_prog.get("error", "")
                            if 0 <= idx < len(checklist_steps):
                                checklist_steps[idx]["status"] = status
                                if error_msg:
                                    checklist_steps[idx]["error"] = error_msg
                                if status == "running":
                                    checklist_active = idx
                                model_sends_explicit_progress = True
                                yield {"type": "task_progress", "step_index": idx, "status": status}
                        except (json.JSONDecodeError, IndexError):
                            pass

                tool_logs.append({"step": event.get("step", 0), "tool": tool_name_ev, "params": event.get("params", {}), "result": tool_result})
                yield {"type": "thinking", "step": event.get("step", 0), "content": f"[Passo {event.get('step', 0)}/{max_steps}] {tool_name_ev} concluido"}
                yield event
                # Yield accumulated checklist events
                for ce in state_ref["yielded"]:
                    yield ce
                state_ref["yielded"].clear()

            elif event["type"] == "done":
                answer = strip_internal_json(event.get("answer", ""))
                final_steps = event.get("steps", state_ref["step"])
                status = event.get("status", "completed")

                # AUTO-CONTINUE: Se ha checklist pendente, continue automaticamente
                has_pending_checklist = any(s.get("status") == "pending" for s in checklist_steps)
                if has_pending_checklist and status == "completed":
                    # Auto-continue: envie "continue" para o modelo executar os passos
                    yield {"type": "thinking", "content": "Auto-executando tarefas pendentes..."}
                    messages.append({"role": "assistant", "content": answer or None})
                    messages.append({"role": "user", "content": "continue"})
                    state_ref["step"] += 1
                    # Continue the loop - don't return yet
                    continue

                # Reseta o estado do checklist para a proxima tarefa
                checklist_steps.clear()
                checklist_active = -1
                checklist_yielded_plan = False
                model_sends_explicit_progress = False

                # Detecta action JSON no texto e emite como evento action para o frontend
                if answer:
                    action_emitted = False
                    # Tenta parsear a resposta inteira como action JSON primeiro
                    try:
                        parsed_full = json.loads(answer.strip())
                        if isinstance(parsed_full, dict) and "action" in parsed_full and "payload" in parsed_full:
                            yield {"type": "action", "action": parsed_full["action"], "payload": parsed_full["payload"]}
                            action_emitted = True
                            answer = ""
                    except (json.JSONDecodeError, TypeError):
                        pass
                    # Se nao conseguiu, busca por JSON de action no texto
                    if not action_emitted:
                        for action_match in re.finditer(r'\{"action"\s*:\s*"(\w+)"\s*,\s*"payload"\s*:\s*(\{[^}]*\})\s*\}', answer):
                            try:
                                act_name = action_match.group(1)
                                act_payload = json.loads(action_match.group(2))
                                yield {"type": "action", "action": act_name, "payload": act_payload}
                                action_emitted = True
                            except (json.JSONDecodeError, IndexError):
                                pass
                    if action_emitted:
                        # Remove os JSONs de action do texto antes de enviar como tokens
                        answer = re.sub(r'\{"action"\s*:\s*"\w+"\s*,\s*"payload"\s*:\s*\{[^}]*\}\s*\}', '', answer).strip()
                        if not answer:
                            answer = "Midia enviada para o player."

                # Stream tokens for the final answer
                if answer:
                    for word in answer.split(" "):
                        yield {"type": "token", "content": word + " "}
                        await asyncio.sleep(0.02)

                # Persist
                if status == "completed" and answer:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, answer))
                    conn.commit()
                    conn.close()
                    await save_llm_reflection(msg.user, answer)
                    learn_from_interaction(msg.user, answer, tool_logs)
                    delete_task_state(task_id)

                if status == "max_steps":
                    save_task_state(task_id, messages, tool_logs, system_prompt, state_ref["step"], max_steps)
                    learn_from_interaction(msg.user, "", tool_logs)
                    done_tools = [l for l in tool_logs if l.get("tool")]
                    tool_summary = "; ".join(set(l["tool"] for l in done_tools)) if done_tools else "nenhuma ferramenta"
                    answer = (
                        f"Atingi o limite de {max_steps} passos. "
                        f"Ferramentas usadas: {tool_summary}. "
                        f"Total de {len(done_tools)} acoes."
                    )
                    yield {"type": "done", "answer": answer, "steps": final_steps, "tool_logs": tool_logs, "task_id": task_id}
                else:
                    yield {"type": "done", "answer": answer, "steps": final_steps, "tool_logs": tool_logs}
                return

            elif event["type"] == "error":
                yield event
                return

            else:
                yield event

    except Exception as e:
        traceback.print_exc()
        yield {"type": "error", "message": str(e)}


AGENT_CONFIGS = {
    "mimo": {"personality": "MiMo Auto (MiMo-V2.5) — assistente rapido e eficiente da Xiaomi", "mood": "opencode", "provider_override": "mimo", "model_override": "mimo-v2.5"},
    "coder": {"personality": "Programador especialista em implementacao", "mood": "opencode"},
    "writer": {"personality": "Escritor tecnico e documentador", "mood": "serio"},
    "helper": {"personality": "Assistente geral prestativo", "mood": "descontraido"},
    "planner": {"personality": "Planejador estrategico de tarefas", "mood": "serio"},
    "reviewer": {"personality": "Revisor de codigo e qualidade", "mood": "serio"},
    "debugger": {"personality": "Especialista em debugging e analysis de erros", "mood": "opencode"},
    "architect": {"personality": "Arquiteto de software senior", "mood": "serio"},
    "analyst": {"personality": "Analista de dados e sistemas", "mood": "serio"},
}

SKILL_DESCRIPTIONS = {
    "web_search": "Use a ferramenta web_search para pesquisar na internet",
    "file_picker": "Use explorer e read para navegar e selecionar arquivos",
    "terminal_run": "Use bash para executar comandos no terminal",
    "code_review": "Analise o codigo com criterios de qualidade, seguranca e performance",
    "test_runner": "Execute testes automatizados e reporte resultados",
    "doc_generator": "Gere documentacao tecnica para o projeto",
    "refactor": "Refatore o codigo mantendo funcionalidade",
    "deploy": "Prepare e execute o deploy da aplicacao",
    "memory": "Consulte e salve na memoria de longo prazo",
    "brain": "Use o sistema de aprendizado neural",
    "plan": "Crie um plano estruturado de execucao",
    "explore": "Explore a estrutura do projeto e arquivos",
}


async def handle_slash_command(cmd: dict, msg: Message) -> AsyncGenerator[dict, None]:
    command = cmd["command"]
    args = cmd["args"]

    if command == "clear":
        delete_task_state(msg.task_id) if msg.task_id else None
        yield {"type": "thinking", "content": "Contexto limpo. Pronto para nova tarefa."}
        yield {"type": "done", "answer": "Contexto limpo com sucesso. Pode iniciar uma nova conversa."}

    elif command == "goal":
        goal_text = args.strip() if args else ""
        if not goal_text:
            yield {"type": "done", "answer": "Uso: /goal <objetivo>\nExemplo: /goal Criar uma API REST completa para gerenciamento de tarefas"}
        else:
            yield {"type": "thinking", "content": f"Definindo objetivo: {goal_text}"}
            save_brain_memory(f"active_goal_{uuid.uuid4().hex[:8]}", goal_text, "goals", 0.9)
            yield {"type": "done", "answer": f"Objetivo definido:\n\n**{goal_text}**\n\nVou trabalhar em direcao a este objetivo. Pode pedir qualquer tarefa relacionada."}

    elif command == "run":
        if not args:
            yield {"type": "done", "answer": "Uso: /run <comando>\nExemplo: /run python main.py"}
        else:
            yield {"type": "thinking", "content": f"Executando: {args}"}
            try:
                from tools.executor import execute_tool
                result = await execute_tool("bash", {"command": args, "workdir": msg.root or ""})
                output = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
                yield {"type": "done", "answer": f"**Resultado:**\n```\n{output[:2000]}\n```"}
            except Exception as e:
                yield {"type": "error", "message": str(e)}

    elif command == "help":
        help_text = (
            "**Comandos Disponiveis:**\n\n"
            "| Comando | Descricao |\n|---|---|\n"
            "| `/goal <texto>` | Definir objetivo de longo prazo |\n"
            "| `/run <cmd>` | Executar comando no terminal |\n"
            "| `/clear` | Limpar contexto atual |\n"
            "| `/status` | Ver status do sistema |\n"
            "| `/doctor` | Diagnostico completo do sistema |\n"
            "| `/stop` | Parar execucao atual |\n"
            "| `/help` | Mostrar esta ajuda |\n\n"
            "**Atalhos:**\n"
 "- `+` para acoes rapidas\n"
            "| `@agente` para mencionar agente especialista |\n"
            "| `@skill` para invocar skill/ferramenta |\n\n"
            "**Menções:** `@coder`, `@writer`, `@debugger`, `@web_search`, `@terminal_run`, etc."
        )
        yield {"type": "done", "answer": help_text}

    elif command == "status":
        yield {"type": "done", "answer": f"Sistema operacional.\nProvider: {msg.provider}\nModelo: {msg.model}\nWorkspace: {msg.root or 'N/A'}"}

    elif command == "stop":
        yield {"type": "done", "answer": "Execucao interrompida pelo usuario."}

    elif command == "doctor":
        import asyncio
        import aiohttp
        from pathlib import Path
        yield {"type": "thinking", "content": "Rodando diagnostico completo do DEEP-OS..."}

        checks = []
        warnings = []
        errors = []

        # 1. Backend (self check)
        checks.append(("Backend (esta instancia)", "OK", "green"))

        # 2. Frontend
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:5175", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        checks.append(("Frontend (localhost:5175)", "OK", "green"))
                    else:
                        warnings.append(f"Frontend retornou status {resp.status}")
                        checks.append(("Frontend (localhost:5175)", f"AVISO (status {resp.status})", "yellow"))
        except Exception:
            errors.append("Frontend não encontrado em localhost:5175")
            checks.append(("Frontend (localhost:5175)", "ERRO - não responde", "red"))

        # 3. Ollama
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("name", "?") for m in data.get("models", [])]
                        checks.append(("Ollama (localhost:11434)", f"OK - {len(models)} modelos", "green"))
                        if not models:
                            warnings.append("Ollama rodando mas sem modelos instalados")
                    else:
                        checks.append(("Ollama (localhost:11434)", f"AVISO (status {resp.status})", "yellow"))
        except Exception:
            warnings.append("Ollama não encontrado (necessario para modelos locais)")
            checks.append(("Ollama (localhost:11434)", "OFFLINE", "yellow"))

        # 4. MiMo Executor
        mimo_path = Path(msg.root or ".") / "bin" / "mimo.exe"
        mimo_path2 = Path(__file__).resolve().parent.parent.parent / "bin" / "mimo.exe"
        if mimo_path.exists() or mimo_path2.exists():
            checks.append(("MiMo Executor (mimo.exe)", "OK", "green"))
        else:
            warnings.append("mimo.exe não encontrado em bin/")
            checks.append(("MiMo Executor (mimo.exe)", "NAO ENCONTRADO", "yellow"))

        # 5. Config YAML
        config_path = Path(msg.root or ".") / "config.yaml"
        if config_path.exists():
            checks.append(("config.yaml", "OK", "green"))
        else:
            errors.append("config.yaml não encontrado")
            checks.append(("config.yaml", "ERRO - ausente", "red"))

        # 6. Banco de dados
        db_path = Path(msg.root or ".") / "data" / "deep_aurea.db"
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            checks.append(("Banco de dados", f"OK ({size_mb:.1f} MB)", "green"))
        else:
            warnings.append("Banco de dados não encontrado (será criado)")
            checks.append(("Banco de dados", "NÃO EXISTE (será criado)", "yellow"))

        # 7. .opencode
        opencode_dir = Path(msg.root or ".") / ".opencode"
        if opencode_dir.exists():
            agents = list((opencode_dir / "agent").glob("*.md")) if (opencode_dir / "agent").exists() else []
            skills = list((opencode_dir / "skills").glob("*/SKILL.md")) if (opencode_dir / "skills").exists() else []
            checks.append((".opencode (agentes/skills)", f"OK - {len(agents)} agentes, {len(skills)} skills", "green"))
        else:
            warnings.append("Pasta .opencode não encontrada")
            checks.append((".opencode", "NAO ENCONTRADO", "yellow"))

        # 8. API Keys
        env_path = Path(msg.root or ".") / "backend" / ".env"
        env_keys = []
        if env_path.exists():
            env_content = env_path.read_text()
            if "ELEVENLABS_API_KEY" in env_content and not env_content.split("ELEVENLABS_API_KEY=")[-1].split("\n")[0].strip():
                warnings.append("ELEVENLABS_API_KEY vazia no .env")
                env_keys.append("ElevenLabs: VAZIA")
            elif "ELEVENLABS_API_KEY" in env_content:
                env_keys.append("ElevenLabs: configurada")
            if "MIMO_API_KEY" in env_content:
                env_keys.append("MiMo: configurada")
        checks.append(("API Keys (.env)", ", ".join(env_keys) if env_keys else "nenhuma encontrada", "green" if env_keys else "yellow"))

        # 9. Provider atual
        checks.append(("Provider ativo", f"{msg.provider} / {msg.model}", "green"))

        # 10. Memoria espiral
        from core.agent_config import load_agent_config
        try:
            cfg = load_agent_config()
            if cfg.spiral_memory.enabled:
                checks.append(("Memoria Espiral", f"ATIVA (intervalo: {cfg.spiral_memory.interval} passos)", "green"))
            else:
                checks.append(("Memoria Espiral", "desativada", "yellow"))
        except Exception:
            checks.append(("Memoria Espiral", "config indisponivel", "yellow"))

        # Monta relatorio
        report = "# /doctor — Diagnostico DEEP-OS\n\n"

        green_count = sum(1 for _, _, c in checks if c == "green")
        yellow_count = sum(1 for _, _, c in checks if c == "yellow") + len(warnings)
        red_count = sum(1 for _, _, c in checks if c == "red") + len(errors)

        if red_count == 0 and yellow_count == 0:
            status_emoji = "TUDO OK"
            status_color = "verde"
        elif red_count == 0:
            status_emoji = "FUNCIONAL COM AVISOS"
            status_color = "amarelo"
        else:
            status_emoji = "PROBLEMAS DETECTADOS"
            status_color = "vermelho"

        report += f"**Status geral:** {status_emoji}\n\n"
        report += "## Checks\n\n"
        report += "| Componente | Status |\n|---|---|\n"
        for name, status, color in checks:
            icon = "+" if color == "green" else ("!" if color == "yellow" else "X")
            report += f"| {name} | {status} |\n"

        if warnings:
            report += "\n## Avisos\n\n"
            for w in warnings:
                report += f"- {w}\n"

        if errors:
            report += "\n## Erros\n\n"
            for e in errors:
                report += f"- {e}\n"

        report += "\n---\n"
        report += f"**Resumo:** {green_count} OK | {yellow_count} avisos | {red_count} erros\n"

        yield {"type": "done", "answer": report}

    else:
        yield {"type": "done", "answer": f"Comando desconhecido: /{command}. Digite /help para ver comandos disponiveis."}


def inject_mention_context(msg: Message, mentions: dict) -> Message:
    extra_context = ""
    if mentions["agents"]:
        from core.opencode_loader import load_opencode_agents
        opencode_agents = load_opencode_agents()
        for agent in mentions["agents"]:
            cfg = AGENT_CONFIGS.get(agent, {})
            if cfg:
                extra_context += f"\n[AGENTE: {agent.upper()}] Personalidade: {cfg['personality']}"
                if cfg.get("mood"):
                    msg.mood = cfg["mood"]
                if cfg.get("provider_override"):
                    msg.provider = cfg["provider_override"]
                if cfg.get("model_override"):
                    msg.model = cfg["model_override"]
            # Tenta carregar prompt do .opencode/agent/
            oc_agent = opencode_agents.get(agent)
            if oc_agent and oc_agent.get("prompt"):
                extra_context += f"\n{oc_agent['prompt']}"
    if mentions["skills"]:
        from core.opencode_loader import load_opencode_skills
        oc_skills = load_opencode_skills()
        for skill in mentions["skills"]:
            # Tenta skill do .opencode primeiro
            oc_skill = oc_skills.get(skill)
            if oc_skill and oc_skill.get("content"):
                extra_context += f"\n[SKILL: {skill}]\n{oc_skill['content'][:3000]}"
            else:
                desc = SKILL_DESCRIPTIONS.get(skill, skill)
                extra_context += f"\n[SKILL: {skill}] Instrucao: {desc}"
    if extra_context:
        msg.system_prompt = (msg.system_prompt or "") + extra_context
    return msg


async def handle_question_stream(msg: Message) -> AsyncGenerator[dict, None]:
    try:
        q = msg.user.strip().lower()
        is_code = any(x in q for x in [
            "arquivo", "file", "codigo", "code", "pasta", "folder",
            "readme", "abra", "abrir", "open", "mostre", "exiba",
            "analise", "resuma", ".py", ".ts", ".js", ".json", ".md",
            "ferramenta", "ferramentas", "procurar", "buscar", "encontrar",
            "explorar", "listar", "verificar", "acessar", "diretorio",
            "sistema", "projeto", "codigo", "funcao", "função", "classe",
            "modulo", "módulo", "config", "configurar", "instalar",
            "executar", "rodar", "compilar", "testar", "depurar", "debug"
        ])
        is_greeting = (
            not is_code and len(q) < 20
            and not any(w in q for w in [
                "como", "qual", "quanto", "onde", "quando",
                "por que", "porque", "preco", "valor", "servico",
                "produto", "montagem", "formatacao", "upgrade",
                "horario", "peca", "computador", "notebook"
            ])
        )

        if is_greeting:
            context = "(conversa casual)"
        elif is_code:
            context = msg.user
        else:
            context = get_rag_context(msg.user)

        instruction = msg.system_prompt if msg.system_prompt else MOOD_INSTRUCTIONS.get(msg.mood, MOOD_INSTRUCTIONS["opencode"])
        context_rule = (
            "Responda naturalmente, sem se prender ao contexto."
            if is_greeting
            else "REGRA: Responda baseado EXCLUSIVAMENTE no Contexto abaixo. Nunca invente fatos."
        )

        user_root = msg.root.strip() if msg.root else ""
        user_path = msg.path.strip() if msg.path else ""

        system = f"{instruction}\n\n{context_rule}\n\nContexto: {context}"

        from core.prompts import TASK_CHECKLIST_PROMPT
        if is_code:
            tool_info = build_compact_tool_prompt(user_root, user_path)
            system += f"\n\n{tool_info}"
            system += f"\n\n{TASK_CHECKLIST_PROMPT}"
            system += PLANNING_PROTOCOL_REMINDER
        elif msg.mood == "opencode":
            tool_info = build_compact_tool_prompt(user_root, user_path)
            system += f"\n\n{tool_info}"

        # Carrega historico como pares de mensagens para manter contexto
        history_pairs = []
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT question, answer FROM history ORDER BY id DESC LIMIT 10")
            for row in reversed(list(cur.fetchall())):
                ans = row["answer"]
                if not ans:
                    continue
                try:
                    parsed_ans = json.loads(ans)
                    if isinstance(parsed_ans, dict) and ("tool" in parsed_ans or "name" in parsed_ans):
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
                history_pairs.append({"role": "user", "content": row["question"]})
                history_pairs.append({"role": "assistant", "content": ans[:500]})
            conn.close()
        except Exception:
            pass

        messages = build_conversation_messages(system, msg.user, history_pairs, images=msg.images)

        # Thinking: preparando resposta
        yield {"type": "thinking_start"}
        yield {"type": "thinking", "content": "[Analisando sua pergunta...]"}

        full_answer = ""
        async for token in stream_chat(msg.provider, msg.model, messages, msg.temperature, api_key=msg.api_key):
            full_answer += token
            yield {"type": "token", "content": token}

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, full_answer))
        conn.commit()
        conn.close()
        await save_llm_reflection(msg.user, full_answer)
        yield {"type": "done", "answer": full_answer}
    except Exception as e:
        yield {"type": "error", "message": str(e)}


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(request: Request, msg: Message):
    if not validate_message_length(msg.user):
        raise HTTPException(400, "Mensagem muito longa")

    # Get session ID (use provider+model as session if not provided)
    session_id = msg.session_id or f"{msg.provider}_{msg.model}"

    # Handle tool approval/rejection - always allow these
    if msg.user.startswith("/approve-tool"):
        msg.tool_confirmed = True
        msg.user = "continue"
    elif msg.user.startswith("/reject-tool"):
        msg.user = "continue"
    # Handle @ mentions (applied to msg before generate)
    mentions = parse_at_mentions(msg.user)
    if mentions["agents"] or mentions["skills"]:
        msg = inject_mention_context(msg, mentions)

    # Check if session is already processing
    if message_queue.is_processing(session_id) and not msg.tool_confirmed:
        # If this is a correction (user interrupted via abort), force-clear and proceed
        if msg.is_correction:
            message_queue.set_processing(session_id, False)
            # Also clear any stuck queued messages for this session
            try:
                q = message_queue._get_queue(session_id)
                while not q.empty():
                    q.get_nowait()
            except Exception:
                pass
        else:
            # Safety: if stuck processing for >60s, force-clear
            import time
            cur_task = message_queue.get_current_task(session_id)
            if cur_task and cur_task.timestamp and (time.time() - cur_task.timestamp > 60):
                message_queue.set_processing(session_id, False)
            else:
                # ── Triagem de urgencia ──
                # Avalia se a mensagem deve interromper a tarefa atual ou esperar na fila
                cur_task_summary = cur_task.user if cur_task else ""
                urgency = await assess_urgency(msg.user, cur_task_summary)

                if urgency["urgent"]:
                    # Mensagem URGENTE: interrompe a tarefa atual, processa a nova, depois retoma
                    message_queue.set_processing(session_id, False)
                    # Salva a tarefa interrompida para retomar depois
                    if cur_task:
                        interrupted_msg = QueuedMessage(
                            user=cur_task.user,
                            provider=cur_task.provider,
                            model=cur_task.model,
                            mood=cur_task.mood,
                            root=cur_task.root,
                            images=cur_task.images,
                            temperature=cur_task.temperature,
                            api_key=cur_task.api_key,
                            task_id=cur_task.task_id,
                        )
                        # Marca como tarefa interrompida para o frontend saber
                        interrupted_msg.interrupted = True
                        await message_queue.enqueue(session_id, interrupted_msg)

                    async def generate_urgent():
                        yield json.dumps({
                            "type": "urgent_interrupt",
                            "reason": urgency["reason"],
                            "method": urgency["method"],
                            "message": f"⚠️ Tarefa interrompida por mensagem urgente. Será retomada depois."
                        }, ensure_ascii=False) + "\n"
                        # Processa a mensagem urgente normalmente
                        try:
                            slash_cmd = parse_slash_command(msg.user)
                            if slash_cmd:
                                async for event in handle_slash_command(slash_cmd, msg):
                                    if await request.is_disconnected():
                                        return
                                    yield json.dumps(event, ensure_ascii=False) + "\n"
                                return
                            is_code_or_task = is_task_message(msg.user)
                            if is_code_or_task:
                                async for event in handle_task_stream(msg):
                                    if await request.is_disconnected():
                                        return
                                    yield json.dumps(event, ensure_ascii=False) + "\n"
                            else:
                                async for event in handle_question_stream(msg):
                                    if await request.is_disconnected():
                                        return
                                    yield json.dumps(event, ensure_ascii=False) + "\n"
                        except Exception as e:
                            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"
                        finally:
                            message_queue.set_processing(session_id, False)

                    # Marca como processando antes de iniciar
                    message_queue.set_processing(session_id, True)
                    return StreamingResponse(generate_urgent(), media_type="application/x-ndjson")
                else:
                    # Mensagem NORMAL: enfileira para processar depois
                    queued = QueuedMessage(
                        user=msg.user,
                        provider=msg.provider,
                        model=msg.model,
                        mood=msg.mood,
                        root=msg.root,
                        images=msg.images,
                        temperature=msg.temperature,
                        api_key=msg.api_key,
                        task_id=msg.task_id,
                    )
                    result = await message_queue.enqueue(session_id, queued)

                    async def generate_queued():
                        yield json.dumps({
                            "type": "queued",
                            "position": result["position"],
                            "queue_size": message_queue.queue_size(session_id),
                            "message": result["message"],
                            "urgency": urgency,
                        }, ensure_ascii=False) + "\n"

                    return StreamingResponse(generate_queued(), media_type="application/x-ndjson")

    # Mark session as processing with timestamp for stuck detection
    import time as _time
    _start_ts = _time.time()
    message_queue.set_processing(session_id, True)
    message_queue.set_current_task(session_id, QueuedMessage(
        user=msg.user, provider=msg.provider, model=msg.model,
        mood=msg.mood, root=msg.root, task_id=msg.task_id,
        timestamp=_start_ts,
    ))

    async def generate():
        try:
            # Handle voice commands
            voice_cmd = parse_voice_action(msg.user)
            if voice_cmd:
                cmd = voice_cmd["command"]
                if cmd in ("clear", "stop", "help", "status"):
                    slash_cmd = {"command": cmd, "args": voice_cmd["args"]}
                    async for event in handle_slash_command(slash_cmd, msg):
                        if await request.is_disconnected():
                            return
                        yield json.dumps(event, ensure_ascii=False) + "\n"
                    return
                if cmd == "media_stop":
                    yield json.dumps({"type": "action", "action": "media_stop"}, ensure_ascii=False) + "\n"
                    yield json.dumps({"type": "done", "answer": "Musica parada."}, ensure_ascii=False) + "\n"
                    return
                if cmd == "media_pause":
                    yield json.dumps({"type": "action", "action": "media_pause"}, ensure_ascii=False) + "\n"
                    yield json.dumps({"type": "done", "answer": "Musica pausada. Diga 'retomar' para continuar."}, ensure_ascii=False) + "\n"
                    return
                if cmd == "media_next":
                    yield json.dumps({"type": "action", "action": "media_next"}, ensure_ascii=False) + "\n"
                    yield json.dumps({"type": "done", "answer": "Proxima musica."}, ensure_ascii=False) + "\n"
                    return
                if cmd == "media_prev":
                    yield json.dumps({"type": "action", "action": "media_prev"}, ensure_ascii=False) + "\n"
                    yield json.dumps({"type": "done", "answer": "Musica anterior."}, ensure_ascii=False) + "\n"
                    return
                if cmd == "close_file":
                    from tools.executor import execute_tool
                    result = await execute_tool("close_app", {"file_path": voice_cmd["args"]})
                    yield json.dumps({"type": "done", "answer": f"Arquivo fechado: {result}"}, ensure_ascii=False) + "\n"
                    return
                if cmd == "close_all":
                    from tools.executor import execute_tool
                    await execute_tool("close_app", {"process_name": "notepad.exe"})
                    yield json.dumps({"type": "done", "answer": "Arquivos fechados."}, ensure_ascii=False) + "\n"
                    return
                if cmd == "media_internal":
                    yield json.dumps({"type": "action", "action": "media_select", "payload": {"player": "internal"}}, ensure_ascii=False) + "\n"
                    yield json.dumps({"type": "done", "answer": "Abrindo no player interno MEDIA..."}, ensure_ascii=False) + "\n"
                    return
                if cmd == "media_external":
                    yield json.dumps({"type": "action", "action": "media_select", "payload": {"player": "external"}}, ensure_ascii=False) + "\n"
                    yield json.dumps({"type": "done", "answer": "Abrindo no Windows Media Player..."}, ensure_ascii=False) + "\n"
                    return

            # Handle slash commands inside generator
            slash_cmd = parse_slash_command(msg.user)
            if slash_cmd:
                async for event in handle_slash_command(slash_cmd, msg):
                    if await request.is_disconnected():
                        return
                    yield json.dumps(event, ensure_ascii=False) + "\n"
                return
            is_code_or_task = is_task_message(msg.user)
            if is_code_or_task:
                async for event in handle_task_stream(msg):
                    if await request.is_disconnected():
                        return
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            else:
                async for event in handle_question_stream(msg):
                    if await request.is_disconnected():
                        return
                    yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"
        finally:
            # Mark session as not processing
            message_queue.set_processing(session_id, False)

    return StreamingResponse(generate(), media_type="application/x-ndjson")


async def _process_queued_message(msg: Message, session_id: str):
    """Processa uma mensagem da fila em background."""
    import httpx
    try:
        message_queue.set_processing(session_id, True)

        # Build the message content
        system_prompt = build_system_prompt(msg)
        is_code_or_task = is_task_message(msg.user)

        # Process the message
        if is_code_or_task:
            events = handle_task_stream(msg)
        else:
            events = handle_question_stream(msg)

        # We can't stream to the original response, so we save the result
        full_answer = ""
        async for event in events:
            if event.get("type") == "done":
                full_answer = event.get("answer", "")

        # Save to history
        if full_answer:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, full_answer))
            conn.commit()
            conn.close()
            await save_llm_reflection(msg.user, full_answer)

    except Exception as e:
        print(f"Error processing queued message: {e}")
    finally:
        message_queue.set_processing(session_id, False)

        # Check for more messages
        next_msg = await message_queue.dequeue(session_id)
        if next_msg:
            next_message = Message(
                user=next_msg.user,
                provider=next_msg.provider,
                model=next_msg.model,
                mood=next_msg.mood,
                root=next_msg.root,
                images=next_msg.images,
                temperature=next_msg.temperature,
                api_key=next_msg.api_key,
                task_id=next_msg.task_id,
                session_id=session_id,
            )
            asyncio.create_task(_process_queued_message(next_message, session_id))


async def handle_task(msg: Message):
    try:
        system_prompt = build_system_prompt(msg)
        tool_logs = []
        max_steps = 15
        tool_temp = msg.temperature if msg.provider == "ollama" else 0.3

        # Greeting detection — skip tools for simple messages
        q = msg.user.strip().lower()
        is_greeting = (
            len(q) < 20
            and not any(w in q for w in ["criar", "fazer", "ler", "buscar", "executar",
                "arquivo", "pasta", "codigo", "mostrar", "explorar", "verificar",
                "analisar", "crie", "liste", "abra", "abrir", "leia", "procure"])
            and not any(c in q for c in [".py", ".ts", ".js", ".json", ".md", ".html"])
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_content(msg.user, msg.images)},
        ]

        for step in range(max_steps):
            # Modelos locais usam LOCAL_TOOLS (reduzido) para caber no contexto
            if msg.provider in ("ollama", "llamacpp"):
                step_tools = [] if is_greeting or not supports_tools(msg.provider, msg.model) else LOCAL_TOOLS
            else:
                step_tools = [] if is_greeting or not supports_tools(msg.provider, msg.model) else TOOLS
            result = await complete_chat_with_tools(
                msg.provider, msg.model, messages, step_tools, tool_temp, api_key=msg.api_key
            )

            content = result.get("content", "")
            reasoning = result.get("reasoning", "")

            if result["type"] == "tool_calls":
                for tc in result["data"]:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_params = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_params = {}
                    if msg.root:
                        root_tools = {"read", "write", "explorer", "explorer_read", "create_directory", "delete", "rename", "file_edit"}
                        if tool_name in root_tools and "root" not in tool_params:
                            tool_params["root"] = msg.root
                        elif tool_name == "bash" and "workdir" not in tool_params:
                            tool_params["workdir"] = msg.root
                    try:
                        tool_result = await execute_tool(tool_name, tool_params)
                        tool_logs.append({"step": step + 1, "tool": tool_name, "params": tool_params, "result": tool_result})
                        assistant_msg = {"role": "assistant", "content": content or None, "tool_calls": [tc]}
                        if reasoning:
                            assistant_msg["content"] = f"<think>\n{reasoning}\n</think>\n" + (assistant_msg.get("content") or "")
                        messages.append(assistant_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False),
                        })
                    except Exception as e:
                        tool_logs.append({"step": step + 1, "tool": tool_name, "params": tool_params, "error": str(e)})
                        assistant_msg = {"role": "assistant", "content": content or None, "tool_calls": [tc]}
                        if reasoning:
                            assistant_msg["content"] = f"<think>\n{reasoning}\n</think>\n" + (assistant_msg.get("content") or "")
                        messages.append(assistant_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps({"error": str(e)}, ensure_ascii=False),
                        })
                continue

            # Final answer
            answer = (result.get("data") or "").strip()
            if answer.startswith("FINAL:"):
                answer = answer[6:].strip()
            if not answer:
                answer = "Pronto."
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, answer))
            conn.commit()
            conn.close()
            await save_llm_reflection(msg.user, answer)
            return {"answer": answer, "type": "task", "steps": step + 1, "tool_logs": tool_logs}

        done_tools = [l for l in tool_logs if l.get("tool")]
        tool_summary = "; ".join(set(l["tool"] for l in done_tools)) if done_tools else "nenhuma ferramenta"
        limit_msg = (
            f"Atingi o limite de {max_steps} passos. "
            f"Ferramentas usadas: {tool_summary}. "
            f"Total de {len(done_tools)} acoes.\n\n"
            f"Digite 'continue' para continuar de onde parei."
        )
        return {"answer": limit_msg, "type": "task", "steps": max_steps, "tool_logs": tool_logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def handle_question(msg: Message):
    try:
        answer = await get_answer(
            msg.user, msg.provider, msg.model,
            msg.mood, msg.temperature, msg.system_prompt,
            api_key=msg.api_key, root=msg.root, path=msg.path, images=msg.images
        )
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, answer))
        conn.commit()
        conn.close()
        await save_llm_reflection(msg.user, answer)
        return {"answer": answer, "type": "question"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_answer(
    question: str, provider: str, model_name: str,
    mood: str, temperature: float = 0.7, system_prompt: str = "",
    api_key: str = "",
    root: str = "",
    path: str = "",
    images: list[str] = None,
):
    q = question.strip().lower()
    is_code = any(x in q for x in [
        "arquivo", "file", "codigo", "code", "pasta", "folder",
        "readme", "abra", "abrir", "open", "mostre", "exiba",
        "analise", "resuma", ".py", ".ts", ".js", ".json", ".md"
    ])
    is_greeting = (
        not is_code and len(q) < 20
        and not any(w in q for w in [
            "como", "qual", "quanto", "onde", "quando",
            "por que", "porque", "preco", "valor", "servico",
            "produto", "montagem", "formatacao", "upgrade",
            "horario", "peca", "computador", "notebook"
        ])
    )

    if is_greeting:
        context = "(conversa casual)"
    elif is_code:
        context = question
    else:
        context = get_rag_context(question)

    instruction = system_prompt if system_prompt else MOOD_INSTRUCTIONS.get(mood, MOOD_INSTRUCTIONS["opencode"])
    context_rule = (
        "Responda naturalmente, sem se prender ao contexto."
        if is_greeting
        else "REGRA: Responda baseado EXCLUSIVAMENTE no Contexto abaixo. Nunca invente fatos."
    )

    system = f"{instruction}\n\n{context_rule}\n\nContexto: {context}"

    user_root = root.strip() if root else ""
    user_path = path.strip() if path else ""
    if is_code:
        from core.prompts import TASK_CHECKLIST_PROMPT
        tool_info = build_compact_tool_prompt(user_root, user_path)
        system += f"\n\n{tool_info}"
        system += f"\n\n{TASK_CHECKLIST_PROMPT}"
        system += PLANNING_PROTOCOL_REMINDER

    # Carrega historico para contexto da conversa
    history_pairs = []
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT question, answer FROM history ORDER BY id DESC LIMIT 10")
        for row in reversed(list(cur.fetchall())):
            ans = row["answer"]
            if not ans:
                continue
            try:
                parsed_ans = json.loads(ans)
                if isinstance(parsed_ans, dict) and ("tool" in parsed_ans or "name" in parsed_ans):
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
            history_pairs.append({"role": "user", "content": row["question"]})
            history_pairs.append({"role": "assistant", "content": ans[:500]})
        conn.close()
    except Exception:
        pass

    messages = build_conversation_messages(system, question, history_pairs, images=images)
    return await complete_chat(provider, model_name, messages, temperature, api_key=api_key)


class OpenRouterKeyBody(BaseModel):
    api_key: str


@router.post("/openrouter/models")
async def openrouter_models(body: OpenRouterKeyBody):
    if not body.api_key:
        return {"models": []}
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {body.api_key}"},
            )
            if resp.status_code != 200:
                return {"models": [], "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                models.append({"value": mid, "label": mid})
            models.sort(key=lambda x: x["value"])
            return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.get("/chat/queue/{session_id}")
async def get_queue_status(session_id: str):
    """Retorna o status da fila de mensagens para uma sessao."""
    status = message_queue.get_status(session_id)
    return {
        "session_id": session_id,
        "is_processing": status["is_processing"],
        "queue_size": status["queue_size"],
        "has_pending": status["queue_size"] > 0 or status["is_processing"],
    }


@router.get("/opencode/agents")
async def list_opencode_agents():
    """Lista agentes disponiveis na pasta .opencode/agent/."""
    from core.opencode_loader import list_available_agents
    return {"agents": list_available_agents()}


@router.get("/opencode/skills")
async def list_opencode_skills():
    """Lista skills disponiveis na pasta .opencode/skills/."""
    from core.opencode_loader import list_available_skills
    return {"skills": list_available_skills()}
