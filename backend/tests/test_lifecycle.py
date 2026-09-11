"""Quick integration test for state machine + lifecycle."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.state_machine import (
    State, FinishReason, ContentCategory, ModelResponse,
    classify_finish_reason, classify_content, validate_tool_call,
    extract_observation, log_transition, LifecycleEvent,
)
from core.lifecycle import (
    LifecycleConfig, LifecycleState, run_lifecycle,
    _has_checkboxes, _has_task_plan_json, _PLANNING_TOLL_NUDGE,
)

# â”€â”€ Test classify_finish_reason â”€â”€
assert classify_finish_reason("tool_calls") == FinishReason.TOOL_CALLS
assert classify_finish_reason("function_call") == FinishReason.TOOL_CALLS
assert classify_finish_reason("length") == FinishReason.LENGTH
assert classify_finish_reason("max_tokens") == FinishReason.LENGTH
assert classify_finish_reason("content_filter") == FinishReason.CONTENT_FILTER
assert classify_finish_reason("stop") == FinishReason.STOP
assert classify_finish_reason("end_turn") == FinishReason.STOP
assert classify_finish_reason(None) == FinishReason.UNKNOWN
print("[PASS] classify_finish_reason")

# â”€â”€ Test classify_content â”€â”€
assert classify_content("Hello world") == ContentCategory.HAS_RESPONSE
assert classify_content("") == ContentCategory.ONLY_THINK
assert classify_content("   ") == ContentCategory.ONLY_THINK
print("[PASS] classify_content")

# â”€â”€ Test validate_tool_call â”€â”€
valid_tc = {"id": "123", "function": {"name": "bash", "arguments": '{"command": "ls"}'}}
v = validate_tool_call(valid_tc)
assert v.valid is True
assert v.tool_name == "bash"
assert v.params == {"command": "ls"}

invalid_tc = {"id": "123", "function": {"name": "", "arguments": ""}}
v2 = validate_tool_call(invalid_tc)
assert v2.valid is False
print("[PASS] validate_tool_call")

# â”€â”€ Test extract_observation â”€â”€
assert "stdout" in extract_observation({"stdout": "hello"})
assert extract_observation("hello") == "hello"
assert extract_observation(None) == ""
print("[PASS] extract_observation")

# â”€â”€ Test log_transition â”€â”€
log_transition(State.START, State.CALL_MODEL, "test", 1)
log_transition(State.CALL_MODEL, State.CHECK_RESPONSE, "test", 2)
print("[PASS] log_transition")

# â”€â”€ Test LifecycleState â”€â”€
ls = LifecycleState()
assert ls.current_state == State.START
ls.transition(State.CALL_MODEL, "test")
assert ls.current_state == State.CALL_MODEL
assert len(ls.events) == 1
ls.append_observation("bash", "test output")
assert len(ls.observations) == 1
ls.reset_stream_accumulators()
assert ls.accumulated_content == ""
assert ls.collected_tool_calls == []
print("[PASS] LifecycleState")

# â”€â”€ Test LifecycleConfig â”€â”€
cfg = LifecycleConfig(max_tool_steps=50, max_api_retries=5)
assert cfg.max_tool_steps == 50
assert cfg.max_api_retries == 5
print("[PASS] LifecycleConfig")

# â”€â”€ Test async lifecycle with mock (non-streaming, immediate final) â”€â”€
import asyncio

async def test_lifecycle_final():
    call_count = 0

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        return ModelResponse(type="content", data="Resposta final do modelo.")

    async def mock_execute(tool_name, params):
        return {"stdout": "ok"}

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "test"}],
        config=LifecycleConfig(max_tool_steps=5),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=mock_execute,
        supports_streaming=False,
    ):
        events.append(event)

    assert call_count == 1
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["answer"] == "Resposta final do modelo."
    print("[PASS] lifecycle final answer")

asyncio.run(test_lifecycle_final())

# â”€â”€ Test async lifecycle with tool call loop â”€â”€
async def test_lifecycle_tool_loop():
    call_count = 0
    tool_count = 0

    plan_content = (
        "- [ ] Listar arquivos\n"
        "- [ ] Processar resultado\n"
        '{"type":"task_plan","steps":["Listar arquivos","Processar resultado"]}'
    )

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                type="tool_calls",
                tool_calls=[{
                    "id": "tc1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": '{"command": "ls"}'},
                }],
                content=plan_content,
            )
        return ModelResponse(type="content", data="Agora sim, resposta final.")

    async def mock_execute(tool_name, params):
        nonlocal tool_count
        tool_count += 1
        return {"stdout": "file1.py\nfile2.py"}

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "test"}],
        config=LifecycleConfig(max_tool_steps=10),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=mock_execute,
        supports_streaming=False,
    ):
        events.append(event)

    assert call_count == 2
    assert tool_count == 1
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert "resposta final" in done_events[0]["answer"]
    print("[PASS] lifecycle tool call loop")

asyncio.run(test_lifecycle_tool_loop())

# â”€â”€ Test think_only nudge â”€â”€
async def test_lifecycle_think_only():
    call_count = 0

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return ModelResponse(type="content", data="", reasoning="Pensamento interno...")
        return ModelResponse(type="content", data="Resposta apos pensar.")

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "test"}],
        config=LifecycleConfig(max_tool_steps=10, max_think_only_loops=3),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=lambda t, p: {},
        supports_streaming=False,
    ):
        events.append(event)

    assert call_count == 4
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["answer"] == "Resposta apos pensar."
    print("[PASS] lifecycle think_only nudge")

asyncio.run(test_lifecycle_think_only())

# â”€â”€ Test API error retry â”€â”€
async def test_lifecycle_api_error():
    call_count = 0

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return ModelResponse(type="content", error="Rate limit exceeded")
        return ModelResponse(type="content", data="Recovered!")

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "test"}],
        config=LifecycleConfig(max_tool_steps=10, max_api_retries=3, api_retry_base_delay=0.01),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=lambda t, p: {},
        supports_streaming=False,
    ):
        events.append(event)

    assert call_count == 3
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["answer"] == "Recovered!"
    print("[PASS] lifecycle API error retry")

asyncio.run(test_lifecycle_api_error())

# â”€â”€ Test truncated â”€â”€
async def test_lifecycle_truncated():
    async def mock_call_model(messages):
        return ModelResponse(type="content", data="Resposta truncada...", finish_reason=FinishReason.LENGTH)

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "test"}],
        config=LifecycleConfig(max_tool_steps=10),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=lambda t, p: {},
        supports_streaming=False,
    ):
        events.append(event)

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0].get("status") == "truncated"
    print("[PASS] lifecycle truncated")

asyncio.run(test_lifecycle_truncated())

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PLANNING TOLL ENFORCEMENT TESTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# â”€â”€ Test _has_checkboxes â”€â”€
assert _has_checkboxes("- [ ] Analisar codigo\n- [ ] Criar estrutura") is True
assert _has_checkboxes("- [x] Feito\n- [~] Rodando") is True
assert _has_checkboxes("- [ ] So uma meta") is False
assert _has_checkboxes("Sem checkboxes") is False
assert _has_checkboxes("") is False
assert _has_checkboxes(None) is False
print("[PASS] _has_checkboxes")

# â”€â”€ Test _has_task_plan_json â”€â”€
assert _has_task_plan_json('{"type":"task_plan","steps":["a","b"]}') is True
assert _has_task_plan_json('{"type": "task_plan", "steps": ["a"]}') is True
assert _has_task_plan_json('Aqui esta o plano:\n{"type":"task_plan","steps":["x"]}') is True
assert _has_task_plan_json('Sem JSON aqui') is False
assert _has_task_plan_json('{"type":"other","steps":["a"]}') is False
assert _has_task_plan_json("") is False
assert _has_task_plan_json(None) is False
print("[PASS] _has_task_plan_json")

# â”€â”€ Test planning toll: BLOCKS tool calls without plan on step 1 â”€â”€
async def test_planning_toll_blocks_no_plan():
    call_count = 0

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                type="tool_calls",
                tool_calls=[{
                    "id": "tc1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": '{"command": "ls"}'},
                }],
                content="Vou listar os arquivos.",
            )
        return ModelResponse(type="content", data="Resposta final.")

    tool_executed = False
    async def mock_execute(tool_name, params):
        nonlocal tool_executed
        tool_executed = True
        return {"stdout": "ok"}

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "liste os arquivos"}],
        config=LifecycleConfig(max_tool_steps=10, planning_enforced=True, planning_check_steps=2),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=mock_execute,
        supports_streaming=False,
    ):
        events.append(event)

    # Step 1: tool call blocked. Step 2: should re-circulate and model gives final answer
    assert tool_executed is False, "Tool should NOT have been executed (planning not presented)"
    assert call_count == 2
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["answer"] == "Resposta final."
    print("[PASS] planning toll blocks no plan")

asyncio.run(test_planning_toll_blocks_no_plan())

# â”€â”€ Test planning toll: ALLOWS tool calls WITH plan on step 1 â”€â”€
async def test_planning_toll_allows_with_plan():
    call_count = 0

    plan_content = (
        "Vou analisar o codigo.\n\n"
        "- [ ] Analisar codigo existente\n"
        "- [ ] Criar estrutura necessaria\n\n"
        '{"type":"task_plan","steps":["Analisar codigo existente","Criar estrutura necessaria"]}'
    )

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                type="tool_calls",
                tool_calls=[{
                    "id": "tc1",
                    "type": "function",
                    "function": {"name": "read", "arguments": '{"path": "main.py"}'},
                }],
                content=plan_content,
            )
        return ModelResponse(type="content", data="Analise concluida.")

    tool_executed = False
    async def mock_execute(tool_name, params):
        nonlocal tool_executed
        tool_executed = True
        return {"content": "codigo aqui"}

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "analise o codigo"}],
        config=LifecycleConfig(max_tool_steps=10, planning_enforced=True, planning_check_steps=2),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=mock_execute,
        supports_streaming=False,
    ):
        events.append(event)

    assert tool_executed is True, "Tool SHOULD have been executed (plan was presented)"
    assert call_count == 2
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    print("[PASS] planning toll allows with plan")

asyncio.run(test_planning_toll_allows_with_plan())

# â”€â”€ Test planning toll: SKIPS check after step 2 â”€â”€
async def test_planning_toll_skips_after_step2():
    call_count = 0

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return ModelResponse(type="content", data="", reasoning="Pensando...")
        if call_count == 3:
            # Step 3: tool call WITHOUT plan â€” should be allowed (past check window)
            return ModelResponse(
                type="tool_calls",
                tool_calls=[{
                    "id": "tc1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": '{"command": "ls"}'},
                }],
                content="",
            )
        return ModelResponse(type="content", data="Pronto.")

    tool_executed = False
    async def mock_execute(tool_name, params):
        nonlocal tool_executed
        tool_executed = True
        return {"stdout": "ok"}

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "teste"}],
        config=LifecycleConfig(max_tool_steps=10, planning_enforced=True, planning_check_steps=2),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=mock_execute,
        supports_streaming=False,
    ):
        events.append(event)

    # Step 1 & 2: think only â†’ nudge. Step 3: tool call allowed (past check window)
    assert tool_executed is True, "Tool should be allowed after step 2"
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    print("[PASS] planning toll skips after step 2")

asyncio.run(test_planning_toll_skips_after_step2())

# â”€â”€ Test planning toll: DISABLED when planning_enforced=False â”€â”€
async def test_planning_toll_disabled():
    call_count = 0

    async def mock_call_model(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                type="tool_calls",
                tool_calls=[{
                    "id": "tc1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": '{"command": "ls"}'},
                }],
                content="Sem planejamento.",
            )
        return ModelResponse(type="content", data="Feito.")

    tool_executed = False
    async def mock_execute(tool_name, params):
        nonlocal tool_executed
        tool_executed = True
        return {"stdout": "ok"}

    events = []
    async for event in run_lifecycle(
        messages=[{"role": "user", "content": "teste"}],
        config=LifecycleConfig(max_tool_steps=10, planning_enforced=False),
        call_model=mock_call_model,
        call_model_stream=None,
        execute_tool_fn=mock_execute,
        supports_streaming=False,
    ):
        events.append(event)

    assert tool_executed is True, "Tool should execute when enforcement is disabled"
    assert call_count == 2
    print("[PASS] planning toll disabled")

asyncio.run(test_planning_toll_disabled())

# â”€â”€ Test planning nudge message content â”€â”€
assert "Mandamento" in _PLANNING_TOLL_NUDGE
assert "checklist" in _PLANNING_TOLL_NUDGE.lower()
assert "task_plan" in _PLANNING_TOLL_NUDGE
print("[PASS] planning nudge message content")

print("\n=== ALL TESTS PASSED ===")
