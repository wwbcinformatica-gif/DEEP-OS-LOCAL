import json
import re

from fastapi import APIRouter, HTTPException

from agents.loop import run_agent
from agents.orchestrator import classify_task, get_agent_config, resolve_model_for_task
from core.llm_native import build_messages, complete_chat
from core.models import AgentTask, Message
from core.prompts import MOOD_INSTRUCTIONS
from core.rag import get_rag_context
from tools.executor import execute_tool

router = APIRouter()


@router.post("/agent/execute")
async def agent_execute(task: AgentTask):
    try:
        if task.agent_type == "auto":
            task.agent_type = classify_task(task.task)
        agent_config = get_agent_config(task.agent_type)
        personality = agent_config.get("system_prompt", "")
        routed_provider, routed_model = resolve_model_for_task(task.agent_type)
        result = await run_agent(
            task.task, routed_provider, routed_model,
            task.temperature, personality=personality,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def extract_tool(text: str) -> dict | None:
    text = text.strip()
    match = re.search(r'\{[^{}]*"tool"[^{}]*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group())
        if "tool" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass
    return None


@router.post("/agent/chat")
async def agent_chat(msg: Message):
    try:
        instruction = msg.system_prompt if msg.system_prompt else MOOD_INSTRUCTIONS.get(msg.mood, MOOD_INSTRUCTIONS["opencode"])
        context = get_rag_context(msg.user)
        is_code = any(x in msg.user.lower() for x in ["arquivo", "file", "codigo", "abra", "open"])

        system = (
            instruction + "\n\n"
            "Contexto: " + context + "\n\n"
            "Regras:\n"
            "1. Para usar ferramentas, responda APENAS com JSON: {\"tool\":\"nome\",\"params\":{...}}\n"
            "2. Para resposta final: FINAL: sua resposta\n"
            "3. Nao explique antes de agir\n"
            "4. Responda em portugues"
        )

        history = []
        for _ in range(10):
            user_msg = (
                "HISTORICO:\n" +
                ("\n".join(history[-10:]) if history else "Nenhuma acao.") +
                f"\n\nUSUARIO: {msg.user}"
            )
            messages = build_messages(system, user_msg)
            response = await complete_chat(msg.provider, msg.model, messages, msg.temperature)
            response = response.strip()

            if response.startswith("FINAL:"):
                answer = response[6:].strip()
                from database.connection import get_conn
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("INSERT INTO history (question, answer) VALUES (?, ?)", (msg.user, answer))
                conn.commit()
                conn.close()
                return {"answer": answer, "steps": len(history) + 1}

            cmd = extract_tool(response)
            if cmd:
                try:
                    tool_result = await execute_tool(cmd.get("tool", ""), cmd.get("params", {}))
                    history.append(
                        f"Tool: {cmd.get('tool')} -> "
                        f"{json.dumps(tool_result, ensure_ascii=False)[:500]}"
                    )
                except Exception as e:
                    history.append(f"Erro: {str(e)}")
            else:
                history.append(f"Resposta do modelo: {response[:200]}")

        return {"answer": "Numero maximo de iteracoes atingido.", "steps": len(history)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/help")
async def agent_help():
    return {
        "name": "OpenCode Agent System",
        "version": "2.0",
        "description": "Sistema de agentes autonomos estilo OpenCode",
        "agents": {
            "jarvis": "Assistente geral",
            "architect": "Arquiteto de software e sistemas",
            "debugger": "Debugger e solucionador de problemas",
            "planner": "Planejador de tarefas e projetos",
            "coder": "Programador especialista",
        },
        "commands": {
            "agent/execute": "POST - Executa tarefa autonoma (multi-step)",
            "agent/chat": "POST - Chat com agente com ferramentas",
        },
    }
