import edge_tts
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    voice: str = "pt-BR-AntonioNeural"
    # Velocidade em PORCENTO relativo ao normal: 0 = normal, +30 = 30% mais
    # rapido, -20 = 20% mais lento. (edge-tts usa esse formato de string.)
    rate: int = 0
    # Tom em HERTZ relativo ao normal: 0 = voz original, -20 = mais grave,
    # +20 = mais agudo.
    pitch: int = 0

# Limites do provedor. Fora disso o servico recusa ou distorce a voz.
RATE_MIN, RATE_MAX = -50, 100
PITCH_MIN, PITCH_MAX = -60, 60


def _limitar(valor: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(maximo, int(valor)))


@router.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    # ── Velocidade e tom vindos da interface ─────────────────────────────────
    #
    # BUG CORRIGIDO: o endpoint tinha `rate="-5%"` e `pitch="-15Hz"` FIXOS no
    # codigo e nao aceitava esses parametros. Como as vozes padrao do Jarvis sao
    # do tipo "edge", as barras de velocidade e tom da tela nao tinham efeito
    # nenhum — o usuario relatou exatamente isso ("parece que nao muda nada").
    #
    # As barras so afetavam o `speakBrowser` (voz do navegador), que e apenas o
    # plano B quando o Edge TTS falha.
    rate = _limitar(request.rate, RATE_MIN, RATE_MAX)
    pitch = _limitar(request.pitch, PITCH_MIN, PITCH_MAX)

    try:
        # Conecta ao servico TTS da Microsoft Edge — streaming imediato
        communicate = edge_tts.Communicate(
            request.text,
            request.voice,
            rate=f"{rate:+d}%",
            pitch=f"{pitch:+d}Hz",
        )

        async def generate():
            """Gera chunks de áudio sob demanda, streaming real."""
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    yield chunk["data"]

        return StreamingResponse(
            generate(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=\"speech.mp3\"",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
