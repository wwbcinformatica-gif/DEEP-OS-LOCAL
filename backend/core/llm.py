import asyncio
import logging
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

_chat_ollama = None
_chat_openai = None
_chat_groq = None

def _lazy_ollama():
    global _chat_ollama
    if _chat_ollama is not None:
        return _chat_ollama
    try:
        from langchain_community.chat_models import ChatOllama
        _chat_ollama = ChatOllama
        return _chat_ollama
    except Exception as e:
        logger.warning(f"ChatOllama unavailable: {e}")
        _chat_ollama = False
        return None

def _lazy_openai():
    global _chat_openai
    if _chat_openai is not None:
        return _chat_openai
    try:
        from langchain_community.chat_models import ChatOpenAI
        _chat_openai = ChatOpenAI
        return _chat_openai
    except Exception as e:
        logger.warning(f"ChatOpenAI unavailable: {e}")
        _chat_openai = False
        return None

def _lazy_groq():
    global _chat_groq
    if _chat_groq is not None:
        return _chat_groq
    try:
        from langchain_groq import ChatGroq
        _chat_groq = ChatGroq
        return _chat_groq
    except Exception as e:
        logger.warning(f"ChatGroq unavailable: {e}")
        _chat_groq = False
        return None

def get_llm(provider: str, model_name: str, temperature: float = 0.7):
    from core.config import GEMINI_API_KEY, GROQ_API_KEY, MIMO_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY
    if provider == "ollama":
        cls = _lazy_ollama()
        if cls:
            return cls(model=model_name, base_url="http://localhost:11434", temperature=temperature)
    elif provider == "openrouter":
        cls = _lazy_openai()
        if cls:
            return cls(
                openai_api_key=OPENROUTER_API_KEY,
                openai_api_base="https://openrouter.ai/api/v1",
                model=model_name,
                temperature=temperature,
            )
    elif provider == "openai":
        cls = _lazy_openai()
        if cls:
            return cls(openai_api_key=OPENAI_API_KEY, model=model_name, temperature=temperature)
    elif provider == "gemini":
        cls = _lazy_openai()
        if cls:
            return cls(
                openai_api_key=GEMINI_API_KEY,
                openai_api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
                model=model_name,
                temperature=temperature,
            )
    elif provider == "mimo":
        cls = _lazy_openai()
        if cls:
            return cls(
                openai_api_key=MIMO_API_KEY,
                openai_api_base="https://api.xiaomimimo.com/v1",
                model=model_name,
                temperature=temperature,
            )
    else:
        cls = _lazy_groq()
        if cls:
            return cls(groq_api_key=GROQ_API_KEY, model_name=model_name, temperature=temperature)
    raise ImportError(f"No LLM available for provider: {provider}")

async def run_llm_async(llm, prompt_values: dict):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: llm.invoke(prompt_values))

async def run_llm_stream(llm, prompt_values: dict) -> AsyncGenerator[str, None]:
    stream = llm.stream(prompt_values)
    for chunk in stream:
        try:
            from langchain_core.messages import AIMessageChunk
            if isinstance(chunk, AIMessageChunk) or hasattr(chunk, "content"):
                content = chunk.content or ""
            else:
                content = str(chunk)
        except ImportError:
            content = str(chunk)
        yield content
