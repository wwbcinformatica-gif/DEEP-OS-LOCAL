# Modelos PROVADOS por chamada real

Gerado por `node tools/provar-modelos.cjs`.
So entra nesta lista o modelo que respondeu HTTP 200 com texto de verdade.

## groq (7)

- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`
- `qwen/qwen3.6-27b`
- `qwen/qwen3.8-27b`
- `groq/compound`
- `groq/compound-mini`
- `allam-2-7b`

## gemini (7)

- `gemini-3.6-flash`
- `gemini-3.5-flash`
- `gemini-3.5-flash-lite`
- `gemini-3-flash-preview`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-flash-latest`

## openrouter (0)


## nvidia (8)

- `nvidia/nemotron-3-super-120b-a12b`
- `nvidia/nemotron-3.5-lightning-30b-a3b`
- `meta/llama-3.2-11b-vision-instruct`
- `meta/muse-glimmer-30b`
- `z-ai/glm-5.3-flash`
- `deepseek-ai/deepseek-v4-pro-0813`
- `deepseek-ai/deepseek-v4-flash-0731`
- `openai/gpt-oss-20b`

## zhipu (0)


## Falharam (NAO usar)

- `gemini-3.1-pro-preview` (gemini) — HTTP 429 — You exceeded your current quota, please check your plan and billing details. For more information on this erro
- `gemini-2.5-pro` (gemini) — HTTP 404 — This model models/gemini-2.5-pro is no longer available to new users. Please update your code to use models/ge
- `gemini-pro-latest` (gemini) — HTTP 429 — You exceeded your current quota, please check your plan and billing details. For more information on this erro
- `openrouter/auto` (openrouter) — HTTP 401 — User not found.
- `anthropic/claude-opus-4.6` (openrouter) — HTTP 401 — User not found.
- `anthropic/claude-sonnet-4.6` (openrouter) — HTTP 401 — User not found.
- `anthropic/claude-haiku-4.5` (openrouter) — HTTP 401 — User not found.
- `openai/gpt-4o` (openrouter) — HTTP 401 — User not found.
- `openai/gpt-4o-mini` (openrouter) — HTTP 401 — User not found.
- `openai/gpt-4.1` (openrouter) — HTTP 401 — User not found.
- `openai/gpt-4.1-mini` (openrouter) — HTTP 401 — User not found.
- `google/gemini-2.5-pro` (openrouter) — HTTP 401 — User not found.
- `google/gemini-2.5-flash` (openrouter) — HTTP 401 — User not found.
- `google/gemini-3.5-flash` (openrouter) — HTTP 401 — User not found.
- `deepseek/deepseek-v3.2` (openrouter) — HTTP 401 — User not found.
- `deepseek/deepseek-v4-flash` (openrouter) — HTTP 401 — User not found.
- `qwen/qwen3-235b-a22b` (openrouter) — HTTP 401 — User not found.
- `meta-llama/llama-3.3-70b-instruct` (openrouter) — HTTP 401 — User not found.
- `mistralai/mistral-large-2512` (openrouter) — HTTP 401 — User not found.
- `x-ai/grok-4.6` (openrouter) — HTTP 401 — User not found.
- `nvidia/nemotron-3-ultra-550b-a55b` (nvidia) — read ECONNRESET
- `nvidia/llama-3.1-nemotron-ultra-253b-v1` (nvidia) — HTTP 404 — Function '84bf12ff-edbd-4435-baea-0fa6a7453d2e': Not found for account 'DYJ4w2djeK-LN9TmSaspSlwUHkgAdxWZB53p5q
- `nvidia/llama-3.1-nemotron-70b-instruct` (nvidia) — HTTP 404 — Function '9b96341b-9791-4db9-a00d-4e43aa192a39': Not found for account 'DYJ4w2djeK-LN9TmSaspSlwUHkgAdxWZB53p5q
- `nvidia/llama-3.1-nemotron-51b-instruct` (nvidia) — HTTP 404 — Function '5beba52c-65a9-4f46-8cd9-656689a1b205': Not found for account 'DYJ4w2djeK-LN9TmSaspSlwUHkgAdxWZB53p5q
- `meta/llama-3.2-90b-vision-instruct` (nvidia) — read ECONNRESET
- `mistralai/mistral-large-2-instruct` (nvidia) — HTTP 404 — Function '7fadd4de-e22a-48e4-90e9-f02ef14a74b9': Not found for account 'DYJ4w2djeK-LN9TmSaspSlwUHkgAdxWZB53p5q
- `google/gemma-4-31b-it` (nvidia) — read ECONNRESET
- `google/gemma-3-12b-it` (nvidia) — HTTP 404 — Function 'ee47df99-c92b-4dc9-b3a7-f3fb0f087b73': Not found for account 'DYJ4w2djeK-LN9TmSaspSlwUHkgAdxWZB53p5q
- `moonshotai/kimi-k3` (nvidia) — read ECONNRESET
- `moonshotai/kimi-k2.6` (nvidia) — HTTP 404 — Function '23d4f03a-b8a6-4adb-a183-7daa083a09cc': Not found for account 'DYJ4w2djeK-LN9TmSaspSlwUHkgAdxWZB53p5q
- `nemotron-3-super-120b-a12b` (nvidia) — HTTP 404 — 404 page not found

- `glm-5.3` (zhipu) — HTTP 429 — 余额不足或无可用资源包,请充值。
- `glm-5.3-flash` (zhipu) — HTTP 429 — 余额不足或无可用资源包,请充值。
- `glm-5.2` (zhipu) — HTTP 429 — 余额不足或无可用资源包,请充值。
- `glm-5` (zhipu) — HTTP 429 — 余额不足或无可用资源包,请充值。
- `glm-4.7` (zhipu) — HTTP 429 — 余额不足或无可用资源包,请充值。
- `glm-4.6` (zhipu) — HTTP 429 — 余额不足或无可用资源包,请充值。