"""Unit tests for 24-Hour Real-Time News Fetcher and Recency Filtering."""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from core.models import NewsArticle
from tools.news_fetcher import (
    _parse_pub_datetime,
    _format_relative_time,
    news_fetcher,
)


class TestRealtimeNewsFilter(unittest.TestCase):
    """Verify that articles older than 24 hours are excluded and recency tags are generated."""

    def test_parse_pub_datetime_rfc2822(self):
        """RFC 2822 string parse test."""
        dt_str = "Wed, 23 Sep 2026 06:00:00 GMT"
        parsed = _parse_pub_datetime(dt_str)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 9)
        self.assertEqual(parsed.day, 23)

    def test_parse_pub_datetime_iso8601(self):
        """ISO 8601 string parse test."""
        dt_str = "2026-09-23T08:30:00Z"
        parsed = _parse_pub_datetime(dt_str)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.hour, 8)
        self.assertEqual(parsed.minute, 30)

    def test_parse_pub_datetime_epoch(self):
        """Epoch timestamp float parse test."""
        now = datetime.now(timezone.utc)
        epoch = now.timestamp()
        parsed = _parse_pub_datetime(epoch)
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed.timestamp(), epoch, delta=1)

    def test_format_relative_time(self):
        """Ensure human-readable relative time labels (e.g. 15m ago, 2h ago, 1d ago)."""
        now = datetime.now(timezone.utc)
        
        # 30 mins ago
        t_30m = now - timedelta(minutes=30)
        self.assertEqual(_format_relative_time(t_30m, now), "30m ago")
        
        # 3 hours ago
        t_3h = now - timedelta(hours=3)
        self.assertEqual(_format_relative_time(t_3h, now), "3h ago")
        
        # 28 hours ago
        t_28h = now - timedelta(hours=28)
        self.assertEqual(_format_relative_time(t_28h, now), "1d ago")

    def test_parse_feed_strict_24h_cutoff(self):
        """Verify _parse_feed filters out items published more than 24 hours ago."""
        now = datetime.now(timezone.utc)
        recent_dt = (now - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        old_dt = (now - timedelta(hours=36)).strftime("%a, %d %b %Y %H:%M:%S GMT")

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Recent Breaking News - ISRO Mission</title>
                    <link>https://example.com/recent</link>
                    <pubDate>{recent_dt}</pubDate>
                    <description>Recent news content</description>
                </item>
                <item>
                    <title>Old Outdated News - Ancient Story</title>
                    <link>https://example.com/old</link>
                    <pubDate>{old_dt}</pubDate>
                    <description>Old news content</description>
                </item>
            </channel>
        </rss>
        """

        articles = news_fetcher._parse_feed(xml_data, limit=5, fallback_source="TestFeed", max_age_hours=24.0)

        # Only the recent article should survive
        self.assertEqual(len(articles), 1)
        self.assertIn("Recent Breaking News", articles[0].title)
        self.assertIsNotNone(articles[0].age_hours)
        self.assertLessEqual(articles[0].age_hours, 24.0)
        self.assertIn("ago", articles[0].time_label)

    def test_dedupe_rank_recency_bonus(self):
        """Articles published more recently should receive a score boost."""
        art_fresh = NewsArticle(
            title="Fresh Breaking Launch",
            link="https://example.com/fresh",
            snippet="Spacecraft launched just now.",
            source="FeedA",
            age_hours=1.5,
            time_label="1h ago"
        )
        art_older = NewsArticle(
            title="Older Tech Report",
            link="https://example.com/older",
            snippet="Tech report from earlier.",
            source="FeedB",
            age_hours=20.0,
            time_label="20h ago"
        )

        ranked = news_fetcher._dedupe_rank([art_older, art_fresh], limit=2)
        # The 1.5h article should be ranked first due to recency bonus
        self.assertEqual(ranked[0].title, "Fresh Breaking Launch")
        self.assertEqual(ranked[1].title, "Older Tech Report")

    def test_get_top_funny_viral_india_news(self):
        """Verify funny viral news fetcher returns articles with recency within 24h limit."""
        results = news_fetcher.get_top_funny_viral_india_news(limit=6)
        self.assertIsInstance(results, list)
        for art in results:
            self.assertTrue(bool(art.title))
            if art.age_hours is not None:
                self.assertLessEqual(art.age_hours, 24.5)


if __name__ == "__main__":
    unittest.main()
