"""Live India news: Google News/Trends, Reddit, Mastodon, Bing News, DuckDuckGo (free public APIs)."""

import html
import logging
import random
import re
import urllib.parse
import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
import feedparser
import httpx
from bs4 import BeautifulSoup
from core.models import NewsArticle

logger = logging.getLogger(__name__)

_HTTP_HEADERS = {
    "User-Agent": "HindiReelStudio/1.0 (news desk; +https://local)",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}


# Display names for known publishers, keyed by normalized host (no
# "www."). Used by publisher_name_from_url (#153).
_PUBLISHER_NAMES = {
    "indianexpress.com": "Indian Express",
    "timesofindia.indiatimes.com": "Times of India",
    "economictimes.indiatimes.com": "Economic Times",
    "hindustantimes.com": "Hindustan Times",
    "thehindu.com": "The Hindu",
    "ndtv.com": "NDTV",
    "news18.com": "News18",
    "aajtak.in": "Aaj Tak",
    "abplive.com": "ABP Live",
    "zeenews.india.com": "Zee News",
    "deccanherald.com": "Deccan Herald",
    "jagran.com": "Dainik Jagran",
    "bhaskar.com": "Dainik Bhaskar",
    "amarujala.com": "Amar Ujala",
    "firstpost.com": "Firstpost",
    "moneycontrol.com": "Moneycontrol",
    "livemint.com": "Mint",
    "businesstoday.in": "Business Today",
    "mypunepulse.com": "MyPunePulse",
    "punemirror.com": "Pune Mirror",
    "mid-day.com": "Mid-Day",
    "theprint.in": "ThePrint",
    "scroll.in": "Scroll",
    "thewire.in": "The Wire",
    "quint.com": "The Quint",
    "thequint.com": "The Quint",
    "opindia.com": "OpIndia",
    "republicworld.com": "Republic World",
    "indiatoday.in": "India Today",
    "dnaindia.com": "DNA India",
    "freepressjournal.in": "Free Press Journal",
}


def publisher_name_from_url(url: str) -> str:
    """Clean publisher display name derived from an article URL (#153).

    Returns e.g. "Indian Express" for an indianexpress.com URL — never the
    raw domain. Unknown hosts fall back to a title-cased domain label.
    Returns "" when no host can be determined.
    """
    try:
        host = urllib.parse.urlparse((url or "").strip()).netloc.lower()
    except Exception:
        host = ""
    host = host.split("@")[-1].split(":")[0].strip()
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    if not host:
        return ""
    if host in _PUBLISHER_NAMES:
        return _PUBLISHER_NAMES[host]
    label = host.split(".")[0]
    parts = [p for p in re.split(r"[-_]+", label) if p]
    if not parts:
        return ""
    return " ".join(p[:1].upper() + p[1:] for p in parts)


# Fetch-time source labels that name the aggregator/search engine rather
# than the publisher (#153, #227). When an article carries one of these,
# its source is refreshed from the (resolved) URL's domain. Mirrors
# story_library's _STALE_AGGREGATOR_SOURCES used by
# repair_news_link_urls — keep the two in sync.
_STALE_AGGREGATOR_SOURCES = frozenset(
    {"Bing News", "DuckDuckGo", "News Wire", "Live Wire"}
)


class NewsFetchError(Exception):
    """Raised when every news source failed or returned nothing.

    Carries ``report`` — a list of per-source attempt dicts
    (``source``, ``outcome`` in {"ok", "empty", "error"}, ``count``,
    ``detail``) — so the UI can show exactly what was tried instead
    of silently returning an empty result.
    """

    def __init__(self, report: List[Dict[str, object]]):
        self.report = list(report or [])
        super().__init__(self._message())

    def _message(self) -> str:
        if not self.report:
            return "News search found nothing and no source was attempted."
        parts = []
        for attempt in self.report:
            src = attempt.get("source", "?")
            outcome = attempt.get("outcome", "?")
            detail = attempt.get("detail") or ""
            if outcome == "ok":
                parts.append(f"{src}: {attempt.get('count', 0)} article(s)")
            elif outcome == "empty":
                parts.append(f"{src}: no results{(' — ' + detail) if detail else ''}")
            else:
                parts.append(f"{src}: failed{(' — ' + detail) if detail else ''}")
        return "News search found nothing. Tried: " + "; ".join(parts) + "."


