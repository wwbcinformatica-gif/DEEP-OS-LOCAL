"""
RAG local do DEEP-OS — indexa a documentacao do projeto para consulta offline.

OBJETIVO
--------
Ter um assistente que conhece ESTE projeto sem depender de nuvem: o indice e
construido a partir de `memory.md`, `STATUS.md`, `docs/*.md`, `AGENTS.md` e
`.memory/MEMORY-*.md`, e consultado por um modelo local (ex: Ollama).

SEM DEPENDENCIAS EXTERNAS
-------------------------
Nao usa FAISS/sentence-transformers (que nao estao instalados). A busca e
lexical, com peso por campo e IDF — funciona bem para documentacao tecnica, que
tem vocabulario especifico (nomes de funcao, de arquivo, de erro).

Se quiser busca semantica depois:
    pip install faiss-cpu sentence-transformers
e troque `buscar()` por embeddings (o projeto ja tem esqueleto em
`backend/memory/vector_memory.py`).

CHUNKING
--------
O texto e dividido por SECOES de markdown (`##`/`###`), nao por tamanho fixo.
Isso mantem o contexto: cada trecho carrega o titulo da secao a que pertence,
o que ajuda muito quando o usuario pergunta sobre uma regra especifica.

USO
---
    python tools/rag_local.py indexar              # constroi o indice
    python tools/rag_local.py buscar "fuso horario lembretes"
    python tools/rag_local.py contexto "por que a voz nao salva"
    python tools/rag_local.py stats
"""
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDICE = RAIZ / ".rag" / "indice.json"

# Console do Windows usa cp1252 por padrao e quebra ao imprimir os acentos e
# travessoes da documentacao (UnicodeEncodeError). Forca UTF-8 na saida.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Fontes da documentacao (o que o assistente passa a "saber")
FONTES = [
    "memory.md",
    "STATUS.md",
    "RECUPERAR-VPS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "manual.md",
    "docs/CHARON-VOZ.md",
    "docs/SAAS_README.md",
]
PASTAS = [".memory", "docs"]

# Palavras muito comuns que nao ajudam a discriminar
STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "um", "uma", "para",
    "com", "por", "que", "nao", "no", "na", "os", "as", "se", "ao", "como",
    "mais", "mas", "foi", "ser", "tem", "ter", "ja", "so", "ou", "pelo",
    "pela", "este", "esta", "isso", "esse", "essa", "the", "of", "to", "in",
    "and", "is", "are", "it", "on", "for", "with", "be", "at", "by",
}


