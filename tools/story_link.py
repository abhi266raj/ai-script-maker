"""Stage 1 helper: fetch the exact story link, verify it is the same story,
and pull 3-4 article images for a professional removable gallery.

Fail-loud contract: network/parse problems raise with details — the UI
surfaces them instead of silently showing an empty gallery.
"""

import re
from typing import Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


_TIMEOUT = 25
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

# Image URLs that are never story photos (logos, sprites, tracking pixels).
_JUNK_RE = re.compile(
    r"(logo|sprite|icon|avatar|placeholder|pixel|spacer|blank|ad-|ads/|"
    r"tracking|beacon|1x1|transparent)",
    re.IGNORECASE,
)


def _norm(url: str) -> str:
    return (url or "").strip().split("#")[0]


def fetch_story_page(url: str, timeout: int = _TIMEOUT) -> Dict:
    """GET the article page. Returns {url, title, text, html}.

    Raises RuntimeError with details on any failure (fail loudly).
    """
    url = _norm(url)
    if not url.lower().startswith(("http://", "https://")):
        raise RuntimeError(f"Not a fetchable article URL: {url!r}")
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout,
                         follow_redirects=True)
    except Exception as e:
        raise RuntimeError(
            f"Could not fetch the story link ({type(e).__name__}: {e}). "
            f"URL: {url}"
        ) from e
    if resp.status_code >= 400:
        raise RuntimeError(
            f"The story link returned HTTP {resp.status_code}. URL: {resp.url}"
        )
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype.lower():
        raise RuntimeError(
            f"The story link did not return an article page "
            f"(content-type: {ctype or 'unknown'}). URL: {resp.url}"
        )
    html = resp.text
    if len(html) < 2000:
        raise RuntimeError(
            f"The story link returned an unusually small page "
            f"({len(html)} chars) — likely a block or paywall. URL: {resp.url}"
        )
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    # Article text: prefer <article>, else body paragraphs.
    text = ""
    article = soup.find("article") or soup.find("main")
    paras = (article or soup).find_all("p")
    text = " ".join(p.get_text(" ", strip=True) for p in paras[:60])
    return {"url": str(resp.url), "title": title, "text": text[:6000],
            "html": html}


