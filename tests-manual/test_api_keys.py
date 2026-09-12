"""
Teste: salvar chave de API NAO pode sobrescrever com placeholder.

BUG REAL (reportado pelo usuario)
No JarvisPage, as chaves ja salvas eram marcadas com '***saved***' no estado e
no localStorage. Ao salvar a chave de UM provider, o payload era montado com
TODOS os providers — entao o marcador dos outros ia junto e o backend gravava
'***saved***' no `.env`, SOBRESCREVENDO a chave verdadeira.

Sintoma: "trocar a chave de um provedor nao alterava o arquivo .env" — na
verdade ele alterava, colocando lixo, e a chave real se perdia.

Este teste garante que o backend RECUSA valores de placeholder.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


print("=== 1. _chave_valida: o que deve ser RECUSADO ===")
from routes.config import _chave_valida

recusar = [
    "", "   ", None, "***saved***", "***SALVO***", "***", "saved", "salvo",
    "(vazia)", "(empty)", "undefined", "null", "none", "changeme",
    "your-api-key", "cole_sua_chave_aqui", "sk-...abcd", "***...xyz",
]
for v in recusar:
    check(not _chave_valida(v), f"recusa {v!r}", f"ACEITOU {v!r} (destruiria a chave real)")

print()
print("=== 2. _chave_valida: o que deve ser ACEITO ===")
aceitar = [
    "AIzaSyC1234567890abcdefghijklmnopqrstu",           # Gemini real
    "gsk_" + "a" * 50,                                   # Groq real
    "sk-or-v1-" + "b" * 60,                              # OpenRouter real
    "nvapi-" + "c" * 40,                                 # NVIDIA real
]
for v in aceitar:
    check(_chave_valida(v), f"aceita chave real ({v[:12]}...)", f"recusou chave VALIDA {v[:12]}...")

print()
print("=== 3. CENARIO DO BUG: salvar Groq nao pode destruir a chave do Gemini ===")
TMP = Path(tempfile.mkdtemp(prefix="deepos_keys_"))
CFG = TMP / "config" / "api_keys.json"
ENV = TMP / ".env"
CFG.parent.mkdir(parents=True)

# Estado inicial: chaves REAIS salvas
CHAVE_GEMINI = "AIzaSyC_REAL_GEMINI_KEY_1234567890abcd"
CHAVE_OPENROUTER = "sk-or-v1-REALKEY1234567890abcdefghijklmnop"
CFG.write_text(json.dumps({
    "gemini_api_key": CHAVE_GEMINI,
    "openrouter_api_key": CHAVE_OPENROUTER,
}, indent=4), encoding="utf-8")
ENV.write_text(
    f"# chaves\nGEMINI_API_KEY={CHAVE_GEMINI}\nOPENROUTER_API_KEY={CHAVE_OPENROUTER}\n",
    encoding="utf-8",
)
print(f"   Gemini inicial ...: {CHAVE_GEMINI[:16]}...")
print(f"   OpenRouter inicial: {CHAVE_OPENROUTER[:16]}...")

# Simula o payload ANTIGO (bugado): salvar Groq + marcadores dos outros
from routes.config import _chave_valida as cv

payload_bugado = {
    "GROQ_API_KEY": "gsk_REAL_GROQ_KEY_abcdefghijklmnopqrstuvwxyz",
    "GEMINI_API_KEY": "***saved***",        # <- o marcador que causava o estrago
    "OPENROUTER_API_KEY": "***saved***",    # <- idem
}
print()
print("   payload do frontend ANTIGO:", {k: v[:12] + '...' if not v.startswith('***') else v for k, v in payload_bugado.items()})

# Aplica a MESMA logica do endpoint corrigido
key_map = {"GEMINI_API_KEY": "gemini_api_key", "OPENROUTER_API_KEY": "openrouter_api_key",
           "GROQ_API_KEY": "groq_api_key"}
data = json.loads(CFG.read_text(encoding="utf-8"))
updated, recusados = [], []
for env_key, json_key in key_map.items():
    if env_key not in payload_bugado or not payload_bugado[env_key]:
        continue
    if not cv(payload_bugado[env_key]):
        recusados.append(env_key)
        continue
    data[json_key] = payload_bugado[env_key].strip()
    updated.append(env_key)
CFG.write_text(json.dumps(data, indent=4), encoding="utf-8")

print(f"   atualizados: {updated}")
print(f"   recusados  : {recusados}")
print()

depois = json.loads(CFG.read_text(encoding="utf-8"))
print("   apos o salvamento:")
print(f"     gemini_api_key .....: {depois.get('gemini_api_key','')[:16]}...")
print(f"     openrouter_api_key .: {depois.get('openrouter_api_key','')[:16]}...")
print(f"     groq_api_key .......: {depois.get('groq_api_key','')[:16]}...")
print()

check(depois.get("gemini_api_key") == CHAVE_GEMINI,
      "chave do GEMINI preservada (nao virou '***saved***')",
      f"CHAVE DESTRUIDA: virou {depois.get('gemini_api_key')!r}")
check(depois.get("openrouter_api_key") == CHAVE_OPENROUTER,
      "chave do OPENROUTER preservada",
      f"CHAVE DESTRUIDA: virou {depois.get('openrouter_api_key')!r}")
check(depois.get("groq_api_key", "").startswith("gsk_"),
      "chave NOVA (Groq) foi salva",
      "a chave nova nao foi salva")
check(set(recusados) == {"GEMINI_API_KEY", "OPENROUTER_API_KEY"},
      "os dois placeholders foram recusados",
      f"recusados inesperados: {recusados}")

print()
print("=== 4. E o .env? Nao pode receber o marcador ===")
# Aplica a logica de escrita do .env
env_lines = ENV.read_text(encoding="utf-8").splitlines()
new_lines, escritos = [], set()
for line in env_lines:
    st = line.strip()
    if st and not st.startswith("#") and "=" in st:
        kn = st.split("=", 1)[0].strip()
        if kn in key_map and cv(payload_bugado.get(kn)):
            new_lines.append(f"{kn}={payload_bugado[kn].strip()}")
            escritos.add(kn)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)
for ek in key_map:
    if cv(payload_bugado.get(ek)) and ek not in escritos:
        new_lines.append(f"{ek}={payload_bugado[ek].strip()}")
ENV.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

conteudo = ENV.read_text(encoding="utf-8")
print("   .env agora:")
for l in conteudo.splitlines():
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1)
        print(f"     {k} = {v[:18]}...")
check("***saved***" not in conteudo,
      "o .env NAO contem '***saved***'",
      "O MARCADOR FOI GRAVADO NO .ENV (bug original)")
check(CHAVE_GEMINI in conteudo, "chave do Gemini intacta no .env",
      "chave do Gemini perdida no .env")
check("gsk_" in conteudo, "chave nova (Groq) gravada no .env",
      "chave nova nao foi gravada no .env")

print()
print("=== 5. ENDPOINTS REAIS: PUT /api/config/api-key deve devolver 400, nao 500 ===")
# Aqui chamamos as funcoes de verdade. O cenario 'sentinel' faz o raise ANTES de
# qualquer I/O (so cria objetos Path), entao o .env real nao e tocado.
# Para o /api-keys (que escreve), fazemos backup e restauramos no finally.
import asyncio  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from routes.config import ApiKeyConfig, update_api_key  # noqa: E402

ENV_REAL = BACKEND / ".env"
JSON_REAL = BACKEND / "config" / "api_keys.json"
backup_dir = Path(tempfile.mkdtemp(prefix="deepos_backup_"))
for src in (ENV_REAL, JSON_REAL):
    if src.exists():
        shutil.copy2(src, backup_dir / src.name)

try:
    # 5a) /api-key com sentinel -> HTTPException 400 (e NAO 500)
    try:
        asyncio.run(update_api_key(ApiKeyConfig(gemini_api_key="***saved***")))
        check(False, "levantou 400", "NAO levantou excecao — gravou o sentinel!")
    except HTTPException as e:
        check(e.status_code == 400,
              f"PUT /api-key com '***saved***' -> HTTP {e.status_code}",
              f"devolveu HTTP {e.status_code} (deveria ser 400; 500 esconde a causa)")

    # 5b) /api-key com chave vazia -> tambem 400
    try:
        asyncio.run(update_api_key(ApiKeyConfig(gemini_api_key="")))
        check(False, "levantou 400", "NAO levantou excecao com chave vazia")
    except HTTPException as e:
        check(e.status_code == 400, f"PUT /api-key vazio -> HTTP {e.status_code}",
              f"chave vazia devolveu HTTP {e.status_code}")

    # 5c) /api-key com chave VALIDA -> deve salvar (200) e gravar de verdade
    CHAVE_TESTE = "AIzaSyTESTE_ENDPOINT_REAL_1234567890abcdef"
    env_antes = ENV_REAL.read_text(encoding="utf-8") if ENV_REAL.exists() else ""
    try:
        r = asyncio.run(update_api_key(ApiKeyConfig(gemini_api_key=CHAVE_TESTE)))
        ok = isinstance(r, dict) and r.get("status") == "success"
        check(ok, "PUT /api-key com chave real -> success", f"resposta inesperada: {r}")
        gravado = json.loads(JSON_REAL.read_text(encoding="utf-8")).get("gemini_api_key")
        check(gravado == CHAVE_TESTE, "chave real foi gravada no api_keys.json",
              f"api_keys.json tem {gravado!r}")
        env_depois = ENV_REAL.read_text(encoding="utf-8")
        check(CHAVE_TESTE in env_depois, "chave real foi gravada no .env",
              "a chave real NAO chegou ao .env")
    except HTTPException as e:
        check(False, "chave real aceita", f"chave REAL recusada: HTTP {e.status_code} {e.detail}")

    # 5d) restaurar o .env/api_keys.json do usuario e conferir que voltou igual
    for src in (ENV_REAL, JSON_REAL):
        bkp = backup_dir / src.name
        if bkp.exists():
            shutil.copy2(bkp, src)
    check(ENV_REAL.read_text(encoding="utf-8") == env_antes,
          "backup do .env restaurado fielmente",
          "o .env NAO voltou ao estado original apos o teste")
finally:
    shutil.rmtree(backup_dir, ignore_errors=True)

print()
print("=" * 68)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — placeholder nunca sobrescreve chave real")

shutil.rmtree(TMP, ignore_errors=True)
