#web_search.py
import json
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# Cache do cliente Gemini para reutilizar (evita criar novo a cada busca)
_gemini_client_cache = None
_gemini_api_key_cache = None


def _get_api_key() -> str:
    """Le chave Gemini de api_keys.json com tratamento de erro."""
    try:
        if not API_CONFIG_PATH.exists():
            print(f"[WebSearch] Arquivo nao encontrado: {API_CONFIG_PATH}")
            return ""
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            key = data.get("gemini_api_key", "")
            if not key or key == "cole_sua_chave_aqui":
                print("[WebSearch] Chave Gemini vazia ou padrao")
                return ""
            return key
    except Exception as e:
        print(f"[WebSearch] Erro ao ler api_keys.json: {e}")
        return ""


def _get_gemini_client():
    global _gemini_client_cache, _gemini_api_key_cache
    api_key = _get_api_key()
    if _gemini_client_cache is None or _gemini_api_key_cache != api_key:
        from google import genai
        _gemini_client_cache = genai.Client(api_key=api_key)
        _gemini_api_key_cache = api_key
    return _gemini_client_cache


def _gemini_search(query: str) -> str:
    client = _get_gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config={"tools": [{"google_search": {}}]},
    )

    text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            text += part.text

    text = text.strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return text


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    """Busca DuckDuckGo com tratamento de erro robusto."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })
        return results
    except Exception as e:
        print(f"[WebSearch] DDG falhou: {e}")
        return []


def _ddg_news(query: str, max_results: int = 8) -> list[dict]:
    """DDG news search — returns actual articles, not website homepages."""
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("url",    ""),
                    "source":  r.get("source", ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG news() failed ({e}) — falling back to text search")
        results = _ddg_search(query, max_results=max_results)
    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   Source: {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_news(query: str, results: list[dict]) -> str:
    if not results:
        return f"No news found for: {query}"

    lines = [f"Latest news: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        if not title:
            continue
        src = f"  [{r['source']}]" if r.get("source") else ""
        lines.append(f"{i}. {title}{src}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:140]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── Briefing helper ────────────────────────────────────────────────────────────

def _gemini_headlines(n: int = 5) -> tuple[list[str], str]:
    """
    Fetches current headlines via Gemini grounded search.
    Optimised for speed: minimal prompt + strict token cap.
    Returns (headline_list, raw_text_for_display).
    """
    import re

    client = _get_gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Current world news: {n} headlines. Numbered list, titles only.",
        config={"tools": [{"google_search": {}}]},
    )

    raw = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            raw += part.text

    headlines = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Only accept lines that begin with a number — skips preamble/closing sentences
        if not re.match(r'^[\d]+[.\)\-]', line):
            continue
        clean = re.sub(r'^[\d]+[.\)\-]\s*', '', line)
        clean = re.sub(r'^\*+\s*',          '', clean).strip()
        if clean and len(clean) > 10:
            headlines.append(clean)

    return headlines[:n], raw.strip()


# ── Modes ──────────────────────────────────────────────────────────────────────

def _search(query: str) -> str:
    """Default search — DDG fast (primary), Gemini grounded (fallback)."""
    try:
        results = _ddg_search(query, max_results=6)
        if results:
            return _format_ddg(query, results)
        print("[WebSearch] DDG retornou vazio, tentando Gemini...")
    except Exception as e:
        print(f"[WebSearch] DDG failed ({e}) — trying Gemini...")

    # Fallback: Gemini (se chave disponivel)
    try:
        api_key = _get_api_key()
        if api_key:
            return _gemini_search(query)
        else:
            return f"Nenhum resultado encontrado para: {query} (DDG vazio e Gemini sem chave)"
    except Exception as e:
        print(f"[WebSearch] Gemini also failed: {e}")
        return f"Search failed: {e}"


def _news(query: str) -> str:
    """News search — DDG fast (primary), Gemini grounded (fallback)."""
    try:
        results = _ddg_news(query, max_results=8)
        if results:
            return _format_news(query, results)
        print("[WebSearch] DDG news retornou vazio, tentando Gemini...")
    except Exception as e:
        print(f"[WebSearch] DDG news failed ({e}) — trying Gemini...")

    # Fallback: Gemini (se chave disponivel)
    try:
        api_key = _get_api_key()
        if api_key:
            return _gemini_search(f"latest news today: {query}")
        else:
            return f"Nenhuma noticia encontrada para: {query} (DDG vazio e Gemini sem chave)"
    except Exception as e2:
        print(f"[WebSearch] Gemini news also failed: {e2}")
        return f"No news found for: {query}"


def _research(query: str) -> str:
    """Deep dive — DDG fast (primary), Gemini grounded (fallback)."""
    try:
        results = _ddg_search(query, max_results=10)
        if results:
            return _format_ddg(query, results)
        print("[WebSearch] DDG research retornou vazio, tentando Gemini...")
    except Exception as e:
        print(f"[WebSearch] DDG research failed ({e}) — trying Gemini...")

    # Fallback: Gemini (se chave disponivel)
    try:
        api_key = _get_api_key()
        if api_key:
            research_query = (
                f"Comprehensive, detailed explanation of: {query}. "
                "Include background context, key facts, current state, and important nuances."
            )
            return _gemini_search(research_query)
        else:
            return f"Nenhum resultado encontrado para: {query} (DDG vazio e Gemini sem chave)"
    except Exception as e:
        print(f"[WebSearch] Gemini research also failed: {e}")
        return f"Research failed: {e}"


def _price(query: str) -> str:
    """Product price lookup — DDG fast (primary), Gemini grounded (fallback)."""
    try:
        results = _ddg_search(f"{query} price buy", max_results=6)
        if results:
            return _format_ddg(query, results)
        print("[WebSearch] DDG price retornou vazio, tentando Gemini...")
    except Exception as e:
        print(f"[WebSearch] DDG price failed ({e}) — trying Gemini...")

    # Fallback: Gemini (se chave disponivel)
    try:
        api_key = _get_api_key()
        if api_key:
            price_query = f"current price of {query} — how much does it cost today"
            return _gemini_search(price_query)
        else:
            return f"Nenhum preco encontrado para: {query} (DDG vazio e Gemini sem chave)"
    except Exception as e:
        print(f"[WebSearch] Gemini price also failed: {e}")
        return f"Price search failed: {e}"


def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )

    # Tenta Gemini primeiro (melhor para comparacoes)
    try:
        api_key = _get_api_key()
        if api_key:
            return _gemini_search(query)
    except Exception as e:
        print(f"[WebSearch] Gemini compare failed: {e} — falling back to DDG")

    # Fallback: DDG para cada item
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
            if r.get("url"):
                lines.append(f"    {r['url']}")
    return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────────

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query."

    if items and mode not in ("compare",):
        mode = "compare"

    if player:
        player.write_log(f"[Search:{mode}] {query or ', '.join(items)}")

    print(f"[WebSearch] mode={mode!r}  query={query!r}")

    try:
        if mode == "compare" and items:
            return _compare(items, aspect)
        if mode == "news":
            return _news(query)
        if mode == "research":
            return _research(query)
        if mode == "price":
            return _price(query)
        return _search(query)

    except Exception as e:
        print(f"[WebSearch] All backends failed: {e}")
        return f"Search failed: {e}"
