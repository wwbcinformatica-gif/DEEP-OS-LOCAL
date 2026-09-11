"""
DEEP-OS â€” Lifecycle Engine
==================================
Orchestrates the complete agent execution cycle using the state machine.

Handles:
- API error retry with exponential backoff
- Streaming response accumulation
- Tool call validation + execution + observation append
- Content classification (response vs think-only)
- Think-only nudge mechanism
- Truncated / filtered state handling
- Anti-Loop: State Hash Counter + Circuit Breaker + Frustration Nudge
- Context Compression: Sumarização Recursiva quando contexto estoura
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from core.state_machine import (
    CircuitBreaker,
    ContentCategory,
    FinishReason,
    FRUSTRATION_NUDGE,
    LifecycleEvent,
    ModelResponse,
    State,
    StateHashTracker,
    build_frustration_nudge_with_context,
    classify_content,
    classify_finish_reason,
    extract_observation,
    log_transition,
    validate_tool_call,
)
import re

from core.context_compression import compress_context

_log = logging.getLogger("wbc.lifecycle")


# â”€â”€â”€ Planning Toll Enforcement â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_PLANNING_TOLL_NUDGE = (
    "ERRO DE PROTOCOLO CRITICO: Voce violou o Mandamento No 9. "
    "Voce tentou executar uma ferramenta sem antes apresentar seu raciocinio "
    "e seu checklist visual para o usuario. Pare tudo.\n\n"
    "PRIMEIRO apresente seu raciocinio, desenhe a lista de checkboxes com "
    "as metas da tarefa no formato:\n"
    "  - [ ] Meta 1\n"
    "  - [ ] Meta 2\n\n"
    "E inclua o JSON task_plan:\n"
    '{"type":"task_plan","steps":["Meta 1","Meta 2"]}\n\n'
    "SO DEPOIS envie os comandos das ferramentas. "
    "Esta e a unica forma de prosseguir."
)


def _has_checkboxes(content: str) -> bool:
    """Verifica se o conteudo contem ao menos 2 checkboxes Markdown (- [ ] ou - [x])."""
    if not content:
        return False
    matches = re.findall(r'- \[[ x~]\]', content)
    return len(matches) >= 2


def _has_task_plan_json(content: str) -> bool:
    """Verifica se o conteudo contem um JSON task_plan com campo 'steps'."""
    if not content:
        return False
    return bool(re.search(r'\{\s*"type"\s*:\s*"task_plan"', content))


# â”€â”€â”€ Graceful Failure Diagnostic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _compile_failure_diagnostics(state: LifecycleState, violation: str) -> dict:
    """
    Compila diagnostico estruturado do motivo da falha para o usuario.
    Extrai dos tool_logs e mensagens recentes o contexto do impasse.
    """
    recent_tools = state.tool_logs[-10:] if state.tool_logs else []
    recent_errors = []
    tools_tried = set()
    failed_tools = set()

    for log in recent_tools:
        tool_name = log.get("tool", "?")
        tools_tried.add(tool_name)
        result = log.get("result", {})
        if isinstance(result, dict) and result.get("error"):
            failed_tools.add(tool_name)
            recent_errors.append({
                "tool": tool_name,
                "params": log.get("params", {}),
                "error": result["error"][:200],
            })

    # Ultimo raciocinio do agente
    last_reasoning = state.accumulated_reasoning or state.accumulated_content or ""
    reasoning_excerpt = last_reasoning[:300] if last_reasoning else "(sem raciocinio registrado)"

    return {
        "violation": violation,
        "steps_executed": state.step,
        "tools_tried": list(tools_tried),
        "failed_tools": list(failed_errors := recent_errors),
        "last_reasoning": reasoning_excerpt,
        "think_only_count": state.think_only_count,
        "tool_call_count": state.circuit_breaker._tool_call_count,
    }


def _build_graceful_failure_message(diagnostics: dict) -> str:
    """
    Gera mensagem amigavel ao usuario explicando onde o agente travou
    e sugerindo acao humana.
    """
    violation = diagnostics.get("violation", "limite excedido")
    tools = diagnostics.get("tools_tried", [])
    errors = diagnostics.get("failed_tools", [])
    steps = diagnostics.get("steps_executed", 0)
    reasoning = diagnostics.get("last_reasoning", "")

    # Monta lista de ferramentas que falharam
    error_details = []
    for err in errors[:3]:
        tool = err.get("tool", "?")
        params = err.get("params", {})
        error_msg = err.get("error", "")
        param_summary = ""
        if isinstance(params, dict):
            for k in ("command", "path", "code", "pattern"):
                if k in params:
                    param_summary = f"{k}={str(params[k])[:40]}"
                    break
        error_details.append(f"  - {tool}({param_summary}): {error_msg[:80]}")

    error_block = "\n".join(error_details) if error_details else "  (nenhum erro especifico registrado)"

    message = (
        f"Nao consegui concluir a tarefa apos {steps} iteracoes.\n\n"
        f"**Motivo:** {violation}\n\n"
        f"**Ferramentas utilizadas:** {', '.join(tools) if tools else 'nenhuma'}\n\n"
        f"**Erros encontrados:**\n{error_block}\n\n"
        f"**O que tentei:** {reasoning[:200]}\n\n"
        "**Sugestoes:**\n"
        "1. Verifique se os dados de entrada estao corretos (caminhos, permissoes, argumentos).\n"
        "2. Reformule o comando com parametros diferentes.\n"
        "3. Tente abordar o problema por outra angulo (ex: usar ferramenta de leitura ao inves de escrita).\n"
        "4. Se o problema persistir, forneca mais contexto sobre o ambiente ou o objetivo."
    )
    return message


@dataclass
class LifecycleConfig:
    max_tool_steps: int = 200
    max_api_retries: int = 3
    max_think_only_loops: int = 5
    tool_timeout: float = 120.0
    consecutive_tool_limit: int = 15
    api_retry_base_delay: float = 1.0
    api_retry_backoff: float = 2.0
    # Anti-Loop Protection
    anti_loop_enabled: bool = True
    max_consecutive_state_hash: int = 4
    circuit_breaker_max_think: int = 8
    circuit_breaker_max_tools: int = 40
    circuit_breaker_max_total: int = 50
    # Context Compression
    context_compression_enabled: bool = True
    max_context_tokens: int = 200000
    # Planning Toll Enforcement
    planning_enforced: bool = False
    planning_check_steps: int = 1
    # Spiral Memory (DEEP-OS)
    spiral_memory_enabled: bool = False
    spiral_memory_interval: int = 4
    on_spiral_refresh: Callable[[int, list, list], Awaitable[str | None]] | None = None


@dataclass
class LifecycleState:
    current_state: State = State.START
    step: int = 0
    messages: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    tool_logs: list = field(default_factory=list)
    events: list = field(default_factory=list)
    accumulated_content: str = ""
    accumulated_reasoning: str = ""
    collected_tool_calls: list = field(default_factory=list)
    consecutive_tool_calls: int = 0
    think_only_count: int = 0
    checklist_nudge_count: int = 0
    api_retry_count: int = 0
    last_bash_command: str = ""
    raw_finish_reason: str = ""
    # Anti-Loop Protection
    state_hash_tracker: StateHashTracker = field(default_factory=StateHashTracker)
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    # Context Compression
    compression_applied: bool = False
    compression_count: int = 0
    # Planning Toll Enforcement
    has_presented_plan: bool = False

    def transition(self, to: State, detail: str = ""):
        prev = self.current_state
        self.current_state = to
        log_transition(prev, to, detail, self.step)
        self.events.append(LifecycleEvent(state=to, detail=detail, step=self.step))

    def append_observation(self, role: str, content: str):
        self.observations.append({"role": role, "content": content})

    def reset_stream_accumulators(self):
        self.accumulated_content = ""
        self.accumulated_reasoning = ""
        self.collected_tool_calls = []


LifecycleToolExecutor = Callable[[str, dict], Awaitable[Any]]
LifecycleModelCaller = Callable[[list], Awaitable[ModelResponse]]
LifecycleStreamCaller = Callable[[list], AsyncGenerator[dict, None]]
LifecycleStreamFinished = Callable[[str, str, list], None]


async def run_lifecycle(
    messages: list,
    config: LifecycleConfig,
    call_model: LifecycleModelCaller,
    call_model_stream: LifecycleStreamCaller | None,
    execute_tool_fn: LifecycleToolExecutor,
    on_stream_token: Callable[[str], None] | None = None,
    on_state_change: Callable[[LifecycleEvent], None] | None = None,
    on_tool_start: Callable[[str, dict], None] | None = None,
    on_tool_end: Callable[[str, Any], None] | None = None,
    is_bash_repeated: Callable[[str], bool] | None = None,
    should_force_final: Callable[[int], bool] | None = None,
    supports_streaming: bool = True,
) -> AsyncGenerator[dict, None]:
    """
    Main lifecycle loop. Yields events as dicts for streaming consumers.

    Yields event types:
        "state_change"   - state transition
        "thinking"       - progress message
        "thinking_start" - step start
        "token"          - streaming token
        "tool_start"     - tool execution begin
        "tool_end"       - tool execution complete
        "tool_error"     - tool execution error
        "done"           - cycle complete
        "error"          - fatal error
    """
    state = LifecycleState(messages=list(messages))
    state.circuit_breaker = CircuitBreaker(
        max_think_only=config.circuit_breaker_max_think,
        max_tool_calls=config.circuit_breaker_max_tools,
        max_total_iterations=config.circuit_breaker_max_total,
    )

    while state.step < config.max_tool_steps:
        state.step += 1

        if should_force_final and should_force_final(state.consecutive_tool_calls):
            state.messages.append({
                "role": "system",
                "content": (
                    "[SISTEMA] Voce ja executou varias ferramentas seguidas. "
                    "APRESENTE O RESUMO DO PROGRESSO ate aqui (o que ja foi feito, o que falta). "
                    "DEPOIS, PERGUNTE AO USUARIO como ele deseja prosseguir. "
                    "NÃO finalize a tarefa — apenas pouse e aguarde instruções. "
                    "O contexto sera MANTIDO para a proxima mensagem."
                ),
            })
            state.consecutive_tool_calls = 0

        # â”€â”€ Anti-Loop: Circuit Breaker check â”€â”€
        if config.anti_loop_enabled and state.circuit_breaker.is_tripped():
            violation = state.circuit_breaker.get_violation_reason()
            _log.warning(
                "[DEEP-OS] âš¡ DISJUNTOR ANTI-LOOP TRIPADO: %s (passo %d)",
                violation, state.step,
            )
            # Compila diagnostico amigavel
            diagnostics = _compile_failure_diagnostics(state, violation)
            graceful_msg = _build_graceful_failure_message(diagnostics)

            # Registra anti-padrao na memoria de longo prazo (se disponivel)
            try:
                from memory.elastic_memory import index_failure_lesson
                tools_tried = diagnostics.get("tools_tried", [])
                failed_tools = [e.get("tool", "") for e in diagnostics.get("failed_tools", [])]
                reasoning = diagnostics.get("last_reasoning", "")
                await index_failure_lesson(
                    task=f"[FALHA] {violation}",
                    failure_reason=reasoning[:500],
                    tools_attempted=tools_tried,
                    error_summary=violation,
                )
            except Exception as e:
                _log.debug("[DEEP-OS] Falha ao registrar anti-padrao: %s", e)

            state.transition(State.FAILED)
            yield {"type": "state_change", "state": State.FAILED.value, "step": state.step}
            yield {"type": "thinking", "step": state.step, "content": f"[CIRCUIT BREAKER] {violation}"}
            yield {
                "type": "done",
                "answer": graceful_msg,
                "steps": state.step,
                "status": "circuit_breaker",
                "tool_logs": state.tool_logs,
                "diagnostics": diagnostics,
            }
            return

        # â”€â”€ Context Compression â”€â”€
        if config.context_compression_enabled and not state.compression_applied:
            new_messages, was_compressed, summary = await compress_context(
                state.messages, config.max_context_tokens,
            )
            if was_compressed:
                state.messages = new_messages
                state.compression_applied = True
                state.compression_count += 1
                yield {"type": "thinking", "step": state.step, "content": f"[COMPRESSION] {summary[:200]}"}
        elif state.compression_applied and state.step > 5:
            # Permite compressão novamente após 5 passos (janela reabastece)
            state.compression_applied = False

        # â”€â”€ Spiral Memory Refresh (DEEP-OS) â”€â”€
        if config.spiral_memory_enabled and config.on_spiral_refresh:
            if state.step > 1 and (
                state.step - (getattr(state, "_last_spiral_refresh", 0)) >= config.spiral_memory_interval
            ):
                try:
                    refresh_msg = await config.on_spiral_refresh(
                        state.step, state.messages, state.tool_logs,
                    )
                    if refresh_msg:
                        state.messages.append({"role": "system", "content": refresh_msg})
                        state._last_spiral_refresh = state.step
                        _log.info(
                            "[DEEP-OS] ðŸŒ€ Refresh de memoria injetado no passo %d",
                            state.step,
                        )
                        yield {
                            "type": "thinking",
                            "step": state.step,
                            "content": f"[DEEP-OS] Memoria espiral refrescada",
                        }
                except Exception as e:
                    _log.warning("[DEEP-OS] Erro no refresh: %s", e)

        state.transition(State.CALL_MODEL)
        yield {"type": "state_change", "state": State.CALL_MODEL.value, "step": state.step}
        yield {"type": "thinking_start", "step": state.step}

        state.reset_stream_accumulators()
        response: ModelResponse | None = None
        api_error = None

        if call_model_stream and supports_streaming:
            response, api_error = await _call_model_with_stream(
                state, config, call_model_stream, on_stream_token
            )
        else:
            response, api_error = await _call_model_with_retry(
                state, config, call_model
            )
            # Sync accumulators from non-streaming response
            if response:
                state.accumulated_content = response.content or response.data or ""
                state.accumulated_reasoning = response.reasoning or ""
                state.collected_tool_calls = response.tool_calls or []

        if api_error:
            state.transition(State.API_ERROR, detail=str(api_error))
            yield {"type": "state_change", "state": State.API_ERROR.value, "step": state.step}
            yield {"type": "done", "answer": f"Erro na API: {api_error}", "steps": state.step}
            return

        if response is None:
            state.transition(State.FAILED)
            yield {"type": "state_change", "state": State.FAILED.value, "step": state.step}
            yield {"type": "done", "answer": "Modelo nao retornou resposta. Verifique a conexao e a chave da API.", "steps": state.step, "status": "failed"}
            return

        state.transition(State.CHECK_RESPONSE, detail=f"type={response.type}")
        yield {"type": "state_change", "state": State.CHECK_RESPONSE.value, "step": state.step}

        # Determine finish reason priority:
        # raw_finish_reason > response.finish_reason > tool_calls > STOP
        if state.raw_finish_reason:
            finish_reason = classify_finish_reason(state.raw_finish_reason)
        elif response.finish_reason != FinishReason.UNKNOWN:
            finish_reason = response.finish_reason
        elif response.type == "tool_calls" or response.tool_calls:
            finish_reason = FinishReason.TOOL_CALLS
        else:
            finish_reason = FinishReason.STOP

        state.transition(State.CLASSIFY_FINISH, detail=f"reason={finish_reason.value}")
        yield {"type": "state_change", "state": State.CLASSIFY_FINISH.value, "step": state.step}

        if finish_reason == FinishReason.TOOL_CALLS:
            # â”€â”€ Planning Toll Enforcement (Passo 1 e 2) â”€â”€
            if (
                config.planning_enforced
                and state.step <= config.planning_check_steps
                and not state.has_presented_plan
            ):
                combined_content = (state.accumulated_content or "") + (state.accumulated_reasoning or "")
                if _has_checkboxes(combined_content) and _has_task_plan_json(combined_content):
                    state.has_presented_plan = True
                    _log.info(
                        "[DEEP-OS] âœ… PLANNING PASS: modelo apresentou raciocinio + checkboxes + task_plan (passo %d)",
                        state.step,
                    )
                    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
                    # FORCED ITERATION BREAK: Plano apresentado, mas NAO executar
                    # ferramentas ainda. Forcar quebra para o frontend renderizar
                    # checkboxes vazios antes de iniciar execucao.
                    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
                    assistant_msg = {
                        "role": "assistant",
                        "content": state.accumulated_content or None,
                        "tool_calls": state.collected_tool_calls,
                    }
                    if state.accumulated_reasoning:
                        reasoning_block = f"<think>\n{state.accumulated_reasoning}\n</think>\n"
                        assistant_msg["content"] = reasoning_block + (assistant_msg.get("content") or "")
                    state.messages.append(assistant_msg)

                    # Injeta nudge de execucao para proxima iteracao
                    state.messages.append({
                        "role": "system",
                        "content": (
                            "[SISTEMA] Seu plano foi apresentado ao usuario com sucesso. "
                            "Agora INICIE A EXECUCAO das ferramentas na ordem do plano. "
                            "Execute a PRIMEIRA ferramenta agora."
                        ),
                    })

                    # Emitir evento de plano para o frontend
                    yield {"type": "thinking", "step": state.step, "content": "[PLAN_PRESENTED] Plano apresentado. Preparando execucao..."}
                    yield {"type": "plan_break", "step": state.step, "content": state.accumulated_content or ""}
                    # FORCAR QUEBRA - continuar para proxima iteracao (execucao)
                    continue

                else:
                    _log.warning(
                        "[DEEP-OS] ðŸš« PLANNING TOLL: modelo tentou tool call sem planejamento (passo %d). Bloqueando.",
                        state.step,
                    )
                    # Registra o assistant message original (com tool_calls) para historico
                    assistant_msg = {
                        "role": "assistant",
                        "content": state.accumulated_content or None,
                        "tool_calls": state.collected_tool_calls,
                    }
                    if state.accumulated_reasoning:
                        reasoning_block = f"<think>\n{state.accumulated_reasoning}\n</think>\n"
                        assistant_msg["content"] = reasoning_block + (assistant_msg.get("content") or "")
                    state.messages.append(assistant_msg)

                    # Injeta a mensagem de erro como system message
                    state.messages.append({
                        "role": "system",
                        "content": _PLANNING_TOLL_NUDGE,
                    })
                    yield {"type": "thinking", "step": state.step, "content": "[PLANNING TOLL] Modelo bloqueado: tool calls sem planejamento. Re-circulando..."}
                    continue

            tool_events = _handle_tool_calls(
                state, config, response, execute_tool_fn,
                on_tool_start, on_tool_end, is_bash_repeated,
            )
            async for event in tool_events:
                yield event
            continue

        elif finish_reason == FinishReason.LENGTH:
            state.transition(State.TRUNCATED)
            yield {"type": "state_change", "state": State.TRUNCATED.value, "step": state.step}
            answer = state.accumulated_content.strip() or "Resposta truncada pelo limite de tokens."
            yield {"type": "thinking", "step": state.step, "content": "[WARN] Resposta truncada (length/ max_tokens)"}
            yield {"type": "done", "answer": answer, "steps": state.step, "status": "truncated"}
            return

        elif finish_reason == FinishReason.CONTENT_FILTER:
            state.transition(State.FILTERED)
            yield {"type": "state_change", "state": State.FILTERED.value, "step": state.step}
            yield {
                "type": "done",
                "answer": "Resposta bloqueada pelo filtro de conteudo.",
                "steps": state.step,
                "status": "filtered",
            }
            return

        elif finish_reason == FinishReason.STOP:
            state.transition(State.CLASSIFY_CONTENT)
            yield {"type": "state_change", "state": State.CLASSIFY_CONTENT.value, "step": state.step}

            content_category = classify_content(
                state.accumulated_content,
                state.accumulated_reasoning,
            )

            if content_category == ContentCategory.HAS_RESPONSE:
                # ── CHECKLIST WITHOUT EXECUTION DETECTION ──
                # Models like qwen3.5 generate checklists but never emit tool_calls.
                # Detect this and force a re-call with explicit nudge.
                combined = (state.accumulated_content or "") + (state.accumulated_reasoning or "")
                has_checklist = _has_checkboxes(combined)
                has_tool_calls = bool(state.collected_tool_calls)
                tools_were_executed = bool(state.tool_logs)

                if has_checklist and not has_tool_calls and not tools_were_executed and state.checklist_nudge_count < 2:
                    _log.warning(
                        "[DEEP-OS] CHECKLIST_SEM_EXECUCAO: modelo gerou checkboxes mas NENHUMA tool call (passo %d)",
                        state.step,
                    )
                    # Append the checklist content as assistant message
                    assistant_msg = {
                        "role": "assistant",
                        "content": state.accumulated_content or None,
                    }
                    if state.accumulated_reasoning:
                        reasoning_block = f"<think>\n{state.accumulated_reasoning}\n</think>\n"
                        assistant_msg["content"] = reasoning_block + (assistant_msg.get("content") or "")
                    state.messages.append(assistant_msg)

                    # Inject explicit nudge to force tool calling
                    state.messages.append({
                        "role": "user",
                        "content": (
                            "ATENCAO: Voce apresentou um plano com checkboxes MAS NAO EXECUTOU NENHUMA FERRAMENTA. "
                            "O plano serve de nada sem execucao!\n\n"
                            "AGORA Execute IMEDIATAMENTE a primeira ferramenta do seu plano. "
                            "Use tool_call nativo — NAO descreva em texto, CHAME a ferramenta.\n"
                            "Exemplo: explorer(path=\"C:/Users\") ou bash(command=\"dir C:/Users\")\n\n"
                            "EXECUTE AGORA. NAO envie mais texto."
                        ),
                    })

                    # Reset accumulators for next iteration
                    state.reset_stream_accumulators()
                    state.has_presented_plan = True
                    state.checklist_nudge_count += 1
                    yield {"type": "thinking", "step": state.step, "content": "[CHECKLIST_SEM_EXECUCAO] Checklists detectadas sem execução. Forçando tool call..."}
                    continue

                state.transition(State.FINAL)
                yield {"type": "state_change", "state": State.FINAL.value, "step": state.step}
                answer = state.accumulated_content.strip()
                if not answer:
                    answer = "Pronto."
                yield {"type": "done", "answer": answer, "steps": state.step, "tool_logs": state.tool_logs}
                return

            elif content_category == ContentCategory.ONLY_THINK:
                state.think_only_count += 1
                state.transition(State.THINK_ONLY)
                yield {"type": "state_change", "state": State.THINK_ONLY.value, "step": state.step}

                # â”€â”€ Anti-Loop: Circuit Breaker para THINK_ONLY â”€â”€
                if config.anti_loop_enabled:
                    cb_count = state.circuit_breaker.record_think_only()
                    _log.info(
                        "[DEEP-OS] ðŸ”„ THINK_ONLY #%d/%d (circuit breaker)",
                        cb_count, state.circuit_breaker.max_think_only,
                    )

                    # State Hash: registra padrão de raciocínio
                    h = state.state_hash_tracker.record_state(
                        state.accumulated_reasoning or state.accumulated_content,
                        tool_name="",
                    )
                    if state.state_hash_tracker.is_loop_detected():
                        consec = state.state_hash_tracker.get_consecutive_count()
                        _log.warning(
                            "[DEEP-OS] ðŸ” LOOP DETECTADO: mesmo padrão de raciocínio repetido %d vezes (hash: %s)",
                            consec, h,
                        )
                        # Gera nudge contextualizado com historico de acoes
                        recent_actions = [
                            {"action": "think_only", "result": {}}
                        ] + state.tool_logs[-4:]
                        contextual_nudge = build_frustration_nudge_with_context(
                            recent_actions,
                            reason=f"Raciocinio repetido {consec} vezes",
                        )
                        state.messages.append({
                            "role": "system",
                            "content": contextual_nudge,
                        })
                        state.state_hash_tracker.reset()
                        state.think_only_count = 0
                        yield {"type": "thinking", "step": state.step, "content": "[ANTI-LOOP] Nudge contextualizado injetado â€” padrao de raciocinio quebrado"}
                        continue

                if state.think_only_count > config.max_think_only_loops:
                    violation = f"THINK_ONLY excedido ({state.think_only_count}/{config.max_think_only_loops})"
                    diagnostics = _compile_failure_diagnostics(state, violation)
                    graceful_msg = _build_graceful_failure_message(diagnostics)
                    state.transition(State.FAILED)
                    yield {"type": "state_change", "state": State.FAILED.value, "step": state.step}
                    yield {
                        "type": "done",
                        "answer": graceful_msg,
                        "steps": state.step,
                        "status": "failed",
                        "diagnostics": diagnostics,
                    }
                    return

                think_msg = (
                    f"[THINK_ONLY {state.think_only_count}/{config.max_think_only_loops}] "
                    "Resposta contem apenas raciocinio. Enviando nudge..."
                )
                yield {"type": "thinking", "step": state.step, "content": think_msg}

                nudge_content = state.accumulated_reasoning or state.accumulated_content
                state.messages.append({
                    "role": "assistant",
                    "content": f"<think>\n{nudge_content}\n</think>" if nudge_content else None,
                })
                state.messages.append({
                    "role": "user",
                    "content": (
                        "[SISTEMA] Seu raciocinio interno foi registrado. "
                        "Agora apresente a RESPOSTA FINAL ao usuario. "
                        "Nao use <think> tags â€” escreva diretamente a resposta."
                    ),
                })
                continue

        else:
            state.transition(State.FINAL)
            answer = state.accumulated_content.strip() or "Pronto."
            yield {"type": "done", "answer": answer, "steps": state.step, "tool_logs": state.tool_logs}
            return

    yield {
        "type": "done",
        "answer": f"Limite de {config.max_tool_steps} passos atingido.",
        "steps": state.step,
        "tool_logs": state.tool_logs,
        "status": "max_steps",
    }


async def _call_model_with_retry(
    state: LifecycleState,
    config: LifecycleConfig,
    call_model: LifecycleModelCaller,
) -> tuple[ModelResponse | None, str | None]:
    delay = config.api_retry_base_delay
    for attempt in range(1, config.max_api_retries + 1):
        try:
            response = await call_model(state.messages)
            if response.error:
                raise Exception(response.error)
            return response, None
        except Exception as e:
            state.api_retry_count += 1
            _log.warning(
                "[DEEP-OS] API_ERROR tentativa %d/%d: %s",
                attempt, config.max_api_retries, e,
            )
            if attempt < config.max_api_retries:
                await asyncio.sleep(delay)
                delay *= config.api_retry_backoff
            else:
                return None, str(e)
    return None, "Max retries exceeded"


async def _call_model_with_stream(
    state: LifecycleState,
    config: LifecycleConfig,
    call_model_stream: LifecycleStreamCaller,
    on_stream_token: Callable[[str], None] | None = None,
) -> tuple[ModelResponse | None, str | None]:
    try:
        full_content = ""
        full_reasoning = ""
        full_tool_calls: dict[int, dict] = {}

        async for chunk in call_model_stream(state.messages):
            chunk_type = chunk.get("type", "")

            if chunk_type == "content":
                data = chunk.get("data", "")
                full_content += data
                state.accumulated_content += data
                if on_stream_token:
                    on_stream_token(data)

            elif chunk_type == "tool_calls":
                full_tool_calls_list = chunk.get("data", [])
                for tc in full_tool_calls_list:
                    idx = tc.get("index", len(full_tool_calls))
                    full_tool_calls[idx] = tc
                full_content = chunk.get("content", full_content)
                full_reasoning = chunk.get("reasoning", full_reasoning)

            elif chunk_type == "done":
                full_content = chunk.get("content", full_content)
                full_reasoning = chunk.get("reasoning", full_reasoning)

        state.accumulated_reasoning = full_reasoning

        if full_tool_calls:
            tool_calls_list = []
            for idx in sorted(full_tool_calls.keys()):
                tc = full_tool_calls[idx]
                func = tc.get("function", {})
                raw_args = func.get("arguments", "")
                try:
                    args = (
                        json.loads(raw_args) if raw_args else {}
                    ) if isinstance(raw_args, str) else raw_args
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls_list.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": func.get("name", ""),
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                })
            state.collected_tool_calls = tool_calls_list
            return ModelResponse(
                type="tool_calls",
                tool_calls=tool_calls_list,
                content=full_content,
                reasoning=full_reasoning,
            ), None

        return ModelResponse(
            type="content",
            data=full_content,
            content=full_content,
            reasoning=full_reasoning,
        ), None

    except Exception as e:
        _log.warning("[DEEP-OS] STREAM_ERROR: %s", e)
        return None, str(e)


async def _handle_tool_calls(
    state: LifecycleState,
    config: LifecycleConfig,
    response: ModelResponse,
    execute_tool_fn: LifecycleToolExecutor,
    on_tool_start: Callable | None,
    on_tool_end: Callable | None,
    is_bash_repeated: Callable | None,
) -> AsyncGenerator[dict, None]:
    state.consecutive_tool_calls += 1

    # â”€â”€ Anti-Loop: Circuit Breaker para tool calls â”€â”€
    if config.anti_loop_enabled:
        cb_count = state.circuit_breaker.record_tool_call()
        _log.info(
            "[DEEP-OS] ðŸ”§ Tool call #%d/%d (circuit breaker)",
            cb_count, state.circuit_breaker.max_tool_calls,
        )

        # State Hash: registra padrão de ação
        tool_names = [validate_tool_call(tc).tool_name for tc in state.collected_tool_calls]
        h = state.state_hash_tracker.record_state(
            state.accumulated_reasoning or "",
            tool_name=",".join(tool_names),
        )
        if state.state_hash_tracker.is_loop_detected():
            consec = state.state_hash_tracker.get_consecutive_count()
            _log.warning(
                "[DEEP-OS] ðŸ” LOOP DE AÃ‡ÃƒO DETECTADO: mesmo padrão repetido %d vezes (hash: %s)",
                consec, h,
            )
            # Gera nudge contextualizado com as ferramentas que estavam sendo chamadas
            contextual_nudge = build_frustration_nudge_with_context(
                state.tool_logs[-5:] if state.tool_logs else [],
                reason=f"Acao repetida {consec} vezes",
            )
            state.messages.append({
                "role": "system",
                "content": contextual_nudge,
            })
            state.state_hash_tracker.reset()
            state.consecutive_tool_calls = 0
            yield {"type": "thinking", "step": state.step, "content": "[ANTI-LOOP] Nudge contextualizado injetado â€” loop de acao quebrado"}
            return

    assistant_msg = {
        "role": "assistant",
        "content": state.accumulated_content if state.accumulated_content else "",
        "tool_calls": state.collected_tool_calls,
    }

    if state.accumulated_reasoning:
        reasoning_block = f"<think>\n{state.accumulated_reasoning}\n</think>\n"
        assistant_msg["content"] = reasoning_block + (assistant_msg.get("content") or "")

    state.messages.append(assistant_msg)

    for tc in state.collected_tool_calls:
        validation = validate_tool_call(tc)

        state.transition(State.VALIDATE_TOOL, detail=f"tool={validation.tool_name} valid={validation.valid}")
        yield {"type": "state_change", "state": State.VALIDATE_TOOL.value, "step": state.step}

        if not validation.valid:
            state.messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": json.dumps({"error": f"Tool call invalida: {validation.error}"}, ensure_ascii=False),
            })
            yield {"type": "thinking", "step": state.step, "content": f"[VALIDATE_TOOL] Rejeitado: {validation.error}"}
            continue

        tool_name = validation.tool_name
        tool_params = validation.params

        if is_bash_repeated and tool_name == "bash":
            cmd = (tool_params.get("command") or "").strip()
            if cmd and cmd == state.last_bash_command:
                feedback = f"[SISTEMA] Comando bash repetido bloqueado: {cmd}. Mude de estrategia."
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps({"error": feedback}, ensure_ascii=False),
                })
                bash_msg = f"[VALIDATE_TOOL] Bash repetido bloqueado: {cmd}"
                yield {"type": "thinking", "step": state.step, "content": bash_msg}
                continue
            state.last_bash_command = cmd

        state.transition(State.EXECUTE_TOOL, detail=f"tool={tool_name}")
        yield {"type": "state_change", "state": State.EXECUTE_TOOL.value, "step": state.step}
        yield {"type": "tool_start", "step": state.step, "tool": tool_name, "params": tool_params}
        if on_tool_start:
            on_tool_start(tool_name, tool_params)

        try:
            tool_result = await asyncio.wait_for(
                execute_tool_fn(tool_name, tool_params),
                timeout=config.tool_timeout,
            )
        except asyncio.TimeoutError:
            timeout_err = f"Ferramenta {tool_name} excedeu tempo limite de {config.tool_timeout}s"
            tool_result = {"error": timeout_err}
        except Exception as e:
            tool_result = {"error": str(e)}

        yield {"type": "tool_end", "step": state.step, "tool": tool_name, "result": tool_result, "accumulated_content": state.accumulated_content}
        if on_tool_end:
            on_tool_end(tool_name, tool_result)

        state.tool_logs.append({
            "step": state.step,
            "tool": tool_name,
            "params": tool_params,
            "result": tool_result,
        })

        state.transition(State.APPEND_OBSERVATION, detail=f"tool={tool_name}")
        yield {"type": "state_change", "state": State.APPEND_OBSERVATION.value, "step": state.step}

        observation = extract_observation(tool_result)

        # Adiciona dica de recuperacao quando ferramenta falha
        if isinstance(tool_result, dict) and tool_result.get("error"):
            error_msg = tool_result["error"]
            recovery_hints = {
                "web_fetch": "Tente usar web_search para encontrar a informacao em outro site, ou use bash com curl para baixar o conteudo diretamente.",
                "web_search": "Tente reformular a busca com termos mais simples em ingles, ou busque diretamente no site usando web_fetch com a URL.",
                "bash": "Verifique se o comando esta correto. Tente executar comandos mais simples primeiro. Se o programa nao existe, instale-o primeiro.",
                "read": "Verifique se o caminho do arquivo esta correto. Use explorer para listar arquivos disponiveis.",
                "write": "Verifique se voce tem permissao de escrita no diretorio. Tente salvar em outro local.",
                "execute_python": "Verifique se o codigo Python esta correto. Tente executar apenas partes menores do codigo primeiro.",
            }
            hint = recovery_hints.get(tool_name, "Mude de estrategia e tente outra abordagem.")
            observation = f"{observation}\n\n[DICA DE RECUPERACAO] {hint}"

        state.append_observation(tool_name, observation)

        state.messages.append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "content": observation,
        })

        obs_msg = f"[APPEND_OBSERVATION] {tool_name} -> {len(observation)} chars registrados"
        yield {"type": "thinking", "step": state.step, "content": obs_msg}

    yield {
        "type": "thinking",
        "step": state.step,
        "content": f"[Passo {state.step}] Aguardando proxima acao do modelo...",
    }
