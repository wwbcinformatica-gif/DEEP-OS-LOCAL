"""
DEEP-OS — Compressão de Contexto
=========================================
Sumarização recursiva de blocos antigos THINK_ONLY e APPEND_OBSERVATION
para liberar espaço de memória de trabalho sem perder o fio da meada.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger("wbc.context_compression")

# Limite de tokens estimado para acionar compressão
COMPRESSION_TRIGGER_RATIO = 0.85  # 85% do max_tokens usado


def _estimate_tokens(text: str) -> int:
    """Estimativa rough de tokens (1 token ≈ 3.5 chars em PT-BR)."""
    if not text:
        return 0
    return len(text) // 3


def _extract_blocks_to_compress(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Separa mensagens em dois grupos:
    - keep: system prompt, últimas N mensagens, mensagens de usuário recentes
    - compress: blocos THINK_ONLY e ferramentas antigas (primeiros 50% do histórico)
    """
    if len(messages) <= 8:
        return messages, []

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= 6:
        return messages, []

    # Mantém as últimas 70% das mensagens não-sistema + todo system
    keep_count = max(8, int(len(non_system) * 0.70))
    keep_non_system = non_system[-keep_count:]
    compress_non_system = non_system[:-keep_count]

    return system_msgs + keep_non_system, compress_non_system


def _summarize_tool_blocks(blocks: list[dict]) -> str:
    """
    Consolida blocos THINK_ONLY + ferramentas em parágrafo abstrato.
    Extrai ações-chave e resultados sem chamar LLM (operação local).
    """
    if not blocks:
        return ""

    actions = []
    errors = []
    observations = []

    for block in blocks:
        role = block.get("role", "")
        content = block.get("content", "")

        if role == "assistant":
            # Tool calls do assistant
            tool_calls = block.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "?")
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    # Extrai resumo da ação
                    param_summary = _summarize_params(name, args)
                    actions.append(f"{name}({param_summary})")

            # Reasoning/thinking content
            if content and "<think>" in content:
                thinking = content.split("<think>")[-1].split("</think>")[0] if "</think>" in content else ""
                if thinking and len(thinking) > 20:
                    actions.append(f"[raciocínio: {thinking[:80]}...]")

        elif role == "tool":
            obs = content[:200] if content else ""
            if "error" in obs.lower() or "erro" in obs.lower():
                errors.append(obs[:100])
            elif obs:
                observations.append(obs[:100])

    parts = []
    if actions:
        parts.append(f"Ações executadas: {', '.join(actions[:15])}")
    if errors:
        parts.append(f"Erros encontrados: {'; '.join(errors[:5])}")
    if observations:
        parts.append(f"Observações-chave: {'; '.join(observations[:5])}")

    if not parts:
        return "[bloco de raciocínio e ferramentas consolidado]"

    return " → ".join(parts)


def _summarize_params(tool_name: str, args: dict) -> str:
    """Gera resumo curto dos parâmetros de uma tool call."""
    if not args:
        return ""

    if tool_name in ("bash", "execute_python"):
        cmd = args.get("command", args.get("code", ""))
        return cmd[:60] + "..." if len(cmd) > 60 else cmd
    elif tool_name in ("read", "write", "delete", "rename", "create_directory"):
        path = args.get("path", args.get("new_path", ""))
        return path.split("/")[-1] if path else ""
    elif tool_name == "explorer":
        return args.get("path", "")[:40]
    elif tool_name == "search":
        return f"'{args.get('pattern', '')}'"
    elif tool_name == "glob":
        return args.get("pattern", "")
    elif tool_name == "web_search":
        return f"'{args.get('query', '')}'"
    elif tool_name == "web_fetch":
        return args.get("url", "")[:40]
    else:
        # Genérico: pega primeira string encontrada
        for v in args.values():
            if isinstance(v, str) and v:
                return v[:40]
        return ""


async def compress_context(
    messages: list[dict],
    max_context_tokens: int = 128000,
) -> tuple[list[dict], bool, str]:
    """
    Comprime o contexto se estiver se aproximando do limite de tokens.

    Retorna:
        - messages: lista possivelmente comprimida
        - compressed: True se compressão foi aplicada
        - summary: descrição do que foi comprimido
    """
    total_tokens = sum(_estimate_tokens(m.get("content", "")) for m in messages)
    trigger = int(max_context_tokens * COMPRESSION_TRIGGER_RATIO)

    if total_tokens <= trigger:
        return messages, False, ""

    _log.info(
        "[CONTEXT-COMPRESSION] 🔻 Tokens estimados: %d/%d (limite: %d). Iniciando compressão...",
        total_tokens, max_context_tokens, trigger,
    )

    keep, compress = _extract_blocks_to_compress(messages)

    if not compress:
        _log.info("[CONTEXT-COMPRESSION] Nenhum bloco elegível para compressão.")
        return messages, False, ""

    compressed_tokens = sum(_estimate_tokens(m.get("content", "")) for m in compress)
    summary_text = _summarize_tool_blocks(compress)

    # Insere resumo como mensagem de sistema comprimida
    compression_msg = {
        "role": "system",
        "content": (
            f"[CONTEXTO COMPRIMIDO] Resumo das ações anteriores:\n{summary_text}\n"
            "Este bloco substituiu {0} mensagens detalhadas para liberar espaço de memória.".format(len(compress))
        ),
    }

    # Reconstrói: keep[0] (system) + compression_msg + keep[1:]
    if keep and keep[0].get("role") == "system":
        new_messages = [keep[0], compression_msg] + keep[1:]
    else:
        new_messages = [compression_msg] + keep

    new_tokens = sum(_estimate_tokens(m.get("content", "")) for m in new_messages)
    saved = total_tokens - new_tokens

    _log.info(
        "[CONTEXT-COMPRESSION] ✅ Comprimidos %d blocos → 1 resumo. "
        "Tokens: %d → %d (economia: ~%d tokens, %.0f%%)",
        len(compress), total_tokens, new_tokens, saved,
        (saved / total_tokens * 100) if total_tokens > 0 else 0,
    )

    return new_messages, True, summary_text
