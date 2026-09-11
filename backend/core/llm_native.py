import json
import re

import httpx
from openai import AsyncOpenAI, Timeout

from core.agent_config import load_agent_config
from core.config import (
    GEMINI_API_KEY,
    GROQ_API_KEY,
    MIMO_API_KEY,
    NVIDIA_API_KEY,
    OPENAI_API_KEY,
    OPENCLAUDE_API_KEY,
    OPENCLAUDE_BASE_URL,
    OPENCODE_API_KEY,
    OPENROUTER_API_KEY,
)
from core.retry import async_retry

MAX_CONTEXT_TOKENS = 128000


def truncate_messages(messages: list, max_tokens: int = MAX_CONTEXT_TOKENS) -> list:
    if not messages:
        return messages

    def rough_tokens(text: str) -> int:
        return len(text) // 3

    total = sum(rough_tokens(m.get("content", "")) for m in messages if isinstance(m.get("content"), str))
    if total <= max_tokens:
        return messages

    system = [messages[0]] if messages[0]["role"] == "system" else []
    rest = messages[len(system):]

    last_user = None
    non_system = list(rest)
    for i in range(len(non_system) - 1, -1, -1):
        if non_system[i]["role"] == "user":
            last_user = non_system.pop(i)
            break

    kept = list(system)
    running = sum(rough_tokens(m.get("content", "")) for m in system if isinstance(m.get("content"), str))

    for m in reversed(non_system):
        t = rough_tokens(m.get("content", "")) if isinstance(m.get("content"), str) else 0
        if running + t <= max_tokens:
            kept.append(m)
            running += t

    if last_user:
        kept.append(last_user)

    return kept


IMG_PATTERN = re.compile(r'!\[image\]\((data:image/[^;]+;base64,[^)]+)\)')


def convert_to_multimodal(messages: list) -> list:
    """Converte mensagens com ![image](data:...) para o formato multimodal da OpenAI."""
    try:
        cfg = load_agent_config()
        if cfg.agent.image_input_mode == "text":
            return messages
    except Exception:
        pass
    for m in messages:
        content = m.get("content")
        if not isinstance(content, str) or "![image](data:image" not in content:
            continue
        parts = []
        last_end = 0
        for match in IMG_PATTERN.finditer(content):
            if match.start() > last_end:
                parts.append({"type": "text", "text": content[last_end:match.start()]})
            parts.append({"type": "image_url", "image_url": {"url": match.group(1)}})
            last_end = match.end()
        if last_end < len(content):
            parts.append({"type": "text", "text": content[last_end:]})
        if parts:
            m["content"] = parts
    return messages


