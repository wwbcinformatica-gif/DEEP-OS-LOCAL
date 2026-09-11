import edge_tts
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    voice: str = "pt-BR-AntonioNeural"

# Cache de conexões edge_tts para reutilizar sessões HTTP
_communicate_cache = {}

@router.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        # Conecta ao serviço TTS da Microsoft Edge — streaming imediato
        communicate = edge_tts.Communicate(
            request.text,
            request.voice,
            rate="-5%",
            pitch="-15Hz",
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
