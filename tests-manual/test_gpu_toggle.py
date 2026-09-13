"""
Teste: os botoes de GPU das configuracoes do Jarvis (Ollama e llama.cpp).

PERGUNTA DO USUARIO
"antes de subir verifica para mim se estas funcoes no jarvis em configuracoes
esta funcionando -> Ollama GPU Aceleracao por GPU / llama.cpp GPU Aceleracao por
GPU"

RESPOSTA: NAO estavam. Nenhuma das duas.

CAUSA
O frontend mandava `{ use_gpu: <bool> }`, mas os dois endpoints validam com um
modelo Pydantic que exige `gpu_enabled`:

    class GpuConfigPayload(BaseModel):
        gpu_enabled: bool
        gpu_layers: int = -1

Resposta do servidor: **422 Unprocessable Entity** — e o `catch {}` vazio do
frontend engolia o erro. O botao mudava de cor, gravava a preferencia so no
localStorage e a configuracao NUNCA era salva no servidor. Ou seja: a tela
mentia, e a GPU continuava como estava.

(Ja tinha acontecido coisa parecida neste projeto: o `.catch(() => {})` que
escondia o 401 da VPS e o marcador `'***saved***'` que "salvava" sem salvar.)

SEGUNDO DEFEITO
O estado inicial do botao vinha SO do localStorage. Se o `config.yaml` fosse
alterado por outro caminho (a mao, outro navegador, outro computador), o botao
mostrava um valor que nao correspondia ao que o servidor ia usar.

Roda OFFLINE (nao chama provedor; usa o TestClient do FastAPI).
"""
import ast
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


def sem_docstrings(codigo: str) -> str:
    """Apaga literais de texto de um arquivo PYTHON (por AST)."""
    arvore = ast.parse(codigo)
    linhas = codigo.splitlines()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            ini_l, ini_c = no.lineno - 1, no.col_offset
            fim_l, fim_c = no.end_lineno - 1, no.end_col_offset
            for i in range(ini_l, fim_l + 1):
                c0 = ini_c if i == ini_l else 0
                c1 = fim_c if i == fim_l else len(linhas[i])
                linhas[i] = linhas[i][:c0] + " " * (c1 - c0) + linhas[i][c1:]
    return "\n".join(linhas)


def tirar_comentarios(bloco: str) -> str:
    """
    Remove comentarios de um trecho de TypeScript/JavaScript.

    POR QUE ISTO EXISTE
    O comentario que EXPLICA a correcao cita o codigo antigo (`{ use_gpu: ... }`,
    o `catch {}` vazio). Procurar por esses textos no trecho cru encontra a
    explicacao e acusa um arquivo ja corrigido — falso positivo que aconteceu nas
    duas primeiras execucoes deste teste.

    E a armadilha nº 5 do docs/CONTINUAR.md ("testes desta suite se enganam
    lendo COMENTARIO/DOCSTRING como codigo"), que ja custou tempo 5 vezes neste
    projeto. Aqui ela apareceu em DOIS testes seguidos, escritos por mim.

    Cuidado ao usar: isto tambem apaga comentarios dentro de strings. Para os
    trechos que este teste analisa (corpo de uma funcao) isso nao acontece.
    """
    linhas = []
    for linha in bloco.splitlines():
        # Corta comentario de linha, mas nao `://` de URL nem `http://`.
        pos = linha.find("//")
        if pos != -1 and "://" not in linha[max(0, pos - 1):pos + 3]:
            linha = linha[:pos]
        linhas.append(linha)
    return "\n".join(linhas)


# O JarvisPage e .tsx: NAO da para passar pelo ast do Python, entao aqui lemos o
# texto cru mesmo. O cuidado com docstring vale para os arquivos .py deste teste.
JARVIS_BRUTO = (RAIZ / "frontend" / "src" / "components" / "saas" / "JarvisPage.tsx").read_text(encoding="utf-8")
JARVIS = JARVIS_BRUTO
# Versao SEM comentarios: e a que vale para "isto ainda existe no codigo?".
JARVIS_SEM_COMENTARIO = tirar_comentarios(JARVIS_BRUTO)

print("=== 1. O frontend manda o payload que o backend EXIGE ===")
# O nome exato do campo: `gpu_enabled`, nao `use_gpu`.
check("gpu_enabled: newVal" in JARVIS,
      "o frontend envia `gpu_enabled` (o campo que o backend exige)",
      "o frontend manda outro campo — o backend responde 422 e nada e salvo")
