# DEEP-OS — Execução de ferramentas: quando o modelo "anuncia e não faz"

**Última atualização:** 2026-09-12

Este documento explica o bug relatado —

> *"o modelo parece estar com dificuldade de utilizar as ferramentas… o modelo
> fala que vai fazer e fica ali no plano de execução e não faz"*

— e como o painel de execução foi refeito no estilo do VS Code.

---

## 1. O sintoma exato

No chat aparecia isto, **cru**, no meio da resposta:

```
<｜DSML｜og7d8j9uokjb1t4tq4l459m5f3…>…</｜DSML｜og7d8j9t?
```

E antes disso o modelo mostrava um plano:

```
Checklist:
[x] Reconhecer solicitação (buscar arquivos .gguf e pastas de modelos)
[ ] Varrer /root e subpastas
[ ] Varrer diretórios comuns (/home, /opt, /workspace, /models, /data)
[ ] Compilar resultado e mostrar localizações
Executando agora:
```

…e **nada era executado**. Pedir "pode executar" só repetia o plano.

---

## 2. Eram DOIS bugs somados

### Bug A — o formato DSML era desconhecido

Alguns modelos — sobretudo **DeepSeek V3.2 / V4 via OpenRouter** — não devolvem
`tool_calls` estruturado. Eles escrevem o **markup nativo deles dentro do
texto**:

```
<｜DSML｜tool_calls>
  <｜DSML｜invoke name="bash">
    <｜DSML｜parameter name="command" string="true">ls -la /root</｜DSML｜parameter>
  </｜DSML｜invoke>
</｜DSML｜tool_calls>
```

O DEEP-OS só conhecia XML do Gemini, JSON e `bash("...")`. Não reconhecia nada
disso, então **nenhuma ferramenta era executada** — o texto virava a "resposta
final" — e o markup **vazava para a tela**.

> **`DSML` aparece em nenhum lugar do código antes desta correção.** Foi a pista
> que fechou o diagnóstico.

