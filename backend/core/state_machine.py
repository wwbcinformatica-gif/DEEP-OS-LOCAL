"""
DEEP-OS — Lifecycle State Machine
========================================
Finite state machine for the LLM agent execution cycle.

Flow:
    START -> CALL_MODEL -> CHECK_RESPONSE
        -> API_ERROR (retry loop) -> CALL_MODEL
        -> ACCUMULATE_STREAM (chunk loop) -> CLASSIFY_FINISH
        -> CLASSIFY_FINISH -> (
            tool_calls  -> VALIDATE_TOOL -> EXECUTE_TOOL -> APPEND_OBSERVATION -> CALL_MODEL
            length      -> TRUNCATED
            content_filter -> FILTERED
            stop        -> CLASSIFY_CONTENT -> (
                has_response -> FINAL
                only_think   -> THINK_ONLY -> (nudge -> CALL_MODEL | exceed_limit -> FAILED)
            )
        )

Anti-Loop Protection:
    - State Hash Counter: detecta padrões repetidos de raciocínio/ação
    - Circuit Breaker: limites máximos de THINK_ONLY e tool calls
    - Frustration Nudge: injeção imperativa de mudança de estratégia
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_log = logging.getLogger("wbc.lifecycle")


class State(Enum):
    START = "start"
    CALL_MODEL = "call_model"
    CHECK_RESPONSE = "check_response"
    API_ERROR = "api_error"
    ACCUMULATE_STREAM = "accumulate_stream"
    CLASSIFY_FINISH = "classify_finish"
    VALIDATE_TOOL = "validate_tool"
    EXECUTE_TOOL = "execute_tool"
    APPEND_OBSERVATION = "append_observation"
    TRUNCATED = "truncated"
    FILTERED = "filtered"
    CLASSIFY_CONTENT = "classify_content"
    FINAL = "final"
    THINK_ONLY = "think_only"
    FAILED = "failed"


class FinishReason(Enum):
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    STOP = "stop"
    UNKNOWN = "unknown"


class ContentCategory(Enum):
    HAS_RESPONSE = "has_response"
    ONLY_THINK = "only_think"


@dataclass
class ModelResponse:
    type: str = "content"
    data: Any = ""
    content: str = ""
    reasoning: str = ""
    tool_calls: list = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.UNKNOWN
    error: str = ""
    is_streaming: bool = False


@dataclass
class ToolValidation:
    valid: bool = True
    tool_name: str = ""
    params: dict = field(default_factory=dict)
    error: str = ""


class StateHashTracker:
    """
    Rastreador de hash de estado para detecção de loops.

    Gera um hash combinando o último pensamento (reasoning) + última ferramenta chamada.
    Se o mesmo padrão se repetir mais de N vezes consecutivas, aciona alerta.
    """

    def __init__(self, max_consecutive: int = 2):
        self._max_consecutive = max_consecutive
        self._recent_hashes: deque[str] = deque(maxlen=10)
        self._consecutive_count: int = 0
        self._last_hash: str = ""

    def record_state(self, reasoning: str, tool_name: str = "") -> str:
        """
        Registra estado atual e retorna o hash gerado.
        Se o hash é igual ao anterior, incrementa contador de consecutivos.
        """
        # Normaliza o reasoning para hash (primeiros 500 chars, stripped)
        normalized = (reasoning or "")[:500].strip().lower()
        raw = f"{normalized}||{tool_name}"
        h = hashlib.md5(raw.encode()).hexdigest()[:12]

        if h == self._last_hash and self._last_hash:
            self._consecutive_count += 1
        else:
            self._consecutive_count = 1

        self._last_hash = h
        self._recent_hashes.append(h)
        return h

    def is_loop_detected(self) -> bool:
        """Retorna True se o mesmo padrão se repetiu mais de max_consecutive vezes."""
        return self._consecutive_count > self._max_consecutive

    def get_consecutive_count(self) -> int:
        return self._consecutive_count

    def reset(self):
        self._recent_hashes.clear()
        self._consecutive_count = 0
        self._last_hash = ""


class CircuitBreaker:
    """
    Disjuntor de loops — limites máximos estritos por subtarefa.

    - Max THINK_ONLY consecutivos
    - Max tool calls por subtarefa
    - Contador total de iterações
    """

    def __init__(
        self,
        max_think_only: int = 5,
        max_tool_calls: int = 20,
        max_total_iterations: int = 20,
    ):
        self.max_think_only = max_think_only
        self.max_tool_calls = max_tool_calls
        self.max_total_iterations = max_total_iterations

        self._think_only_count: int = 0
        self._tool_call_count: int = 0
        self._total_iterations: int = 0
        self._tripped: bool = False

    def record_think_only(self) -> int:
        self._think_only_count += 1
        self._total_iterations += 1
        return self._think_only_count

    def record_tool_call(self) -> int:
        self._tool_call_count += 1
        self._total_iterations += 1
        return self._tool_call_count

    def is_tripped(self) -> bool:
        """Retorna True se qualquer limite foi excedido."""
        if self._tripped:
            return True
        if self._think_only_count >= self.max_think_only:
            self._tripped = True
            return True
        if self._tool_call_count >= self.max_tool_calls:
            self._tripped = True
            return True
        if self._total_iterations >= self.max_total_iterations:
            self._tripped = True
            return True
        return False

    def get_violation_reason(self) -> str:
        if self._think_only_count >= self.max_think_only:
            return f"THINK_ONLY excedido ({self._think_only_count}/{self.max_think_only})"
        if self._tool_call_count >= self.max_tool_calls:
            return f"Tool calls excedido ({self._tool_call_count}/{self.max_tool_calls})"
        if self._total_iterations >= self.max_total_iterations:
            return f"Iterações totais excedido ({self._total_iterations}/{self.max_total_iterations})"
        return ""

    def reset_on_tool_success(self):
        """Reseta contador de THINK_ONLY quando uma tool executa com sucesso."""
        self._think_only_count = 0

    def reset(self):
        self._think_only_count = 0
        self._tool_call_count = 0
        self._total_iterations = 0
        self._tripped = False

    @property
    def stats(self) -> dict:
        return {
            "think_only": self._think_only_count,
            "tool_calls": self._tool_call_count,
            "total": self._total_iterations,
            "tripped": self._tripped,
        }


FRUSTRATION_NUDGE = (
    "<CRITICAL_SYSTEM_ALERT_ANTI_LOOP>\n"
    "O DISJUNTOR ANTI-LOOP DO SISTEMA FOI ACIONADO. Voce esta preso em um loop de raciocinio.\n\n"
    "PASSO OBRIGATORIO 1 — AUTO-EXPLICACAO:\n"
    "Liste em 1-3 linhas EXATAMENTE o que voce tentou fazer nas ultimas iteracoes e POR QUE falhou.\n"
    "Exemplo: 'Tentei 3x executar bash(dir C:\\Users) e recebi acesso negado todas as vezes.'\n\n"
    "PASSO OBRIGATORIO 2 — MUDANCA DE ESTRATEGIA:\n"
    "Agora execute UMA das opcoes abaixo (escolha a mais adequada):\n"
    "  A) Se tentou ESCRITA/CODIGO: mude para LEITURA/DIAGNOSTICO primeiro.\n"
    "     Ex: Se tentou write(), use read() ou bash(dir ...) para entender a estrutura.\n"
    "  B) Se tentou o MESMO COMANDO com MESMOS PARAMETROS: mude o parametro.\n"
    "     Ex: Se bash(dir C:\\Users) falhou, tente bash(dir C:\\) ou bash(dir D:\\).\n"
    "  C) Se tentou ESTRATEGIA A varias vezes: use ESTRATEGIA B completamente diferente.\n"
    "     Ex: Se tentou resolver via terminal, tente via search() ou explorer().\n"
    "  D) Se NENHUMA das anteriores funciona: admita que precisa de dados novos.\n"
    "     Responda ao usuario com: 'Preciso de mais informacoes para prosseguir.'\n\n"
    "PROIBICOES ABSOLUTAS:\n"
    "- NAO repita NENHUM comando ou tool call que ja foi executado nesta sessao.\n"
    "- NAO use a mesma ferramenta com os mesmos argumentos.\n"
    "- NAO continue pensando sem agir. Acao IMEDIATA agora.\n"
    "</CRITICAL_SYSTEM_ALERT_ANTI_LOOP>"
)


def build_frustration_nudge_with_context(
    recent_actions: list[dict],
    reason: str = "loop_detectado",
) -> str:
    """
    Gera um FRUSTRATION_NUDGE contextualizado com as ultimas acoes do agente.
    Isso permite que o modelo saiba EXATAMENTE o que falhou.
    """
    action_summary_lines = []
    for i, action in enumerate(recent_actions[-5:], 1):
        tool = action.get("tool", action.get("action", "?"))
        params = action.get("params", {})
        result = action.get("result", {})
        error = ""
        if isinstance(result, dict):
            error = result.get("error", "")
        param_str = ""
        if isinstance(params, dict):
            # Pega o parametro mais relevante
            for k in ("command", "path", "code", "pattern", "query", "url"):
                if k in params:
                    param_str = f"{k}={str(params[k])[:60]}"
                    break
            if not param_str:
                param_str = str(params)[:60]

        status_icon = "[ERRO]" if error else "[OK]"
        error_detail = f" -> {error[:80]}" if error else ""
        action_summary_lines.append(f"  {i}. {status_icon} {tool}({param_str}){error_detail}")

    action_block = "\n".join(action_summary_lines) if action_summary_lines else "  (nenhuma acao registrada)"

    return (
        "<CRITICAL_SYSTEM_ALERT_ANTI_LOOP>\n"
        "O DISJUNTOR ANTI-LOOP DO SISTEMA FOI ACIONADO.\n"
        f"Motivo: {reason}\n\n"
        "ULTIMAS ACOES TENTADAS (analise o que falhou):\n"
        f"{action_block}\n\n"
        "PASSO OBRIGATORIO 1 — AUTO-EXPLICACAO:\n"
        "Liste em 1-3 linhas EXATAMENTE o que voce tentou e POR QUE falhou.\n\n"
        "PASSO OBRIGATORIO 2 — MUDANCA DE ESTRATEGIA:\n"
        "  A) Se tentou ESCRITA/CODIGO: mude para LEITURA/DIAGNOSTICO.\n"
        "  B) Se tentou MESMO COMANDO: mude o parametro ou caminho.\n"
        "  C) Se tentou ESTRATEGIA A repetidamente: use ESTRATEGIA B completamente diferente.\n"
        "  D) Se nada funciona: responda ao usuario que precisa de mais dados.\n\n"
        "PROIBICOES: NAO repita comandos. NAO continue pensando sem agir. Acao IMEDIATA.\n"
        "</CRITICAL_SYSTEM_ALERT_ANTI_LOOP>"
    )


@dataclass
class LifecycleEvent:
    state: State
    timestamp: float = 0.0
    detail: str = ""
    step: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


def classify_finish_reason(raw_finish_reason: str | None) -> FinishReason:
    mapping = {
        "tool_calls": FinishReason.TOOL_CALLS,
        "function_call": FinishReason.TOOL_CALLS,
        "length": FinishReason.LENGTH,
        "max_tokens": FinishReason.LENGTH,
        "content_filter": FinishReason.CONTENT_FILTER,
        "stop": FinishReason.STOP,
        "end_turn": FinishReason.STOP,
        "stop_sequence": FinishReason.STOP,
    }
    return mapping.get(raw_finish_reason or "", FinishReason.UNKNOWN)


def classify_content(
    content: str,
    reasoning: str = "",
) -> ContentCategory:
    clean = (content or "").strip()
    if clean:
        return ContentCategory.HAS_RESPONSE
    return ContentCategory.ONLY_THINK


def validate_tool_call(tool_call: dict) -> ToolValidation:
    func = tool_call.get("function", {})
    name = func.get("name", "")
    raw_args = func.get("arguments", "")

    if not name:
        return ToolValidation(valid=False, error="Nome da ferramenta vazio")

    try:
        import json
        params = (
            json.loads(raw_args) if raw_args else {}
        ) if isinstance(raw_args, str) else raw_args
    except (json.JSONDecodeError, TypeError):
        params = {}

    return ToolValidation(valid=True, tool_name=name, params=params)


def extract_observation(tool_result: Any) -> str:
    if isinstance(tool_result, str):
        return tool_result
    if isinstance(tool_result, dict):
        import json
        return json.dumps(tool_result, ensure_ascii=False)
    return str(tool_result) if tool_result else ""


def log_transition(from_state: State, to_state: State, detail: str = "", step: int = 0):
    _log.info(
        "[DEEP-OS] Transição: %s -> %s %s%s",
        from_state.value,
        to_state.value,
        f"(passo {step})" if step else "",
        f" | {detail}" if detail else "",
    )
