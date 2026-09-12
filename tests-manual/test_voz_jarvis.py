"""
Teste: a voz do Jarvis (leitura da resposta).

DUAS QUEIXAS DO USUARIO
1. "a resposta de voz parece robotica"
2. "a velocidade e o tom nao mudam nada ou quase nada quando mexо na barra"

CAUSAS ENCONTRADAS

(a) O REGEX DE LIMPEZA APAGAVA A LETRA "a" COM TIL.
    A alternancia de um dos `.replace` era `sdkjf|ã|©|®|™|°` — ou seja, o
    caractere U+00E3 estava na lista de REMOCAO. Resultado em portugues:
        "não"        -> "no"
        "então"      -> "ento"
        "informação" -> "informaço"
        "manhã"      -> "manh"
    "não" e uma das palavras mais frequentes do idioma: a fala saia errada o
    tempo todo. E o tipo de defeito que se descreve como voz "robotica".

(b) AS BARRAS DE VELOCIDADE E TOM NAO AFETAVAM A VOZ PADRAO.
    As vozes padrao do Jarvis sao do tipo "edge" (Edge TTS, neural). O
    `speak()` mandava para `/api/tts` apenas `{ text, voice }` — e o backend
    tinha `rate="-5%"` e `pitch="-15Hz"` FIXOS. As barras so chegavam ao
    `speakBrowser`, que e o plano B quando o Edge falha.
    Ou seja: quem estava na voz boa (Edge) nao tinha controle nenhum; quem
    estava na voz ruim (navegador) tinha. Exatamente o inverso do desejado.

(c) UM TEXTO LONGO IA NUMA UNICA UTTERANCE.
    A leitura perdia a entonacao do meio para o fim e soava corrida/monotona.

Este teste roda a funcao de verdade (extraida do .tsx e executada no Node) —
teste de texto nao pegaria o defeito (b), que e de EFEITO, nao de presenca.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JARVIS = RAIZ / "frontend" / "src" / "components" / "saas" / "JarvisPage.tsx"
HELPER = Path(__file__).resolve().parent / "_voz_extrair.cjs"
TTS = RAIZ / "backend" / "routes" / "tts.py"

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


print("=== 1. Comportamental: executa prepararTextoParaFala de verdade ===")
try:
    proc = subprocess.run(
        ["node", str(HELPER), str(JARVIS)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if proc.returncode != 0:
        check(False, "extrai e executa as funcoes de voz",
              f"o helper falhou (codigo {proc.returncode}): {(proc.stderr or '')[:300]}")
        resultados = []
    else:
        resultados = json.loads(proc.stdout)
        check(True, f"extrai e executa as funcoes ({len(resultados)} casos)", "")
except FileNotFoundError:
    print("   PULADO  node nao encontrado — os testes estaticos abaixo ainda valem")
    resultados = []
except Exception as e:
    check(False, "extrai e executa as funcoes de voz", f"erro: {type(e).__name__}: {e}")
    resultados = []

for r in resultados:
    entrada = str(r["entrada"])[:42]
    check(bool(r["ok"]), f"{r['nome']}",
          f"{r['nome']} — entrada {entrada!r} deu {str(r['obtido'])[:70]!r}")

if resultados:
    print()
    print("=== 2. O bug do til nao pode voltar (checagem direta) ===")
    tils = [r for r in resultados if r["nome"].startswith("preserva")]
    check(len(tils) >= 5, f"testados {len(tils)} casos com til", "poucos casos com til")
    check(all(r["ok"] for r in tils),
          "todas as palavras com til sao preservadas",
          "alguma palavra com til continua sendo alterada")

print()
print("=== 3. O regex destrutivo foi removido do codigo ===")
src = JARVIS.read_text(encoding="utf-8")
# A alternancia exata que causava o bug.
#
# ATENCAO: a mensagem de falha e montada ANTES do check (o argumento e avaliado
# de qualquer forma), entao ela NAO pode usar `apagador.group(1)` sem guarda —
# era isso que quebrava o teste quando ele PASSAVA.
apagador = re.search(r"\.replace\(/([^/]*\u00e3[^/]*)/g", src)
detalhe = f"ainda existe um replace que apaga o til: /{apagador.group(1)}/" if apagador else ""
check(apagador is None,
      "nenhum replace remove a letra 'a' com til (U+00E3)",
      detalhe)
check("prepararTextoParaFala" in src,
      "existe a funcao prepararTextoParaFala (ponto unico da limpeza)",
      "nao existe a funcao de preparacao — a limpeza continua espalhada em replaces soltos")
check("dividirEmFrases" in src,
      "existe dividirEmFrases (fala por frase, com pausas naturais)",
      "o texto longo continua indo numa unica utterancia")

print()
print("=== 4. Velocidade e tom chegam ao Edge TTS ===")
tts = TTS.read_text(encoding="utf-8")


def sem_comentarios_py(texto: str) -> str:
    """
    Remove comentarios e docstrings antes de procurar texto.

    OBRIGATORIO nesta suite: o proprio comentario que EXPLICA a correcao cita o
    valor antigo (`rate="-5%"`), e sem isto o teste acusa falha no codigo ja
    corrigido. Ja aconteceu varias vezes neste projeto — comentario nao e codigo.
    """
    sem_doc = re.sub(r'""".*?"""', "", texto, flags=re.S)
    sem_doc = re.sub(r"'''.*?'''", "", sem_doc, flags=re.S)
    return "\n".join(l for l in sem_doc.splitlines() if not l.strip().startswith("#"))


tts_codigo = sem_comentarios_py(tts)
src_codigo = sem_comentarios_py(src)

check("rate: int" in tts_codigo and "pitch: int" in tts_codigo,
      "o endpoint /api/tts aceita rate e pitch",
      "o /api/tts nao aceita velocidade/tom — era a causa das barras sem efeito")
check('{rate:+d}%' in tts_codigo,
      "rate e repassado ao edge_tts no formato de porcentagem",
      "rate nao chega ao edge_tts")
check('{pitch:+d}Hz' in tts_codigo,
      "pitch e repassado ao edge_tts no formato de Hertz",
      "pitch nao chega ao edge_tts")
# O valor fixo antigo nao pode voltar (procurado SO no codigo, sem comentarios)
check('rate="-5%"' not in tts_codigo and 'pitch="-15Hz"' not in tts_codigo,
      "nao ha mais rate/pitch FIXOS no backend",
      "o backend voltou a fixar rate=-5% / pitch=-15Hz (as barras nao teriam efeito)")
check("RATE_MIN" in tts_codigo and "PITCH_MIN" in tts_codigo,
      "ha limites para os valores (fora deles o provedor distorce a voz)",
      "sem limites, um valor extremo da barra pode quebrar o audio")

check("velocidadeParaEdge" in src_codigo and "tomParaEdge" in src_codigo,
      "o frontend converte as barras para o formato do Edge",
      "o frontend nao converte as barras — o Edge nao recebe os valores")

# Procura dentro da funcao speak() inteira (a janela fixa de 400 chars nao
# alcancava o corpo, que tem comentarios no meio — falso negativo do teste).
m_speak = re.search(r"const speak = async \(text: string\) => \{(.*?)\n  \};", src_codigo, re.S)
corpo_speak = m_speak.group(1) if m_speak else ""
check(bool(corpo_speak), "isolei o corpo da funcao speak()", "nao consegui isolar speak()")
check("rate: velocidadeParaEdge(voiceRate)" in corpo_speak,
      "a velocidade da barra e ENVIADA ao servidor",
      "a velocidade continua sem ser enviada — a barra nao faz nada na voz Edge")
check("pitch: tomParaEdge(voicePitch)" in corpo_speak,
      "o tom da barra e ENVIADO ao servidor",
      "o tom continua sem ser enviado — a barra nao faz nada na voz Edge")

# O ponto neutro do tom precisa devolver a voz original
m_tom = re.search(r"const tomParaEdge = \(pitch: number\) =>\s*([^;]+);", src_codigo)
expr_tom = m_tom.group(1) if m_tom else ""
check("pitch - 50" in expr_tom,
      "o tom tem ponto NEUTRO no meio da barra (50 = voz original)",
      f"a conversao de tom nao usa 50 como neutro: {expr_tom[:80]}")

print()
print("=== 5. Fallback visivel ao usuario ===")
check("Voz do servidor indisponivel" in src,
      "quando o Edge falha, o usuario e AVISADO (nao fica no console)",
      "a falha do Edge continua silenciosa — o usuario nao sabe que caiu para a voz robotica")
check("VOZES_NATURAIS_PREFERIDAS" in src,
      "a escolha da voz do navegador prefere vozes neurais/naturais",
      "a voz do navegador continua caindo na pt padrao (a mais robotica)")

print()
print("=" * 72)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — voz natural e barras com efeito")
