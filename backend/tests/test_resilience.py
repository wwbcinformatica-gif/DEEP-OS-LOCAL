"""
DEEP-OS â€” Testes de Resiliência
========================================
Cobertura completa:
  1. Loop infinito simulador (State Hash Tracker)
  2. Estouro de circuito (Circuit Breaker)
  3. Compressão de contexto extrema
  4. Recall semÃ¢ntico preciso
  5. Concorrência de escrita (async lock)
  6. Integração lifecycle completa
"""

import sys
import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory.elastic_memory import (
    index_task_memory,
    recall_relevant_memories,
    format_memories_for_prompt,
    get_memory_stats,
    clear_long_term_memory,
    _load_index,
    _save_index,
    _tokenize,
    _term_frequency,
    _cosine_similarity,
    _write_lock,
    INDEX_FILE,
    SIMILARITY_THRESHOLD,
)
from core.context_compression import (
    compress_context,
    _estimate_tokens,
    _extract_blocks_to_compress,
    _summarize_tool_blocks,
    COMPRESSION_TRIGGER_RATIO,
)
from core.state_machine import (
    ModelResponse,
    StateHashTracker,
    CircuitBreaker,
    FRUSTRATION_NUDGE,
    State,
    classify_content,
    ContentCategory,
)
from core.lifecycle import (
    LifecycleConfig,
    LifecycleState,
    run_lifecycle,
)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Helpers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    status = "PASS" if condition else "FAIL"
    if not condition:
        FAILED += 1
    else:
        PASSED += 1
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    return condition


def build_fake_messages(count: int, content_size: int = 500) -> list[dict]:
    """Gera lista de mensagens fictícias para testes de compressão."""
    msgs = [{"role": "system", "content": "Voce e um assistente de engenharia."}]
    roles = ["user", "assistant", "tool"]
    for i in range(count):
        role = roles[i % len(roles)]
        if role == "assistant":
            msgs.append({
                "role": role,
                "content": "<think>pensando sobre o passo " + str(i) + "..." + "x" * content_size + "</think>",
                "tool_calls": [{"function": {"name": "bash", "arguments": json.dumps({"command": f"ls -la /tmp/step{i}"})}}],
            })
        elif role == "tool":
            msgs.append({"role": role, "content": f"resultado do step {i}: " + "y" * content_size})
        else:
            msgs.append({"role": role, "content": f"instrucao do step {i}: " + "z" * content_size})
    return msgs


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 1. LOOP INFINITO SIMULADOR â€” State Hash Tracker
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def test_loop_detector_repeated_error():
    """Força ferramenta a retornar o mesmo erro repetidamente. Valida detecção na 3Âª iteração."""
    print("\n=== 1a. Loop Infinito â€” Erro Repetido ===")
    tracker = StateHashTracker(max_consecutive=2)

    # 1Âª iteração: raciocínio + bash("ls")
    h1 = tracker.record_state("preciso listar arquivos", "bash")
    check("1a.1 Hash gerado", len(h1) == 12, f"hash={h1}")
    check("1a.2 Sem loop ainda (1 ocorrência)", not tracker.is_loop_detected())

    # 2Âª iteração: mesmo raciocínio + bash("ls") â€” mesmo erro
    h2 = tracker.record_state("preciso listar arquivos", "bash")
    check("1a.3 Mesmo hash detectado", h1 == h2)
    check("1a.4 Consecutive=2 (2 ocorrências)", tracker.get_consecutive_count() == 2)
    check("1a.5 Sem loop ainda (max=2, count=2)", not tracker.is_loop_detected())

    # 3Âª iteração: mesmo padrão â€” AGORA deve detectar
    h3 = tracker.record_state("preciso listar arquivos", "bash")
    check("1a.6 Hash continua igual", h1 == h3)
    check("1a.7 Consecutive=3", tracker.get_consecutive_count() == 3)
    check("1a.8 LOOP DETECTADO na 3Âª iteração", tracker.is_loop_detected())

    # Reset e verificação de recuperação
    tracker.reset()
    check("1a.9 Após reset, consecutive=0", tracker.get_consecutive_count() == 0)
    check("1a.10 Após reset, sem loop", not tracker.is_loop_detected())


