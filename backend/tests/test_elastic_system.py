"""Quick test for new elastic memory + anti-loop systems."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.elastic_memory import (
    index_task_memory,
    recall_relevant_memories,
    format_memories_for_prompt,
    get_memory_stats,
    clear_long_term_memory,
)
from core.context_compression import compress_context
from core.state_machine import StateHashTracker, CircuitBreaker

async def test_elastic_memory():
    print("=== Teste Memoria Elastica ===")
    await clear_long_term_memory()

    await index_task_memory(
        "Criar endpoint de login com FastAPI",
        "Usar @app.post com bcrypt para hash de senhas",
        ["bash", "write", "read"],
        "FastAPI precisa de uvicorn para rodar em producao",
    )
    await index_task_memory(
        "Configurar PostgreSQL no Docker",
        "Usar docker-compose com volume persistente",
        ["bash"],
        "Sempre usar volumes para dados persistentes",
    )
    await index_task_memory(
        "Deploy com GitHub Actions CI/CD",
        "Criar workflow YAML com steps de build e deploy",
        ["write", "bash"],
        "Usar secrets do GitHub para credenciais",
    )

    stats = await get_memory_stats()
    print(f"Stats: {stats}")

    results = await recall_relevant_memories("como fazer deploy de aplicacao python")
    print(f"Recall results: {len(results)}")
    for r in results:
        print(f"  - [{r['relevance']}] {r['task'][:60]}")

    formatted = format_memories_for_prompt(results)
    print(f"Formatted prompt length: {len(formatted)} chars")
    print()

async def test_anti_loop():
    print("=== Teste Anti-Loop ===")
    tracker = StateHashTracker(max_consecutive=2)
    h1 = tracker.record_state("thinking about API design", "bash")
    h2 = tracker.record_state("thinking about API design", "bash")
    print(f"Same hash: {h1 == h2}, Consecutive: {tracker.get_consecutive_count()}, Loop: {tracker.is_loop_detected()}")

    cb = CircuitBreaker(max_think_only=5, max_tool_calls=7)
    for i in range(6):
        cb.record_think_only()
    print(f"Think-only: {cb._think_only_count}, Tripped: {cb.is_tripped()}, Reason: {cb.get_violation_reason()}")
    print()

async def test_compression():
    print("=== Teste Compressao de Contexto ===")
    messages = [
        {"role": "system", "content": "Voce e um assistente."},
        {"role": "user", "content": "Faca algo"},
        {"role": "assistant", "content": "vou analisar...", "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"ls"}'}}]},
        {"role": "tool", "content": "file1.txt file2.txt"},
        {"role": "assistant", "content": "agora vou processar...", "tool_calls": [{"function": {"name": "read", "arguments": '{"path":"file1.txt"}'}}]},
        {"role": "tool", "content": "conteudo do arquivo " + "x" * 2000},
        {"role": "assistant", "content": "continuando..."},
        {"role": "assistant", "content": "Aqui esta o resultado final."},
    ]
    compressed, was_compressed, summary = await compress_context(messages, max_context_tokens=200)
    print(f"Compressed: {was_compressed}, Messages: {len(messages)} -> {len(compressed)}")
    print()

async def main():
    await test_elastic_memory()
    await test_anti_loop()
    await test_compression()
    print("Todos os testes passaram!")

if __name__ == "__main__":
    asyncio.run(main())
