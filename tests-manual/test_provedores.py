"""
Teste: registro de provedores (comuns + personalizados criados pelo usuario).

BUG REAL QUE ORIGINOU ISTO (relatado pelo usuario)
"no projeto nao tem onde inserir a chave do provedor openai"

`openai`, `opencode` e `openclaude` eram suportados pelo backend, tinham chave
carregada no frontend e estavam no mapa de envio — mas NAO existiam na lista que
monta os campos da tela, entao nao havia onde colar a chave.

Pedido do usuario: "pode inserir outros provedores ou uma opcao para que eu crie
provedores novos, pois sempre tem provedores novos; ja deixa no projeto os mais
comuns incluso".

Este teste garante as duas coisas:
  1. os provedores comuns existem no registro e tem metadados validos;
  2. o usuario consegue criar/editar/remover um provedor proprio, e esse provedor
     passa a funcionar no caminho real do chat (`get_client`).
"""
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
sys.path.insert(0, str(BACKEND))

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


print("=== 1. Provedores comuns: os que faltavam estao no registro ===")
from core import provedores as P  # noqa: E402

# Estes eram os que NAO tinham campo na interface.
OBRIGATORIOS = ["openai", "openrouter", "openclaude", "opencode", "gemini", "groq",
                "nvidia", "zhipu", "mimo", "ollama", "llamacpp"]
for pid in OBRIGATORIOS:
    check(pid in P.PRESETS, f"'{pid}' registrado", f"'{pid}' NAO esta no registro")

print()
print("=== 2. Provedores comuns novos (pedido: 'ja deixa os mais comuns') ===")
NOVOS = ["deepseek", "xai", "mistral", "anthropic", "together", "fireworks",
         "cerebras", "perplexity", "deepinfra", "hyperbolic",
         "lmstudio", "vllm", "textgenwebui", "jan"]
for pid in NOVOS:
    check(pid in P.PRESETS, f"'{pid}' incluido", f"'{pid}' nao foi incluido")

print()
print("=== 3. Todo preset tem metadados utilizaveis ===")
for pid, meta in P.PRESETS.items():
    problemas = []
    if not meta.get("label"):
        problemas.append("sem label")
    if not meta.get("base_url"):
        problemas.append("sem base_url")
    elif not str(meta["base_url"]).startswith(("http://", "https://")):
        problemas.append("base_url invalida")
    if not meta.get("compativel_openai", True):
        problemas.append("nao compativel com o SDK do OpenAI")
    if problemas:
        check(False, f"'{pid}' ok", f"'{pid}': {', '.join(problemas)}")
check(all(
    p.get("label") and p.get("base_url") and str(p["base_url"]).startswith(("http://", "https://"))
    for p in P.PRESETS.values()
), f"todos os {len(P.PRESETS)} presets tem label + base_url valida",
   "algum preset esta incompleto")

print()
print("=== 4. slug(): nome digitado -> id seguro para variavel de ambiente ===")
casos = [
    ("Meu Provedor", "meu_provedor"),
    ("Configuração Nova", "configuracao_nova"),   # acento removido, nao virou '_'
    ("Provedor 2", "provedor_2"),
    ("2 Provedores", "p_2_provedores"),           # nao pode comecar com numero
    ("a-b/c.d", "a_b_c_d"),
    ("", ""),
]
for entrada, esperado in casos:
    obtido = P.slug(entrada)
    check(obtido == esperado, f"slug({entrada!r}) = {obtido!r}", f"slug({entrada!r}) = {obtido!r}, esperado {esperado!r}")

# O id vira NOME DE VARIAVEL DE AMBIENTE: so pode ter [A-Z0-9_]
import re  # noqa: E402
for entrada, _ in casos:
    s = P.slug(entrada)
    if s:
        check(re.fullmatch(r"[a-z][a-z0-9_]*", s) is not None,
              f"slug({entrada!r}) e um nome valido de variavel",
              f"slug({entrada!r}) = {s!r} nao serve como nome de variavel de ambiente")

print()
print("=== 5. Criar, resolver, listar e remover provedor personalizado ===")
# Isola o arquivo real: o teste nao pode mexer nos provedores do usuario.
ORIGINAL = P.ARQUIVO
TMP = Path(tempfile.mkdtemp(prefix="deepos_prov_")) / "provedores_custom.json"
P.ARQUIVO = TMP