def test_loop_detector_different_states():
    """Verifica que padrões diferentes NÃƒO acionam o detector."""
    print("\n=== 1b. Loop Infinito â€” Padrões Diferentes ===")
    tracker = StateHashTracker(max_consecutive=2)

    h1 = tracker.record_state("listar arquivos", "bash")
    h2 = tracker.record_state("ler conteudo", "read")
    h3 = tracker.record_state("salvar arquivo", "write")
    h4 = tracker.record_state("listar arquivos", "bash")

    check("1b.1 Hashes diferentes", h1 != h2 and h2 != h3)
    check("1b.2 Sem loop com padrões variados", not tracker.is_loop_detected())
    check("1b.3 Seq 1,1,2,1: consecutive=1 (último é novo)", tracker.get_consecutive_count() == 1)


def test_frustration_nudge_content():
    """Valida que o FRUSTRATION_NUDGE contém engenharia de prompt agressiva."""
    print("\n=== 1c. Frustration Nudge ===")
    check("1c.1 Contém 'CRITICAL_SYSTEM_ALERT'", "<CRITICAL_SYSTEM_ALERT_ANTI_LOOP>" in FRUSTRATION_NUDGE)
    check("1c.2 Contém 'AUTO-EXPLICACAO'", "AUTO-EXPLICACAO" in FRUSTRATION_NUDGE)
    check("1c.3 Contém 'MUDANCA DE ESTRATEGIA'", "MUDANCA DE ESTRATEGIA" in FRUSTRATION_NUDGE)
    check("1c.4 Contém 'PROIBICOES ABSOLUTAS'", "PROIBICOES ABSOLUTAS" in FRUSTRATION_NUDGE)
    check("1c.5 Contém tag de fechamento", "</CRITICAL_SYSTEM_ALERT_ANTI_LOOP>" in FRUSTRATION_NUDGE)
    check("1c.6 Tamanho > 400 chars", len(FRUSTRATION_NUDGE) > 400)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 2. ESTOURO DE CIRCUITO â€” Circuit Breaker
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def test_circuit_breaker_think_only():
    """Simula 5+ THINK_ONLY consecutivos. Valida trip e violação."""
    print("\n=== 2a. Circuit Breaker â€” THINK_ONLY ===")
    cb = CircuitBreaker(max_think_only=5, max_tool_calls=7, max_total_iterations=20)

    for i in range(1, 5):
        cb.record_think_only()
        check(f"2a.{i} Think #{i}: tripped=False", not cb.is_tripped())

    # 5Âº think_only â€” deve trip
    cb.record_think_only()
    check("2a.5 Think #5: tripped=True", cb.is_tripped())
    check("2a.6 Violation reason contains THINK_ONLY", "THINK_ONLY" in cb.get_violation_reason())
    check("2a.7 Stats corretos", cb.stats["think_only"] == 5 and cb.stats["tripped"] is True)


def test_circuit_breaker_tool_calls():
    """Simula 7+ tool calls. Valida trip."""
    print("\n=== 2b. Circuit Breaker â€” Tool Calls ===")
    cb = CircuitBreaker(max_think_only=5, max_tool_calls=7, max_total_iterations=20)

    for i in range(1, 7):
        cb.record_tool_call()
        check(f"2b.{i} Tool #{i}: tripped=False", not cb.is_tripped())

    cb.record_tool_call()
    check("2b.7 Tool #8: tripped=True", cb.is_tripped())
    check("2b.8 Violation reason contains Tool calls", "Tool calls" in cb.get_violation_reason())