# Sem comentarios: o comentario que explica a correcao CITA `use_gpu`, e ler isso
# como codigo acusaria um arquivo ja corrigido.
check("use_gpu" not in JARVIS_SEM_COMENTARIO,
      "nao sobrou o campo antigo `use_gpu` no codigo",
      "ainda existe `use_gpu` — o payload voltou a ser recusado com 422")
check("gpu_layers: -1" in JARVIS,
      "o frontend manda `gpu_layers: -1` (automatico)",
      "sem gpu_layers o backend assume -1, mas o envio explicito evita surpresa")

print()
print("=== 2. O erro nao pode ser engolido ===")
# O `catch {}` vazio era o que escondia a falha.
m_toggle = JARVIS_BRUTO.split("const toggleGpu = async (provider: string) => {")[1].split("\n  };")[0]
m_toggle_limpo = tirar_comentarios(m_toggle)
check("catch {}" not in m_toggle_limpo,
      "o toggle nao tem `catch {}` vazio",
      "o erro continua sendo engolido — a tela diria que salvou sem salvar")
check("!resp.ok" in m_toggle and "throw" in m_toggle,
      "a resposta e conferida e o erro e propagado",
      "resposta HTTP ruim passa como sucesso")
check("!newVal" in m_toggle,
      "o botao VOLTA ao estado anterior se o salvamento falhar",
      "o botao ficaria mentindo sobre o estado real")
check("authHeaders()" in m_toggle,
      "a chamada leva o token (o middleware protege /api/*)",
      "sem token a chamada toma 401 na VPS — o defeito que ja ocorreu aqui")

print()
print("=== 3. O estado inicial vem do SERVIDOR, nao do localStorage ===")
check("/llamacpp/gpu" in JARVIS,
      "o frontend le a configuracao real do llama.cpp",
      "o botao do llama.cpp comeca com um chute do localStorage")
check("/ollama/gpu" in JARVIS,
      "o frontend le a configuracao real do Ollama",
      "o botao do Ollama comeca com um chute do localStorage")

print()
print("=== 4. Roda de verdade: o backend ACEITA o payload novo e RECUSA o antigo ===")
try:
    import main  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402

    c = TestClient(main.app)

    # Guarda o valor atual para restaurar (nao deixar o config do usuario mudado).
    antes = c.get("/llamacpp/gpu").json()
    print(f"   (valor atual do llama.cpp: {antes})")

    r_novo = c.post("/llamacpp/gpu", json={"gpu_enabled": True, "gpu_layers": -1})
    check(r_novo.status_code == 200,
          f"POST com {{gpu_enabled, gpu_layers}} -> 200 (o payload novo funciona)",
          f"o payload novo foi recusado: HTTP {r_novo.status_code} {r_novo.text[:120]}")

    # Controle NEGATIVO: o payload antigo tem de continuar sendo recusado. Sem
    # este controle, um backend que aceitasse QUALQUER coisa passaria no teste.
    r_antigo = c.post("/llamacpp/gpu", json={"use_gpu": False})
    check(r_antigo.status_code == 422,
          "POST com {use_gpu} -> 422 (o payload antigo era mesmo o defeito)",
          f"o payload antigo passou com HTTP {r_antigo.status_code} — o teste nao prova nada")

    # O Ollama usa o mesmo modelo de dados, entao so conferimos que a rota existe
    # e responde 200 com o campo certo (nao mexemos no config do Ollama).
    r_get_ollama = c.get("/ollama/gpu")
    check(r_get_ollama.status_code == 200 and "gpu_enabled" in r_get_ollama.json(),
          "GET /ollama/gpu responde com `gpu_enabled`",
          f"resposta inesperada do Ollama: {r_get_ollama.status_code} {r_get_ollama.text[:120]}")

    # Restaura o valor que estava antes do teste.
    c.post("/llamacpp/gpu", json={"gpu_enabled": antes.get("gpu_enabled", True),
                                 "gpu_layers": antes.get("gpu_layers", -1)})
    depois = c.get("/llamacpp/gpu").json()
    check(depois.get("gpu_enabled") == antes.get("gpu_enabled"),
          "o valor do usuario foi restaurado depois do teste",
          f"o teste deixou o config alterado: antes={antes} depois={depois}")
except Exception as e:
    check(False, "o cenario HTTP executou", f"{type(e).__name__}: {e}")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — o botao de GPU salva de verdade")