É um problema conhecido e documentado do próprio DeepSeek:
- [Tool calls not parsed correctly with DeepSeek-V4](https://github.com/NousResearch/hermes-agent/issues/15453)
- [PR: stop deepseek.v3.2 leaking tool-call scaffolding into the text channel](https://github.com/NousResearch/hermes-agent/pull/98764)
- [Discussão no HuggingFace: DSML markup no output](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/discussions/209)

**Detalhe que faz diferença:** o delimitador usa a barra vertical de **largura
total** (`｜`, U+FF5C), não o `|` ASCII (U+007C). Comparar com o caractere errado
faz o parser **nunca** casar. O `_DSML_VERTICAIS` aceita os dois.

### Bug B — faltava o fallback no caminho das TAREFAS

Este é o mais grave e explica por que "não faz":

| Caminho | Tinha fallback de texto? |
|---------|--------------------------|
| `stream_chat_with_tools` (chat em streaming) | ✅ tinha |
| **`complete_chat_with_tools`** (usado pelas **tarefas**) | ❌ **não tinha** |

Se o modelo não devolvesse `tool_calls` nativo, o texto era tratado como
resposta final e **o loop terminava**. Como as tarefas usam o caminho
não-streaming, a assimetria produzia exatamente o sintoma: anuncia, mostra o
plano, e para.

---

## 3. Formatos suportados agora

`extrair_tools_do_texto()` cobre, nesta ordem:

| Formato | Quem usa |
|---------|----------|
| **DSML** com container `tool_calls` | DeepSeek **V4** |
| **DSML** com container `function_calls` | DeepSeek **V3.2** |
| DSML com `<invoke>` solto (sem container) | variações do modelo |
| XML do Gemini (`<tc_call><function=…>`) | Gemini |
| JSON em bloco de código ou solto | vários |
| `bash("comando")` | vários |
| `{"action": …, "action_input": …}` | MiMo V2.5 |

### Tolerâncias implementadas (todas observadas na prática)

- container Ausente — o modelo às vezes solta só o `<invoke>`;
- parâmetros como **tags XML** *ou* como **JSON cru** dentro do invoke;
- atributo `string="true|false"` **opcional**;
- aspas simples ou duplas no nome da função;
- barra vertical larga (U+FF5C) ou ASCII (U+007C);
- **várias** chamadas na mesma resposta (DSML devolve lista, não só uma).

### Tipagem dos parâmetros

| Atributo | Comportamento |
|----------|---------------|
| `string="true"` | mantém **texto** (caminhos, comandos) |
| `string="false"` | interpreta (número, booleano, lista, objeto) |
| ausente | tenta JSON **apenas se o valor parecer JSON** |

Esse último caso é importante: sem ele, um comando como `ls -la` ou um caminho
como `downloads` seria corrompido na conversão. Há teste específico para isso.

---

## 4. O markup nunca mais aparece para o usuário

`limpar_markup_dsml()` remove o markup do texto exibido, **inclusive** tags com
nome ilegível (que o modelo às vezes emite). O conteúdo extraído vai para a
execução — repeti-lo na resposta só poluiria.

Também foi verificado que texto **sem** DSML volta intacto: uma resposta normal
que contenha `|` ou `{json}` no meio não é alterada.

---

## 5. Painel de execução no estilo VS Code

**Antes:** lista plana. Cada evento virava um bloco idêntico, sem hierarquia,
sem duração, sem o plano real. O frontend **ignorava** os eventos
`task_checklist`, `task_progress` e `thinking` que o backend já enviava.

**Agora**, três camadas — o mesmo vocabulário visual do painel de tarefas do
VS Code:

```
▶ EXECUÇÃO                                    2/4 passos
▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  50%
────────────────────────────────────────────────────────
PLANO
 ✔ 1  Reconhecer solicitação
 ◐ 2  Varrer /root e subpastas            ← gira enquanto executa
 ○ 3  Varrer diretórios comuns
 ○ 4  Compilar resultado
────────────────────────────────────────────────────────
ATIVIDADE
 ● 🛠 bash                                     1.2s  15:56:01
   ├─ passo 1   {"command":"find / -name '*.gguf'"}
 ● ✔ glob                                     0.3s  15:56:03
   └─ passo 2   {"pattern":"**/*.gguf"}
 ● ℹ Resposta concluida                    412 tokens 15:56:05
────────────────────────────────────────────────────────
● Executando    50%                    12 eventos
```

O que mudou na prática:

| Antes | Agora |
|-------|-------|
| lista plana, sem hierarquia | **árvore** com conectores (`├─`, `└─`) |
| sem noção de tempo | **duração** por ferramenta (`1.2s`, `840ms`, `1m03s`) |
| plano só como texto do modelo | **plano real** vindo do backend, com estado por passo |
| passo parado parecia travado | **ícone girando** no passo em execução |
| sem visão do todo | **barra de progresso** e contador `2/4` |
| eventos `thinking`/`task_*` descartados | todos tratados e exibidos |

**Detalhe de cor:** a barra fica âmbar enquanto executa, **verde** a 100% e
**vermelha** se algum passo falhar — a leitura de estado é imediata.

---

## 6. Por que isso não vai voltar

`tests-manual/test_dsml_tools.py` (35 verificações) cobre:

- as duas variantes de container e as tolerâncias de formato;
- **tipagem**: que `ls -la` continue texto (senão a ferramenta `bash` quebra);
- **remoção do markup**, incluindo a tag ilegível do print do usuário;
- que texto comum **não** vire chamada de ferramenta;
- e uma verificação **estrutural**: que os **dois** caminhos (streaming e
  não-streaming) usem o extrator e limpem o markup — foi essa assimetria que
  causou o bug.

---

## Ver também

- [`MODELOS.md`](MODELOS.md) — por que modelos davam 404; o `/models` que mente
- [`PROVEDORES.md`](PROVEDORES.md) — provedores comuns e personalizados
- [`CHARON-VOZ.md`](CHARON-VOZ.md) — a arquitetura da voz
- [`../memory.md`](../memory.md) — regras e armadilhas do projeto