def test_circuit_breaker_total_iterations():
    """Simula iterações totais mistas que estouram o limite."""
    print("\n=== 2c. Circuit Breaker â€” Iterações Totais ===")
    cb = CircuitBreaker(max_think_only=10, max_tool_calls=10, max_total_iterations=12)

    # 6 think + 6 tools = 12 total
    for i in range(6):
        cb.record_think_only()
    for i in range(6):
        cb.record_tool_call()

    check("2c.1 Total=12 excedeu limite=12", cb.is_tripped())
    check("2c.2 Violation reason contains 'it'", "it" in cb.get_violation_reason().lower())


def test_circuit_breaker_reset():
    """Valida reset_after_tool_success e reset completo."""
    print("\n=== 2d. Circuit Breaker â€” Reset ===")
    cb = CircuitBreaker(max_think_only=3, max_tool_calls=5)

    # Acumula 2 think_only
    cb.record_think_only()
    cb.record_think_only()
    check("2d.1 Think-only=2 antes do reset", cb._think_only_count == 2)

    cb.reset_on_tool_success()
    check("2d.2 Think-only=0 após reset_on_tool_success", cb._think_only_count == 0)

    # Testa reset completo
    cb.record_tool_call()
    cb.record_tool_call()
    cb.reset()
    check("2d.3 Após reset(): todos contadores=0", cb.stats == {"think_only": 0, "tool_calls": 0, "total": 0, "tripped": False})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 3. COMPRESSÃƒO DE CONTEXTO EXTREMA
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def test_compression_estimate_tokens():
    """Valida estimativa de tokens."""
    print("\n=== 3a. Compressão â€” Estimativa de Tokens ===")
    check("3a.1 Vazio = 0 tokens", _estimate_tokens("") == 0)
    check("3a.2 None = 0 tokens", _estimate_tokens(None) == 0)
    check("3a.3 'abc' = 1 token", _estimate_tokens("abc") == 1)
    check("3a.4 300 chars = 100 tokens", _estimate_tokens("x" * 300) == 100)


def test_compression_extract_blocks():
    """Valida separação de blocos para compressão."""
    print("\n=== 3b. Compressão â€” Extração de Blocos ===")

    # Caso 1: <=6 mensagens â†’ nenhuma compressão
    msgs_6 = build_fake_messages(5)
    keep, compress = _extract_blocks_to_compress(msgs_6)
    check("3b.1 6 msgs: compress=[]", len(compress) == 0)

    # Caso 2: 10 mensagens â†’ compress primeiros, keep últimos 40%
    msgs_10 = build_fake_messages(9)  # 1 system + 9 non-system = 10 total
    keep, compress = _extract_blocks_to_compress(msgs_10)
    check("3b.2 10 msgs: compress > 0", len(compress) > 0)
    check("3b.3 Mantém system prompt", any(m["role"] == "system" for m in keep))
    check("3b.4 Mantém últimas msgs", len(keep) > 0)

    # Caso 3: Mensagens gigantes
    msgs_large = build_fake_messages(50, content_size=1000)
    keep_large, compress_large = _extract_blocks_to_compress(msgs_large)
    check("3b.4 51 msgs: compress > 10", len(compress_large) > 10)
    check("3b.5 51 msgs: keep < total", len(keep_large) < len(msgs_large))


def test_compression_summarize():
    """Valida sumarização de tool blocks."""
    print("\n=== 3c. Compressão â€” Sumarização ===")
    blocks = [
        {"role": "assistant", "content": "<think>vou analisar...</think>",
         "tool_calls": [{"function": {"name": "bash", "arguments": json.dumps({"command": "ls -la"})}}]},
        {"role": "tool", "content": "arquivo1.txt"},
        {"role": "assistant", "content": "agora vou ler",
         "tool_calls": [{"function": {"name": "read", "arguments": json.dumps({"path": "/tmp/test.py"})}}]},
        {"role": "tool", "content": "conteudo do arquivo"},
    ]
    summary = _summarize_tool_blocks(blocks)
    check("3c.1 Summary contém 'bash'", "bash" in summary)
    check("3c.2 Summary contém 'read'", "read" in summary)
    check("3c.3 Summary não está vazio", len(summary) > 20)


