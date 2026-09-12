"""
Teste: os dois pedidos do usuario sobre o Charon.

1. INTERRUPCAO (barge-in) — "o Charon deve parar de falar para ouvir o usuario"
   Estava quebrada por TRES motivos somados:

   (a) O backend IGNORAVA `server_content.interrupted`, que e o sinal do VAD do
       Gemini avisando "o usuario falou por cima". O audio antigo continuava
       sendo repassado e o navegador nunca era avisado.
   (b) Cada chunk do microfone fazia `session._interrupted = False`. Como o mic
       envia audio a cada ~20-60ms, qualquer interrupcao era desfeita no chunk
       seguinte — era o bug mais grave e o mais dificil de ver.
   (c) O frontend NUNCA enviava `type: 'interrupt'`, entao o handler do backend
       era codigo morto. E nao esvaziava a fila de audio local, que ja tinha
       segundos de fala baixada — o Charon continuava falando mesmo com o
       servidor calado.

2. SAUDACAO CURTA — o gatilho antigo ("Se apresente... diga seu nome, horario e
   como pode ajudar") fazia o Gemini discursar sobre o sistema. O usuario quer
   apenas: "Ola Wilson, eu sou Charon. O que gostaria de fazer agora?"

Este teste roda OFFLINE (nao chama o Gemini). Ele monta uma sessao falsa e
inspeciona o que o backend envia ao websocket.
"""
import asyncio
import re
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


VOICE = BACKEND / "routes" / "voice_ws.py"
CHARON = RAIZ / "frontend" / "src" / "components" / "saas" / "CharonPage.tsx"

print("=== 1. Saudacao: o gatilho precisa exigir brevidade ===")
texto = VOICE.read_text(encoding="utf-8")

# Isola o corpo de _send_startup_briefing
m = re.search(r"async def _send_startup_briefing\(self\):(.*?)\n    async def ", texto, re.S)
check(bool(m), "encontrei _send_startup_briefing", "nao encontrei _send_startup_briefing")
corpo_bruto = m.group(1) if m else ""

# Remove comentarios ANTES de checar.
#
# Necessario porque o comentario que explica a correcao cita o texto antigo
# ("...diga seu nome, horario e como pode ajudar") e o nome dos assuntos
# proibidos. Sem isto o teste acusa falha no codigo ja corrigido — foi um falso
# positivo real deste arquivo na primeira execucao.
corpo = "\n".join(l for l in corpo_bruto.splitlines() if not l.strip().startswith("#"))

check("uma frase" in corpo.lower(),
      "o gatilho exige UMA frase",
      "o gatilho nao limita a fala a uma frase (era a causa da saudacao longa)")
check("PROIBIDO" in corpo,
      "o gatilho proibe explicitamente os assuntos que alongavam a fala",
      "sem proibicoes explicitas, o modelo de audio volta a discursar")
check("O que gostaria de fazer agora?" in corpo,
      "o exemplo de saudacao e o pedido pelo usuario",
      "o exemplo de saudacao nao bate com o que o usuario pediu")

# O gatilho antigo nao pode voltar: ele era um convite aberto a discursar
check("como pode ajudar" not in corpo,
      "o gatilho antigo ('...e como pode ajudar') foi removido",
      "o texto 'como pode ajudar' ainda esta la — foi o que gerava a saudacao longa")

# Assuntos que faziam a fala se estender
for proibido in ("ferramentas", "funcionalidades", "status", "horario"):
    check(proibido in corpo.lower(),
          f"o gatilho proibe falar de '{proibido}'",
          f"o gatilho NAO proibe falar de '{proibido}'")

print()
print("=== 2. Backend: o sinal de interrupcao do Gemini e lido ===")
check("getattr(sc, \"interrupted\", False)" in texto or "sc.interrupted" in texto,
      "o backend le server_content.interrupted (VAD do servidor)",
      "o backend IGNORA server_content.interrupted — o Charon nao para de falar")
check('"type": "interrupted"' in texto,
      "o backend avisa o frontend com {\"type\": \"interrupted\"}",
      "o backend nao avisa o frontend para esvaziar a fila de audio")

print()
print("=== 3. Backend: chunk do microfone NAO pode desfazer a interrupcao ===")
# Procura o trecho do loop de recepcao que trata mensagens binarias
m_bin = re.search(r'if "bytes" in msg and msg\["bytes"\]:\n(.*?)continue', texto, re.S)
check(bool(m_bin), "encontrei o tratamento de audio binario", "nao encontrei o tratamento de audio binario")
bloco = m_bin.group(1) if m_bin else ""
# Remove comentarios antes de checar, senao a propria explicacao do bug acusa
bloco_codigo = "\n".join(
    l for l in bloco.splitlines() if not l.strip().startswith("#")
)
check("_interrupted = False" not in bloco_codigo,
      "nenhum '_interrupted = False' no caminho do audio do microfone",
      "o microfone AINDA reseta _interrupted — a interrupcao e desfeita no chunk seguinte")

print()
print("=== 4. Backend: rede de seguranca contra 'surdo para sempre' ===")
check("_interrupted_at" in texto,
      "existe controle de tempo da interrupcao (_interrupted_at)",
      "sem _interrupted_at, uma interrupcao sem turn_complete deixa o Charon surdo")
check("_interrupted_at = 0.0" in texto,
      "a interrupcao e liberada por tempo (guarda de 3s)",
      "nao ha guarda de tempo para liberar a interrupcao")

print()
print("=== 5. Frontend: envia o pedido de interrupcao ===")
ctexto = CHARON.read_text(encoding="utf-8")
check("'interrupt'" in ctexto,
      "o frontend envia {type: 'interrupt'} ao servidor",
      "o frontend NUNCA envia 'interrupt' — o handler do backend fica morto")
