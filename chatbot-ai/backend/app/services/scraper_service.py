import re
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

_STRIP_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "svg", "form")
_REQUEST_TIMEOUT = httpx.Timeout(15.0)
_USER_AGENT = "AIChatbotPlatform-KnowledgeCrawler/1.0"


class ScrapeError(Exception):
    pass


async def fetch_html(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                raise ScrapeError(f"URL did not return HTML content (got {content_type or 'unknown'})")
            return response.text
    except httpx.HTTPStatusError as exc:
        raise ScrapeError(f"HTTP {exc.response.status_code} fetching {url}") from exc
    except httpx.RequestError as exc:
        raise ScrapeError(f"Could not reach {url}: {exc}") from exc


def extract_text(html: str) -> tuple[str, str]:
    """Returns (title, cleaned_text)."""

    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return title, text.strip()


def discover_links(html: str, base_url: str, *, exclude_patterns: list[str]) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute, _ = urldefrag(urljoin(base_url, href))
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https") or parsed.netloc != base_domain:
            continue
        if any(pattern and pattern in absolute for pattern in exclude_patterns):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)

    return links


async def crawl(
    base_url: str,
    *,
    single_url_only: bool,
    max_pages: int,
    max_depth: int,
    include_subpages: bool,
    exclude_patterns: list[str],
) -> list[str]:
    """Breadth-first crawl starting at base_url. Returns the ordered list of
    URLs discovered (including base_url itself), capped at max_pages."""

    if single_url_only or not include_subpages:
        return [base_url]

    visited: set[str] = {base_url}
    queue: list[tuple[str, int]] = [(base_url, 0)]
    discovered = [base_url]

    while queue and len(discovered) < max_pages:
        url, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        try:
            html = await fetch_html(url)
        except ScrapeError:
            continue

        for link in discover_links(html, base_url, exclude_patterns=exclude_patterns):
            if link in visited:
                continue
            visited.add(link)
            discovered.append(link)
            queue.append((link, depth + 1))
            if len(discovered) >= max_pages:
                break

    return discovered[:max_pages]
