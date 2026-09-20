"""Live India news: Google News/Trends, Reddit, Mastodon (free public APIs)."""

import re
import urllib.parse
from typing import List, Optional
import feedparser
import httpx
from bs4 import BeautifulSoup
from core.models import NewsArticle

_HTTP_HEADERS = {
    "User-Agent": "HindiReelStudio/1.0 (news desk; +https://local)",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}

_INDIA_TERMS = (
    "india", "indian", "bharat", "delhi", "mumbai", "modi", "isro", "rupee",
    "kashmir", "lok sabha", "bjp", "congress", "upi", "gaganyaan", "varanasi",
    "hindi", "sc india", "supreme court", "rbi", "nse", "sensex", "pakistan",
    "china", "border", "ladakh", "punjab", "tamil", "bengal", "hyderabad",
)


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()[:80]


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
    """Fetches real-time, verified live news articles from global wire feeds."""

    def __init__(self, max_articles: int = 5):
        self.max_articles = max_articles
        self._timeout = 8.0

    def _parse_feed(self, feed_url: str, limit: int, fallback_source: str = "Live Wire") -> List[NewsArticle]:
        """Helper to parse an RSS feed into clean NewsArticle objects."""
        articles: List[NewsArticle] = []
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:limit]:
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

                summary_raw = getattr(entry, "summary", "")
                snippet = clean_html(summary_raw)

                articles.append(
                    NewsArticle(
                        title=title,
                        link=link,
                        source=source,
                        snippet=snippet,
                        published=published,
                    )
                )
        except Exception as e:
            print(f"Warning: news feed parsing failed for {feed_url}: {e}")
        return articles

    def search_news(self, query: str, limit: Optional[int] = None) -> List[NewsArticle]:
        """Search Google News RSS for any real-time query."""
        n = limit or self.max_articles
        encoded_query = urllib.parse.quote(query.strip())
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        return self._parse_feed(feed_url, n, fallback_source="News Wire")

    def get_top_world_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time top global world headlines."""
        feed_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        return self._parse_feed(feed_url, limit, fallback_source="World Wire")

    def get_top_tech_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time technology and AI headlines."""
        feed_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"
        return self._parse_feed(feed_url, limit, fallback_source="Tech Wire")

    def get_top_business_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time business and finance headlines."""
        feed_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"
        return self._parse_feed(feed_url, limit, fallback_source="Business Wire")

    def get_top_india_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time top headlines across India."""
        feed_url = "https://news.google.com/rss/headlines/section/geo/India?hl=en-IN&gl=IN&ceid=IN:en"
        return self._parse_feed(feed_url, limit, fallback_source="India Wire")

    def get_top_indian_culture_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time news on Indian culture, heritage, festivals, temples, and traditions."""
        query = "Indian culture OR Indian heritage OR Indian festivals OR ancient temples OR Indian art OR Ayurveda OR classical dance"
        encoded = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        return self._parse_feed(feed_url, limit, fallback_source="Culture Wire")

    def get_top_india_tech_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time news on ISRO, Indian space missions, startups, and Digital India."""
        query = "ISRO OR Indian space mission OR Digital India OR Indian tech startup OR UPI"
        encoded = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        return self._parse_feed(feed_url, limit, fallback_source="India Tech Wire")

    def get_top_indian_politics_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetch real-time news on Indian politics, Parliament, elections, policies, and governance."""
        query = "Indian politics OR Indian elections OR Parliament of India OR Lok Sabha OR Rajya Sabha OR Election Commission OR Indian government policy"
        encoded = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        return self._parse_feed(feed_url, limit, fallback_source="Indian Politics Wire")

    def _dedupe_rank(self, articles: List[NewsArticle], limit: int) -> List[NewsArticle]:
        seen = set()
        ranked: List[tuple] = []
        for art in articles:
            key = _norm_title(art.title)
            if not key or key in seen:
                continue
            seen.add(key)
            ranked.append((_india_score(art.title, art.snippet, art.source), art))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [art for _, art in ranked[:limit]]

    def _fetch_reddit(self, subreddits: List[str], limit: int) -> List[NewsArticle]:
        articles: List[NewsArticle] = []
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
                        permalink = d.get("permalink") or ""
                        link = d.get("url") or (f"https://www.reddit.com{permalink}" if permalink else "")
                        articles.append(
                            NewsArticle(
                                title=title,
                                link=link,
                                source=f"Reddit r/{sub}",
                                snippet=(d.get("selftext") or "")[:240],
                                published=str(d.get("created_utc") or ""),
                            )
                        )
        except Exception as e:
            print(f"Warning: reddit fetch failed: {e}")
        return articles

    def _fetch_mastodon_india(self, limit: int) -> List[NewsArticle]:
        """Public Mastodon hashtag timeline — free Twitter-like posts about India."""
        articles: List[NewsArticle] = []
        tags = ("india", "IndianNews", "breakingnews")
        try:
            with httpx.Client(headers=_HTTP_HEADERS, timeout=self._timeout, follow_redirects=True) as client:
                for tag in tags:
                    url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit={min(limit, 12)}"
                    r = client.get(url)
                    if r.status_code != 200:
                        continue
                    for post in r.json():
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
                                published=post.get("created_at") or "",
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
                items = self._parse_feed(url, limit, fallback_source="X/Nitter")
                if items:
                    return items
            except Exception:
                continue
        return []

    def get_india_trending(self, limit: int = 8) -> List[NewsArticle]:
        """Top India-concern stories: Google News IN, Trends IN, Reddit, Mastodon, Nitter."""
        pooled: List[NewsArticle] = []
        pooled += self._parse_feed(
            "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
            12,
            fallback_source="Google News India",
        )
        pooled += self._parse_feed(
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN",
            10,
            fallback_source="Google Trends India",
        )
        pooled += self._parse_feed(
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
            8,
            fallback_source="Times of India",
        )
        world = self._parse_feed(
            "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
            10,
            fallback_source="World",
        )
        pooled += [a for a in world if _india_score(a.title, a.snippet) >= 3]
        pooled += self._fetch_reddit(["india", "IndiaNews"], 12)
        world_reddit = self._fetch_reddit(["worldnews"], 12)
        pooled += [a for a in world_reddit if _india_score(a.title, a.snippet) >= 3]
        pooled += self._fetch_mastodon_india(8)
        pooled += self._fetch_nitter_india(8)
        return self._dedupe_rank(pooled, limit)


news_fetcher = NewsFetcher()