def _normalizar(texto: str) -> list[str]:
    """Minusculas, sem acento, somente letras/numeros."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return [p for p in re.findall(r"[a-z0-9_]+", t) if p not in STOPWORDS and len(p) > 1]


# Sinonimos do dominio do projeto.
#
# Busca lexical nao cruza palavras diferentes com o mesmo sentido: o usuario
# pergunta "por que a voz nao salva" e a documentacao fala de "identidade por
# tenant". Sem isso, os trechos que apenas CONTEM a palavra "voz" ganhavam da
# resposta real. Este mapa liga os termos que o usuario usa aos que a
# documentacao usa.
SINONIMOS = {
    "voz": ["identidade", "tenant", "assistant_name", "voice"],
    "nome": ["assistant_name", "identidade"],
    "salvar": ["persistir", "gravar", "gravacao", "salva"],
    "salva": ["persistir", "gravar", "gravacao"],
    "lembrete": ["reminder", "reminders", "agendador"],
    "lembretes": ["reminder", "reminders", "agendador"],
    "aviso": ["lembrete", "reminder"],
    "fuso": ["timezone", "utc", "brasilia", "horario"],
    "horario": ["timezone", "fuso", "utc"],
    "hora": ["timezone", "fuso", "horario"],
    "microfone": ["mic", "getusermedia", "audiocontext", "captura"],
    "mic": ["microfone", "getusermedia"],
    "audio": ["mic", "worklet", "playback", "pcm"],
    "cortando": ["underrun", "prebuffer", "ring", "cauda"],
    "engasgando": ["underrun", "stutter", "prebuffer"],
    "lento": ["delay", "gargalo", "timeout"],
    "porta": ["port", "8001", "bind", "already"],
    "servidor": ["vps", "systemd", "backend"],
    "caiu": ["502", "queda", "erro", "offline"],
    "erro": ["bug", "falha", "excecao", "traceback"],
    "deploy": ["publicar", "publicacao", "nginx", "scripts"],
    "publicar": ["deploy", "nginx", "dist"],
    "senha": ["password", "credencial", "seguranca"],
    "seguranca": ["senha", "token", "jwt", "vazamento"],
    "token": ["jwt", "autenticacao", "auth"],
    "permissao": ["autorizacao", "auth", "bloqueio"],
    "rota": ["endpoint", "router", "api", "path"],
    "endpoint": ["rota", "router", "api"],
    "banco": ["database", "sqlite", "tabela"],
    "tabela": ["database", "sqlite", "coluna"],
}


def _expandir(termos: list[str]) -> Counter:
    """Conta os termos da pergunta, somando sinonimos do dominio."""
    pesos = Counter(termos)
    for t in list(pesos):
        for s in SINONIMOS.get(t, ()):
            pesos[s] += 0.6   # peso menor: sinonimo ajuda, mas nao domina
    return pesos

    achados: list[Path] = []
    for f in FONTES:
        p = RAIZ / f
        if p.is_file():
            achados.append(p)
    for pasta in PASTAS:
        d = RAIZ / pasta
        if d.is_dir():
            achados.extend(sorted(d.glob("*.md")))
    # remove duplicados mantendo a ordem
    vistos = set()
    unicos = []
    for p in achados:
        if p not in vistos:
            vistos.add(p)
            unicos.append(p)
    return unicos


def _chunkar(caminho: Path, texto: str) -> list[dict]:
    """
    Divide por secao de markdown. Cada chunk carrega o titulo da secao
    (e o titulo pai, quando houver) para dar contexto na busca.
    """
    linhas = texto.split("\n")
    chunks: list[dict] = []
    titulo_atual = caminho.name
    titulo_pai = ""
    buffer: list[str] = []

    def fechar():
        corpo = "\n".join(buffer).strip()
        if corpo:
            chunks.append({
                "fonte": str(caminho.relative_to(RAIZ)).replace("\\", "/"),
                "secao": titulo_atual,
                "pai": titulo_pai,
                "texto": corpo,
            })

    for linha in linhas:
        m = re.match(r"^(#{1,4})\s+(.*)$", linha)
        if m:
            fechar()
            buffer = []
            nivel = len(m.group(1))
            titulo = m.group(2).strip()
            if nivel <= 2:
                titulo_pai = titulo if nivel == 2 else ""
                titulo_atual = titulo
            else:
                titulo_atual = f"{titulo_pai} > {titulo}" if titulo_pai else titulo
            continue
        buffer.append(linha)
    fechar()
    return chunks


def indexar() -> int:
    """Constroi o indice e grava em .rag/indice.json."""
    arquivos = _arquivos_fonte()
    if not arquivos:
        print("Nenhum arquivo de documentacao encontrado.")
        return 1

    chunks: list[dict] = []
    for caminho in arquivos:
        try:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  AVISO: nao li {caminho.name}: {e}")
            continue
        for c in _chunkar(caminho, texto):
            c["tokens"] = _normalizar(f"{c['secao']} {c['pai']} {c['texto']}")
            chunks.append(c)

    if not chunks:
        print("Nenhum chunk gerado.")
        return 1

    # IDF: quanto mais raro o termo, mais ele discrimina
    df = Counter()
    for c in chunks:
        df.update(set(c["tokens"]))
    n = len(chunks)
    idf = {t: math.log((n + 1) / (f + 1)) + 1.0 for t, f in df.items()}

    # Remove tokens do indice final (economiza espaco; recomputamos na busca)
    for c in chunks:
        c.pop("tokens", None)

    INDICE.parent.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps({
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "total_chunks": len(chunks),
        "total_termos": len(idf),
        "arquivos": [str(p.relative_to(RAIZ)).replace("\\", "/") for p in arquivos],
        "idf": idf,
        "chunks": chunks,
    }, ensure_ascii=False), encoding="utf-8")

    print(f"Indice criado: {INDICE.relative_to(RAIZ)}")
    print(f"  arquivos ...... {len(arquivos)}")
    print(f"  trechos ....... {len(chunks)}")
    print(f"  termos unicos . {len(idf)}")
    return 0


def _carregar() -> dict:
    if not INDICE.exists():
        print("Indice nao existe. Rode: python tools/rag_local.py indexar")
        sys.exit(1)
    return json.loads(INDICE.read_text(encoding="utf-8"))


def buscar(pergunta: str, top: int = 8, min_fracao: float = 0.25) -> list[dict]:
    """
    Retorna os trechos mais relevantes para a pergunta.

    Duas melhorias sobre "pegar os N primeiros":

    1. `top` e um TETO, nao uma cota. Retorna menos se poucos trechos forem
       relevantes (evita encher o contexto com ruido).
    2. `min_fracao`: mantem quem tiver pelo menos essa fracao do melhor score.
       Sem isso, um trecho exato podia ficar de fora por pouco — foi o que
       aconteceu ao perguntar sobre a voz nao salvar por usuario: os 5
       primeiros eram genericos sobre "voz" e o trecho do bug real ficou em 7o.
    """
    dados = _carregar()
    idf = dados["idf"]
    termos = _normalizar(pergunta)
    if not termos:
        return []

    alvo = _expandir(termos)
    pontuados = []
    for c in dados["chunks"]:
        texto_norm = _normalizar(f"{c['secao']} {c['pai']} {c['texto']}")
        if not texto_norm:
            continue
        freq = Counter(texto_norm)
        cabecalho_norm = set(_normalizar(f"{c['secao']} {c['pai']}"))

        pontos = 0.0
        for termo, peso_pergunta in alvo.items():
            if termo in freq:
                # TF logaritmico + IDF.
                #
                # NAO normalizar pelo tamanho do chunk: ao dividir por
                # len(texto_norm), trechos grandes (ex.: "Historico", que
                # resume todas as sessoes) perdiam para trechos curtos, mesmo
                # contendo a resposta. O IDF ja cuida de desvalorizar termos
                # comuns; o log evita que repeticao domine.
                pontos += (1.0 + math.log(1 + freq[termo])) * idf.get(termo, 1.0) * peso_pergunta
                if termo in cabecalho_norm:
                    pontos *= 1.5
        if pontos > 0:
            pontuados.append((pontos, c))

    if not pontuados:
        return []

    pontuados.sort(key=lambda x: -x[0])
    melhor = pontuados[0][0]
    corte = melhor * min_fracao
    selecionados = [p for p in pontuados if p[0] >= corte][:top]
    return [{**c, "pontos": round(p, 3)} for p, c in selecionados]


def montar_contexto(pergunta: str, top: int = 5, limite_chars: int = 6000) -> str:
    """Contexto pronto para colar num prompt de modelo local."""
    trechos = buscar(pergunta, top)
    if not trechos:
        return "(nada encontrado na documentacao do projeto)"
    partes = []
    usado = 0
    for t in trechos:
        bloco = f"### {t['fonte']} — {t['secao']}\n{t['texto']}"
        if usado + len(bloco) > limite_chars:
            bloco = bloco[: max(0, limite_chars - usado)]
        partes.append(bloco)
        usado += len(bloco)
        if usado >= limite_chars:
            break
    return "\n\n---\n\n".join(partes)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    comando = sys.argv[1].lower()

    if comando == "indexar":
        return indexar()

    if comando == "stats":
        d = _carregar()
        print(f"Criado em ...... {d['criado_em']}")
        print(f"Trechos ........ {d['total_chunks']}")
        print(f"Termos ......... {d['total_termos']}")
        print(f"Arquivos ....... {len(d['arquivos'])}")
        for a in d["arquivos"]:
            print(f"   - {a}")
        return 0

    if comando in ("buscar", "contexto"):
        if len(sys.argv) < 3:
            print(f"Uso: python tools/rag_local.py {comando} \"sua pergunta\"")
            return 1
        pergunta = " ".join(sys.argv[2:])
        if comando == "contexto":
            print(montar_contexto(pergunta))
            return 0
        for i, t in enumerate(buscar(pergunta), 1):
            print(f"\n[{i}] score={t['pontos']}  {t['fonte']}")
            print(f"    secao: {t['secao']}")
            print("    " + t["texto"][:400].replace("\n", "\n    "))
        return 0

    print(f"Comando desconhecido: {comando}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