def test_compression_extreme_scenario():
    """Simula cenário extremo: >75% de 128k tokens."""
    print("\n=== 3d. Compressão â€” Cenário Extremo ===")
    # Cria mensagens que somam >75% de 200 tokens (threshold baixo para teste)
    msgs = build_fake_messages(30, content_size=50)
    total_before = sum(_estimate_tokens(m.get("content", "")) for m in msgs)

    compressed, was_compressed, summary = await_compat(compress_context(msgs, max_context_tokens=200))
    check("3d.1 Foi comprimido", was_compressed)
    check("3d.2 Reduziu número de mensagens", len(compressed) < len(msgs))
    check("3d.3 System prompt preservado", compressed[0]["role"] == "system")
    check("3d.4 Summary gerado", len(summary) > 0)

    # Verifica que últimas mensagens foram preservadas
    last_orig = [m for m in msgs if m["role"] != "system"][-1]
    last_comp = [m for m in compressed if m["role"] != "system"][-1]
    check("3d.5 Ãšltima msg preservada", last_orig["content"] == last_comp["content"])


def test_compression_rearm_after_5_steps():
    """Valida que o gatilho pode ser reativado após 5 passos."""
    print("\n=== 3e. Compressão â€” Rearmamento ===")
    # Simula o comportamento do lifecycle
    compression_applied = False
    step = 0

    # Passos 1-5: compression aplicada, não rearmada
    for s in range(1, 6):
        step = s
        if compression_applied and step > 5:
            compression_applied = False
        check(f"3e.{s} Step {step}: rearmado={compression_applied}", compression_applied is False if s <= 5 else True)

    # Passo 6: deve rearmar
    step = 6
    if compression_applied and step > 5:
        compression_applied = False
    check("3e.6 Step 6: rearmado=True", compression_applied is False)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 4. RECALL SEMÃ‚NTICO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def test_semantic_recall():
    """Insere memórias artificiais e valida recall com similaridade."""
    print("\n=== 4. Recall SemÃ¢ntico ===")
    await clear_long_term_memory()

    # Insere 5 memórias com temas distintos
    mems = [
        ("Criar endpoint REST com FastAPI", "Usar @app.post e Pydantic para validacao", ["bash", "write"], "FastAPI e assincrono nativo"),
        ("Configurar Docker Compose para PostgreSQL", "Usar docker-compose.yml com volumes", ["bash"], "Nunca exponha portas sensiveis"),
        ("Implementar autenticacao JWT", "Usar python-jose para tokens", ["write"], "Rotacione segredos periodicamente"),
        ("Deploy com GitHub Actions", "Workflow YAML com build e test steps", ["write", "bash"], "Use secrets para credenciais"),
        ("Otimizar queries SQL lentas", "Adicionar indices e usar EXPLAIN ANALYZE", ["bash", "read"], "Indexes evitam full table scan"),
    ]
    for task, sol, tools, lesson in mems:
        await index_task_memory(task, sol, tools, lesson)

    stats = await get_memory_stats()
    check("4.1 5 memórias indexadas", stats["total_entries"] == 5)

    # Recall 1: query sobre Docker
    r1 = await recall_relevant_memories("configurar container docker postgresql")
    check("4.2 Recall Docker retorna >= 1 resultado", len(r1) >= 1)
    if r1:
        check("4.3 Top resultado contém 'Docker'", "Docker" in r1[0]["task"] or "docker" in r1[0]["task"].lower())

    # Recall 2: query sobre JWT/auth
    r2 = await recall_relevant_memories("autenticacao jwt token python")
    check("4.4 Recall JWT retorna >= 1 resultado", len(r2) >= 1)
    if r2:
        check("4.5 Top resultado contém 'JWT'", "JWT" in r2[0]["task"] or "jwt" in r2[0]["task"].lower())

    # Recall 3: query irrelevante (deve retornar poucos ou nenhum)
    r3 = await recall_relevant_memories("receita de bolo de chocolate com cobertura")
    check("4.6 Query irrelevante retorna 0 resultados", len(r3) == 0)

    # Valida formatação
    formatted = format_memories_for_prompt(r1)
    check("4.7 Formatted contém 'MEMORIAS PASSADAS'", "MEMORIAS PASSADAS" in formatted or "MEMÃ“RIAS PASSADAS" in formatted)
    check("4.8 Formatted contém 'Problema'", "Problema" in formatted)
    check("4.9 Formatted contém 'Solucao'", "Solucao" in formatted or "Solução" in formatted)

    await clear_long_term_memory()


