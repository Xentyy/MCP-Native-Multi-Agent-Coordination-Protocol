"""Web arama ve içerik özetleme araçları — gerçek DuckDuckGo araması."""
from __future__ import annotations

import re
from typing import Any

import httpx
from pydantic import BaseModel, Field


class WebSearchParams(BaseModel):
    query: str = Field(description="Arama sorgusu")
    max_results: int = Field(default=5, ge=1, le=20)


class FetchPageParams(BaseModel):
    url: str = Field(description="Getirilecek sayfa URL'i")


class SummarizeParams(BaseModel):
    text: str = Field(description="Özetlenecek metin")
    max_sentences: int = Field(default=5, ge=1, le=15)


class ExtractLinksParams(BaseModel):
    html: str = Field(description="HTML içeriği")


# DuckDuckGo HTML sonuç regex'leri
_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_DDG_SNIPPET_RE = re.compile(
    r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|span)>',
    re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


async def web_search(params: WebSearchParams) -> list[dict[str, str]]:
    """DuckDuckGo HTML endpoint'i üzerinden gerçek arama."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    }
    url = "https://html.duckduckgo.com/html/"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.post(url, data={"q": params.query}, headers=headers)
            r.raise_for_status()
            html = r.text

        results: list[dict[str, str]] = []
        titles = _DDG_RESULT_RE.findall(html)
        snippets = _DDG_SNIPPET_RE.findall(html)

        for i, (href, title_html) in enumerate(titles[: params.max_results]):
            snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
            title = _strip_tags(title_html)
            # DuckDuckGo internal redirect URL → temizle
            clean_url = href
            if "duckduckgo.com/l/" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    from urllib.parse import unquote
                    clean_url = unquote(m.group(1))
            results.append({"title": title, "url": clean_url, "snippet": snippet})

        if not results:
            # Fallback: basit regex ile title/url çek
            raw_links = re.findall(
                r'href="(https?://[^"]+)"[^>]*>\s*([^<]{10,100})',
                html,
            )
            seen: set[str] = set()
            for href, txt in raw_links:
                if "duckduckgo" in href or href in seen:
                    continue
                seen.add(href)
                results.append({"title": txt.strip(), "url": href, "snippet": ""})
                if len(results) >= params.max_results:
                    break

        return results

    except Exception as exc:
        return [{"title": "Arama hatası", "url": "", "snippet": str(exc)}]


async def fetch_page(params: FetchPageParams) -> dict[str, str]:
    """URL'deki sayfayı getirir ve düz metne çevirir."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(
                params.url,
                headers={"User-Agent": "MNACP-Bot/1.0 (+research)"},
            )
            r.raise_for_status()
            html = r.text

        # Script/style/nav bloklarını sil
        html = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Paragraf ve başlıkları satıra dönüştür
        html = re.sub(r"<(?:p|br|h[1-6]|li)[^>]*>", "\n", html, flags=re.IGNORECASE)
        text = _strip_tags(html)
        # Boş satırları temizle
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        clean = "\n".join(lines)
        return {"url": params.url, "content": clean[:8000], "status": str(r.status_code)}
    except Exception as exc:
        return {"url": params.url, "content": "", "error": str(exc)}


def summarize(params: SummarizeParams) -> str:
    """Metni cümle bazlı özetler."""
    sentences = re.split(r"(?<=[.!?])\s+", params.text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    selected = sentences[: params.max_sentences]
    return " ".join(selected)


def extract_links(params: ExtractLinksParams) -> list[str]:
    """HTML içeriğinden bağlantıları çıkarır."""
    return re.findall(r'href=["\']([^"\']+)["\']', params.html)


TOOL_HANDLERS: dict[str, tuple[type[BaseModel], Any]] = {
    "web_search": (WebSearchParams, web_search),
    "fetch_page": (FetchPageParams, fetch_page),
    "summarize": (SummarizeParams, summarize),
    "extract_links": (ExtractLinksParams, extract_links),
}
