# WBC-ZERO-G 5.0 — Legacy Architecture Decisions (Completed)
_Extracted from MEMORY.md §Discovered durable knowledge. Historical completed work from 2026-06-21._

## Three-Pillar Adaptive Architecture (2026-06-21, COMPLETED)
Expanded the lifecycle engine with three interconnected systems:
1. **Elastic Memory** (`memory/elastic_memory.py`): Zero-dependency TF-cosine similarity vector search. Indexes structured task summaries on FINAL state. Retrieves relevant past insights at START of new tasks via `recall_relevant_memo ries()`. Persisted to `data/memory/long_term/index.json` (max 500 entries, SHA-256 dedup). Runs alongside existing `brain.py` FAQ system.
2. **Anti-Loop Protection** (`core/state_machine.py`): `StateHashTracker` (MD5 of reasoning[:500] + tool_name, detects same pattern >2 consecutive times), `CircuitBreaker` (hard limits: max 5 THINK_ONLY, max 7 tool calls, max 20 total iterations per subtask), `FRUSTRATION_NUDGE` (imperative system message injected before FAILED state, resets counters for one retry).
3. **Context Compression** (`core/context_compression.py`): Reactive summarization at 75% token window (128k default). Consolidates old THINK_ONLY + tool blocks into abstract paragraph. Preserves system prompt + last 40% of messages + last user message. Reopens compression window every 5 steps.

## Zero-dependency elastic memory over FAISS
New `elastic_memory.py` uses its own tokenizer + TF + cosine similarity (no ML libraries). Old FAISS/HuggingFace stack retained in `vector_memory.py` for backward compatibility with `brain.py`.

## Dual learning on task completion
`agents/loop.py` calls both `index_task_memory()` (elastic memory) AND `aprender_com_a_tarefa()` (brain.py/FAQ). Elastic memory is primary long-term storage; brain.py provides backward compatibility.

## Anti-loop is per-lifecycle-execution
Each `run_lifecycle()` call gets fresh `CircuitBreaker` and `StateHashTracker`. Limits are per-subtask, not global.

## Planning Toll Enforcement (2026-06-21, COMPLETED)
Hard enforcement gate in `run_lifecycle()` at TOOL_CALLS branch. When `step ≤ 2` and model response has `tool_calls` but lacks reasoning text with markdown checkboxes and `task_plan` JSON — BLOCK tool execution. Inject imperative system message and `continue` the loop. Three files: `lifecycle.py` (validation gate), `chat.py` (prompt injection), `prompts.py` (prompt content).

## Crisis Resolution Architecture (2026-06-21, COMPLETED)
1. **Contextualized Frustration Nudge**: `FRUSTRATION_NUDGE` uses `<CRITICAL_SYSTEM_ALERT_ANTI_LOOP>` tags. `build_frustration_nudge_with_context()` injects last 5 tool actions with errors + forced self-explanation + strategy-change options (A-D).
2. **Graceful Failure Diagnostic**: `_compile_failure_diagnostics()` extracts last tool_logs, failed tools with params/errors, last reasoning excerpt. `_build_graceful_failure_message()` generates friendly Portuguese message with explanation + suggestions.
3. **Anti-Pattern Semantic Memory**: `index_failure_lesson()` records `[FAILURE_LESSON]` entries in `index.json` with `is_failure: True` flag. Future `recall_relevant_memo ries()` surfaces these as warnings.
4. **Atomic Write for Concurrent Safety**: `_save_index()` uses `tempfile.mkstemp()` + `os.replace()` (with Windows fallback to `unlink()` + `rename()`). `asyncio.Lock` serializes all writes.
5. **Iteration Break for Plan-Execution Separation**: When `has_presented_plan` transitions False→True, yield plan event and `continue` WITHOUT calling `_handle_tool_calls()`. Forces new model call for execution.

## Lifecycle state machine (2026-06-21, COMPLETED)
Replaced ad-hoc while loop in `agents/loop.py` with formal state machine (`core/state_machine.py` 16 states + `core/lifecycle.py` engine). States: START→CALL_MODEL→CHECK_RESPONSE→(API_ERROR→retry | ACCUMULATE_STREAM→CLASSIFY_FINISH→(tool_calls→VALIDATE_TOOL→EXECUTE_TOOL→APPEND_OBSERVATION→loop | length→TRUNCATED | content_filter→FILTERED | stop→CLASSIFY_CONTENT→(FINAL | THINK_ONLY→nudge→loop | FAILED))). Engine is async generator yielding event dicts. Preserves all existing safety locks. **finish_reason priority**: raw_finish_reason > response.finish_reason > tool_calls > STOP default. 12/12 integration tests passing.
