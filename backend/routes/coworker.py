import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.llm_native import complete_chat_with_tools, stream_chat_with_tools
from tools.executor import execute_tool
from tools.function_defs import TOOLS

router = APIRouter()

COWORKER_MODEL = "claude-sonnet-4-6"

COWORKER_SYSTEM_PROMPT = """Você é Claude, um assistente de IA que trabalha como coworker do usuário em tarefas de engenharia de software. Você é especialista em:

- Desenvolvimento full-stack (Python, TypeScript, React, FastAPI, etc.)
- Arquitetura de software e design de sistemas
- Debugging e solução de problemas
- Code review e melhores práticas
- Refatoração e otimização de código
- Leitura, escrita, edição e exclusão de arquivos no projeto

REGRAS:
1. Seja proativo - execute ao inves de apenas explicar
2. Use as ferramentas disponiveis para ler, criar, editar e deletar arquivos
3. Explique seu raciocínio de forma clara
4. Responda em português
5. Considere segurança, performance e manutenibilidade
6. Trabalhe de forma colaborativa - pergunte quando precisar de mais contexto"""

COWORKER_TOOL_PROMPT = """

Você tem acesso TOTAL ao sistema de arquivos do projeto.
Diretório atual: {root_info}

Use as ferramentas para:
- Ler arquivos e diretórios
- Criar e editar arquivos
- Executar comandos no terminal
- Buscar texto em arquivos
- Criar e deletar diretórios

Sempre que precisar interagir com o projeto, use as ferramentas nativas."""


class CoworkerRequest(BaseModel):
    task: str
    context: str = ""
    provider: str = "openclaude"
    model: str = COWORKER_MODEL
    temperature: float = 0.3
    api_key: str = ""
    stream: bool = True
    root: str = ""
    path: str = ""


class CoworkerResponse(BaseModel):
    answer: str
    provider: str
    model: str


@router.post("/coworker/chat")
async def coworker_chat(req: CoworkerRequest):
    try:
        context_parts = [COWORKER_SYSTEM_PROMPT]
        root_info = ""

        if req.root:
            root_info = req.root
        else:
            from core.config import get_base_dir
            root_info = str(get_base_dir())

        if req.context:
            context_parts.append(f"\nContexto do projeto:\n{req.context[:4000]}")
        context_parts.append(f"\n{COWORKER_TOOL_PROMPT.format(root_info=root_info)}")
        if req.path:
            context_parts.append(f"Arquivo atual: {req.path}")

        system = "\n".join(context_parts)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": req.task},
        ]

        # Agent loop with tool calling
        max_steps = 15
        for step in range(max_steps):
            result = await complete_chat_with_tools(
                req.provider, req.model, messages, TOOLS, req.temperature, api_key=req.api_key
            )

            if result["type"] == "tool_calls":
                for tc in result["data"]:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_params = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_params = {}
                    try:
                        tool_result = await execute_tool(tool_name, tool_params)
                        assistant_msg = {"role": "assistant", "content": "", "tool_calls": [tc]}
                        messages.append(assistant_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False),
                        })
                    except Exception as e:
                        messages.append({"role": "assistant", "content": "", "tool_calls": [tc]})
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
            return CoworkerResponse(answer=answer or "Pronto.", provider=req.provider, model=req.model)

        return CoworkerResponse(answer="Número máximo de passos atingido.", provider=req.provider, model=req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/coworker/stream")
async def coworker_stream(req: CoworkerRequest):
    async def generate():
        try:
            context_parts = [COWORKER_SYSTEM_PROMPT]
            root_info = ""

            if req.root:
                root_info = req.root
            else:
                from core.config import get_base_dir
                root_info = str(get_base_dir())

            if req.context:
                context_parts.append(f"\nContexto do projeto:\n{req.context[:4000]}")
            context_parts.append(f"\n{COWORKER_TOOL_PROMPT.format(root_info=root_info)}")
            if req.path:
                context_parts.append(f"Arquivo atual: {req.path}")

            system = "\n".join(context_parts)
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": req.task},
            ]

            max_steps = 15
            for step in range(max_steps):
                yield json.dumps({"type": "thinking", "content": f"[Passo {step + 1}/{max_steps}]"}) + "\n"

                full_answer = ""
                collected_tools = []

                async for chunk in stream_chat_with_tools(
                    req.provider, req.model, messages, TOOLS, req.temperature, api_key=req.api_key
                ):
                    if chunk["type"] == "content":
                        full_answer += chunk["data"]
                        yield json.dumps({"type": "token", "content": chunk["data"]}) + "\n"
                    elif chunk["type"] == "tool_calls":
                        collected_tools = chunk["data"]

                if collected_tools:
                    for tc in collected_tools:
                        tool_name = tc["function"]["name"]
                        try:
                            tool_params = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            tool_params = {}
                        yield json.dumps({"type": "tool_start", "tool": tool_name, "params": tool_params}) + "\n"
                        try:
                            tool_result = await execute_tool(tool_name, tool_params)
                            messages.append({"role": "assistant", "content": full_answer or "", "tool_calls": [tc]})
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            })
                            yield json.dumps({"type": "tool_end", "tool": tool_name, "result": tool_result}) + "\n"
                        except Exception as e:
                            yield json.dumps({"type": "tool_error", "tool": tool_name, "error": str(e)}) + "\n"
                            messages.append({"role": "assistant", "content": full_answer or "", "tool_calls": [tc]})
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps({"error": str(e)}, ensure_ascii=False),
                            })
                    continue

                # Final answer
                answer = full_answer.strip()
                if answer.startswith("FINAL:"):
                    answer = answer[6:].strip()
                if not answer:
                    answer = "Pronto."
                yield json.dumps({"type": "done", "answer": answer}) + "\n"
                return

            yield json.dumps({"type": "done", "answer": "Número máximo de passos atingido."}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/coworker/help")
async def coworker_help():
    return {
        "name": "Claude Coworking Agent",
        "version": "2.0",
        "description": "Agente coworker com tool calling para engenharia de software colaborativa",
        "provider": "openclaude",
        "model": COWORKER_MODEL,
        "capabilities": [
            "Tool calling para ler, criar, editar e deletar arquivos",
            "Execução de comandos no terminal",
            "Busca de texto em arquivos",
            "Streaming de respostas em tempo real",
            "Contexto completo da conversa",
        ],
        "endpoints": {
            "POST /coworker/chat": "Chat completo com tool calling",
            "POST /coworker/stream": "Streaming de tokens com tool calling",
        },
    }