def get_client(provider: str, api_key_override: str = "", timeout_read: float = 120.0) -> AsyncOpenAI:
    timeout = Timeout(connect=10.0, read=timeout_read, write=10.0, pool=10.0)
    if provider == "ollama":
        return AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=timeout)
    elif provider == "groq":
        key = api_key_override or GROQ_API_KEY
        if not key:
            raise ValueError("GROQ_API_KEY nao configurada. Crie backend/.env com GROQ_API_KEY=gsk_...")
        return AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=key, timeout=timeout)
    elif provider == "openrouter":
        key = api_key_override or OPENROUTER_API_KEY
        if not key:
            raise ValueError("OPENROUTER_API_KEY nao configurada. Crie backend/.env com OPENROUTER_API_KEY=sk-or-...")
        return AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
            timeout=timeout,
        )
    elif provider == "openai":
        key = api_key_override or OPENAI_API_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY nao configurada. Crie backend/.env com OPENAI_API_KEY=sk-...")
        return AsyncOpenAI(api_key=key, timeout=timeout)
    elif provider == "gemini":
        key = api_key_override or GEMINI_API_KEY
        if not key:
            raise ValueError("GEMINI_API_KEY nao configurada. Crie backend/.env com GEMINI_API_KEY=AIza...")
        return AsyncOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=key,
            timeout=timeout,
        )
    elif provider == "opencode":
        key = api_key_override or OPENCODE_API_KEY
        if not key:
            raise ValueError("OPENCODE_API_KEY nao configurada. Crie backend/.env com OPENCODE_API_KEY=oc_...")
        return AsyncOpenAI(
            base_url="https://opencode.ai/zen/v1",
            api_key=key,
            timeout=timeout,
        )
    elif provider == "nvidia":
        key = api_key_override or NVIDIA_API_KEY
        if not key:
            raise ValueError("NVIDIA_API_KEY nao configurada. Crie backend/.env com NVIDIA_API_KEY=nvapi-...")
        return AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=key,
            timeout=timeout,
        )
    elif provider == "openclaude":
        key = api_key_override or OPENCLAUDE_API_KEY
        if not key:
            raise ValueError("OPENCLAUDE_API_KEY nao configurada. Crie backend/.env com a chave do seu servidor OpenClaude")
        return AsyncOpenAI(
            base_url=OPENCLAUDE_BASE_URL,
            api_key=key,
            timeout=timeout,
        )
    elif provider == "mimo":
        key = api_key_override or MIMO_API_KEY
        if not key:
            raise ValueError("MIMO_API_KEY nao configurada. Crie backend/.env com MIMO_API_KEY=sk-...")
        return AsyncOpenAI(
            base_url="https://api.xiaomimimo.com/v1",
            api_key=key,
            timeout=timeout,
        )
    elif provider == "llamacpp":
        return AsyncOpenAI(base_url="http://localhost:8080/v1", api_key="llamacpp", timeout=timeout)
    raise ValueError(f"Unknown provider: {provider}")


OLLAMA_BASE_URL = "http://localhost:11434"


def _is_multimodal(messages: list) -> bool:
    for m in messages:
        if isinstance(m.get("content"), list):
            return True
    return False


def _convert_to_ollama_native(messages: list) -> list:
    result = []
    for m in messages:
        entry: dict = {"role": m["role"]}
        content = m.get("content")
        if isinstance(content, list):
            text_parts = []
            images = []
            for part in content:
                if part["type"] == "text":
                    text_parts.append(part["text"])
                elif part["type"] == "image_url":
                    url = part["image_url"]["url"]
                    if "," in url:
                        b64 = url.split(",", 1)[1]
                    else:
                        b64 = url
                    images.append(b64)
            entry["content"] = "".join(text_parts) or ""
            if images:
                entry["images"] = images
        elif isinstance(content, str):
            entry["content"] = content
        else:
            # Garante que content nunca seja None para Ollama
            entry["content"] = str(content) if content is not None else ""
        result.append(entry)
    return result


def _ollama_gpu_options() -> dict:
    try:
        from routes.ollama_route import get_gpu_config
        cfg = get_gpu_config()
        if cfg.get("gpu_enabled", True):
            return {"num_gpu": cfg.get("gpu_layers", -1)}
        return {"num_gpu": 0}
    except Exception:
        return {}


async def _ollama_chat_stream(model: str, messages: list, temperature: float = 0.7):
    url = f"{OLLAMA_BASE_URL}/api/chat"
    opts = {"temperature": temperature}
    opts.update(_ollama_gpu_options())
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": opts,
    }
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client, client.stream("POST", url, json=payload) as response:
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                msg = chunk.get("message", {})
                if msg.get("content"):
                    yield msg["content"]
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                continue