try:
    check(P.listar_custom() == [], "comeca vazio", "o arquivo temporario nao comecou vazio")

    criado = P.salvar({
        "label": "Meu Provedor Teste",
        "base_url": "https://api.exemplo.com/v1",
        "models": ["modelo-a", "modelo-b"],
    })
    check(criado["id"] == "meu_provedor_teste", f"id gerado: {criado['id']}", f"id inesperado: {criado['id']}")
    check(criado["key_env"] == "MEU_PROVEDOR_TESTE_API_KEY",
          "env da chave segue o padrao <ID>_API_KEY",
          f"env inesperado: {criado['key_env']}")
    check(len(criado["models"]) == 2, "2 modelos salvos", f"modelos: {criado['models']}")

    # Resolver precisa achar como provedor registrado
    meta = P.resolver("meu_provedor_teste")
    check(meta is not None, "resolver() encontra o provedor criado", "resolver() NAO encontrou o provedor criado")
    check(meta and meta["base_url"] == "https://api.exemplo.com/v1",
          "resolver() devolve a base_url correta", f"base_url: {meta and meta.get('base_url')}")

    # E o caminho REAL do chat precisa aceitar
    from core.llm_native import get_client
    cliente = get_client("meu_provedor_teste", api_key_override="chave-falsa")
    check(cliente is not None, "get_client() aceita o provedor criado",
          "get_client() NAO aceita um provedor criado pelo usuario")
    check("exemplo.com" in str(cliente.base_url),
          "get_client() usa a base_url do provedor", f"base_url do cliente: {cliente.base_url}")

    # Sem chave e sem ser local, tem de reclamar de forma clara
    try:
        get_client("meu_provedor_teste")
        check(False, "sem chave reclama", "aceitou provedor sem chave sem reclamar")
    except ValueError as e:
        check("API_KEY" in str(e).upper(), f"sem chave a mensagem e clara", f"mensagem pouco clara: {e}")

    # Atualizar preserva os modelos quando o novo vem vazio
    P.salvar({"id": "meu_provedor_teste", "label": "Meu Provedor Teste", "base_url": "https://api.exemplo.com/v2"})
    meta2 = P.resolver("meu_provedor_teste")
    check(meta2 and meta2["base_url"] == "https://api.exemplo.com/v2",
          "atualizar troca a base_url", f"base_url: {meta2 and meta2.get('base_url')}")
    check(meta2 and len(meta2["models"]) == 2,
          "atualizar NAO apaga os modelos quando o novo vem vazio",
          f"os modelos foram perdidos: {meta2 and meta2.get('models')}")

    # Validacoes
    for ruim, motivo in [
        ({"label": "", "base_url": "https://x.com"}, "sem nome"),
        ({"label": "X", "base_url": ""}, "sem base_url"),
        ({"label": "X", "base_url": "ftp://x.com"}, "base_url sem http"),
        ({"label": "Openai", "base_url": "https://x.com"}, "nome que colide com provedor do codigo"),
    ]:
        try:
            P.salvar(ruim)
            check(False, f"recusa {motivo}", f"ACEITOU entrada invalida ({motivo}): {ruim}")
        except ValueError:
            check(True, f"recusa {motivo}", "")

    # listar() precisa trazer os dois grupos
    tudo = P.listar()
    check(len(tudo["comuns"]) == len(P.PRESETS), f"listar() traz {len(tudo['comuns'])} comuns",
          f"listar() trouxe {len(tudo['comuns'])} comuns, esperado {len(P.PRESETS)}")
    check(len(tudo["personalizados"]) == 1, "listar() traz 1 personalizado",
          f"personalizados: {len(tudo['personalizados'])}")

    # Remover
    check(P.remover("meu_provedor_teste") is True, "remover() devolve True",
          "remover() nao removeu")
    check(P.resolver("meu_provedor_teste") is None, "provedor removido nao resolve mais",
          "o provedor removido ainda resolve")
    check(P.remover("nao_existe") is False, "remover() inexistente devolve False",
          "remover() de inexistente devolveu True")

finally:
    P.ARQUIVO = ORIGINAL

print()
print("=== 6. Presets NAO podem ser removidos pelo usuario ===")
check(P.remover("openai") is False, "remover('openai') e recusado",
      "o usuario conseguiu remover um provedor do codigo")
