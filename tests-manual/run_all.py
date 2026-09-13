"""
Runner dos testes manuais do DEEP-OS.

Uso:
    python tests-manual/run_all.py            # roda tudo
    python tests-manual/run_all.py security   # roda os que casam com "security"

Por que existe: antes era preciso rodar 8 comandos separados e comparar a saida
na mao. Aqui tudo roda em sequencia, com resumo final e codigo de saida
(0 = tudo passou, 1 = alguma falha) — o que permite usar em CI.
"""
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

# Onde esta o interpretador com as dependencias do backend.
#
# POR QUE UMA LISTA: os dois projetos gemeos do DEEP-OS guardam o venv em
# lugares diferentes —
#   C:\DEEP-OS        -> <raiz>\venv\Scripts\python.exe      (Windows)
#   C:\DEEP-OS-LOCAL  -> <raiz>\backend\venv\Scripts\python.exe
# Antes o runner olhava so `<raiz>/venv`, entao no LOCAL ele nao achava o Python
# e o suite inteiro falhava na largada (parecia bug do codigo, era do runner).
CANDIDATOS_VENV = [
    RAIZ / "venv" / "Scripts" / "python.exe",
    RAIZ / "backend" / "venv" / "Scripts" / "python.exe",
    RAIZ / ".venv" / "Scripts" / "python.exe",
    RAIZ / "venv" / "bin" / "python",              # Linux
    RAIZ / "backend" / "venv" / "bin" / "python",  # Linux
    RAIZ / ".venv" / "bin" / "python",
]
VENV_PY = next((p for p in CANDIDATOS_VENV if p.exists()), None)
SEM_VENV = VENV_PY is None
if SEM_VENV:
    # Ultimo recurso: o proprio interpretador que esta rodando este arquivo.
    # Assim o suite roda mesmo sem venv (com as dependencias do sistema).
    VENV_PY = Path(sys.executable)

# (arquivo, descricao, marcador de sucesso)
TESTES = [
    ("test_all_routes.py", "Rotas: registro, ordem de catch-all, protecao de auth",
     "rotas OK"),
    ("test_security_middleware.py", "Seguranca: middleware de rotas (cenario de proxy)",
     "protecao OK"),
    ("test_security_downloads.py", "Seguranca: isolamento de downloads e segredos",
     "seguranca OK"),
    ("test_tenant_slug.py", "Downloads: slug do tenant unificado (pasta com ':' x '_')",
     "slug unificado"),
    ("test_identity_endpoint.py", "Identidade: rota HTTP grava e le (isolamento)",
     "gravou e leu corretamente"),
    ("test_master_identity.py", "Identidade: cada conta master isolada",
     "identidade master isolada"),
    ("test_voice_isolation.py", "Voz do Charon: isolada por tenant",
     "voz isolada por tenant"),
    ("test_tenant_identity.py", "Identidade: assistente/usuario por tenant",
     "isolamento por tenant OK"),
    ("test_reminder_timezone.py", "Lembretes: fuso horario (Brasilia UTC-3)",
     "fuso horario OK"),
    ("test_reminders.py", "Lembretes: persistencia, vencimento, action",
     "lembretes OK"),
    ("test_reminder_summary.py", "Lembretes: resumo em documento + download",
     "TODOS OS TESTES PASSARAM"),
    ("test_api_keys.py", "Chaves de API: placeholder ('***saved***') nao sobrescreve chave real",
     "TODOS OS TESTES PASSARAM"),
    ("test_model_lists.py", "Modelos: listas coerentes entre arquivos, sem IDs extintos",
     "TODOS OS TESTES PASSARAM"),
    ("test_charon_barge_in.py", "Charon: saudacao curta + interrupcao (barge-in)",
     "TODOS OS TESTES PASSARAM"),
    ("test_provedores.py", "Provedores: comuns + personalizados criados pelo usuario",
     "TODOS OS TESTES PASSARAM"),
    ("test_dsml_tools.py", "Ferramentas: parser DSML (modelo que anuncia e nao executa)",
     "TODOS OS TESTES PASSARAM"),
    ("test_charon_historico.py", "Charon: historico da conversa (contexto da sessao)",
     "TODOS OS TESTES PASSARAM"),
    ("test_voz_jarvis.py", "Voz do Jarvis: texto para fala e barras de velocidade/tom",
     "TODOS OS TESTES PASSARAM"),
    ("test_historico_conversa.py", "Historico: mensagens salvas, restauradas e exportaveis",
     "TODOS OS TESTES PASSARAM"),
    ("test_tools_headless.py", "Ferramentas por ambiente: VPS (sem tela) x PC (com desktop)",
     "TODOS OS TESTES PASSARAM"),
    ("audit_headless_tools.py", "Auditoria: quais tools carregam (headless)",
     "NAO importam/carregam: 0"),
]