async def _ollama_chat_stream_with_tools(model: str, messages: list, tools: list, temperature: float = 0.7):
    """Ollama native API with tool calling support."""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    opts = {"temperature": temperature}
    opts.update(_ollama_gpu_options())
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": opts,
    }
    if tools:
        payload["tools"] = tools
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
    full_content = ""
    full_tool_calls = []
    async with httpx.AsyncClient(timeout=timeout) as client, client.stream("POST", url, json=payload) as response:
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                msg = chunk.get("message", {})
                if msg.get("content"):
                    content = msg["content"]
                    full_content += content
                    yield {"type": "content", "data": content}
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        full_tool_calls.append(tc)
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                continue

    if full_tool_calls:
        parsed = []
        for tc in full_tool_calls:
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            parsed.append({
                "id": f"ollama_{abs(hash(str(tc))) % 100000}",
                "type": "function",
                "function": {
                    "name": func.get("name", ""),
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            })
        yield {"type": "tool_calls", "data": parsed, "content": full_content, "reasoning": ""}
    else:
        yield {"type": "done", "content": full_content, "reasoning": ""}


async def _ollama_chat_complete(model: str, messages: list, temperature: float = 0.7) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    opts = {"temperature": temperature}
    opts.update(_ollama_gpu_options())
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": opts,
    }
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        data = resp.json()
        return data.get("message", {}).get("content", "")


async def stream_chat(
    provider: str,
    model: str,
    messages: list,
    temperature: float = 0.7,
    api_key: str = "",
):
    if provider == "llamacpp":
        from routes.llamacpp_route import ensure_llamacpp_model
        status = ensure_llamacpp_model(model)
        if status.get("error"):
            yield f"ERR: {status['error']}"
            return
    messages = truncate_messages(messages)
    messages = convert_to_multimodal(messages)
    # Sanitiza mensagens para garantir que content nunca seja None
    for m in messages:
        if "content" not in m or m["content"] is None:
            m["content"] = ""
    if provider == "ollama" and _is_multimodal(messages):
        native_msgs = _convert_to_ollama_native(messages)
        async for chunk in _ollama_chat_stream(model, native_msgs, temperature):
            yield chunk
        return
    client = get_client(provider, api_key)
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            stream=True,
        )
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[LLM] Erro de parsing na resposta ({provider}/{model}): {e}")
        yield f"ERR: Resposta malformada do LLM: {e}"
        return
    except Exception as e:
        # Fallback: tenta sem stream se o provider nao suporta
        print(f"[LLM] Streaming falhou para {provider}/{model}, retrying sem stream: {type(e).__name__}: {e}")
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
                stream=False,
            )
            content = resp.choices[0].message.content or ""
            if content:
                yield content
        except Exception as fallback_err:
            print(f"[LLM] Fallback non-streaming também falhou: {type(fallback_err).__name__}: {fallback_err}")
            yield f"ERR: Falha ao chamar LLM ({provider}/{model}): {fallback_err}"
        return
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def complete_chat(
    provider: str,
    model: str,
    messages: list,
    temperature: float = 0.7,
    api_key: str = "",
) -> str:
    if provider == "llamacpp":
        from routes.llamacpp_route import ensure_llamacpp_model
        status = ensure_llamacpp_model(model)
        if status.get("error"):
            return f"ERR: {status['error']}"
    messages = truncate_messages(messages)
    messages = convert_to_multimodal(messages)
    # Sanitiza mensagens para garantir que content nunca seja None
    for m in messages:
        if "content" not in m or m["content"] is None:
            m["content"] = ""
    if provider == "ollama" and _is_multimodal(messages):
        native_msgs = _convert_to_ollama_native(messages)
        return await _ollama_chat_complete(model, native_msgs, temperature)
    client = get_client(provider, api_key)
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
        stream=False,
    )
    return resp.choices[0].message.content or ""


def _is_vision_model(model: str) -> bool:
    """Retorna True se o nome do modelo indicar ser um modelo de visao (vl, vision, gemma4)."""
    name = model.split(":")[0].lower()
    return bool(re.search(r'(vl|vision|gemma4)', name))