check(P.resolver("openai") is not None, "'openai' continua registrado",
      "'openai' sumiu do registro")

print()
print("=== 7. Rota de provedores existe e vem ANTES do catch-all ===")
ROTAS = BACKEND / "routes" / "config.py"
texto = ROTAS.read_text(encoding="utf-8")
pos_prov = texto.find('@router.get("/provedores")')
pos_catch = texto.find('@router.get("/{section}")')
check(pos_prov != -1, "existe GET /api/config/provedores", "rota de provedores ausente")
check(pos_catch != -1, "existe o catch-all", "catch-all desapareceu")
check(pos_prov != -1 and pos_catch != -1 and pos_prov < pos_catch,
      "a rota de provedores vem ANTES do catch-all (FastAPI resolve por ordem)",
      "a rota de provedores vem DEPOIS do catch-all — nunca sera alcancada")
check('@router.post("/provedores")' in texto, "existe POST /api/config/provedores",
      "nao ha rota para criar provedor")
check('@router.delete("/provedores/{pid}")' in texto, "existe DELETE /api/config/provedores/{pid}",
      "nao ha rota para remover provedor")
check('@router.post("/provedores/modelos")' in texto, "existe rota para buscar modelos",
      "nao ha rota para buscar a lista de modelos do provedor")

print()
print("=== 8. A interface usa a lista do BACKEND (nao so a estatica) ===")
JARVIS = RAIZ / "frontend" / "src" / "components" / "saas" / "JarvisPage.tsx"
cj = JARVIS.read_text(encoding="utf-8")
check("/api/config/provedores" in cj,
      "o frontend busca a lista de provedores do backend",
      "o frontend so usa a lista estatica — provedor novo do backend nao aparece")
check("provedoresComChave" in cj,
      "a secao de chaves e montada a partir da lista unificada",
      "a secao de chaves nao usa a lista unificada (risco do bug do openai voltar)")
check("Adicionar provedor" in cj,
      "existe o botao '+ Adicionar provedor'",
      "o usuario nao consegue criar provedor novo pela interface")
check("Buscar modelos" in cj or ">Modelos<" in cj or "'Modelos'" in cj,
      "existe o botao de buscar modelos",
      "nao ha como carregar os modelos de um provedor novo")

print()
print("=== 9. Salvar chave funciona para provedor NOVO (nao so os do mapa fixo) ===")
# Dois bugs da mesma familia que o registro introduziria se o mapa fixo ficasse:
#   (a) SALVAR: o payload era montado de `envKeyMap[prov.keyField]`, que so
#       conhece os nove originais. Num provedor novo isso e `undefined`, entao a
#       chave era descartada em silencio.
#   (b) LER: o `envToField` era fixo, entao um provedor novo nunca recebia o
#       marcador de "chave salva" — o campo aparecia vazio com a chave no servidor.
check("_API_KEY`" in cj or "_API_KEY'" in cj or "toUpperCase()}_API_KEY" in cj,
      "o frontend monta <ID>_API_KEY quando o provedor nao esta no mapa fixo",
      "sem fallback, salvar a chave de um provedor novo nao envia nada (envKeyMap[id] = undefined)")
check("const envToField" not in cj,
      "a leitura das chaves nao usa mais mapa fixo (usa as chaves da resposta)",
      "o `envToField` fixo ainda existe — provedor novo nunca mostra 'chave salva'")

# E o backend precisa REPORTAR a chave dos provedores novos
import asyncio  # noqa: E402


async def _checar_api_keys():
    from routes.config import get_api_keys
    return await get_api_keys()


try:
    reportado = asyncio.run(_checar_api_keys())
    check(isinstance(reportado, dict) and len(reportado) >= len(P.PRESETS),
          f"GET /api/config/api-keys reporta os {len(P.PRESETS)} provedores do registro",
          f"reportou apenas {len(reportado) if isinstance(reportado, dict) else '?'} — provedor novo apareceria como '(vazia)'")
    for pid in ["openai", "deepseek", "mistral", "lmstudio"]:
        check(pid in (reportado or {}), f"'{pid}' aparece no GET /api-keys",
              f"'{pid}' NAO aparece no GET /api-keys")
except Exception as e:
    check(False, "GET /api-keys executou", f"erro: {type(e).__name__}: {e}")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — provedores comuns + personalizados OK")
