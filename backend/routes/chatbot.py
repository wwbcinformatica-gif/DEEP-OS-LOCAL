"""
DEEP-OS — Rotas do ChatBot (Providers IA)
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("chatbot")
router = APIRouter()

# Configuracao padrao do ChatBot
_chatbot_config = {
    "provider": "ollama",
    "model": "llama3",
    "ollama_url": "http://localhost:11434",
    "gemini_model": "gemini-2.0-flash",
    "gemini_api_key": "",
    "openai_model": "gpt-3.5-turbo",
    "openai_api_key": "",
}


class ChatBotConfig(BaseModel):
    provider: str = "ollama"
    model: str = ""
    ollama_url: str = ""
    gemini_model: str = ""
    gemini_api_key: str = ""
    openai_model: str = ""
    openai_api_key: str = ""


class TestRequest(BaseModel):
    provider: str
    message: str = "ola"


@router.get("/api/chatbot/config")
async def get_config():
    """Retorna configuracao atual do ChatBot."""
    return _chatbot_config


@router.post("/api/chatbot/config")
async def save_config(config: ChatBotConfig):
    """Salva configuracao do ChatBot."""
    _chatbot_config.update(config.model_dump())
    logger.info(f"ChatBot config salva: provider={config.provider}")
    return {"status": "ok", "config": _chatbot_config}


@router.post("/api/chatbot/test")
async def test_provider(req: TestRequest):
    """
    Testa o provider de IA selecionado.
    Retorna a resposta do modelo.
    """
    provider = req.provider
    message = req.message or "ola"

    try:
        if provider == "ollama":
            return await _test_ollama(message)
        elif provider == "gemini":
            return await _test_gemini(message)
        elif provider == "openai":
            return await _test_openai(message)
        else:
            return {"error": f"Provider desconhecido: {provider}"}
    except Exception as e:
        logger.error(f"Erro ao testar provider {provider}: {e}")
        return {"error": str(e)}


async def _test_ollama(message: str) -> dict:
    """Testa provider Ollama local."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Verifica se Ollama esta rodando
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                return {"error": "Ollama nao esta rodando no servidor"}

            models = resp.json().get("models", [])
            if not models:
                return {"error": "Nenhum modelo encontrado no Ollama"}

            # Envia mensagem de teste
            model_name = _chatbot_config.get("model", "llama3")
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model_name, "prompt": message, "stream": False},
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                return {"response": data.get("response", "Sem resposta")}
            else:
                return {"error": f"Erro Ollama: {resp.status_code}"}

    except httpx.ConnectError:
        return {"error": "Ollama nao esta rodando. Instale com: curl -fsSL https://ollama.com/install.sh | sh"}
    except Exception as e:
        return {"error": str(e)}


async def _test_gemini(message: str) -> dict:
    """Testa provider Gemini (API cloud)."""
    import os
    import httpx

    api_key = _chatbot_config.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"error": "GEMINI_API_KEY nao configurada no servidor"}

    model = _chatbot_config.get("gemini_model", "gemini-2.0-flash")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": message}]}],
                "generationConfig": {"maxOutputTokens": 100},
            }
            resp = await client.post(url, json=payload)

            if resp.status_code == 200:
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return {"response": text or "Sem resposta"}
            else:
                return {"error": f"Erro Gemini API: {resp.status_code} - {resp.text[:200]}"}

    except Exception as e:
        return {"error": str(e)}


async def _test_openai(message: str) -> dict:
    """Testa provider OpenAI (API cloud)."""
    import os
    import httpx

    api_key = _chatbot_config.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return {"error": "OPENAI_API_KEY nao configurada no servidor"}

    model = _chatbot_config.get("openai_model", "gpt-3.5-turbo")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": message}],
                "max_tokens": 100,
            }
            resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"response": text or "Sem resposta"}
            else:
                return {"error": f"Erro OpenAI API: {resp.status_code} - {resp.text[:200]}"}

    except Exception as e:
        return {"error": str(e)}


@router.post("/api/chatbot/connect")
async def connect_whatsapp():
    """Placeholder para conexao WhatsApp."""
    return {"message": "WhatsApp连接功能 em desenvolvimento"}
