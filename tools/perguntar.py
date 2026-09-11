"""
Assistente local do DEEP-OS — responde sobre o projeto usando a documentacao.

COMO FUNCIONA
-------------
1. Recupera os trechos relevantes da sua documentacao (`tools/rag_local.py`)
2. Monta um prompt com esse contexto
3. Manda para um modelo LOCAL via Ollama e imprime a resposta

Ou seja: o modelo nao precisa "saber" o DEEP-OS. Ele recebe os trechos certos
e responde com base neles. Isso e o que torna um modelo pequeno util aqui.

PRE-REQUISITOS
--------------
    ollama serve                          # em um terminal
    ollama pull qwen2.5-coder:14b         # ou qualquer modelo que voce tenha

    python tools/rag_local.py indexar     # constroi/atualiza o indice

USO
---
    python tools/perguntar.py "por que a voz nao salva por usuario?"
    python tools/perguntar.py --modelo llama3.1:8b "como faco deploy?"
    python tools/perguntar.py --contexto "..."       # so mostra os trechos
    python tools/perguntar.py --modelfile            # gera Modelfile do Ollama
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import rag_local  # noqa: E402

OLLAMA_URL = "http://localhost:11434"
MODELO_PADRAO = "qwen2.5-coder:14b"

INSTRUCAO = """Voce e um assistente tecnico do projeto DEEP-OS.

Regras:
- Responda em portugues do Brasil, direto e pratico.
- Baseie-se SOMENTE no CONTEXTO abaixo (documentacao real do projeto).
- Se o contexto nao tiver a resposta, diga claramente que nao encontrou na
  documentacao e sugira onde procurar (qual arquivo).
- Cite o arquivo e a secao de onde tirou a informacao.
- Nao invente nomes de funcao, arquivo ou comando."""


def _listar_modelos() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
            dados = json.loads(r.read().decode("utf-8"))
        return [m.get("name", "") for m in dados.get("models", [])]
    except Exception:
        return []


def perguntar(pergunta: str, modelo: str, top: int = 5, stream: bool = True) -> int:
    contexto = rag_local.montar_contexto(pergunta, top=top)

    if contexto.startswith("(nada encontrado"):
        print("Nada encontrado na documentacao para essa pergunta.")
        print("Tente outras palavras, ou rode: python tools/rag_local.py indexar")
        return 1

    prompt = f"{INSTRUCAO}\n\n--- CONTEXTO ---\n{contexto}\n--- FIM DO CONTEXTO ---\n\nPergunta: {pergunta}\n\nResposta:"

    corpo = json.dumps({
        "model": modelo,
        "prompt": prompt,
        "stream": stream,
        "options": {"temperature": 0.2},  # baixo: queremos fidelidade ao contexto
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=corpo,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            if not stream:
                print(json.loads(r.read().decode("utf-8")).get("response", ""))
                return 0
            for linha in r:
                linha = linha.decode("utf-8").strip()
                if not linha:
                    continue
                try:
                    pedaco = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if pedaco.get("response"):
                    sys.stdout.write(pedaco["response"])
                    sys.stdout.flush()
                if pedaco.get("done"):
                    break
        print()
        return 0
    except urllib.error.URLError as e:
        print(f"\nNao consegui falar com o Ollama em {OLLAMA_URL}")
        print(f"  Erro: {e}")
        print("\nVerifique se o Ollama esta rodando:  ollama serve")
        print("Modelos disponiveis localmente:")
        for m in _listar_modelos():
            print(f"   - {m}")
        return 1
    except Exception as e:
        print(f"\nErro ao gerar resposta: {type(e).__name__}: {e}")
        return 1


def gerar_modelfile(modelo_base: str, destino: Path) -> int:
    """
    Gera um Modelfile do Ollama que embute a documentacao como contexto.

    Assim voce cria um modelo proprio ('deepos') que ja conhece o projeto,
    sem precisar passar contexto em cada chamada.
    """
    dados = rag_local._carregar()
    partes = []
    for c in dados["chunks"]:
        partes.append(f"### {c['fonte']} — {c['secao']}\n{c['texto']}")
    documento = "\n\n".join(partes)

    # Ollama aceita system prompt grande, mas ha limite pratico. Trunca com aviso.
    LIMITE = 60000
    if len(documento) > LIMITE:
        print(f"AVISO: documentacao tem {len(documento)} chars; truncando em {LIMITE}.")
        print("       Para o conjunto completo, use tools/perguntar.py (busca por relevancia).")
        documento = documento[:LIMITE]

    conteudo = f"""FROM {modelo_base}

SYSTEM \"\"\"{INSTRUCAO}

--- DOCUMENTACAO DO PROJETO DEEP-OS ---
{documento}
--- FIM ---
\"\"\"

PARAMETER temperature 0.2
PARAMETER num_ctx 8192
"""
    destino.write_text(conteudo, encoding="utf-8")
    print(f"Modelfile gerado: {destino}")
    print()
    print("Para criar o modelo e usar:")
    print(f"   ollama create deepos -f {destino.name}")
    print("   ollama run deepos")
    print()
    print("Ou no assistente:")
    print("   python tools/perguntar.py --modelo deepos \"sua pergunta\"")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Assistente local do DEEP-OS (RAG + Ollama)")
    p.add_argument("pergunta", nargs="*", help="O que voce quer saber")
    p.add_argument("--modelo", default=MODELO_PADRAO, help=f"Modelo do Ollama (padrao: {MODELO_PADRAO})")
    p.add_argument("--top", type=int, default=5, help="Quantos trechos usar (padrao: 5)")
    p.add_argument("--contexto", action="store_true", help="So mostra os trechos, sem chamar o modelo")
    p.add_argument("--modelos", action="store_true", help="Lista os modelos do Ollama")
    p.add_argument("--modelfile", action="store_true", help="Gera um Modelfile do Ollama")
    args = p.parse_args()

    if args.modelos:
        modelos = _listar_modelos()
        if not modelos:
            print("Nenhum modelo (ou Ollama nao esta rodando). Rode: ollama serve")
            return 1
        print("Modelos disponiveis:")
        for m in modelos:
            print(f"   - {m}")
        return 0

    if args.modelfile:
        return gerar_modelfile(args.modelo, RAIZ / "Modelfile")

    pergunta = " ".join(args.pergunta).strip()
    if not pergunta:
        p.print_help()
        return 1

    if args.contexto:
        print(rag_local.montar_contexto(pergunta, top=args.top))
        return 0

    print(f"[modelo: {args.modelo}]\n")
    return perguntar(pergunta, args.modelo, top=args.top)


if __name__ == "__main__":
    sys.exit(main())
