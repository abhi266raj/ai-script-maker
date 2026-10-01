"""Stage 1 helper: fetch the exact story link, verify it is the same story,
and pull 3-4 article images for a professional removable gallery.

Fail-loud contract: network/parse problems raise with details — the UI
surfaces them instead of silently showing an empty gallery.
"""

import re
from typing import Dict, List, Optional, Tuple
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
# NOTE (issue #86): the ``ads/`` alternative uses a negative lookbehind so it
# does NOT match inside longer words — the bare substring also matched
# ``/uploads/`` (``uplo[ads/]``), silently killing every WordPress article
# image (``.../wp-content/uploads/...``). Real ad paths (``/ads/``,
# ``/my-ads/``, ``/banners/ads/``) are still dropped; the user explicitly
# does not want ad images.
_JUNK_RE = re.compile(
    r"(logo|sprite|icon|avatar|placeholder|pixel|spacer|blank|ad-|(?<![a-z])ads/|"
    r"tracking|beacon|1x1|transparent)",
    re.IGNORECASE,
)


# Alt text that marks an image as an unwanted asset (logos, icons, author
# avatars, ads, social/share buttons, decorative spacers). This is the
# PRIMARY relevance signal for extracted images: present alt text drives
# the keep/remove decision. Missing/empty alt text is NOT a pass by
# itself — the URL junk rules and content-type preflights still apply.
_UNWANTED_ALT_RE = re.compile(
    r"(\blogos?\b|\bfavicon\b|\bavatars?\b|\bicons?\b|"
    r"\bad\b|advertis\w*|sponsor\w*|"
    r"\bplaceholder\b|\bspacer\b|\bpixels?\b|"
    r"profile\s+(photo|picture|image)s?|"
    r"author\s+(photo|picture|image|avatar)s?|"
    r"\bbyline\b|share\s+(on|this|button)|follow\s+(us|on)|"
    r"social\s+(media\s+)?(icons?|buttons?|share)|"
    r"decorat\w*|banner\s+ad\b)",
    re.IGNORECASE,
)


def image_alt_is_unwanted(alt: Optional[str]) -> bool:
    """True when alt text shows the image is an unwanted asset.

    Logos, icons, avatars, ads, social/share buttons and decorative
    spacers are excluded. Empty or missing alt text returns False —
    absence of alt text is never treated as a removal signal on its
    own; the URL junk rules and content-type checks still apply.
    """
    if not alt or not alt.strip():
        return False
    return bool(_UNWANTED_ALT_RE.search(alt))


def _norm(url: str) -> str:
    return (url or "").strip().split("#")[0]


# Tags that mark site chrome (never story content) when an image sits
# under them. Issue #86: the fetcher must return ONLY story images.
_CHROME_TAGS = ("header", "nav", "footer", "aside")

# Story-body selectors, tried after <article>/<main>/[role=main].
_STORY_BODY_SELECTORS = (
    '[itemprop="articleBody"]',
    ".article-body", ".articleBody",
    ".article-content", ".articleContent",
    ".story-body", ".storyBody",
    ".story-content", ".storyContent",
    ".entry-content", ".post-content", ".post-body",
    "#article-body", "#story-body",
)


def _story_body_container(soup):
    """Return ``(container, scoped)`` for in-article image extraction.

    Prefers ``<article>``, then ``<main>`` / ``[role="main"]``, then common
    story-body selectors. ``scoped`` is False when no article body could
    be identified — the caller falls back to a whole-page scan and must
    say so honestly (never silently).
    """
    for finder in (lambda: soup.find("article"),
                   lambda: soup.find("main"),
                   lambda: soup.find(attrs={"role": "main"})):
        container = finder()
        if container is not None:
            return container, True
    for sel in _STORY_BODY_SELECTORS:
        container = soup.select_one(sel)
        if container is not None:
            return container, True
    return None, False


def _in_chrome(tag, *, allow_header_inside: bool) -> bool:
    """True when ``tag`` sits under site-chrome elements.

    ``<header>`` counts as chrome only in whole-page fallback — inside a
    scoped article body it is the article's own header (often wrapping
    the hero image), not the site header.
    """
    for parent in tag.parents:
        name = getattr(parent, "name", None)
        if name in _CHROME_TAGS and (name != "header" or not allow_header_inside):
            return True
    return False


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


def extract_story_images_with_alt(html: str, base_url: str,
                                   limit: int = 4,
                                   scope_report: Optional[Dict] = None
                                   ) -> List[Tuple[str, Optional[str]]]:
    """Extract up to ``limit`` story images as ``(url, alt_text)`` pairs.

    Priority: og:image → twitter:image → JSON-LD image → in-article
    photos. Page-level meta (og/twitter/JSON-LD) is the publisher's
    declared story image and is kept as-is. In-article extraction is
    scoped to the story body (``<article>`` → ``<main>``/``[role=main]``
    → common story-body selectors); images under ``<header>``/``<nav>``/
    ``<footer>``/``<aside>`` are site chrome and are excluded (issue
    #86). When no article body can be identified, the scan falls back
    to the whole page — still excluding chrome by ancestor — and
    ``scope_report["scoped"]`` is set to False so the caller can say so
    honestly instead of silently returning whatever the page yields.

    ``<amp-img>`` tags are parsed like ``<img>`` (AMP pages use them
    instead). Logos, sprites, SVGs and tracking pixels are skipped,
    and so is any image whose alt text marks it as an unwanted asset
    (see :func:`image_alt_is_unwanted`) — present alt text is the
    primary keep/remove signal. Meta/JSON-LD images carry no alt text
    (``None``). URLs are absolutized and deduplicated.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: List[Tuple[str, Optional[str]]] = []
    seen = set()

    def _add(raw: str, alt: Optional[str] = None) -> None:
        u = _norm(urljoin(base_url, raw or ""))
        if not u.lower().startswith(("http://", "https://")):
            return
        if u.lower().endswith(".svg"):
            return
        if _JUNK_RE.search(u):
            return
        if image_alt_is_unwanted(alt):
            return
        key = u.lower()
        if key in seen:
            return
        seen.add(key)
        found.append((u, (alt or "").strip() or None))

    # 1. Open Graph / Twitter cards (no alt text available)
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
    # 4. In-article photos, scoped to the story body (issue #86): only
    # story images — never site chrome. <amp-img> is parsed like <img>
    # because AMP pages use it instead.
    container, scoped = _story_body_container(soup)
    if scope_report is not None:
        scope_report["scoped"] = scoped
    roots = [container] if scoped else [soup]
    for root in roots:
        for img in root.find_all(["img", "amp-img"]):
            if _in_chrome(img, allow_header_inside=scoped):
                continue
            alt = img.get("alt")
            src = (img.get("src") or img.get("data-src")
                   or img.get("data-lazy-src") or "")
            if src:
                _add(src, alt)
            srcset = img.get("srcset") or img.get("data-srcset") or ""
            if srcset:
                # Take the largest candidate (last in srcset order).
                parts = [p.strip().split(" ")[0] for p in srcset.split(",")]
                if parts:
                    _add(parts[-1], alt)
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    return found[:limit]


def extract_story_images(html: str, base_url: str,
                         limit: int = 4) -> List[str]:
    """Extract up to ``limit`` story images from an article page.

    URL-only view of :func:`extract_story_images_with_alt` — the same
    priority order and the same logo/junk/alt-text filtering apply.
    """
    return [u for u, _ in extract_story_images_with_alt(html, base_url, limit)]


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