def _extract_tool_from_text(text: str) -> dict | None:
    """Detecta e extrai tool calls que o modelo gerou como texto (nao native)."""
    if not text or len(text.strip()) < 5:
        return None
    text = text.strip()

    # Gemini XML format detection
    _tco = chr(60) + "tc" + "_" + "call" + chr(62)
    _tcc = chr(60) + "/tc" + "_" + "call" + chr(62)
    _p1 = _tco + chr(32) + chr(60) + "function=" + "(\\w+)" + chr(62) + "\\s*(.*?)" + _tcc
    _m = re.search(_p1, text, re.DOTALL)
    if not _m:
        _p2 = chr(60) + "function=" + "(\\w+)" + chr(62) + "\\s*(.*?)" + chr(60) + "/function" + chr(62)
        _m = re.search(_p2, text, re.DOTALL)
    if _m:
        _tn = _m.group(1)
        _pr = {}
        _pp = chr(60) + "parameter=" + "(\\w+)" + chr(62) + "(.*?)" + chr(60) + "/parameter" + chr(62)
        for _pm in re.finditer(_pp, text, re.DOTALL):
            _pr[_pm.group(1)] = _pm.group(2).strip()
        return {
            "id": f"txt_{abs(hash(text)) % 100000}",
            "type": "function",
            "function": {"name": _tn, "arguments": json.dumps(_pr)},
        }

    # Remove prefixo ! ou outros chars antes do JSON
    cleaned = text.lstrip("!").lstrip("-").strip()

    # 1. Tenta code blocks JSON
    for m in re.finditer(r'```(?:json)?\s*\n?(.*?)```', cleaned, re.DOTALL):
        try:
            parsed = json.loads(m.group(1).strip())
            tc = _normalize_text_tool(parsed)
            if tc:
                return tc
        except json.JSONDecodeError:
            pass

    # 2. Busca JSON por contagem de chaves
    i = 0
    while i < len(cleaned):
        idx = cleaned.find('{', i)
        if idx == -1:
            break
        depth = 0
        j = idx
        while j < len(cleaned):
            if cleaned[j] == '{':
                depth += 1
            elif cleaned[j] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(cleaned[idx:j+1])
                        tc = _normalize_text_tool(parsed)
                        if tc:
                            return tc
                    except json.JSONDecodeError:
                        pass
                    break
            j += 1
        i = idx + 1

    # 3. Pattern: bash("comando") ou read("path")
    for m in re.finditer(r'(bash|read|write|explorer|search|glob|delete|rename|create_directory)\s*\(\s*["\'](.+?)["\']', cleaned):
        tool_name = m.group(1)
        arg_val = m.group(2)
        param_key = "command" if tool_name == "bash" else "path" if tool_name in ("read", "explorer", "delete", "create_directory") else "pattern" if tool_name == "glob" else "query" if tool_name == "search" else "content"
        return {
            "id": f"txt_{abs(hash(cleaned)) % 100000}",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps({param_key: arg_val}),
            },
        }

    # 4. Pattern: web_search(query = "...") ou tool_name(param = "value")
    all_tool_names = ["web_search", "web_fetch", "bash", "read", "write", "search", "explorer", "glob",
                      "execute_python", "create_directory", "delete", "rename", "file_edit",
                      "task_create", "task_update", "memory_write", "memory_read",
                      "fork_subagent", "media_play", "monitor_dashboard"]
    for m in re.finditer(r'(\w+)\s*\(\s*(\w+)\s*=\s*["\'](.+?)["\']\s*\)', cleaned):
        tool_name = m.group(1)
        param_name = m.group(2)
        param_val = m.group(3)
        if tool_name in all_tool_names:
            return {
                "id": f"txt_{abs(hash(cleaned)) % 100000}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps({param_name: param_val}),
                },
            }

    # 5. Pattern: tool `tool_name` com param = "value" (Markdown code + natural language)
    for m in re.finditer(r'`(\w+)`\s+com\s+(\w+)\s*=\s*["\'](.+?)["\']', cleaned):
        tool_name = m.group(1)
        param_name = m.group(2)
        param_val = m.group(3)
        if tool_name in all_tool_names:
            return {
                "id": f"txt_{abs(hash(cleaned)) % 100000}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps({param_name: param_val}),
                },
            }

    # 6. Pattern: Ação: `tool_name` com param = "value"
    for m in re.finditer(r'[Aa][çc][ãa]o:\s*`(\w+)`\s+com\s+(\w+)\s*=\s*["\'](.+?)["\']', cleaned):
        tool_name = m.group(1)
        param_name = m.group(2)
        param_val = m.group(3)
        if tool_name in all_tool_names:
            return {
                "id": f"txt_{abs(hash(cleaned)) % 100000}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps({param_name: param_val}),
                },
            }

    # 7. Pattern: Ação: tool_name com param="value" (sem backticks)
    for m in re.finditer(r'[Aa][çc][ãa]o:\s*(\w+)\s+com\s+(\w+)\s*=\s*["\'](.+?)["\']', cleaned):
        tool_name = m.group(1)
        param_name = m.group(2)
        param_val = m.group(3)
        if tool_name in all_tool_names:
            return {
                "id": f"txt_{abs(hash(cleaned)) % 100000}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps({param_name: param_val}),
                },
            }

    # 8. Generic: any tool_name(param_name) or tool_name: "value"
    for m in re.finditer(r'(\w+)\s*[:=]\s*["\']([^"\']{2,})["\']', cleaned):
        possible_tool = m.group(1).lower()
        possible_val = m.group(2)
        if possible_tool in all_tool_names:
            # Determine parameter name based on tool
            param_map = {
                "web_search": "query", "web_fetch": "url", "bash": "command",
                "read": "path", "write": "path", "search": "pattern",
                "explorer": "path", "glob": "pattern", "execute_python": "code",
                "create_directory": "path", "delete": "path", "rename": "old_path",
                "file_edit": "path", "memory_write": "key", "memory_read": "key",
                "fork_subagent": "task", "media_play": "path",
            }
            param_name = param_map.get(possible_tool, "value")
            return {
                "id": f"txt_{abs(hash(cleaned)) % 100000}",
                "type": "function",
                "function": {
                    "name": possible_tool,
                    "arguments": json.dumps({param_name: possible_val}),
                },
            }

    return None


