import io
import tempfile
import os
import subprocess
import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# Verificar se Superwhisper está instalado
def check_superwhisper():
    """Verifica se o Superwhisper está disponível no sistema."""
    try:
        # Tenta encontrar o executável do Superwhisper
        result = subprocess.run(
            ["where", "superwhisper"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

# Verificar se SpeechRecognition está disponível
def check_speech_recognition():
    """Verifica se a biblioteca SpeechRecognition está instalada."""
    try:
        import speech_recognition
        return True
    except ImportError:
        return False


@router.post("/api/stt/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = "pt",
):
    """
    Transcreve um arquivo de áudio.
    
    Opções disponíveis:
    1. Superwhisper (recomendado) - use o atalho global
    2. Web Speech API - use o navegador
    3. Google Speech Recognition - via speech_recognition
    
    - **file**: Arquivo de áudio (wav, mp3, m4a, ogg, etc.)
    - **language**: Código do idioma (pt, en, es, etc.)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")
    
    # Tentar usar speech_recognition se disponível
    if check_speech_recognition():
        try:
            import speech_recognition as sr
            
            # Salvar arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Usar Google Speech Recognition (gratuito)
                recognizer = sr.Recognizer()
                with sr.AudioFile(tmp_path) as source:
                    audio_data = recognizer.record(source)
                
                # Tentar reconhecimento
                text = recognizer.recognize_google(audio_data, language=language or "pt-BR")
                
                return JSONResponse({
                    "text": text,
                    "segments": [],
                    "language": language or "pt",
                    "method": "google",
                    "message": "Transcrição via Google Speech Recognition"
                })
            finally:
                os.unlink(tmp_path)
                
        except Exception as e:
            print(f"[STT] Erro com speech_recognition: {str(e)}")
            # Continuar para próxima opção
    
    # Verificar Superwhisper
    if check_superwhisper():
        return JSONResponse({
            "text": "",
            "segments": [],
            "language": language or "pt",
            "method": "superwhisper",
            "message": "Superwhisper detectado! Use o atalho Ctrl+Espaço para falar.",
            "instructions": {
                "step1": "Pressione Ctrl+Espaço para ativar o Superwhisper",
                "step2": "Fale sua mensagem",
                "step3": "O texto será digitado automaticamente no chat"
            }
        })
    
    # Fallback: instruções para usar Web Speech API
    return JSONResponse({
        "text": "",
        "segments": [],
        "language": language or "pt",
        "method": "web_speech_api",
        "message": "Use o botão de microfone no chat para usar o Web Speech API",
        "instructions": {
            "step1": "Clique no botão 🎙️ no canto inferior do chat",
            "step2": "Fale sua mensagem",
            "step3": "O texto será reconhecido e enviado"
        },
        "recommendation": "Para melhor experiência, instale o Superwhisper em superwhisper.com"
    })


@router.get("/api/stt/status")
async def stt_status():
    """Verifica o status dos serviços STT disponíveis."""
    return {
        "superwhisper": check_superwhisper(),
        "speech_recognition": check_speech_recognition(),
        "web_speech_api": True,  # Sempre disponível no navegador
        "recommendation": "Superwhisper" if check_superwhisper() else "Web Speech API"
    }


@router.get("/api/stt/health")
async def health_check():
    """Verifica se o STT está funcionando."""
    return {
        "status": "ok",
        "available": True,
        "methods": {
            "superwhisper": check_superwhisper(),
            "speech_recognition": check_speech_recognition(),
            "web_speech_api": True
        }
    }