def _parse_pub_datetime(raw: str, entry=None) -> Optional[datetime.datetime]:
    """Parse publication date into UTC datetime from feedparser entry or string."""
    if entry and hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
        except Exception:
            pass
    if entry and hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime.datetime(*entry.updated_parsed[:6], tzinfo=datetime.timezone.utc)
        except Exception:
            pass
    if raw is not None:
        clean = str(raw).strip()
        # Handle Unix timestamp (e.g. from Reddit)
        try:
            val = float(clean)
            return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
        except (ValueError, TypeError, OverflowError):
            pass
        # Handle RFC 2822 / standard RSS date
        try:
            dt = parsedate_to_datetime(clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            pass
        # Handle ISO-8601 (e.g. Mastodon)
        try:
            dt = datetime.datetime.fromisoformat(clean.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            pass
    return None


def _format_relative_time(dt: Optional[datetime.datetime], now: Optional[datetime.datetime] = None) -> str:
    """Format datetime into human-friendly relative label (e.g. 15m ago, 2h ago)."""
    if not dt:
        return ""
    if not now:
        now = datetime.datetime.now(datetime.timezone.utc)
    diff = (now - dt).total_seconds()
    if diff < 0:
        return "Just now"
    minutes = int(diff // 60)
    hours = int(diff // 3600)
    if minutes < 60:
        return f"{max(1, minutes)}m ago"
    if hours < 24:
        return f"{hours}h ago"
    days = int(diff // 86400)
    return f"{days}d ago"

_INDIA_TERMS = (
    "india", "indian", "bharat", "delhi", "mumbai", "bengaluru", "bangalore",
    "gurgaon", "noida", "kolkata", "chennai", "hyderabad", "pune", "ahmedabad",
    "modi", "isro", "rupee", "kashmir", "lok sabha", "bjp", "congress", "upi",
    "gaganyaan", "varanasi", "hindi", "sc india", "supreme court", "rbi", "nse",
    "sensex", "zomato", "swiggy", "blinkit", "ola", "uber", "rickshaw", "jugaad",
    "viral", "dosa", "chai", "tapri", "traffic", "pakistan", "china", "border",
    "ladakh", "punjab", "tamil", "bengal",
)


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def is_english_text(text: str) -> bool:
    """True when the alphabetic characters are Latin (English hashtags only)."""
    letters = [c for c in (text or "") if c.isalpha()]
    if len(letters) < 3:
        return False
    latin = sum(1 for c in letters if ("a" <= c.lower() <= "z"))
    return (latin / len(letters)) >= 0.9


def phrase_to_hashtag(phrase: str) -> str:
    """Turn a short English trend name into a single #Tag. Empty if not English."""
    if not is_english_text(phrase):
        return ""
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    if not words or len(words) > 5:
        return ""
    parts = []
    for w in words:
        parts.append(w if w.isupper() or any(ch.isdigit() for ch in w) else w[:1].upper() + w[1:])
    tag = "#" + "".join(parts)
    if len(tag) < 4 or len(tag) > 40:
        return ""
    return tag


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()[:80]


_TOPIC_STOPWORDS = frozenset(
    "the a an and or of to in on for with by from at as is are was were be "
    "been has have had do does did will would can could should this that "
    "these those it its new latest breaking news today".split()
)


def _topic_score(title: str, snippet: str = "", query: str = "") -> int:
    """Relevance of an article to the user's query: term overlap + phrase bonus."""
    terms = [t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
             if len(t) > 2 and t not in _TOPIC_STOPWORDS]
    if not terms:
        return 0
    blob = f"{title} {snippet}".lower()
    score = 0
    for term in terms:
        if term in blob:
            score += 5
    phrase = " ".join(terms)
    if phrase and phrase in blob:
        score += 5
    return score


def _india_score(title: str, snippet: str = "", source: str = "") -> int:
    blob = f"{title} {snippet} {source}".lower()
    score = 0
    for term in _INDIA_TERMS:
        if term in blob:
            score += 3
    if any(k in blob for k in ("breaking", "live", "alert", "exclusive")):
        score += 2
    if any(k in (source or "").lower() for k in ("india", "toi", "hindu", "ndtv", "reddit", "trends")):
        score += 2
    return score


class NewsFetcher:
    """Fetches real-time, verified live news articles strictly from the last 24 hours."""

    def __init__(self, max_articles: int = 8):
        self.max_articles = max_articles
        self._timeout = 8.0

    def _parse_feed(
        self,
        feed_url: str,
        limit: int,
        fallback_source: str = "Live Wire",
        max_age_hours: Optional[float] = 24.0,
    ) -> List[NewsArticle]:
        """Helper to parse an RSS feed into clean NewsArticle objects filtered by recency."""
        articles: List[NewsArticle] = []
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            # Fetch with a hard timeout first: feedparser.parse(url) does
            # its own fetching with NO timeout and can hang a refresh
            # forever on a stalled connection.
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout,
                             follow_redirects=True) as client:
                r = client.get(feed_url)
                if r.status_code != 200:
                    return []
                feed = feedparser.parse(r.content)
            for entry in feed.entries:
                title = clean_html(getattr(entry, "title", "Untitled"))
                link = getattr(entry, "link", "")
                published = getattr(entry, "published", "")

                source = fallback_source
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()
                elif hasattr(entry, "source") and hasattr(entry.source, "title"):
                    source = entry.source.title

                dt = _parse_pub_datetime(published, entry)
                age_h = None
                time_lbl = ""
                if dt:
                    age_h = max(0.0, (now - dt).total_seconds() / 3600.0)
                    time_lbl = _format_relative_time(dt, now)
                    if max_age_hours is not None and age_h > max_age_hours:
                        continue
                elif max_age_hours is not None:
                    # If publication date cannot be verified, give reasonable benefit of doubt
                    # but prefer feeds with explicit timestamps
                    time_lbl = "Today"

                summary_raw = getattr(entry, "summary", "")
                snippet = clean_html(summary_raw)

                articles.append(
                    NewsArticle(
                        title=title,
                        link=link,
                        source=source,
                        snippet=snippet,
                        published=published,
                        age_hours=round(age_h, 1) if age_h is not None else None,
                        time_label=time_lbl,
                    )
                )
                if len(articles) >= limit:
                    break
        except Exception as e:
            print(f"Warning: news feed parsing failed for {feed_url}: {e}")
        return articles

    def _http_get(self, url: str) -> httpx.Response:
        """Single GET with the shared UA/timeout. Test seam: monkeypatch in tests."""
        with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout,
                          follow_redirects=True) as client:
            return client.get(url)

    def _fetch_rss_or_raise(
        self,
        feed_url: str,
        limit: int,
        fallback_source: str = "Live Wire",
        max_age_hours: Optional[float] = 24.0,
    ) -> List[NewsArticle]:
        """RSS fetch that raises on transport/HTTP failure (#121).

        Unlike :meth:`_parse_feed` (which swallows failures for best-effort
        pool callers), this surfaces the failure so the multi-source chain
        can record exactly which source failed and why.
        """
        r = self._http_get(feed_url)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {feed_url}")
        feed = feedparser.parse(r.content)
        if getattr(feed, "bozo", False) and not feed.entries:
            raise RuntimeError(f"unparseable feed: {feed_url}")
        articles: List[NewsArticle] = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for entry in feed.entries:
            title = clean_html(getattr(entry, "title", "Untitled"))
            link = getattr(entry, "link", "")
            published = getattr(entry, "published", "")
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip()
            elif hasattr(entry, "source") and hasattr(entry.source, "title"):
                source = entry.source.title
            else:
                # #229: derive the label from the item's URL domain — never
                # the fetch-method wire name ("News Wire" / "Bing News" /
                # "Live Wire"), which leaked into share text as if it were
                # the publisher.
                source = publisher_name_from_url(link)
                if not source:
                    # Loud last resort: warn visibly instead of silently
                    # mislabeling the item with the wire name.
                    print(f"Warning: #229 could not derive a publisher name "
                          f"from link {link!r} (feed {feed_url}); falling "
                          f"back to {fallback_source!r}")
                    source = fallback_source
            dt = _parse_pub_datetime(published, entry)
            age_h = None
            time_lbl = ""
            if dt:
                age_h = max(0.0, (now - dt).total_seconds() / 3600.0)
                time_lbl = _format_relative_time(dt, now)
                if max_age_hours is not None and age_h > max_age_hours:
                    continue
            elif max_age_hours is not None:
                time_lbl = "Today"
            snippet = clean_html(getattr(entry, "summary", ""))
            if not title or not link:
                continue
            articles.append(
                NewsArticle(
                    title=title,
                    link=link,
                    source=source,
                    snippet=snippet,
                    published=published,
                    age_hours=round(age_h, 1) if age_h is not None else None,
                    time_label=time_lbl,
                )
            )
            if len(articles) >= limit:
                break
        return articles

    # -- #121 multi-source chain -------------------------------------------

    _DDG_INTERNAL_HOSTS = frozenset({"duckduckgo.com", "www.duckduckgo.com"})

    def _src_google_news(self, query: str, limit: int) -> Tuple[List[NewsArticle], List[Dict[str, object]]]:
        """Google News RSS: strict 24h search, then a looser 48h fallback."""
        attempts: List[Dict[str, object]] = []
        q = f"when:24h {query.strip()}"
        feed_url = ("https://news.google.com/rss/search?q="
                    + urllib.parse.quote(q) + "&hl=en-IN&gl=IN&ceid=IN:en")
        arts = self._fetch_rss_or_raise(feed_url, limit, fallback_source="News Wire",
                                       max_age_hours=24.0)
        attempts.append({"source": "google-news-rss/24h",
                         "outcome": "ok" if arts else "empty",
                         "count": len(arts), "detail": ""})
        if not arts:
            feed_url = ("https://news.google.com/rss/search?q="
                        + urllib.parse.quote(query.strip()) + "&hl=en-IN&gl=IN&ceid=IN:en")
            arts = self._fetch_rss_or_raise(feed_url, limit, fallback_source="News Wire",
                                           max_age_hours=48.0)
            attempts.append({"source": "google-news-rss/48h",
                             "outcome": "ok" if arts else "empty",
                             "count": len(arts), "detail": "24h query was empty"})
        return arts, attempts

    def _src_bing_news(self, query: str, limit: int) -> List[NewsArticle]:
        """Bing News RSS — independent RSS index from Google's."""
        feed_url = ("https://www.bing.com/news/search?q="
                    + urllib.parse.quote(query.strip()) + "&format=rss")
        return self._fetch_rss_or_raise(feed_url, limit, fallback_source="Bing News",
                                       max_age_hours=48.0)

    @staticmethod
    def _ddg_real_url(href: str) -> str:
        """Unwrap a DuckDuckGo redirect href to the real article URL (#135).

        DDG double-encodes the target inside ``uddg`` (parse_qs decodes
        only once), so unquote repeatedly until stable — otherwise the
        link comes out as ``https%3A%2F%2F...`` garbage. Reject
        anything that is not an http(s) URL.
        """
        href = (href or "").strip()
        if not href:
            return ""
        if href.startswith("//"):
            href = "https:" + href
        try:
            parsed = urllib.parse.urlparse(href)
        except Exception:
            return ""
        if parsed.netloc.lower() in NewsFetcher._DDG_INTERNAL_HOSTS:
            qs = urllib.parse.parse_qs(parsed.query)
            real = (qs.get("uddg") or [""])[0]
            decoded = real
            for _ in range(4):
                nxt = urllib.parse.unquote(decoded)
                if nxt == decoded:
                    break
                decoded = nxt
            real = decoded.strip()
            if real.startswith("http://") or real.startswith("https://"):
                return real
            return ""
        if parsed.netloc:
            return href
        return ""

    def _src_duckduckgo(self, query: str, limit: int) -> List[NewsArticle]:
        """DuckDuckGo HTML search with regex-based link extraction (#121).

        Last-resort source: no API, no RSS — parse the classic HTML
        endpoint and regex out result anchors + snippets, unwrapping
        DDG's redirect URLs to the real article links.
        """
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query.strip())
        r = self._http_get(url)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        page = r.text or ""
        anchors = re.findall(
            r'<a\b(?=[^>]*\bclass="result__a")[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>',
            page, re.DOTALL | re.IGNORECASE)
        if not anchors:
            # Page shape changed: fall back to any anchor carrying a DDG
            # redirect (uddg=) href before giving up loudly.
            anchors = re.findall(
                r'<a\b[^>]*\bhref="([^"]*uddg=[^"]+)"[^>]*>(.*?)</a>',
                page, re.DOTALL | re.IGNORECASE)
        snippets = re.findall(
            r'<a\b(?=[^>]*\bclass="result__snippet")[^>]*>(.*?)</a>',
            page, re.DOTALL | re.IGNORECASE)
        if not snippets:
            snippets = re.findall(
                r'<(?:div|td|span)\b[^>]*\bclass="result__snippet"[^>]*>(.*?)</(?:div|td|span)>',
                page, re.DOTALL | re.IGNORECASE)
        if not anchors:
            # Page shape changed or was blocked — say so loudly, don't
            # pretend the query had no results.
            raise RuntimeError("no result anchors found in DuckDuckGo HTML "
                               "(page shape changed or request blocked)")
        articles: List[NewsArticle] = []
        for i, (href, inner) in enumerate(anchors):
            link = self._ddg_real_url(html.unescape(href))
            if not link:
                continue
            title = clean_html(inner)
            if not title:
                continue
            snippet = clean_html(snippets[i]) if i < len(snippets) else ""
            articles.append(
                NewsArticle(
                    title=title,
                    link=link,
                    source="DuckDuckGo",
                    snippet=snippet,
                    published="",
                    age_hours=None,
                    time_label="",
                )
            )
            if len(articles) >= limit:
                break
        return articles

    # -- #136/#143 aggregator redirect resolution ----------------------------

    # Hosts that are known to serve redirect/intermediate URLs rather than
    # the final article. #143: this list is only used to decide
    # fail-closed (skip loudly) vs fail-open (keep the original URL) when
    # a URL cannot be fetched for resolution — the resolution itself is
    # universal (every URL is followed through its redirect chain).
    _AGGREGATOR_REDIRECT_HOSTS = frozenset({
        "news.google.com", "www.news.google.com",
        "www.bing.com", "bing.com",
        "duckduckgo.com", "www.duckduckgo.com",
        "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
        "news.yahoo.com", "www.news.yahoo.com",
    })

    def resolve_final_url(self, url: str) -> str:
        """Follow the FULL redirect chain to the final destination URL (#143).

        Uses the shared timeout/UA with ``follow_redirects=True``, so
        multi-hop chains (aggregator → shortener → publisher) are fully
        resolved. Returns the final URL, or "" when it cannot be
        determined (network error, non-200, non-http result) — the
        caller decides whether to skip loudly or keep the original.
        """
        url = (url or "").strip()
        if not url:
            return ""
        # Protocol-relative URLs (//host/path) from scraped HTML.
        if url.startswith("//"):
            url = "https:" + url
        # Repeatedly unquote: some aggregators double/triple-encode (#135).
        prev = None
        cur = url
        while prev != cur:
            prev = cur
            cur = urllib.parse.unquote(cur)
        url = cur
        if not (url.startswith("http://") or url.startswith("https://")):
            return ""
        try:
            r = self._http_get(url)
        except Exception:
            return ""
        if r.status_code != 200:
            return ""
        final = str(getattr(r, "url", "") or "").strip()
        if not final:
            return ""
        if not (final.startswith("http://") or final.startswith("https://")):
            return ""
        try:
            if urllib.parse.urlparse(final).netloc.lower() in self._AGGREGATOR_REDIRECT_HOSTS:
                return ""  # still an aggregator redirect — not resolved
        except Exception:
            return ""
        return final

    def _resolve_publisher_url(self, url: str) -> str:
        """Resolve an aggregator redirect URL to the final publisher URL (#136).

        Kept for backwards compatibility; delegates to
        :meth:`resolve_final_url` (#143).
        """
        return self.resolve_final_url(url)

    def _resolve_aggregator_links(
        self, articles: List[NewsArticle]
    ) -> Tuple[List[NewsArticle], int]:
        """Rewrite redirect links to final publisher URLs (#136, #143).

        #143: EVERY article URL is followed through its complete redirect
        chain (not just known aggregator hosts) — this catches Bing
        redirects, URL shorteners, and any future aggregator pattern.
        When the final URL differs, it replaces the original.
        #153: the source is refreshed to the final publisher's name when
        the URL changes — a "Bing News"/"DuckDuckGo" label must not
        survive on a resolved publisher link. #227: the source is also
        refreshed when the URL is unchanged but the stored source is a
        stale aggregator name ("Bing News"/"DuckDuckGo"/"News Wire"/
        "Live Wire") — DDG unwraps to the final publisher URL at parse
        time, so without this the "DuckDuckGo" label would survive.

        Returns (kept_articles, skipped_count). Articles that cannot be
        resolved are handled loudly:
        - URL on a known redirect/aggregator host → dropped, counted in
          ``skipped`` (the redirect URL is useless; never stored).
        - Other URLs → kept as-is (fail-open: a direct publisher link
          that blocks bots still works in the user's browser).
        """
        kept: List[NewsArticle] = []
        skipped = 0
        for art in articles:
            link = (art.link or "").strip()
            if not link:
                skipped += 1
                continue
            try:
                host = urllib.parse.urlparse(link).netloc.lower()
            except Exception:
                host = ""
            final = self.resolve_final_url(link)
            if final:
                url_changed = final != link
                if url_changed:
                    art.link = final
                # #153/#227: the aggregator's source ("Bing News",
                # "DuckDuckGo", "News Wire", "Live Wire") is meaningless
                # on the publisher link — refresh the label to the final
                # publisher's name whenever the URL changed OR the stored
                # source is a stale aggregator name (mirrors
                # repair_news_link_urls' condition). #227: DDG already
                # unwraps to the final publisher URL at parse time, so the
                # stale "DuckDuckGo" label survives URL resolution —
                # refresh it from the URL's domain.
                old_source = (art.source or "").strip()
                if url_changed or old_source in _STALE_AGGREGATOR_SOURCES:
                    new_source = publisher_name_from_url(final)
                    if new_source:
                        art.source = new_source
                    else:
                        # Fail loudly: never silently mislabel; keep the
                        # old label audibly.
                        logger.warning(
                            "could not derive publisher name from final URL "
                            "%r; keeping source %r", final, art.source)
                kept.append(art)
            elif host in self._AGGREGATOR_REDIRECT_HOSTS:
                # Known redirect URL that could not be resolved — useless.
                skipped += 1
            else:
                # Fail-open: probably a direct link whose server blocks
                # bots; it still works in the user's browser.
                kept.append(art)
        return kept, skipped

    def _dedupe_rank_topic(self, articles: List[NewsArticle], query: str,
                          limit: int) -> List[NewsArticle]:
        """Dedupe + rank by query relevance, then recency (#121)."""
        seen = set()
        ranked: List[tuple] = []
        for art in articles:
            key = _norm_title(art.title)
            if not key or key in seen:
                continue
            seen.add(key)
            recency_bonus = 0
            if art.age_hours is not None:
                if art.age_hours <= 3.0:
                    recency_bonus = 10
                elif art.age_hours <= 6.0:
                    recency_bonus = 7
                elif art.age_hours <= 12.0:
                    recency_bonus = 4
                elif art.age_hours <= 24.0:
                    recency_bonus = 2
            score = (_india_score(art.title, art.snippet, art.source)
                     + _topic_score(art.title, art.snippet, query)
                     + recency_bonus)
            ranked.append((score, -(art.age_hours if art.age_hours is not None else 999.0), art))
        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [art for _, _, art in ranked[:limit]]

    def search_news_multi(self, query: str,
                          limit: Optional[int] = None,
                          rng: Optional[random.Random] = None
                          ) -> Tuple[List[NewsArticle], List[Dict[str, object]]]:
        """Aggressive multi-source news search (#121, #133, #135, #136).

        Source order is randomized on every call and each source
        contributes at most 2 articles (round-robin) instead of draining
        one source first (#133). The merged set is deduped and ranked by
        query relevance. Aggregator redirect links (Google News) are
        resolved to the final publisher URL before storage; unresolvable
        redirects are skipped with a report entry — an aggregator URL
        never reaches the UI (#136). Real network calls — never
        local-only.

        Returns (articles, report); raises :class:`NewsFetchError` with
        the full per-source report when every source failed or returned
        nothing — never a silent empty list.
        """
        n = limit or self.max_articles
        q = (query or "").strip()
        if not q:
            raise NewsFetchError([{"source": "none", "outcome": "error",
                                   "count": 0, "detail": "empty query"}])
        per_source = 2  # round-robin cap: 1-2 articles per site (#133)
        rnd = rng if rng is not None else random
        report: List[Dict[str, object]] = []
        pooled: List[NewsArticle] = []

        def _google():
            arts, attempts = self._src_google_news(q, per_source)
            return arts, attempts

        def _bing():
            arts = self._src_bing_news(q, per_source)
            return arts, [{"source": "bing-news-rss",
                           "outcome": "ok" if arts else "empty",
                           "count": len(arts), "detail": ""}]

        def _ddg():
            arts = self._src_duckduckgo(q, per_source)
            return arts, [{"source": "duckduckgo-html",
                           "outcome": "ok" if arts else "empty",
                           "count": len(arts), "detail": ""}]

        sources = [("google-news-rss", _google),
                   ("bing-news-rss", _bing),
                   ("duckduckgo-html", _ddg)]
        rnd.shuffle(sources)  # fresh random order on every call (#133)

        for name, fetch in sources:
            try:
                arts, attempts = fetch()
            except Exception as e:  # noqa: BLE001 - recorded in the report, raised loudly below
                report.append({"source": name, "outcome": "error",
                               "count": 0, "detail": f"{type(e).__name__}: {e}"})
                continue
            kept, skipped = self._resolve_aggregator_links(arts)
            if skipped:
                note = (f"{skipped} aggregator redirect(s) skipped "
                        f"(could not resolve to publisher URL)")
                remaining = skipped
                for att in reversed(attempts):
                    if remaining:
                        cut = min(remaining, int(att.get("count", 0) or 0))
                        att["count"] = int(att.get("count", 0) or 0) - cut
                        remaining -= cut
                        d = att.get("detail") or ""
                        att["detail"] = f"{d}; {note}" if d else note
                    if not att.get("count"):
                        att["outcome"] = "empty"
            report.extend(attempts)
            pooled.extend(kept)

        ranked = self._dedupe_rank_topic(pooled, q, n)
        if not ranked:
            raise NewsFetchError(report)
        return ranked, report

    def search_news(self, query: str, limit: Optional[int] = None) -> List[NewsArticle]:
        """Multi-source news search (#121, #133, #135, #136).

        Same signature as before; now backed by Google News RSS, Bing
        News RSS and DuckDuckGo HTML in randomized order (#133) with
        round-robin 1-2 articles per source, relevance ranking, DDG link
        decoding (#135) and aggregator-redirect resolution to publisher
        URLs (#136). Raises :class:`NewsFetchError` (carrying the
        per-source report) when every source failed or returned nothing —
        callers surface it loudly instead of reporting an empty result.
        """
        articles, _report = self.search_news_multi(query, limit)
        return articles

    def get_top_world_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time top global world headlines from the last 24 hours."""
        q = urllib.parse.quote("when:24h (World News OR international OR United Nations OR diplomacy)")
        feed_url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        arts = self._parse_feed(feed_url, limit * 2, fallback_source="World Wire", max_age_hours=24.0)
        if len(arts) < limit:
            fallback_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
            arts += self._parse_feed(fallback_url, limit, fallback_source="World Wire", max_age_hours=24.0)
        return self._dedupe_rank(arts, limit)

    def get_top_tech_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time technology and AI headlines from the last 24 hours."""
        q = urllib.parse.quote("when:24h (Artificial Intelligence OR OpenAI OR Google AI OR NVIDIA OR Apple OR Microsoft OR LLM)")
        feed_url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        arts = self._parse_feed(feed_url, limit * 2, fallback_source="Tech Wire", max_age_hours=24.0)
        if len(arts) < limit:
            section_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"
            arts += self._parse_feed(section_url, limit, fallback_source="Tech Wire", max_age_hours=24.0)
        return self._dedupe_rank(arts, limit)

    def get_top_business_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time business and finance headlines from the last 24 hours."""
        q = urllib.parse.quote("when:24h (Sensex OR Nifty OR RBI OR Indian economy OR stock market India OR inflation India OR GST)")
        feed_url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
        arts = self._parse_feed(feed_url, limit * 2, fallback_source="Business Wire", max_age_hours=24.0)
        if len(arts) < limit:
            arts += self._parse_feed("https://economictimes.indiatimes.com/rssfeedstopstories.cms", limit, fallback_source="Economic Times", max_age_hours=24.0)
            arts += self._parse_feed("https://www.livemint.com/rss/news", limit, fallback_source="LiveMint", max_age_hours=24.0)
        return self._dedupe_rank(arts, limit)

    def get_top_india_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time top headlines across India strictly from the last 24 hours."""
        arts: List[NewsArticle] = []
        # 1. Google News India geo section
        arts += self._parse_feed(
            "https://news.google.com/rss/headlines/section/geo/India?hl=en-IN&gl=IN&ceid=IN:en",
            limit * 2,
            fallback_source="India Wire",
            max_age_hours=24.0,
        )
        # 2. Top Indian wire feeds (TOI, Hindu, Indian Express, HT)
        arts += self._parse_feed(
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
            limit,
            fallback_source="Times of India",
            max_age_hours=24.0,
        )
        arts += self._parse_feed(
            "https://www.thehindu.com/news/national/feeder/default.rss",
            limit,
            fallback_source="The Hindu",
            max_age_hours=24.0,
        )
        arts += self._parse_feed(
            "https://indianexpress.com/feed/",
            limit,
            fallback_source="Indian Express",
            max_age_hours=24.0,
        )
        return self._dedupe_rank(arts, limit)

    def get_top_indian_culture_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time news on Indian culture, heritage, festivals, temples, and traditions from last 24h."""
        query = "when:24h (Indian culture OR Indian heritage OR Indian festivals OR ancient temples OR Indian art OR Ayurveda OR classical dance OR Varanasi OR Ayodhya)"
        encoded = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        arts = self._parse_feed(feed_url, limit * 2, fallback_source="Culture Wire", max_age_hours=24.0)
        if len(arts) < limit:
            # Broader 48h search if strict 24h is sparse for culture
            fallback_q = urllib.parse.quote("Indian culture OR Indian festivals OR ancient temples OR Indian art OR Ayurveda")
            arts += self._parse_feed(f"https://news.google.com/rss/search?q={fallback_q}&hl=en-IN&gl=IN&ceid=IN:en", limit, fallback_source="Culture Wire", max_age_hours=48.0)
        return self._dedupe_rank(arts, limit)

    def get_top_india_tech_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time news on ISRO, Indian space missions, startups, and Digital India from last 24h."""
        query = "when:24h (ISRO OR Indian space mission OR Digital India OR Indian tech startup OR UPI OR semiconductor India OR AI India)"
        encoded = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        return self._dedupe_rank(self._parse_feed(feed_url, limit * 2, fallback_source="India Tech Wire", max_age_hours=24.0), limit)

    def get_top_indian_politics_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch real-time news on Indian politics, Parliament, elections, policies, and governance from last 24h."""
        query = "when:24h (Indian politics OR Indian elections OR Parliament of India OR Lok Sabha OR Rajya Sabha OR Election Commission OR Indian government policy OR Supreme Court India)"
        encoded = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        arts = self._parse_feed(feed_url, limit * 2, fallback_source="Indian Politics Wire", max_age_hours=24.0)
        if len(arts) < limit:
            arts += self._parse_feed("https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms", limit, fallback_source="TOI Politics", max_age_hours=24.0)
        return self._dedupe_rank(arts, limit)

    def get_top_funny_viral_india_news(self, limit: int = 8) -> List[NewsArticle]:
        """Fetch hilarious, quirky, relatable Indian stories, jugaad, and viral moments from the last 24 hours."""
        pooled: List[NewsArticle] = []

        # 1. Google News targeted queries for funny, quirky, viral Indian happenings (24h)
        queries = [
            "when:24h (\"viral\" OR \"bizarre\" OR \"hilarious\" OR \"jugaad\" OR \"meme\" OR \"quirky\") (India OR Delhi OR Bengaluru OR Mumbai OR Gurgaon OR Noida OR Desi OR Indian)",
            "when:24h (site:timesofindia.indiatimes.com/viral-news OR site:ndtv.com/offbeat OR site:hindustantimes.com/trending OR site:indianexpress.com/article/trending-viral-news)",
            "when:24h (\"Zomato\" OR \"Swiggy\" OR \"Blinkit\" OR \"Ola\" OR \"Uber\" OR \"auto driver\" OR \"metro\") (viral OR funny OR debate OR hilarious OR bizarre OR expenses)",
        ]

        for q_text in queries:
            encoded = urllib.parse.quote(q_text)
            feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
            pooled += self._parse_feed(feed_url, limit, fallback_source="Desi Quirky Wire", max_age_hours=24.0)

        # 2. Reddit viral and relatable Indian discussions (last 24h)
        pooled += self._fetch_reddit(["india", "IndiaSpeaks", "delhi", "bangalore", "mumbai"], limit)

        return self._dedupe_rank(pooled, limit)

    def _dedupe_rank(self, articles: List[NewsArticle], limit: int) -> List[NewsArticle]:
        """Deduplicate, rank by recency and relevance, and cap at limit."""
        seen = set()
        ranked: List[tuple] = []
        for art in articles:
            key = _norm_title(art.title)
            if not key or key in seen:
                continue
            seen.add(key)
            # Recency bonus: newer stories score higher (up to +10 for < 6h)
            recency_bonus = 0
            if art.age_hours is not None:
                if art.age_hours <= 3.0:
                    recency_bonus = 10
                elif art.age_hours <= 6.0:
                    recency_bonus = 7
                elif art.age_hours <= 12.0:
                    recency_bonus = 4
                elif art.age_hours <= 24.0:
                    recency_bonus = 2
            score = _india_score(art.title, art.snippet, art.source) + recency_bonus
            ranked.append((score, -(art.age_hours if art.age_hours is not None else 999.0), art))
        # Sort primarily by score desc, then by youngest age desc (smallest hours)
        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [art for _, _, art in ranked[:limit]]

    def _fetch_reddit(self, subreddits: List[str], limit: int) -> List[NewsArticle]:
        articles: List[NewsArticle] = []
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout, follow_redirects=True) as client:
                for sub in subreddits:
                    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
                    r = client.get(url)
                    if r.status_code != 200:
                        continue
                    children = r.json().get("data", {}).get("children", [])
                    for child in children:
                        d = child.get("data") or {}
                        title = (d.get("title") or "").strip()
                        if not title or d.get("stickied"):
                            continue
                        created_utc = d.get("created_utc")
                        dt = _parse_pub_datetime(str(created_utc)) if created_utc else None
                        age_h = None
                        time_lbl = ""
                        if dt:
                            age_h = max(0.0, (now - dt).total_seconds() / 3600.0)
                            if age_h > 24.0:
                                continue
                            time_lbl = _format_relative_time(dt, now)
                        permalink = d.get("permalink") or ""
                        link = d.get("url") or (f"https://www.reddit.com{permalink}" if permalink else "")
                        articles.append(
                            NewsArticle(
                                title=title,
                                link=link,
                                source=f"Reddit r/{sub}",
                                snippet=(d.get("selftext") or "")[:240],
                                published=str(created_utc or ""),
                                age_hours=round(age_h, 1) if age_h is not None else None,
                                time_label=time_lbl,
                            )
                        )
        except Exception as e:
            print(f"Warning: reddit fetch failed: {e}")
        return articles

    def _fetch_mastodon_india(self, limit: int) -> List[NewsArticle]:
        """Public Mastodon hashtag timeline — free Twitter-like posts about India strictly from last 24h."""
        articles: List[NewsArticle] = []
        now = datetime.datetime.now(datetime.timezone.utc)
        tags = ("india", "IndianNews", "breakingnews")
        try:
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout, follow_redirects=True) as client:
                for tag in tags:
                    url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit={min(limit, 12)}"
                    r = client.get(url)
                    if r.status_code != 200:
                        continue
                    for post in r.json():
                        created_at = post.get("created_at") or ""
                        dt = _parse_pub_datetime(created_at)
                        age_h = None
                        time_lbl = ""
                        if dt:
                            age_h = max(0.0, (now - dt).total_seconds() / 3600.0)
                            if age_h > 24.0:
                                continue
                            time_lbl = _format_relative_time(dt, now)
                        text = clean_html(post.get("content") or "")
                        if len(text) < 40:
                            continue
                        title = text.split("\n")[0][:180]
                        if _india_score(title, text) < 3 and tag != "india":
                            continue
                        articles.append(
                            NewsArticle(
                                title=title,
                                link=post.get("url") or "",
                                source="Mastodon",
                                snippet=text[:240],
                                published=created_at,
                                age_hours=round(age_h, 1) if age_h is not None else None,
                                time_label=time_lbl,
                            )
                        )
        except Exception as e:
            print(f"Warning: mastodon fetch failed: {e}")
        return articles

    def _fetch_nitter_india(self, limit: int) -> List[NewsArticle]:
        """Best-effort public Nitter RSS (X/Twitter mirror). Often blocked; ignore failures."""
        hosts = (
            "https://nitter.poast.org",
            "https://nitter.net",
        )
        query = urllib.parse.quote("India OR Bharat min_retweets:20")
        for host in hosts:
            try:
                url = f"{host}/search/rss?f=tweets&q={query}"
                items = self._parse_feed(url, limit, fallback_source="X/Nitter", max_age_hours=24.0)
                if items:
                    return items
            except Exception:
                continue
        return []

    def _fetch_google_trends_trending(self, limit: int = 15) -> List[NewsArticle]:
        """Fetch Google Trends daily trending searches for India with story titles."""
        articles: List[NewsArticle] = []
        now = datetime.datetime.now(datetime.timezone.utc)
        url = "https://trends.google.com/trending/rss?geo=IN"
        try:
            import xml.etree.ElementTree as ET
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout, follow_redirects=True) as client:
                r = client.get(url)
                if r.status_code == 200:
                    root = ET.fromstring(r.content)
                    ns = {"ht": "https://trends.google.com/trending/rss"}
                    for item in root.findall(".//item"):
                        topic = item.find("title").text if item.find("title") is not None else ""
                        pub = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        dt = _parse_pub_datetime(pub)
                        age_h = None
                        time_lbl = ""
                        if dt:
                            age_h = max(0.0, (now - dt).total_seconds() / 3600.0)
                            if age_h > 24.0:
                                continue
                            time_lbl = _format_relative_time(dt, now)

                        news_items = item.findall("ht:news_item", ns)
                        if news_items:
                            for ni in news_items:
                                t = ni.find("ht:news_item_title", ns)
                                u = ni.find("ht:news_item_url", ns)
                                s = ni.find("ht:news_item_source", ns)
                                title = clean_html(t.text if t is not None and t.text else "")
                                link = u.text if u is not None and u.text else ""
                                source = s.text if s is not None and s.text else "Google Trends"
                                if title:
                                    articles.append(
                                        NewsArticle(
                                            title=title,
                                            link=link,
                                            source=f"Trends ({source})",
                                            snippet=f"Trending topic: {topic}",
                                            published=pub,
                                            age_hours=round(age_h, 1) if age_h is not None else None,
                                            time_label=time_lbl,
                                        )
                                    )
                        elif topic:
                            articles.append(
                                NewsArticle(
                                    title=f"Trending in India: {clean_html(topic)}",
                                    link=f"https://trends.google.com/trends/trendingsearches/daily?geo=IN",
                                    source="Google Trends India",
                                    snippet=f"Popular breakout search in India: {topic}",
                                    published=pub,
                                    age_hours=round(age_h, 1) if age_h is not None else None,
                                    time_label=time_lbl,
                                )
                            )
                        if len(articles) >= limit:
                            break
        except Exception as e:
            print(f"Warning: google trends fetch failed: {e}")
        return articles

    def fetch_famous_english_hashtags(self, limit: int = 12) -> list:
        """English hashtags already trending on X, plus English Google Trends topics.

        Instagram has no public hashtag feed, so X (trends24) and Google Trends
        stand in for tags people are actually posting. Non-Latin topics are dropped.
        Each entry is {tag, headline, link, source}.
        """
        entries: list = []
        seen = set()

        def _push(tag: str, headline: str, link: str, source: str) -> None:
            tag = (tag or "").strip()
            key = tag.lower()
            if not tag.startswith("#") or key in seen or not is_english_text(tag):
                return
            headline = (headline or "").strip()
            if not is_english_text(headline):
                headline = tag.lstrip("#")
            seen.add(key)
            entries.append({
                "tag": tag,
                "headline": headline,
                "link": link or "",
                "source": source,
            })

        for label, link in self._fetch_x_trend_labels():
            raw = label.strip()
            if raw.startswith("#"):
                tag = "#" + re.sub(r"[^A-Za-z0-9_]", "", raw[1:])
            else:
                tag = phrase_to_hashtag(raw)
            if not tag:
                continue
            _push(tag, raw.lstrip("#"), link, "X")
            if len(entries) >= limit:
                return entries[:limit]

        # Fill remaining slots with English Google Trends search topics.
        for art in self._fetch_google_trends_topics(limit=20):
            tag = phrase_to_hashtag(art.title.replace("Trending in India:", "").strip())
            _push(tag, art.title, art.link, art.source or "Google Trends")
            if len(entries) >= limit:
                break
        return entries[:limit]

    def _fetch_x_trend_labels(self) -> list:
        """Ordered (label, search_url) pairs from the public India X trends page."""
        url = "https://trends24.in/india/"
        found = []
        try:
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout, follow_redirects=True) as client:
                r = client.get(url)
                if r.status_code != 200:
                    return []
            for href, text in re.findall(
                r'href="(https://twitter\.com/search\?q=[^"]+)"[^>]*>([^<]+)',
                r.text,
            ):
                label = html.unescape(text).strip()
                if not label or not is_english_text(label):
                    continue
                found.append((label, html.unescape(href)))
        except Exception as e:
            print(f"Warning: X trends fetch failed: {e}")
        # Preserve order, drop duplicates.
        out, seen = [], set()
        for label, link in found:
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((label, link))
        # Actual #hashtags first — those are the names already used on X.
        out.sort(key=lambda pair: (0 if pair[0].startswith("#") else 1))
        return out

    def _fetch_google_trends_topics(self, limit: int = 15) -> List[NewsArticle]:
        """English-only Google Trends search topics (the query, not a regional headline)."""
        articles: List[NewsArticle] = []
        url = "https://trends.google.com/trending/rss?geo=IN"
        try:
            import xml.etree.ElementTree as ET
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout, follow_redirects=True) as client:
                r = client.get(url)
                if r.status_code != 200:
                    return []
            root = ET.fromstring(r.content)
            ns = {"ht": "https://trends.google.com/trending/rss"}
            for item in root.findall(".//item"):
                topic = item.findtext("title") or ""
                topic = clean_html(topic).strip()
                if not is_english_text(topic):
                    continue
                news_title = ""
                news_link = ""
                news_source = "Google Trends"
                for ni in item.findall("ht:news_item", ns):
                    title_el = ni.find("ht:news_item_title", ns)
                    url_el = ni.find("ht:news_item_url", ns)
                    src_el = ni.find("ht:news_item_source", ns)
                    candidate = clean_html(title_el.text if title_el is not None and title_el.text else "")
                    if is_english_text(candidate):
                        news_title = candidate
                        news_link = url_el.text if url_el is not None and url_el.text else ""
                        news_source = src_el.text if src_el is not None and src_el.text else "Google Trends"
                        break
                articles.append(
                    NewsArticle(
                        title=news_title or f"Trending in India: {topic}",
                        link=news_link or "https://trends.google.com/trends/trendingsearches/daily?geo=IN",
                        source=f"Google Trends ({news_source})" if news_title else "Google Trends",
                        snippet=f"Popular search: {topic}",
                    )
                )
                if len(articles) >= limit:
                    break
        except Exception as e:
            print(f"Warning: english google trends fetch failed: {e}")
        return articles

    def get_india_trending(self, limit: int = 8) -> List[NewsArticle]:
        """Top India-concern trending stories strictly from last 24 hours."""
        pooled: List[NewsArticle] = []
        # 1. Google Trends live breakout topics
        pooled += self._fetch_google_trends_trending(limit=15)
        # 2. Google News India trending 24h
        pooled += self._parse_feed(
            "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
            12,
            fallback_source="Google News India",
            max_age_hours=24.0,
        )
        # 3. Top India publications (TOI, The Hindu, Indian Express)
        pooled += self._parse_feed(
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
            10,
            fallback_source="Times of India",
            max_age_hours=24.0,
        )
        pooled += self._parse_feed(
            "https://www.thehindu.com/news/national/feeder/default.rss",
            10,
            fallback_source="The Hindu",
            max_age_hours=24.0,
        )
        # 4. Quirky, viral and humorous India stories (last 24h)
        pooled += self.get_top_funny_viral_india_news(limit=10)
        # 5. Reddit & social buzz (last 24h)
        pooled += self._fetch_reddit(["india", "IndiaNews", "IndiaSpeaks", "delhi", "bangalore"], 12)
        world_reddit = self._fetch_reddit(["worldnews"], 12)
        pooled += [a for a in world_reddit if _india_score(a.title, a.snippet) >= 3]
        pooled += self._fetch_mastodon_india(8)
        pooled += self._fetch_nitter_india(8)
        return self._dedupe_rank(pooled, limit)


news_fetcher = NewsFetcher()