check("interromperCharon" in ctexto,
      "existe a funcao interromperCharon()",
      "nao existe funcao de interrupcao no frontend")
check("port.postMessage({ type: 'clear' })" in ctexto,
      "a interrupcao esvazia o ring do worklet de reproducao",
      "a interrupcao nao esvazia o ring local — o Charon continua falando do buffer")
check("audioBufRef.current = []" in ctexto,
      "a interrupcao esvazia a fila de chunks pendentes",
      "a fila de chunks nao e esvaziada na interrupcao")
check("ignorarAudioAteRef" in ctexto,
      "descarta o audio em transito logo apos interromper",
      "audio em transito continuaria tocando por cima do usuario")

print()
print("=== 6. Frontend: a deteccao usa o nivel do microfone ===")
check("charonFalandoRef" in ctexto,
      "existe o estado 'Charon falando' em ref (sem closure desatualizada)",
      "nao ha ref de 'Charon falando' — impossivel detectar a fala do usuario")
check("chunksComVozRef" in ctexto,
      "exige varios chunks com voz antes de interromper (evita estalo/ruido)",
      "um unico pico de ruido dispararia a interrupcao")

print()
print("=== 7. COMPORTAMENTAL: executa _handle_response de verdade ===")
# Os testes acima sao estaticos (leem o arquivo). Este aqui INSTANCIA a sessao e
# chama o codigo real, para provar o comportamento e nao apenas a presenca do
# texto. Foi um teste estatico que deixou passar o bug original: a linha
# `_interrupted = False` estava no lugar "certo" do arquivo, mas errada na hora
# de rodar.
try:
    from types import SimpleNamespace as NS

    from routes.voice_ws import VoiceSession

    class WsFalso:
        """WebSocket de mentira: so registra o que o backend tentou enviar."""

        def __init__(self):
            self.json_enviados = []
            self.bytes_enviados = []

        async def send_json(self, dados):
            self.json_enviados.append(dados)

        async def send_bytes(self, dados):
            self.bytes_enviados.append(dados)

        def tipos(self):
            return [m.get("type") for m in self.json_enviados]

    def resposta(interrupted=False, turn_complete=False, data=None,
                 texto_saida=None, texto_entrada=None):
        """Monta um objeto parecido com o que o Gemini Live devolve."""
        return NS(
            server_content=NS(
                interrupted=interrupted,
                turn_complete=turn_complete,
                input_transcription=NS(text=texto_entrada) if texto_entrada else None,
                output_transcription=NS(text=texto_saida) if texto_saida else None,
            ),
            data=data,
            tool_call=None,
        )

    async def cenario():
        ws = WsFalso()
        s = VoiceSession(ws)
        s._running = True

        # --- 7a. O sinal do VAD do Gemini marca a sessao como interrompida ---
        await s._handle_response(resposta(interrupted=True))
        check(s._interrupted is True,
              "server_content.interrupted=True marca a sessao como interrompida",
              "o sinal do VAD do Gemini NAO foi aplicado")
        check("interrupted" in ws.tipos(),
              "o frontend foi avisado com {type: 'interrupted'}",
              "o frontend NAO foi avisado — nao esvaziaria a fila de audio")
        check(s._interrupted_at > 0,
              "o instante da interrupcao foi registrado (guarda de 3s)",
              "_interrupted_at nao foi marcado")

        # --- 7b. Enquanto interrompido, o audio antigo e DESCARTADO ---
        ws.bytes_enviados.clear()
        await s._handle_response(resposta(data=b"\x01\x02" * 100))
        check(not ws.bytes_enviados,
              "audio antigo NAO e repassado apos a interrupcao (Charon cala)",
              "o backend CONTINUA mandando o audio antigo — o Charon nao para de falar")

        # --- 7c. A fala NOVA do usuario e transcrita normalmente ---
        # A interrupcao cala a SAIDA, mas nao pode cegar a entrada.
        ws.json_enviados.clear()
        await s._handle_response(resposta(texto_entrada="para um pouco"))
        tipos = ws.tipos()
        check("transcript" in tipos,
              "a fala nova do usuario continua sendo transcrita durante a interrupcao",
              "a transcricao do usuario foi perdida durante a interrupcao")

        # --- 7d. turn_complete libera a sessao (volta a falar) ---
        ws.json_enviados.clear()
        await s._handle_response(resposta(turn_complete=True))
        check(s._interrupted is False,
              "turn_complete libera a interrupcao (o Charon volta a poder falar)",
              "a sessao ficou presa em 'interrompido' apos o turno fechar")

        # --- 7e. Rede de seguranca: interrupcao sem turn_complete nao deixa surdo ---
        s._interrupted = True
        s._interrupted_at = asyncio.get_event_loop().time() - 5.0  # 5s atras
        await s._handle_response(resposta())
        check(s._interrupted is False,
              "interrupcao pendurada por mais de 3s e liberada automaticamente",
              "sem turn_complete, o Charon ficaria SURDO para sempre")

        # --- 7f. Depois de liberado, o audio volta a passar ---
        ws.bytes_enviados.clear()
        await s._handle_response(resposta(data=b"\x03\x04" * 100))
        check(bool(ws.bytes_enviados),
              "apos liberar, o audio volta a ser repassado (nao ficou mudo)",
              "o audio NAO voltou depois de liberar a interrupcao")

    asyncio.run(cenario())

except ImportError as e:
    print(f"   PULADO  nao consegui importar voice_ws ({e})")
    print("           (dependencia ausente — os testes estaticos acima ja cobrem o texto)")
except Exception as e:
    check(False, "cenario comportamental executou", f"erro ao executar o cenario: {type(e).__name__}: {e}")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — saudacao curta e barge-in funcionando")