def testes_esquecidos() -> list[str]:
    """
    Arquivos de teste que existem na pasta mas NAO estao na lista TESTES.

    POR QUE ISTO EXISTE
    A lista acima e fixa. Consequencia: um arquivo novo e escrito, passa quando
    rodado na mao e **nunca mais roda** no `run_all.py` — vira um teste morto que
    da a impressao de estar protegendo o codigo. Isso aconteceu de verdade nesta
    sessao: criei `test_tools_headless.py`, rodei sozinho (passou) e a suite
    continuou dizendo "20 testes", sem ele.

    E a mesma classe de defeito que ja custou tempo neste projeto: uma regra que
    depende de alguem lembrar. Aqui a ferramenta avisa sozinha.
    """
    na_lista = {nome for nome, _, _ in TESTES}
    return sorted(
        p.name
        for p in AQUI.glob("test_*.py")
        if p.name not in na_lista and p.name != Path(__file__).name
    )


def main() -> int:
    filtro = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    alvos = [t for t in TESTES if not filtro or filtro in t[0].lower()]

    if not alvos:
        print(f"Nenhum teste casa com {filtro!r}")
        return 1

    print("=" * 72)
    print(f"DEEP-OS — testes manuais  ({len(alvos)} arquivo(s))")
    print(f"Projeto: {RAIZ}")
    if SEM_VENV:
        print("AVISO: nao encontrei o venv do projeto — usando o interpretador atual.")
        print("       Se faltar dependencia, rode com o Python do venv do backend.")
    print(f"Python: {VENV_PY}")
    print("=" * 72)

    # Aviso (nao falha) para teste que ficou de fora da lista.
    esquecidos = testes_esquecidos()
    if esquecidos and not filtro:
        print("\n" + "!" * 72)
        print("ATENCAO: existem testes na pasta que NAO estao na lista TESTES e")
        print("portanto NAO rodaram agora (teste que nao roda nao protege nada):")
        for nome in esquecidos:
            print(f"   - {nome}")
        print("Acrescente-os em TESTES neste arquivo.")
        print("!" * 72)

    resultados = []
    for arquivo, descricao, marcador in alvos:
        caminho = AQUI / arquivo
        if not caminho.exists():
            resultados.append((arquivo, "AUSENTE", 0.0, ""))
            print(f"\n[--] {arquivo} — ARQUIVO NAO ENCONTRADO")
            continue

        print(f"\n[{arquivo}]")
        print(f"  {descricao}")
        t0 = time.time()
        proc = subprocess.run(
            [str(VENV_PY), str(caminho)],
            capture_output=True, text=True, cwd=str(AQUI),
        )
        dur = time.time() - t0
        saida = (proc.stdout or "") + (proc.stderr or "")

        if marcador in saida:
            status = "OK"
        elif "FALHA" in saida or proc.returncode != 0:
            status = "FALHOU"
        else:
            status = "SEM MARCADOR"

        resultados.append((arquivo, status, dur, saida))
        marca = {"OK": "OK ", "FALHOU": "!! ", "SEM MARCADOR": "?? "}[status]
        print(f"  {marca} {status} em {dur:.1f}s")

    # ── Resumo ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("RESUMO")
    print("=" * 72)
    for arquivo, status, dur, _ in resultados:
        icone = {"OK": "OK  ", "FALHOU": "FALHA", "SEM MARCADOR": "??  ", "AUSENTE": "AUSENTE"}[status]
        print(f"  [{icone}] {arquivo:<32} {dur:5.1f}s")

    falhas = [r for r in resultados if r[1] != "OK"]
    print()
    if falhas:
        print(f"{len(falhas)} de {len(resultados)} com problema. Saida dos que falharam:")
        for arquivo, status, _, saida in falhas:
            print("\n" + "-" * 72)
            print(f"--- {arquivo} ({status}) ---")
            linhas = saida.strip().split("\n")
            print("\n".join(linhas[-25:]))
        return 1

    print(f"TODOS OS {len(resultados)} TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