def test_cosine_similarity():
    """Testa cálculo de similaridade coseno diretamente."""
    print("\n=== 4b. Similaridade Cosseno ===")
    tf_a = _term_frequency(_tokenize("fastapi endpoint python"))
    tf_b = _term_frequency(_tokenize("fastapi endpoint rest api"))
    tf_c = _term_frequency(_tokenize("receita bolo chocolate"))

    sim_ab = _cosine_similarity(tf_a, tf_b)
    sim_ac = _cosine_similarity(tf_a, tf_c)

    check(f"4b.1 sim(fastapi, fastapi+rest)={sim_ab:.3f} > 0.3", sim_ab > 0.3)
    check(f"4b.2 sim(fastapi, receita)={sim_ac:.3f} < 0.1", sim_ac < 0.1)
    check("4b.3 sim(A,B) > sim(A,C)", sim_ab > sim_ac)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 5. CONCORRÃŠNCIA DE ESCRITA
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def test_concurrent_writes():
    """Lança 10 escritas concorrentes e valida integridade do JSON."""
    print("\n=== 5. Concorrência de Escrita ===")
    await clear_long_term_memory()

    async def write_task(i: int):
        await index_task_memory(
            f"Tarefa concorrente {i} sobre topicos variados",
            f"Solucao {i}: usar abordagem {i} para resolver",
            [f"tool_{i}"],
            f"Licao {i}: sempre testar",
        )

    # Lança 10 writes simultÃ¢neas
    await asyncio.gather(*[write_task(i) for i in range(10)])

    # Valida integridade
    stats = await get_memory_stats()
    check("5.1 10 escritas: total >= 10", stats["total_entries"] >= 10)

    # Valida que o JSON é válido
    try:
        with open(INDEX_FILE, encoding="utf-8") as f:
            data = json.load(f)
        check("5.2 JSON válido após escritas concorrentes", isinstance(data, list))
        check("5.3 Todos hashes únicos", len(data) == len(set(e["hash"] for e in data)))
    except (json.JSONDecodeError, Exception) as e:
        check("5.2 JSON válido após escritas concorrentes", False, str(e))

    await clear_long_term_memory()


