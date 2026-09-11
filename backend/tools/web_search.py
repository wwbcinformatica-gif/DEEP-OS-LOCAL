"""
Web Search Tool — busca na web com multiplos provedores e fallback automatico.
Provedores: duckduckgo-search → DuckDuckGo HTML → Google Search.
"""
import re
import time

import httpx

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _parse_ddg_html(html: str) -> list[dict]:
    """Parseia resultados do DuckDuckGo HTML."""
    results = []
    # Padrao 1: result__a
    titles_urls = re.findall(
        r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL
    )
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    for i, (url, title) in enumerate(titles_urls):
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
        if clean_title and url.startswith("http"):
            results.append({"title": clean_title, "url": url, "snippet": clean_snippet})

    # Padrao 2: data-testid="result-title-a" (DDG novo)
    if not results:
        titles_urls2 = re.findall(
            r'data-testid="result-title-a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        snippets2 = re.findall(r'data-testid="result-snippet"[^>]*>(.*?)</div>', html, re.DOTALL)
        for i, (url, title) in enumerate(titles_urls2):
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            clean_snippet = re.sub(r'<[^>]+>', '', snippets2[i]).strip() if i < len(snippets2) else ""
            if clean_title:
                results.append({"title": clean_title, "url": url, "snippet": clean_snippet})

    return results


def _parse_google_html(html: str) -> list[dict]:
    """Parseia resultados do Google Search (HTML simples)."""
    results = []
    # Google usa divs com h3 para titulos
    blocks = re.findall(r'<a href="/url\?q=([^&"]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?<div[^>]*>(.*?)</div>', html, re.DOTALL)
    for url, title, snippet in blocks:
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
        if clean_title and url.startswith("http"):
            results.append({"title": clean_title, "url": url, "snippet": clean_snippet[:200]})
    return results


async def _search_ddg(query: str) -> list[dict]:
    """Busca via DuckDuckGo HTML."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=_HEADERS,
        )
        if resp.status_code == 200:
            return _parse_ddg_html(resp.text)
    return []


async def _search_ddg_api(query: str) -> list[dict]:
    """Busca via ddgs package (mais confiavel)."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=10):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:200],
                })
            return results
    except Exception:
        return []


async def _search_google(query: str) -> list[dict]:
    """Busca via Google Search HTML."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(
            "https://www.google.com/search",
            params={"q": query, "hl": "pt-BR", "num": "10"},
            headers=_HEADERS,
        )
        if resp.status_code == 200:
            return _parse_google_html(resp.text)
    return []


async def _search_brave(query: str, api_key: str = "") -> list[dict]:
    """Busca via Brave Search API (se chave configurada)."""
    if not api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": "10"},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", "")[:200],
                })
            return results
    return []


async def tool_web_search(
    query: str,
    allowed_domains: list | None = None,
    blocked_domains: list | None = None,
    api_key: str = "",
) -> dict:
    """Busca na web com fallback automatico entre provedores."""
    start = time.time()

    # Tenta duckduckgo-search package primeiro (mais confiavel)
    results = []
    provider = "duckduckgo-api"
    try:
        results = await _search_ddg_api(query)
    except Exception:
        pass

    # Fallback: DuckDuckGo HTML
    if not results:
        provider = "duckduckgo-html"
        try:
            results = await _search_ddg(query)
        except Exception:
            pass

    # Fallback: Google
    if not results:
        provider = "google"
        try:
            results = await _search_google(query)
        except Exception:
            pass

    # Fallback: Brave API
    if not results and api_key:
        provider = "brave"
        try:
            results = await _search_brave(query, api_key)
        except Exception:
            pass

    # Filtra por dominios
    filtered = []
    for r in results:
        url = r.get("url", "")
        if allowed_domains and not any(d in url for d in allowed_domains):
            continue
        if blocked_domains and any(d in url for d in blocked_domains):
            continue
        filtered.append(r)

    duration = round(time.time() - start, 2)

    if not filtered:
        return {
            "query": query,
            "results": [],
            "provider": provider,
            "duration_seconds": duration,
            "error": "Nenhum resultado encontrado em nenhum provedor",
            "tip": "Tente reformular a busca ou usar termos mais especificos",
        }

    return {
        "query": query,
        "results": filtered[:10],
        "provider": provider,
        "count": len(filtered),
        "duration_seconds": duration,
    }