def _normalize_text_tool(parsed: dict) -> dict | None:
    """Normaliza JSON de tool call text-based para formato OpenAI."""
    if not isinstance(parsed, dict):
        return None

    # Formato: {"tool": "name", "params": {...}}
    if "tool" in parsed:
        name = parsed["tool"]
        params = parsed.get("params", {})
        return {
            "id": f"txt_{abs(hash(str(parsed))) % 100000}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(params)},
        }

    # Formato: {"name": "func", "arguments": {...}}
    if "name" in parsed:
        name = parsed["name"]
        args = parsed.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        return {
            "id": f"txt_{abs(hash(str(parsed))) % 100000}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }

    # Formato: {"action": "bash", "action_input": {"command": "..."}} (MiMo V2.5)
    if "action" in parsed and "action_input" in parsed:
        action_name = parsed["action"]
        action_input = parsed["action_input"]
        if isinstance(action_input, str):
            try:
                action_input = json.loads(action_input)
            except json.JSONDecodeError:
                action_input = {}
        
        return {
            "id": f"txt_{abs(hash(str(parsed))) % 100000}",
            "type": "function",
            "function": {"name": action_name, "arguments": json.dumps(action_input)},
        }

    # Formato: {"action": "media_play", "payload": {...}}
    if "action" in parsed and "payload" in parsed:
        action_name = parsed["action"]
        payload = parsed["payload"]
        return {
            "id": f"txt_{abs(hash(str(parsed))) % 100000}",
            "type": "function",
            "function": {"name": action_name, "arguments": json.dumps(payload)},
        }

    return None


async def stream_chat_with_tools(
    provider: str,
    model: str,
    messages: list,
    tools: list,
    temperature: float = 0.3,
    api_key: str = "",
):
    if provider == "llamacpp":
        from routes.llamacpp_route import ensure_llamacpp_model
        status = ensure_llamacpp_model(model)
        if status.get("error"):
            yield {"type": "content", "data": f"ERR: {status['error']}"}
            return
    messages = truncate_messages(messages)
    messages = convert_to_multimodal(messages)
    # Sanitiza mensagens para garantir que content nunca seja None
    for m in messages:
        if "content" not in m or m["content"] is None:
            m["content"] = ""
    if provider == "ollama":
        native_msgs = _convert_to_ollama_native(messages)
        effective_tools = tools
        if _is_vision_model(model):
            effective_tools = []
        if effective_tools:
            print(f"[LLM] Ollama native API with {len(effective_tools)} tools")
            async for chunk in _ollama_chat_stream_with_tools(model, native_msgs, effective_tools, temperature):
                yield chunk
            return
        else:
            full = ""
            async for chunk in _ollama_chat_stream(model, native_msgs, temperature):
                full += chunk
                yield {"type": "content", "data": chunk}
            yield {"type": "done", "content": full, "reasoning": ""}
            return
    client = get_client(provider, api_key)
    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=8192, stream=True)
    if tools:
        if provider == "ollama" and _is_vision_model(model):
            print(f"[LLM] VISION MODEL {model} - stripping tools")
            tools = []
    if tools:
        kwargs["tools"] = tools
    tool_names = [t["function"]["name"] for t in kwargs.get("tools", [])]
    print(f"[LLM] stream_chat_with_tools: provider={provider} model={model} tools={len(tool_names)} names={tool_names[:15]} msgs={len(messages)}")
    print(f"[LLM] msg_roles={[m.get('role') for m in messages]}")
    if messages and messages[0].get("role") == "system":
        sp = messages[0].get("content", "")
        print(f"[LLM] system_prompt len={len(sp)} first200={sp[:200]}")
    try:
        stream = await client.chat.completions.create(**kwargs)
    except Exception as e:
        # Fallback: tenta sem tools se o erro for de tool calling
        if tools and ("tool" in str(e).lower() or "function" in str(e).lower()
                       or "400" in str(e) or "422" in str(e)):
            print(f"[LLM] Tool calling falhou para {provider}/{model}, retrying sem tools: {e}")
            kwargs.pop("tools", None)
            stream = await client.chat.completions.create(**kwargs)
        else:
            raise
    full_tool_calls = {}
    accumulated_content = ""
    accumulated_reasoning = ""
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if not delta:
            continue

        # Capture reasoning_content (DeepSeek thinking tokens)
        rc = getattr(delta, "reasoning_content", None)
        if rc:
            accumulated_reasoning += rc
            yield {"type": "content", "data": rc}

        if delta.content:
            accumulated_content += delta.content
            yield {"type": "content", "data": delta.content}

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in full_tool_calls:
                    full_tool_calls[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                if tc.id:
                    full_tool_calls[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        full_tool_calls[idx]["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        full_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

    print(f"[LLM] stream done: content_len={len(accumulated_content)} reasoning_len={len(accumulated_reasoning)} native_tool_calls={len(full_tool_calls)}")
    if full_tool_calls:
        result = []
        for idx in sorted(full_tool_calls.keys()):
            tc = full_tool_calls[idx]
            try:
                args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            result.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": json.dumps(args),
                },
            })
        print(f"[LLM] YIELDING tool_calls: {[r['function']['name'] for r in result]}")
        yield {"type": "tool_calls", "data": result, "content": accumulated_content, "reasoning": accumulated_reasoning}
    else:
        # Fallback: extrai tool calls do texto quando o modelo nao usa native tool calling
        extracted = _extract_tool_from_text(accumulated_content)
        if extracted:
            print(f"[LLM] FALLBACK extracted tool from text: {extracted['function']['name']}")
            yield {"type": "tool_calls", "data": [extracted], "content": accumulated_content, "reasoning": accumulated_reasoning}
        else:
            print(f"[LLM] NO TOOL CALLS - yielding done with content: {accumulated_content[:200]}")
            yield {"type": "done", "content": accumulated_content, "reasoning": accumulated_reasoning}


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def complete_chat_with_tools(
    provider: str,
    model: str,
    messages: list,
    tools: list,
    temperature: float = 0.3,
    api_key: str = "",
) -> dict:
    if provider == "llamacpp":
        from routes.llamacpp_route import ensure_llamacpp_model
        status = ensure_llamacpp_model(model)
        if status.get("error"):
            return {"type": "content", "data": f"ERR: {status['error']}", "reasoning": ""}
    messages = truncate_messages(messages)
    messages = convert_to_multimodal(messages)
    # Sanitiza mensagens para garantir que content nunca seja None
    for m in messages:
        if "content" not in m or m["content"] is None:
            m["content"] = ""
    if provider == "ollama" and _is_multimodal(messages):
        native_msgs = _convert_to_ollama_native(messages)
        content = await _ollama_chat_complete(model, native_msgs, temperature)
        return {"type": "content", "data": content, "reasoning": ""}
    client = get_client(provider, api_key)
    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=2048, stream=False)
    if tools:
        if provider == "ollama" and _is_vision_model(model):
            tools = []  # Modelos de visao no Ollama nao suportam tool calling
    if tools:
        kwargs["tools"] = tools
    try:
        resp = await client.chat.completions.create(**kwargs)
    except json.JSONDecodeError as e:
        print(f"[LLM] JSONDecodeError na resposta do LLM ({provider}/{model}): {e}")
        return {"type": "content", "data": f"ERR: Resposta malformada do LLM: {e}", "reasoning": ""}
    msg = resp.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning_content", None) or ""
    if msg.tool_calls:
        parsed_tool_calls = []
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"[LLM] JSONDecodeError ao parsear tool_call arguments: {e}")
                args = {}
            parsed_tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": json.dumps(args),
                },
            })
        return {
            "type": "tool_calls",
            "data": parsed_tool_calls,
            "content": content,
            "reasoning": reasoning,
        }
    return {"type": "content", "data": content, "reasoning": reasoning}