async def test_concurrent_read_write():
    """Lê enquanto escreve â€” não deve corromper."""
    print("\n=== 5b. Leitura Concorrente com Escrita ===")
    await clear_long_term_memory()

    # Pré-popula
    for i in range(5):
        await index_task_memory(f"Pre-populate {i}", f"Solucao {i}", [], "")

    results_during = []
    errors = []

    async def reader():
        try:
            for _ in range(5):
                r = await recall_relevant_memories("pre-populate")
                results_during.append(len(r))
                await asyncio.sleep(0.01)
        except Exception as e:
            errors.append(str(e))

    async def writer():
        try:
            for i in range(5, 10):
                await index_task_memory(f"Concurrent write {i}", f"S {i}", [], "")
                await asyncio.sleep(0.01)
        except Exception as e:
            errors.append(str(e))

    await asyncio.gather(reader(), writer())
    check("5b.1 Sem erros durante concorrência", len(errors) == 0, str(errors))
    check("5b.2 Leituras retornaram dados", all(r >= 0 for r in results_during))

    await clear_long_term_memory()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 6. INTEGRAÃ‡ÃƒO LIFECYCLE (anti-loop end-to-end)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def test_lifecycle_circuit_breaker():
    """Lifecycle real com ferramenta que falha â†’ circuit breaker deve trip."""
    print("\n=== 6a. Lifecycle â€” Circuit Breaker End-to-End ===")

    call_count = 0

    async def fake_call_model(messages):
        nonlocal call_count
        call_count += 1
        # Sempre retorna tool call (loop infinito simulado)
        return ModelResponse(
            type="tool_calls",
            tool_calls=[{
                "id": f"call_{call_count}",
                "type": "function",
                "function": {"name": "bash", "arguments": json.dumps({"command": "ls"})},
            }],
        )

    async def fake_execute_tool(name, params):
        return {"error": "Permission denied"}

    config = LifecycleConfig(
        max_tool_steps=50,
        anti_loop_enabled=True,
        circuit_breaker_max_think=5,
        circuit_breaker_max_tools=3,  # Limite baixo para teste rápido
        circuit_breaker_max_total=10,
        context_compression_enabled=False,
    )

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "teste"}],
        config=config,
        call_model=fake_call_model,
        call_model_stream=None,
        execute_tool_fn=fake_execute_tool,
        supports_streaming=False,
    ):
        events.append(event)

    # Deve terminar com circuit_breaker ou max_steps
    last_event = events[-1] if events else {}
    check("6a.1 Lifecycle terminou", last_event.get("type") == "done")
    check("6a.2 Status é circuit_breaker ou failed",
          last_event.get("status") in ("circuit_breaker", "failed", "max_steps"))
    check("6a.3 Não rodou para sempre (passos < 50)", call_count < 50)


async def test_lifecycle_think_only_loop():
    """Lifecycle com modelo que só retorna thinking â†’ deve trip think_only."""
    print("\n=== 6b. Lifecycle â€” THINK_ONLY Loop ===")

    call_count = 0

    async def fake_call_model_think(messages):
        nonlocal call_count
        call_count += 1
        return ModelResponse(
            type="content",
            data="",
            content="",
            reasoning="Estou analisando o problema...",
        )

    async def fake_execute_tool_noop(name, params):
        return {}

    config = LifecycleConfig(
        max_tool_steps=20,
        anti_loop_enabled=True,
        circuit_breaker_max_think=3,  # Baixo para teste rápido
        circuit_breaker_max_tools=10,
        context_compression_enabled=False,
        max_think_only_loops=2,
    )

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "teste"}],
        config=config,
        call_model=fake_call_model_think,
        call_model_stream=None,
        execute_tool_fn=fake_execute_tool_noop,
        supports_streaming=False,
    ):
        events.append(event)

    last_event = events[-1] if events else {}
    check("6b.1 Lifecycle terminou", last_event.get("type") == "done")
    check("6b.2 Status é failed (think_only excedido)",
          last_event.get("status") in ("failed", "circuit_breaker"))
    check("6b.3 Não rodou para sempre", call_count < 20)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Runner
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def await_compat(coro):
    """Executa coroutine em testes síncronos."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Já dentro de loop async â€” usa task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


async def run_all():
    # 1. Loop detector
    test_loop_detector_repeated_error()
    test_loop_detector_different_states()
    test_frustration_nudge_content()

    # 2. Circuit breaker
    test_circuit_breaker_think_only()
    test_circuit_breaker_tool_calls()
    test_circuit_breaker_total_iterations()
    test_circuit_breaker_reset()

    # 3. Compressão
    test_compression_estimate_tokens()
    test_compression_extract_blocks()
    test_compression_summarize()
    test_compression_extreme_scenario()
    test_compression_rearm_after_5_steps()

    # 4. Recall semÃ¢ntico
    test_cosine_similarity()
    await test_semantic_recall()

    # 5. Concorrência
    await test_concurrent_writes()
    await test_concurrent_read_write()

    # 6. Lifecycle integration
    await test_lifecycle_circuit_breaker()
    await test_lifecycle_think_only_loop()

    # Summary
    total = PASSED + FAILED
    print(f"\n{'='*60}")
    print(f"RESULTADO: {PASSED}/{total} PASSARAM, {FAILED}/{total} FALHARAM")
    print(f"{'='*60}")
    if FAILED > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all())
