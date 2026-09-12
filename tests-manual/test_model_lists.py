"""
Teste: as listas de modelos do frontend estao coerentes e sem IDs extintos.

CONTEXTO (bugs reais encontrados)
1. DIVERGENCIA ENTRE OS DOIS ARQUIVOS
   `frontend/src/lib/constants.ts` e `components/saas/JarvisPage.tsx` declaravam
   as mesmas listas de forma diferente: os IDs da NVIDIA tinham prefixo
   `nvidia/` num arquivo e nao no outro. Como o prefixo e OBRIGATORIO (testado
   com chamada real: com prefixo 200, sem prefixo 404), um dos dois lugares
   estava necessariamente quebrado.

2. IDS EXTINTOS
   Havia 9+ IDs que nao existem mais nas APIs (llama-3.3-70b-versatile na Groq,
   gemini-1.5-*, anthropic/claude-3.5-sonnet no OpenRouter, gemini-2.0-flash no
   Google...). Escolher um deles dava 404 sem nenhuma pista para o usuario.

3. PROVEDOR INVISIVEL
   `zhipu` tinha lista de modelos em MODELS mas NAO estava no array PROVIDERS,
   entao nunca aparecia no seletor.

Este teste roda OFFLINE (so le os arquivos) e trava esses tres casos.
A verificacao contra as APIs de verdade e feita por `tools/provar-modelos.cjs`,
que precisa de internet e por isso nao entra na suite automatica.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONSTANTS = RAIZ / "frontend" / "src" / "lib" / "constants.ts"
JARVIS = RAIZ / "frontend" / "src" / "components" / "saas" / "JarvisPage.tsx"

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


def ler(caminho: Path) -> str:
    if not caminho.exists():
        print(f"   FALHOU arquivo nao encontrado: {caminho}")
        falhas.append(f"arquivo ausente: {caminho}")
        return ""
    return caminho.read_text(encoding="utf-8")


# ── Extrai MODELS de constants.ts ────────────────────────────────────────────
def extrair_models_constants(texto: str) -> dict:
    """Le o objeto MODELS: { groq: [ {value:'x'} ], ... }."""
    inicio = texto.find("export const MODELS")
    if inicio == -1:
        return {}
    corpo = texto[inicio:]
    resultado = {}
    # Cada bloco: nome: [ ... ]
    for m in re.finditer(r"^\s{2}(\w+):\s*\[(.*?)^\s{2}\],", corpo, re.S | re.M):
        nome = m.group(1)
        ids = re.findall(r"value:\s*'([^']+)'", m.group(2))
        resultado[nome] = ids
    return resultado


# ── Extrai PROVIDERS de constants.ts (array de nomes) ────────────────────────
def extrair_providers_constants(texto: str) -> list:
    m = re.search(r"export const PROVIDERS\s*=\s*\[(.*?)\]", texto, re.S)
    if not m:
        return []
    return re.findall(r"'([^']+)'", m.group(1))


# ── Extrai PROVIDERS de JarvisPage.tsx (objetos com id e models) ──────────────
# Nomes de provedores cujos modelos vem do runtime (Ollama, llama.cpp):
# preenchido por extrair_providers_jarvis.
DINAMICOS = set()


def extrair_providers_jarvis(texto: str) -> dict:
    """
    Le o array PROVIDERS de JarvisPage.tsx.

    Implementacao por DIVISAO, nao por regex "preguicoso".

    Por que: o provider `ollama` tem `models: []` (lista vazia — os modelos vem
    do runtime). Com regex do tipo `id:'x'...models:\\[(.*?)\\]`, o grupo vazio
    nao fecha o padrao, o motor continua avançando e captura os modelos do
    provider SEGUINTE. Isso gerou falso positivo ("ollama DIVERGE") duas vezes.

    Dividindo o array em blocos por `{ id: '`, cada bloco contem exatamente um
    provider, e basta pegar o PRIMEIRO `models: [...]` de cada bloco.
    """
    inicio = texto.find("const PROVIDERS = [")
    if inicio == -1:
        return {}
    fim = texto.find("\n];", inicio)
    corpo = texto[inicio:fim] if fim != -1 else texto[inicio:]

    resultado = {}
    # Cada bloco de provider comeca em "\n  { id: 'nome'" — EXATAMENTE 2 espacos
    # de indentacao. Isso e essencial: as entradas de MODELO tambem sao
    # "{ id: '...' }", mas com 4 espacos. Sem exigir a indentacao exata, o split
    # fatiava cada modelo como se fosse um provider (59 pedacos em vez de 6) e a
    # lista saia vazia.
    pedacos = re.split(r"(?m)^ {2}\{\s*id:\s*'", corpo)
    for pedaco in pedacos[1:]:  # o primeiro pedaco e o cabecalho do array
        m_nome = re.match(r"(\w+)'", pedaco)
        if not m_nome:
            continue
        nome = m_nome.group(1)
        # Primeiro "models: [ ... ]" DESTE bloco
        m_mod = re.search(r"models:\s*\[(.*?)\]", pedaco, re.S)
        ids = re.findall(r"id:\s*'([^']+)'", m_mod.group(1)) if m_mod else []
        resultado[nome] = ids
        if re.search(r"dynamic:\s*true", pedaco):
            DINAMICOS.add(nome)
    return resultado


print("=== 1. Os arquivos existem e declararam as listas ===")
tc = ler(CONSTANTS)
tj = ler(JARVIS)
models = extrair_models_constants(tc)
prov_const = extrair_providers_constants(tc)
prov_jarvis = extrair_providers_jarvis(tj)

check(bool(models), f"MODELS lido de constants.ts ({len(models)} provedores)", "nao consegui ler MODELS de constants.ts")
check(bool(prov_const), f"PROVIDERS lido de constants.ts ({len(prov_const)})", "nao consegui ler PROVIDERS de constants.ts")
check(bool(prov_jarvis), f"PROVIDERS lido de JarvisPage.tsx ({len(prov_jarvis)})", "nao consegui ler PROVIDERS de JarvisPage.tsx")

print()
print("=== 2. Todo provedor com modelos aparece no seletor (bug do zhipu) ===")
for nome in sorted(models):
    if nome == "llamacpp":
        continue  # lista vazia de proposito (detectada em runtime)
    check(nome in prov_const,
          f"'{nome}' esta em PROVIDERS",
          f"'{nome}' tem modelos em MODELS mas NAO esta em PROVIDERS (nunca aparece no seletor)")

print()
print("=== 3. Listas iguais nos dois arquivos (bug da divergencia) ===")
comuns = sorted(set(models) & set(prov_jarvis))
check(len(comuns) >= 5, f"{len(comuns)} provedores presentes nos dois arquivos", "poucos provedores em comum — parsing suspeito")
for nome in comuns:
    a, b = set(models[nome]), set(prov_jarvis[nome])
    if nome in DINAMICOS:
        # Ollama/llama.cpp sao `dynamic: true`: a lista real vem de
        # /ollama/models em runtime. Em constants.ts fica so um fallback
        # estatico, entao as duas listas DIFEREM de proposito.
        check(True,
              f"'{nome}': dinamico — JarvisPage detecta em runtime, constants.ts tem fallback de {len(a)}",
              "")
        continue
    if not a and not b:
        continue
    iguais = a == b
    check(iguais, f"'{nome}': {len(a)} modelos identicos nos dois arquivos",
          f"'{nome}' DIVERGE -> so em constants.ts: {sorted(a - b)} | so em JarvisPage: {sorted(b - a)}")

print()
print("=== 4. Nenhum ID extinto conhecido ===")
# IDs que foram confirmados como inexistentes nas APIs reais.
MORTOS = {
    # Groq
    "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama-3.3-70b-instruct",
    "minimaxai/minimax-m2.7",
    # Gemini
    "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-pro-latest", "gemini-1.5-flash-latest",
    "gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-2.0-flash-exp",
    "gemini-2.5-flash-preview-04-17", "gemini-2.5-pro-preview-05-06", "gemini-2.5-pro",
    # OpenRouter
    "anthropic/claude-3.5-sonnet", "anthropic/claude-3-haiku:free",
    "meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.1-70b-instruct:free", "google/gemini-2.0-flash-exp:free",
    "google/gemma-3-27b-it:free", "deepseek/deepseek-chat-v3-0324:free",
    "qwen/qwen-2.5-72b-instruct:free", "mistralai/mistral-7b-instruct:free",
    "microsoft/phi-4-reasoning:free",
    # NVIDIA (a conta nao tem acesso ou o ID mudou)
    "llama-3.1-nemotron-70b-instruct", "llama-3.3-nemotron-super-49b-v1",
    "llama-3.1-nemotron-8b-v1", "llama-3.1-nemotron-mini-4b-instruct",
    "meta/llama-3.1-405b-instruct", "meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct",
    "mistralai/mistral-large-2-instruct", "google/gemma-2-27b-it", "gemma-2-9b-it",
    "phi-3-medium-4k-instruct", "mistral-nemo-12b-instruct", "gemma-2-9b-it",
    # OpenCode zen (nao existem no catalogo)
    "nemotron-3-super-free",
    # Zhipu
    "glm-4-flash", "glm-4-plus", "glm-4v-flash",
}

todos_ids = {}
for nome, ids in models.items():
    for i in ids:
        todos_ids.setdefault(i, []).append(f"constants.ts/{nome}")
for nome, ids in prov_jarvis.items():
    for i in ids:
        todos_ids.setdefault(i, []).append(f"JarvisPage.tsx/{nome}")

encontrados = {i: onde for i, onde in todos_ids.items() if i in MORTOS}
for i, onde in sorted(encontrados.items()):
    print(f"   MORTO  {i}  ({', '.join(onde)})")
check(not encontrados,
      f"nenhum dos {len(MORTOS)} IDs extintos esta nas listas",
      f"{len(encontrados)} ID(s) extinto(s) ainda nas listas (ver acima)")

print()
print("=== 5. IDs da NVIDIA mantem o prefixo obrigatorio ===")
# Testado com chamada real: 'nvidia/nemotron-3-super-120b-a12b' -> 200,
# 'nemotron-3-super-120b-a12b' -> 404. Sem o prefixo, o modelo nao existe.
nv = []
for nome, ids in models.items():
    if nome == "nvidia":
        nv += ids
for nome, ids in prov_jarvis.items():
    if nome == "nvidia":
        nv += ids
sem_prefixo = [i for i in set(nv) if "/" not in i]
check(not sem_prefixo,
      f"todos os {len(set(nv))} IDs da NVIDIA tem prefixo (nvidia/, meta/, deepseek-ai/)",
      f"IDs da NVIDIA SEM prefixo (dao 404): {sem_prefixo}")

print()
print("=== 6. Defaults do backend nao usam modelo extinto ===")
BACKEND_CFG = RAIZ / "backend" / "core" / "config.py"
BACKEND_BOT = RAIZ / "backend" / "routes" / "chatbot.py"

def sem_comentarios(texto: str, ext: str) -> str:
    """
    Remove comentarios antes de procurar IDs extintos.

    Necessario porque os proprios comentarios que EXPLICAM a correcao citam o ID
    antigo (ex: '# "gemini-1.5-pro" foi extinto...'), e sem isto o teste acusava
    falha no arquivo ja corrigido. Comentario nao e codigo em uso.
    """
    if ext == ".py":
        return "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("#"))
    return texto


for arquivo in (BACKEND_CFG, BACKEND_BOT):
    if not arquivo.exists():
        continue
    bruto = arquivo.read_text(encoding="utf-8")
    texto = sem_comentarios(bruto, arquivo.suffix)
    achados = [m for m in MORTOS if f'"{m}"' in texto or f"'{m}'" in texto]
    check(not achados,
          f"{arquivo.name}: sem modelo extinto nos defaults (fora de comentarios)",
          f"{arquivo.name} ainda usa como default: {achados}")

print()
print("=== 7. Todo provedor do backend tem campo de chave na interface ===")
# BUG REAL (relatado pelo usuario): "no projeto nao tem onde inserir a chave do
# provedor openai". `openai`, `opencode` e `openclaude` eram suportados pelo
# backend (core/llm_native.py), tinham chave carregada e estavam no mapa de envio
# — mas NAO existiam em PROVIDERS, e o modal monta um campo por item de
# PROVIDERS (`PROVIDERS.filter(p => !p.dynamic)`). Resultado: nenhum lugar para
# colar a chave. Este teste garante que os dois lados nao divirjam de novo.

LLM_NATIVE = RAIZ / "backend" / "core" / "llm_native.py"
prov_backend = set()
if LLM_NATIVE.exists():
    bruto = LLM_NATIVE.read_text(encoding="utf-8")
    sem_com = "\n".join(l for l in bruto.splitlines() if not l.lstrip().startswith("#"))
    prov_backend = set(re.findall(r'provider\s*==\s*"(\w+)"', sem_com))

check(bool(prov_backend), f"li {len(prov_backend)} provedores de llm_native.py", "nao consegui ler llm_native.py")

# Provedores com keyField na interface (os que precisam de chave)
com_campo = {n for n, cfg in prov_jarvis.items() if n in models or n in DINAMICOS}
# Ollama/llama.cpp nao usam chave; openclaude tem chave mas servidor local.
SEM_CHAVE = {"ollama", "llamacpp", "llm"}

faltando = sorted(p for p in prov_backend if p not in SEM_CHAVE and p not in prov_jarvis)
check(not faltando,
      f"todos os provedores do backend tem entrada na interface ({len(prov_backend - SEM_CHAVE - set(faltando))})",
      f"provedores SEM campo de chave na interface: {faltando} "
      f"(o usuario nao tem onde colar a chave!)")

# E o inverso: um provedor na interface que o backend nao conhece nao funciona
extra = sorted(p for p in prov_jarvis if p not in prov_backend and p not in SEM_CHAVE)
check(not extra,
      "nenhum provedor na interface e desconhecido do backend",
      f"provedores na interface que o backend NAO suporta: {extra}")

print()
print("=== 8. Botao de teste de chave existe e usa chamada real ===")
ROTAS_CONFIG = RAIZ / "backend" / "routes" / "config.py"
if ROTAS_CONFIG.exists():
    rc = ROTAS_CONFIG.read_text(encoding="utf-8")
    check("testar-chave" in rc,
          "existe o endpoint POST /api/config/testar-chave",
          "nao existe endpoint para testar a chave")
    check("complete_chat" in rc,
          "o teste usa o MESMO caminho de codigo do chat (complete_chat)",
          "o teste nao usa o caminho real do chat — o veredito nao refletiria a realidade")
    # Nao pode validar por /models: descobrimos que aquele endpoint mente.
    # A checagem e feita SO no corpo de `testar_chave` — o `/models` aparece
    # legitimamente em `buscar_modelos_do_provedor` (o botao "Modelos"), que e
    # outra funcao e nao serve para validar chave. Varrer o arquivo inteiro
    # acusava falso positivo.
    m_teste = re.search(r"async def testar_chave\(.*?\n(?=@router|class |# ──)", rc, re.S)
    corpo_teste = m_teste.group(0) if m_teste else ""
    check(bool(corpo_teste), "isolei o corpo de testar_chave", "nao consegui isolar testar_chave")

    # Remove docstring e comentarios antes de checar.
    #
    # TERCEIRA vez que esta armadilha apareceu nesta suite: a propria docstring
    # de `testar_chave` EXPLICA que nao usa /models ("Nao usa `/models` de
    # proposito..."), e a busca por texto encontrava essa mencao e acusava falha
    # no codigo correto. Documentacao nao e codigo em uso.
    corpo_codigo = re.sub(r'""".*?"""', "", corpo_teste, flags=re.S)
    corpo_codigo = re.sub(r"'''.*?'''", "", corpo_codigo, flags=re.S)
    corpo_codigo = "\n".join(
        l for l in corpo_codigo.splitlines() if not l.strip().startswith("#")
    )

    check("/models" not in corpo_codigo,
          "o teste NAO valida a chave pelo /models (que mente)",
          "testar_chave usa /models — o do OpenRouter e publico e aprova chave falsa")

    # O botao "Buscar modelos" PODE usar /models (e o unico jeito de listar um
    # provedor desconhecido) — mas deve avisar quando nao e confiavel.
    check("NAO_CONFIAVEIS" in rc and "confiavel" in rc,
          "o 'Buscar modelos' marca os provedores cujo /models nao e confiavel",
          "o 'Buscar modelos' nao avisa sobre OpenRouter/NVIDIA, cujo /models engana")
else:
    print("   PULADO  backend/routes/config.py nao encontrado")

check("Testar" in tj or "Testar" in tc,
      "o frontend tem botao 'Testar' por provedor",
      "nao ha botao para testar a chave na interface")

print()
print("=" * 68)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — listas coerentes e sem IDs extintos")