def extract_story_images(html: str, base_url: str,
                         limit: int = 4) -> List[str]:
    """Extract up to ``limit`` story images from an article page.

    Priority: og:image → twitter:image → JSON-LD image → in-article
    <img>/<figure> photos. Logos, sprites, SVGs and tracking pixels are
    skipped; URLs are absolutized and deduplicated.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: List[str] = []
    seen = set()

    def _add(raw: str) -> None:
        u = _norm(urljoin(base_url, raw or ""))
        if not u.lower().startswith(("http://", "https://")):
            return
        if u.lower().endswith(".svg"):
            return
        if _JUNK_RE.search(u):
            return
        key = u.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(u)

    # 1. Open Graph / Twitter cards
    for prop in ("og:image", "og:image:secure_url",
                 "twitter:image", "twitter:image:src"):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            _add(tag["content"])
    # 2. link rel=image_src
    link_tag = soup.find("link", rel="image_src")
    if link_tag and link_tag.get("href"):
        _add(link_tag["href"])
    # 3. JSON-LD images
    import json as _json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "")
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if "@graph" in node and isinstance(node["@graph"], list):
                nodes.extend(n for n in node["@graph"] if isinstance(n, dict))
                continue
            img = node.get("image")
            imgs = img if isinstance(img, list) else [img]
            for im in imgs:
                if isinstance(im, str):
                    _add(im)
                elif isinstance(im, dict) and im.get("url"):
                    _add(im["url"])
    # 4. In-article photos (<article>/<main>/<figure> first, then body)
    containers = []
    for sel in ("article", "main"):
        c = soup.find(sel)
        if c:
            containers.append(c)
    containers.extend(soup.find_all("figure"))
    if not containers:
        containers = [soup]
    for container in containers:
        for img in container.find_all("img"):
            src = (img.get("src") or img.get("data-src")
                   or img.get("data-lazy-src") or "")
            if src:
                _add(src)
            srcset = img.get("srcset") or img.get("data-srcset") or ""
            if srcset:
                # Take the largest candidate (last in srcset order).
                parts = [p.strip().split(" ")[0] for p in srcset.split(",")]
                if parts:
                    _add(parts[-1])
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    return found[:limit]


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-zA-Z\u0900-\u097F]{4,}", (text or "").lower()))


def verify_same_story_code(article: Dict, expected_headline: str,
                           verified_facts: List[str]) -> Tuple[bool, str]:
    """Deterministic same-story check (no LLM).

    Compares the fetched article's title/text against the verified headline
    and facts via keyword overlap. Returns (is_same, reason).
    """
    a_title = article.get("title", "") or ""
    a_text = article.get("text", "") or ""
    if not a_title and not a_text:
        return False, "The fetched page had no readable title or text to compare."
    exp_toks = _tokens(expected_headline)
    art_toks = _tokens(a_title + " " + a_text[:2000])
    if not exp_toks:
        return False, "No verified headline to compare against."
    overlap = len(exp_toks & art_toks) / max(1, len(exp_toks))
    if overlap >= 0.35:
        return True, (
            f"Title/keyword overlap {overlap:.0%} with the verified headline — "
            "same story (deterministic check)."
        )
    # Fallback: do the verified facts' keywords appear in the article?
    fact_toks = set()
    for f in (verified_facts or [])[:8]:
        fact_toks |= _tokens(f)
    fact_toks -= exp_toks
    if fact_toks:
        hit = len(fact_toks & art_toks) / max(1, len(fact_toks))
        if hit >= 0.4:
            return True, (
                f"Headline overlap was low ({overlap:.0%}) but "
                f"{hit:.0%} of verified-fact keywords appear in the article — "
                "same story (deterministic check)."
            )
    return False, (
        f"Only {overlap:.0%} keyword overlap with the verified headline — "
        "this link may point at a different story."
    )


def verify_same_story_llm(article: Dict, expected_headline: str,
                          verified_facts: List[str],
                          engine_mode: str = "first_local_then_agy"
                          ) -> Tuple[bool, str]:
    """LLM same-story check using the app's engine selection.

    Asks the model whether the fetched article is the same news story as
    the verified headline/facts. Returns (is_same, reason). Fail loudly on
    engine errors.
    """
    from core.dual_engine import dual_engine, ModelGenerationError

    facts_txt = "\n".join(f"- {f}" for f in (verified_facts or [])[:10]) or ["(none)"]
    prompt = (
        "You are a news-desk verification assistant. Decide whether the "
        "fetched web article is the SAME news story as the verified one.\n\n"
        f"VERIFIED HEADLINE: {expected_headline}\n"
        f"VERIFIED FACTS:\n{facts_txt}\n\n"
        f"FETCHED ARTICLE TITLE: {article.get('title', '')}\n"
        f"FETCHED ARTICLE URL: {article.get('url', '')}\n"
        f"FETCHED ARTICLE TEXT (excerpt):\n{(article.get('text', '') or '')[:2500]}\n\n"
        "Answer in exactly this format:\n"
        "VERDICT: YES or NO\n"
        "REASON: one sentence explaining the verdict."
    )
    try:
        raw, engine_used = dual_engine.generate(
            prompt=prompt,
            instructions="You verify whether two news items describe the same story. Be strict but fair.",
            mode=engine_mode,
        )
    except ModelGenerationError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"LLM verification failed ({type(e).__name__}: {e})"
        ) from e
    m = re.search(r"VERDICT:\s*(YES|NO)", raw or "", re.IGNORECASE)
    if not m:
        raise RuntimeError(
            "LLM verification returned no parseable VERDICT. "
            f"Raw output: {(raw or '')[:300]!r}"
        )
    is_same = m.group(1).upper() == "YES"
    r = re.search(r"REASON:\s*(.+)", raw or "", re.IGNORECASE | re.DOTALL)
    reason = r.group(1).strip().split("\n")[0][:300] if r else ""
    return is_same, f"{reason} (via {engine_used})" if reason else f"(via {engine_used})"
