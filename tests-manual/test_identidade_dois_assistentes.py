"""
Teste: a IDENTIDADE e a mesma nos dois assistentes (Charon e Jarvis).

O QUE O USUARIO VIU
Ele trocou o nome do usuario no Charon e o JARVIS continuou chamando a pessoa
pelo nome antigo. "eu tinha salvo um nome de usuario de yuri no charon que ja foi
trocado para wilson e agora em jarvis ele acabou recebendo que o usuario tem o
nome de yuri".

CAUSA
Os dois liam de fontes DIFERENTES:

  - Charon (`voice_ws.py`) .... `core.tenant_identity.get_identity(tenant)` -> BANCO
  - Jarvis (`chat.py`) ........ `config.yaml` da RAIZ -> um arquivo GLOBAL

O Charon gravava no tenant (por assinante) e o Jarvis continuava lendo o arquivo
global, que ninguem atualizava. Num SaaS isso e pior: `config.yaml` e um arquivo
so para TODOS os assinantes, entao a identidade de um cliente apareceria no chat
do outro.

CORRECAO
`_load_identity` do Jarvis passou a seguir a MESMA ordem da rota
`/api/config/identity`: tenant (JWT / ContextVar) primeiro, `config.yaml` como
fallback para o app sem login. E o cache passou a ser POR CHAVE — um cache unico
faria o primeiro assinante a chamar "emprestar" a identidade para os outros.

Roda OFFLINE.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
sys.path.insert(0, str(BACKEND))

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


CHAT = (BACKEND / "routes" / "chat.py").read_text(encoding="utf-8")
VOICE = (BACKEND / "routes" / "voice_ws.py").read_text(encoding="utf-8")

print("=== 1. O Jarvis le a identidade do TENANT, nao do arquivo global ===")
check("from core.tenant_identity import get_identity as _get_tenant_identity" in CHAT,
      "o chat.py importa a identidade do tenant",
      "o Jarvis continua lendo so o config.yaml global")
check("get_current_tenant" in CHAT,
      "o Jarvis tambem olha o tenant do ContextVar central",
      "sem o ContextVar, a identidade por assinante nao chega no chat")
# O cache tem de ser por chave: um cache unico mistura assinantes.
check("__global__" in CHAT,
      "o cache da identidade e por chave (tenant x global)",
      "ha um cache unico — o primeiro assinante 'empresta' a identidade aos outros")

print()
print("=== 2. Os dois assistentes usam o MESMO modulo de identidade ===")
check("core.tenant_identity" in VOICE,
      "o Charon le a identidade do tenant",
      "o Charon nao usa o modulo central de identidade")
check("core.tenant_identity" in CHAT,
      "o Jarvis le a identidade do tenant",
      "os dois divergem — era exatamente a causa do nome trocado")

print()
print("=== 3. Roda de verdade: tenant x global dao resultados coerentes ===")
try:
    import main  # noqa: E402
    from core.models import Message  # noqa: E402
    from core.tenant_identity import set_current_tenant  # noqa: E402
    from routes.chat import _load_identity, build_system_prompt  # noqa: E402

    set_current_tenant(None)
    sem_tenant = _load_identity()
    check(bool(sem_tenant.get("assistant_name")),
          f"sem login, cai no global: {sem_tenant.get('assistant_name')!r}",
          "sem login nao devolveu identidade nenhuma")

    TENANT = "master-admin:wwbc22@gmail.com"
    set_current_tenant(TENANT)
    com_tenant = _load_identity()
    check(com_tenant.get("assistant_name") == "Atena",
          f"com o tenant do usuario, o Jarvis ve {com_tenant.get('assistant_name')!r}",
          f"com tenant devolveu {com_tenant.get('assistant_name')!r} "
          f"(o banco tem 'Atena')")

    # O prompt do Jarvis tem de carregar o nome do TENANT, nao o global.
    sp = build_system_prompt(Message(user="oi", provider="groq", model="x", assistente="jarvis"))
    check("EXATAMENTE: Atena" in sp,
          "o system prompt do Jarvis usa o nome do assistente do TENANT",
          "o prompt do Jarvis nao carrega o nome do tenant")
    check("Nome do usuario:" in sp,
          "o system prompt do Jarvis traz o nome do usuario",
          "o prompt do Jarvis nao traz o nome do usuario")

    # CONTROLE NEGATIVO: sem tenant, o prompt NAO pode trazer o nome do assinante.
    set_current_tenant(None)
    sp_global = build_system_prompt(Message(user="oi", provider="groq", model="x", assistente="jarvis"))
    check("EXATAMENTE: Atena" not in sp_global,
          "sem login, o prompt NAO vaza a identidade do assinante",
          "sem login o Jarvis entregou a identidade de um assinante — vazamento")

    # E o cache nao pode misturar: voltando ao tenant, tem de dar o valor dele.
    set_current_tenant(TENANT)
    de_novo = _load_identity()
    check(de_novo.get("assistant_name") == "Atena",
          "alternar tenant/global nao mistura o cache",
          f"depois de ir e voltar, veio {de_novo.get('assistant_name')!r}")
    set_current_tenant(None)
except Exception as e:
    check(False, "o cenario de identidade executou", f"{type(e).__name__}: {e}")

print()
print("=== 3b. NOME DO USUARIO e separado por assistente ===")
# DECISAO DO USUARIO: "o jarvis e jarvis ele nao tem charon" e "separados tambem"
# — nome do ASSISTENTE compartilhado, nome do USUARIO separado por assistente.
# Foi o defeito relatado: "salvei yuri no charon, troquei para wilson, e o jarvis
# recebeu yuri".
try:
    from core.tenant_identity import get_identity, set_identity  # noqa: E402

    T = "master-admin:wwbc22@gmail.com"
    # Guarda o que estava para restaurar no fim (nao deixar dado de teste).
    antes_charon = get_identity(T, "charon")["user_name"]
    antes_jarvis = get_identity(T, "jarvis")["user_name"]

    set_identity(T, "Atena", "Yuri", voice="Kore", assistente="charon")
    set_identity(T, "Atena", "Wilson", voice="Kore", assistente="jarvis")

    c = get_identity(T, "charon")
    j = get_identity(T, "jarvis")
    check(c["user_name"] == "Yuri" and j["user_name"] == "Wilson",
          f"cada assistente tem o seu nome de usuario (charon={c['user_name']!r}, "
          f"jarvis={j['user_name']!r})",
          f"os nomes se misturaram: charon={c['user_name']!r} jarvis={j['user_name']!r}")
    check(c["assistant_name"] == j["assistant_name"],
          f"o nome do ASSISTENTE continua unico para os dois: {c['assistant_name']!r}",
          "o nome do assistente ficou separado — o usuario pediu um so")

    # E o prompt do chat tem de respeitar isso (o Jarvis recebe o nome do Jarvis).
    # ATENCAO: `build_system_prompt` le o tenant do ContextVar quando nao recebe
    # um — sem definir o tenant aqui, os dois prompts caem no config.yaml global e
    # o teste acusa troca de nomes sem que exista defeito (foi o que aconteceu na
    # primeira execucao: os dois vinham 'Wilson', do global).
    set_current_tenant(T)
    sp_c = build_system_prompt(Message(user="oi", provider="groq", model="x", assistente="charon"))
    sp_j = build_system_prompt(Message(user="oi", provider="groq", model="x", assistente="jarvis"))
    set_current_tenant(None)
    check("Nome do usuario: Yuri" in sp_c and "Nome do usuario: Wilson" in sp_j,
          "cada prompt leva o nome do seu assistente",
          "os prompts trocaram os nomes de usuario entre si")

    # CONTROLE NEGATIVO: sem perfil, usa o campo compartilhado (nao um dos dois).
    generico = get_identity(T)
    check(generico["user_name"] in ("Wilson", "Yuri"),
          f"sem perfil, cai no campo compartilhado ({generico['user_name']!r})",
          "sem perfil devolveu algo inesperado")

    # Restaura o estado do banco.
    set_identity(T, "Atena", antes_charon or "Wilson", voice="Kore", assistente="charon")
    set_identity(T, "Atena", antes_jarvis or "Wilson", voice="Kore", assistente="jarvis")
    check(get_identity(T, "charon")["user_name"] == (antes_charon or "Wilson"),
          "o teste restaurou o valor que estava no banco",
          "o teste deixou dado alterado no banco do usuario")
except Exception as e:
    check(False, "o cenario de nome separado executou", f"{type(e).__name__}: {e}")

print()
print("=== 4. A voz: nome desconhecido nao passa cru para a API ===")
# "na escolha da voz esta Charon, mas quem fala e Aoede". Um nome invalido ia
# direto para o `prebuilt_voice_config` do Gemini.
try:
    from routes.voice_ws import GEMINI_VOICES, _resolve_voice  # noqa: E402

    check(_resolve_voice("Charon") == "Charon",
          "voz valida e mantida",
          "a voz valida foi alterada")
    check(_resolve_voice("charon") == "Charon",
          "a resolucao aceita minusculas",
          "nao aceita minusculas")
    check(_resolve_voice("Atena") == "Charon",
          "nome de assistente como voz cai no padrao (era o defeito)",
          "um nome invalido continua indo cru para a API do Gemini")
    check(_resolve_voice("aode") == "Charon",
          "typo de voz cai no padrao",
          "typo continua indo cru para a API")
    check(set(GEMINI_VOICES.values()) == {
        "Charon", "Puck", "Kore", "Fenrir", "Leda", "Orus", "Aoede", "Zephyr"},
        "a lista de vozes e a que o Gemini aceita",
        f"lista de vozes inesperada: {sorted(GEMINI_VOICES.values())}")
except Exception as e:
    check(False, "o cenario de voz executou", f"{type(e).__name__}: {e}")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — Charon e Jarvis com a MESMA identidade")