def build_user_content(text: str, images: list[str] = None) -> str | list:
    """Monta o conteudo do usuario no formato multimodal da OpenAI se houver imagens."""
    if not images:
        return text
    parts = []
    if text:
        parts.append({"type": "text", "text": text})
    for b64 in images:
        # Remove prefixo data:image/...;base64, se presente
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return parts


def build_messages(system: str, user: str, history: list[str] = None, images: list[str] = None) -> list:
    msgs = [{"role": "system", "content": system}]
    if history:
        for h in history:
            msgs.append({"role": "user", "content": h})
    msgs.append({"role": "user", "content": build_user_content(user, images)})
    return msgs


def build_conversation_messages(system: str, user: str, history_pairs: list[dict] = None, max_pairs: int = 10, images: list[str] = None) -> list:
    """
    Constroi mensagens preservando o contexto completo da conversa.
    history_pairs: lista de dicionarios [{"role": "user"|"assistant", "content": "..."}]
    """
    msgs = [{"role": "system", "content": system}]
    if history_pairs:
        # Filtra apenas tool calls JSON (nao action_cards)
        clean = []
        for h in history_pairs:
            content = h.get("content", "")
            if not content:
                continue
            try:
                parsed = json.loads(content.strip())
                if isinstance(parsed, dict) and ("tool" in parsed or "name" in parsed):
                    continue
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
            clean.append(h)
        for h in clean[-max_pairs * 2:]:  # max_pairs * 2 = user + assistant
            content = h["content"] or ""
            # Para tool results, mantem mais contexto (atel 8000 chars)
            if h["role"] == "tool":
                msgs.append({"role": h["role"], "content": content[:8000]})
            else:
                msgs.append({"role": h["role"], "content": content[:3000]})
    msgs.append({"role": "user", "content": build_user_content(user, images)})
    return msgs
