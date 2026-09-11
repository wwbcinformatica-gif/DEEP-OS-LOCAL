"""
DEEP-OS â€” Agent Loop
=============================
Refactored to use the Lifecycle Engine (state machine).

Implements: CALL_MODEL -> CHECK_RESPONSE -> CLASSIFY_FINISH -> TOOL/COLUMN/FINAL

Integrates:
- Elastic Memory: RAG recall at START, indexing at FINAL
- Anti-Loop Protection: via LifecycleConfig
- Context Compression: via LifecycleEngine
"""

from typing import Any

from core.agent_config import load_agent_config
from core.lifecycle import LifecycleConfig, run_lifecycle
from core.spiral_memory import (
    deve_refrescar,
    extrair_snapshot,
    formatar_snapshot_para_prompt,
    gerar_snapshot_com_llm,
)
from core.state_machine import ModelResponse
from memory.brain import aprender_com_a_tarefa
from memory.elastic_memory import (
    format_memories_for_prompt,
    index_task_memory,
    recall_relevant_memories,
)
from tools.executor import execute_tool
from tools.function_defs import TOOLS

AGENT_SYSTEM_PROMPT = """
Voce e um agente autonomo de engenharia de software.

REGRAS:
1. Aja agora. Use as ferramentas diretamente — nao planeje, nao explique o que vai fazer.
2. Proibido usar formatacao de passos. Nunca escreva "[Passo X/Y]", "[Step 1]", "1/5" ou similar.
3. Ferramentas executam em silencio em segundo plano. Nao anuncie cada acao.
4. Quando a tarefa estiver completa, apresente direto: o resultado final + um breve resumo do que foi feito.
5. Tom direto e agil — sem burocracia, sem explicacoes longas.
6. Responda em portugues.
7. Se um comando bash falhar ou retornar vazio, MUDE DE ESTRATEGIA imediatamente — nao repita o mesmo comando.
8. Nunca execute o mesmo comando bash duas vezes seguidas. Se o comando ja foi executado no passo anterior, escolha outra abordagem.

CONTEXTO DO PROJETO:
{project_context}

PERSONALIDADE: {personality}
TAREFA: {task}
{rag_context}
"""


def _get_project_context() -> str:
    """Get project context for system prompt - project structure and key files."""
    from pathlib import Path
    
    try:
        workspace = Path(__file__).resolve().parent.parent.parent
        name = workspace.name
        
        # Get top-level structure
        dirs = []
        files = []
        for item in workspace.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                dirs.append(f"  📁 {item.name}/")
            elif item.is_file() and item.suffix in ('.md', '.yaml', '.json', '.py', '.ts', '.tsx', '.bat'):
                files.append(f"  📄 {item.name}")
        
        # Get key config info
        config_path = workspace / "config.yaml"
        config_info = ""
        if config_path.exists():
            config_info = "\nConfig: config.yaml"
        
        context = f"""Projeto: {name}
Diretorio: {workspace}

Estrutura:
{chr(10).join(dirs[:10])}
{chr(10).join(files[:5])}

O projeto DEEP-OS e um Sistema Operacional de Agentes de IA (backend Python FastAPI + frontend React/TypeScript).

VOCÊ TEM ACESSO TOTAL A ESTE PROJETO!
Use as ferramentas para navegar e manipular:
- explorer(path="{workspace}") para ver pastas
- read(path="{workspace}/arquivo.py") para ler arquivos
- bash(command="dir {workspace}") para listar contents
- bash(command="tree /F {workspace}") para ver árvore completa

NÃO DIGA QUE NÃO TEM ACESSO - VOCÊ TEM! Use as ferramentas diretamente."""
        
        return context
    except Exception as e:
        return f"Projeto: DEEP-OS (erro ao carregar contexto: {e})"


