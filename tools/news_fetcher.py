"""Live India news: Google News/Trends, Reddit, Mastodon (free public APIs)."""

import re
import urllib.parse
import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional
import feedparser
import httpx
from bs4 import BeautifulSoup
from core.models import NewsArticle

_HTTP_HEADERS = {
    "User-Agent": "HindiReelStudio/1.0 (news desk; +https://local)",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}


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
            feed = feedparser.parse(feed_url)
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

    def search_news(self, query: str, limit: Optional[int] = None) -> List[NewsArticle]:
        """Search Google News RSS with when:24h qualifier for fresh real-time results."""
        n = limit or self.max_articles
        q = f"when:24h {query.strip()}"
        encoded_query = urllib.parse.quote(q)
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        results = self._parse_feed(feed_url, n, fallback_source="News Wire", max_age_hours=24.0)
        if not results:
            # Fallback to standard query without when:24h if too restrictive
            encoded_query = urllib.parse.quote(query.strip())
            feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
            results = self._parse_feed(feed_url, n, fallback_source="News Wire", max_age_hours=48.0)
        return results

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

