"""
DEEP-OS â€” CLI Monitor Interativo
=========================================
Painel de monitoramento em tempo real com formatação Rich/ANSI.

Executa tarefas via agente e exibe:
- Transições de estado com cores
- Alertas de anti-loop e circuit breaker
- Contexto RAG recuperado (sucessos + anti-padrões)
- Resumo de falhas e diagnósticos

Uso:
    python -m cli.monitor "sua tarefa aqui"
    python -m cli.monitor --provider groq --model llama-3.1-70b-versatile "sua tarefa"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Garante que o backend está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.state_machine import State

# â”€â”€â”€ ANSI Colors (fallback se rich não disponível) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# â”€â”€â”€ State Colors â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

STATE_COLORS = {
    State.START:              "\033[97m",   # branco
    State.CALL_MODEL:        "\033[94m",   # azul
    State.CHECK_RESPONSE:    "\033[96m",   # ciano
    State.API_ERROR:         "\033[91m",   # vermelho
    State.ACCUMULATE_STREAM: "\033[93m",   # amarelo
    State.CLASSIFY_FINISH:   "\033[95m",   # magenta
    State.VALIDATE_TOOL:     "\033[93m",   # amarelo
    State.EXECUTE_TOOL:      "\033[93m",   # amarelo
    State.APPEND_OBSERVATION:"\033[92m",   # verde
    State.TRUNCATED:         "\033[91m",   # vermelho
    State.FILTERED:          "\033[91m",   # vermelho
    State.CLASSIFY_CONTENT:  "\033[95m",   # magenta
    State.FINAL:             "\033[92m",   # verde
    State.THINK_ONLY:        "\033[95m",   # roxo
    State.FAILED:            "\033[91m",   # vermelho
}

STATE_ICONS = {
    State.START:              ">>>",
    State.CALL_MODEL:        "LLM",
    State.CHECK_RESPONSE:    "?",
    State.API_ERROR:         "ERR",
    State.ACCUMULATE_STREAM: "~",
    State.CLASSIFY_FINISH:   ">>",
    State.VALIDATE_TOOL:     "CHK",
    State.EXECUTE_TOOL:      "RUN",
    State.APPEND_OBSERVATION:"ADD",
    State.TRUNCATED:         "!!!",
    State.FILTERED:          "XXX",
    State.CLASSIFY_CONTENT:  ">>",
    State.FINAL:             "OK!",
    State.THINK_ONLY:        "THK",
    State.FAILED:            "FAL",
}

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

BANNER_ALERT = (
    f"{RED}{BOLD}"
    "â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—\n"
    "â•‘  âš ï¸  ANTI-LOOP ACTIVATED  âš ï¸                           â•‘\n"
    "â•‘  Padrão de raciocínio/ação repetido detectado.          â•‘\n"
    "â•‘  Nudge de frustração injetado no contexto.              â•‘\n"
    "â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
    f"{RESET}"
)

BANNER_CIRCUIT = (
    f"{RED}{BOLD}"
    "â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—\n"
    "â•‘  ðŸš¨ CIRCUIT BREAKER TRIP  ðŸš¨                           â•‘\n"
    "â•‘  Limite de iterações excedido. Fluxo interrompido.      â•‘\n"
    "â•‘  Gerando diagnóstico de falha...                        â•‘\n"
    "â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
    f"{RESET}"
)

BANNER_COMPRESSION = (
    f"{YELLOW}"
    "â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—\n"
    "â•‘  ðŸ“¦ CONTEXT COMPRESSION  ðŸ“¦                            â•‘\n"
    "â•‘  Contexto proximo do limite. Compressao aplicada.       â•‘\n"
    "â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
    f"{RESET}"
)


# â”€â”€â”€ Output Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def print_state_transition(state: str, step: int, detail: str = ""):
    """Imprime transição de estado com cor."""
    try:
        s = State(state)
        color = STATE_COLORS.get(s, "")
        icon = STATE_ICONS.get(s, "???")
    except (ValueError, KeyError):
        color = ""
        icon = "?"

    detail_str = f" {DIM}({detail}){RESET}" if detail else ""
    print(f"  {color}{BOLD}[{icon:3s}]{RESET} Passo {step:2d} â†’ {color}{state}{RESET}{detail_str}")


def print_tool_start(tool: str, params: dict, step: int):
    """Imprime início de execução de ferramenta."""
    param_summary = ""
    if isinstance(params, dict):
        for k in ("command", "path", "code", "pattern", "query"):
            if k in params:
                param_summary = f"{k}={str(params[k])[:50]}"
                break
        if not param_summary:
            param_summary = str(params)[:50]

    print(f"  {YELLOW}{BOLD}[RUN ]{RESET} Passo {step:2d} â†’ {BOLD}{tool}{RESET}({param_summary})")


def print_tool_end(tool: str, result: dict, step: int):
    """Imprime fim de execução de ferramenta."""
    if isinstance(result, dict) and result.get("error"):
        print(f"  {RED}[ERRO]{RESET} Passo {step:2d} â†’ {tool}: {result['error'][:80]}")
    else:
        result_str = str(result)[:60] if result else "ok"
        print(f"  {GREEN}[DONE]{RESET} Passo {step:2d} â†’ {tool}: {result_str}")


def print_anti_loop_alert():
    """Exibe banner de anti-loop."""
    print()
    print(BANNER_ALERT)
    print()


def print_circuit_breaker_trip():
    """Exibe banner de circuit breaker."""
    print()
    print(BANNER_CIRCUIT)
    print()


def print_compression_alert():
    """Exibe banner de compressão."""
    print()
    print(BANNER_COMPRESSION)
    print()


def print_rag_context(memories: list[dict]):
    """Exibe resumo das memórias RAG recuperadas."""
    if not memories:
        print(f"  {DIM}â„¹ï¸  Nenhuma memória RAG recuperada.{RESET}")
        return

    success = [m for m in memories if not m.get("is_failure")]
    failures = [m for m in memories if m.get("is_failure")]

    print(f"\n  {CYAN}{BOLD}â”€â”€ RAG Context Recuperado â”€â”€{RESET}")

    if failures:
        print(f"  {RED}{BOLD}âš ï¸  Anti-padrões ({len(failures)}):{RESET}")
        for m in failures:
            print(f"    {RED}â€¢ [{m.get('relevance', 0):.2f}] FALHA: {m['task'][:60]}{RESET}")
            if m.get("lessons_learned"):
                print(f"      {DIM}Lição: {m['lessons_learned'][:80]}{RESET}")

    if success:
        print(f"  {GREEN}{BOLD}âœ… Experiências ({len(success)}):{RESET}")
        for m in success:
            print(f"    {GREEN}â€¢ [{m.get('relevance', 0):.2f}] {m['task'][:60]}{RESET}")

    print()


def print_final_answer(answer: str, status: str, steps: int, elapsed: float):
    """Exibe resposta final formatada."""
    if status == "circuit_breaker":
        print_circuit_breaker_trip()
    elif status == "failed":
        print(f"\n{RED}{BOLD}{'='*60}{RESET}")
        print(f"{RED}{BOLD}  FALHA NA EXECUÃ‡ÃƒO{RESET}")
        print(f"{RED}{BOLD}{'='*60}{RESET}")
    else:
        print(f"\n{GREEN}{BOLD}{'='*60}{RESET}")
        print(f"{GREEN}{BOLD}  EXECUÃ‡ÃƒO CONCLUÃDA{RESET}")
        print(f"{GREEN}{BOLD}{'='*60}{RESET}")

    print(f"\n  {BOLD}Status:{RESET} {status}")
    print(f"  {BOLD}Passos:{RESET} {steps}")
    print(f"  {BOLD}Tempo:{RESET}  {elapsed:.1f}s")
    print(f"\n  {BOLD}Resposta:{RESET}")
    # Wrapping simples para terminal
    for line in answer.split("\n"):
        print(f"    {line}")
    print()


def print_diagnostics(diagnostics: dict):
    """Exibe diagnóstico de falha formatado."""
    if not diagnostics:
        return
    print(f"\n  {YELLOW}{BOLD}â”€â”€ Diagnóstico â”€â”€{RESET}")
    print(f"  Violação: {diagnostics.get('violation', '?')}")
    print(f"  Passos executados: {diagnostics.get('steps_executed', 0)}")
    print(f"  Ferramentas tentadas: {', '.join(diagnostics.get('tools_tried', []))}")
    failed = diagnostics.get("failed_tools", [])
    if failed:
        print(f"  Ferramentas com erro:")
        for f in failed[:3]:
            print(f"    {RED}â€¢ {f.get('tool', '?')}: {f.get('error', '?')[:60]}{RESET}")
    reasoning = diagnostics.get("last_reasoning", "")
    if reasoning:
        print(f"  Ãšltimo raciocínio: {reasoning[:120]}...")
    print()


# â”€â”€â”€ Main CLI Runner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def run_interactive(
    task: str,
    provider: str = "groq",
    model: str = "llama-3.1-70b-versatile",
    temperature: float = 0.3,
    personality: str = "Voce e um engenheiro de software eficiente e objetivo.",
):
    """Executa tarefa com monitoramento visual completo."""
    from memory.elastic_memory import recall_relevant_memories, format_memories_for_prompt
    from agents.loop import run_agent

    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  DEEP-OS â€” CLI Monitor{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"  {BOLD}Tarefa:{RESET} {task[:80]}")
    print(f"  {BOLD}Provider:{RESET} {provider}")
    print(f"  {BOLD}Model:{RESET} {model}")
    print(f"  {BOLD}Temperature:{RESET} {temperature}")
    print()

    # Recall RAG
    print(f"  {CYAN}ðŸ” Buscando memórias relevantes...{RESET}")
    try:
        memories = await recall_relevant_memories(task, top_k=5)
        print_rag_context(memories)
    except Exception as e:
        print(f"  {RED}âš ï¸  Falha no recall: {e}{RESET}")

    print(f"  {CYAN}â–¶ Iniciando ciclo do agente...{RESET}\n")

    start_time = time.time()
    result = await run_agent(
        task=task,
        provider=provider,
        model=model,
        temperature=temperature,
        personality=personality,
    )
    elapsed = time.time() - start_time

    print_final_answer(
        answer=result.get("result", ""),
        status=result.get("status", "unknown"),
        steps=result.get("steps", 0),
        elapsed=elapsed,
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="DEEP-OS â€” CLI Monitor Interativo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", help="Tarefa a ser executada pelo agente")
    parser.add_argument("--provider", default="groq", help="Provider LLM (default: groq)")
    parser.add_argument("--model", default="llama-3.1-70b-versatile", help="Modelo LLM")
    parser.add_argument("--temperature", type=float, default=0.3, help="Temperatura (0.0-1.0)")
    parser.add_argument("--personality", default="Voce e um engenheiro de software eficiente e objetivo.",
                        help="Personalidade do agente")

    args = parser.parse_args()
    asyncio.run(run_interactive(
        task=args.task,
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        personality=args.personality,
    ))


if __name__ == "__main__":
    main()