async def run_agent(
    task: str,
    provider: str,
    model: str,
    temperature: float = 0.3,
    max_steps: int = None,
    personality: str = "Voce e um engenheiro de software eficiente e objetivo.",
    keeper_provider: str = "",
    keeper_model: str = "",
    keeper_api_key: str = "",
):
    cfg = load_agent_config()
    max_tool_steps = max_steps if max_steps is not None else cfg.agent.max_tool_steps

    # â”€â”€ Long-Term Memory: Recall relevant memories at START â”€â”€
    rag_context_block = ""
    try:
        past_memories = await recall_relevant_memories(task, top_k=5)
        if past_memories:
            rag_context_block = format_memories_for_prompt(past_memories)
            print(f"[ELASTIC-MEMORY] ðŸ” Recuperadas {len(past_memories)} memórias relevantes para a tarefa.")
        else:
            print("[ELASTIC-MEMORY] â„¹ï¸ Nenhuma memória relevante encontrada.")
    except Exception as e:
        print(f"[ELASTIC-MEMORY] âš ï¸ Falha no recall: {e}")

    async def call_model(messages: list) -> ModelResponse:
        from core.llm_native import complete_chat_with_tools
        # Verifica se o modelo suporta tool calling
        from routes.chat import supports_tools
        effective_tools = TOOLS if supports_tools(provider, model) else []
        result = await complete_chat_with_tools(provider, model, messages, effective_tools, temperature)
        return ModelResponse(
            type=result.get("type", "content"),
            data=result.get("data", ""),
            content=result.get("content", ""),
            reasoning=result.get("reasoning", ""),
            tool_calls=result.get("data", []) if result.get("type") == "tool_calls" else [],
        )

    async def execute_tool_fn(tool_name: str, params: dict) -> Any:
        try:
            import asyncio
            return await asyncio.wait_for(execute_tool(tool_name, params), timeout=60.0)
        except asyncio.TimeoutError:
            return {"error": f"Ferramenta {tool_name} excedeu o tempo limite de 60s"}
        except Exception as e:
            return {"error": str(e)}

    use_keeper = bool(keeper_provider and keeper_model)

    async def spiral_refresh(step: int, msgs: list, logs: list) -> str | None:
        if not logs:
            return None

        if use_keeper:
            snapshot = await gerar_snapshot_com_llm(msgs, logs, keeper_provider, keeper_model, keeper_api_key)
            if snapshot:
                return snapshot

        snapshot = extrair_snapshot(msgs, logs)
        return formatar_snapshot_para_prompt(snapshot)

    spiral_refresh._last = 0

    config = LifecycleConfig(
        max_tool_steps=max_tool_steps,
        max_api_retries=3,
        tool_timeout=120.0,
        consecutive_tool_limit=15,
        # Anti-Loop Protection
        anti_loop_enabled=True,
        max_consecutive_state_hash=4,
        circuit_breaker_max_think=8,
        circuit_breaker_max_tools=40,
        circuit_breaker_max_total=50,
        # Context Compression
        context_compression_enabled=True,
        max_context_tokens=200000,
        # Spiral Memory (DEEP-OS)
        spiral_memory_enabled=True,
        spiral_memory_interval=4,
        on_spiral_refresh=spiral_refresh,
    )

    # Get project context for system prompt
    project_context = _get_project_context()

    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT.format(
            personality=personality,
            task=task,
            project_context=project_context,
            rag_context=rag_context_block,
        )},
        {"role": "user", "content": task},
    ]

    brain_log = []

    async for event in run_lifecycle(
        messages=messages,
        config=config,
        call_model=call_model,
        call_model_stream=None,
        execute_tool_fn=execute_tool_fn,
        supports_streaming=False,
    ):
        if event["type"] == "tool_start":
            brain_log.append({
                "step": event.get("step", 0),
                "action": event["tool"],
                "params": event["params"],
            })
        elif event["type"] == "tool_end":
            if brain_log:
                brain_log[-1]["result"] = event.get("result", {})
        elif event["type"] == "tool_error":
            if brain_log:
                brain_log[-1]["result"] = {"error": event.get("error", "")}
        elif event["type"] == "done":
            answer = event.get("answer", "")
            tool_logs = event.get("tool_logs", [])
            status = event.get("status", "completed")
            brain_log_final = tool_logs or brain_log

            # â”€â”€ Long-Term Memory: Index successful task at FINAL â”€â”€
            if status == "completed" and answer and answer != "Pronto.":
                try:
                    tools_used = list({log.get("tool", "") for log in brain_log_final if log.get("tool")})
                    index_result = await index_task_memory(
                        task=task,
                        solution_summary=answer[:1000],
                        tools_used=tools_used,
                        lessons_learned=f"Tarefa concluída com {len(brain_log_final)} passos. Status: {status}",
                    )
                    if index_result.get("status") == "indexed":
                        print(f"[ELASTIC-MEMORY] ðŸ§  Experiência indexada: hash={index_result.get('hash')}")
                except Exception as e:
                    print(f"[ELASTIC-MEMORY] âš ï¸ Falha ao indexar: {e}")

                # Mantém o brain.py original para retrocompatibilidade
                await aprender_com_a_tarefa(task, brain_log_final, provider, model)

            # â”€â”€ Anti-Padrao: Registra falha na memoria de longo prazo â”€â”€
            elif status in ("circuit_breaker", "failed", "max_steps"):
                try:
                    from memory.elastic_memory import index_failure_lesson
                    tools_used = list({log.get("tool", "") for log in brain_log_final if log.get("tool")})
                    error_detail = ""
                    for log in reversed(brain_log_final):
                        result = log.get("result", {})
                        if isinstance(result, dict) and result.get("error"):
                            error_detail = result["error"][:200]
                            break

                    await index_failure_lesson(
                        task=task,
                        failure_reason=answer[:500] if answer else "Falha desconhecida",
                        tools_attempted=tools_used,
                        error_summary=f"Status: {status}. {error_detail}",
                    )
                    print(f"[ELASTIC-MEMORY] ðŸš« Anti-padrao registrado para tarefa: {task[:60]}")
                except Exception as e:
                    print(f"[ELASTIC-MEMORY] âš ï¸ Falha ao registrar anti-padrao: {e}")

            return {
                "status": status,
                "steps": event.get("steps", 0),
                "result": answer,
                "log": brain_log_final,
                "compression_count": getattr(config, 'compression_count', 0),
                "circuit_breaker_stats": {},
            }

    return {
        "status": "failed",
        "steps": 0,
        "result": "Ciclo de vida encerrado inesperadamente.",
        "log": brain_log,
    }
