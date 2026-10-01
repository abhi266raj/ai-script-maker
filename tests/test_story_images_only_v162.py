"""Issue #86 (v1.6.2): image fetcher grabs site chrome — fetch only story images.

Pins:
- in-article extraction is scoped to the story body; images under
  <header>/<nav>/<footer>/<aside> (site chrome) are excluded;
- the article's OWN <header> (hero area) is still scanned;
- og:image / twitter:image / JSON-LD are untouched by scoping;
- <amp-img> is parsed like <img>;
- _JUNK_RE's ads/ no longer kills /uploads/ but still drops real ad paths;
- no identifiable article body -> whole-page fallback WITH an honest
  scope_report["scoped"] == False (never silently zero);
- refresh_images surfaces that fallback in its outcome note.
"""

import pytest

from tools.story_link import (
    extract_story_images,
    extract_story_images_with_alt,
)


BASE = "https://publisher.example/story"


def _urls(pairs):
    return [u for u, _ in pairs]


# ---------------------------------------------------------------------------
# Article scoping: site chrome excluded, story images kept
# ---------------------------------------------------------------------------

_CHROME_HTML = """<html><head></head><body>
<header><img src="https://cdn.example/photos/site-masthead.jpg" alt="masthead photo"></header>
<nav><img src="https://cdn.example/photos/nav-menu.jpg" alt="navigation menu"></nav>
<article>
  <img src="https://cdn.example/wp-content/uploads/2026/10/metro.jpg" alt="metro construction site">
  <img src="https://cdn.example/photos/crowd.jpg" alt="crowd at station">
</article>
<aside><figure><img src="https://cdn.example/photos/related-thumb.jpg" alt="related story"></figure></aside>
<footer><img src="https://cdn.example/photos/footer-badge.jpg" alt="footer badge"></footer>
</body></html>"""


def test_site_chrome_excluded_article_images_kept():
    rep = {}
    pairs = extract_story_images_with_alt(_CHROME_HTML, BASE, limit=10,
                                          scope_report=rep)
    urls = _urls(pairs)
    assert rep["scoped"] is True
    assert "https://cdn.example/wp-content/uploads/2026/10/metro.jpg" in urls
    assert "https://cdn.example/photos/crowd.jpg" in urls
    # Site chrome — none of these URLs trip the junk filter, so only the
    # article scoping can exclude them.
    assert "https://cdn.example/photos/site-masthead.jpg" not in urls
    assert "https://cdn.example/photos/nav-menu.jpg" not in urls
    assert "https://cdn.example/photos/related-thumb.jpg" not in urls
    assert "https://cdn.example/photos/footer-badge.jpg" not in urls


def test_article_own_header_hero_is_kept():
    html = """<html><body>
<header><img src="https://cdn.example/photos/site-masthead.jpg" alt="masthead photo"></header>
<article><header><img src="https://cdn.example/photos/hero.jpg" alt="story hero image"></header>
<p>Body copy.</p>
<img src="https://cdn.example/photos/body.jpg" alt="body photo">
</article></body></html>"""
    urls = _urls(extract_story_images_with_alt(html, BASE, limit=10))
    # The article's own <header> is story content (hero area), not site chrome.
    assert "https://cdn.example/photos/hero.jpg" in urls
    assert "https://cdn.example/photos/body.jpg" in urls
    assert "https://cdn.example/photos/site-masthead.jpg" not in urls


def test_role_main_and_entry_content_scoping():
    for body_open in ('<div role="main">', '<div class="entry-content">'):
        html = (f"<html><body>{body_open}"
                '<img src="https://cdn.example/photos/story.jpg" alt="story photo">'
                "</div>"
                '<header><img src="https://cdn.example/photos/site.jpg" alt="site photo"></header>'
                "</body></html>")
        rep = {}
        urls = _urls(extract_story_images_with_alt(html, BASE, limit=10,
                                                   scope_report=rep))
        assert rep["scoped"] is True
        assert "https://cdn.example/photos/story.jpg" in urls
        assert "https://cdn.example/photos/site.jpg" not in urls


def test_page_meta_untouched_by_scoping():
    html = """<html><head>
<meta property="og:image" content="https://cdn.example/og-hero.jpg">
<meta name="twitter:image" content="https://cdn.example/tw-hero.jpg">
<script type="application/ld+json">{"image": "https://cdn.example/ld-hero.jpg"}</script>
</head><body>
<header><img src="https://cdn.example/photos/site.jpg" alt="site photo"></header>
<article><img src="https://cdn.example/photos/story.jpg" alt="story photo"></article>
</body></html>"""
    urls = _urls(extract_story_images_with_alt(html, BASE, limit=10))
    # Publisher-declared story images are kept as-is; site chrome still out.
    assert "https://cdn.example/og-hero.jpg" in urls
    assert "https://cdn.example/tw-hero.jpg" in urls
    assert "https://cdn.example/ld-hero.jpg" in urls
    assert "https://cdn.example/photos/story.jpg" in urls
    assert "https://cdn.example/photos/site.jpg" not in urls


# ---------------------------------------------------------------------------
# AMP: <amp-img> parsed like <img>
# ---------------------------------------------------------------------------

def test_amp_img_parsed():
    html = """<html><body><article>
<amp-img src="https://cdn.example/photos/amp-photo.jpg" alt="amp photo"></amp-img>
</article></body></html>"""
    urls = _urls(extract_story_images_with_alt(html, BASE, limit=10))
    assert "https://cdn.example/photos/amp-photo.jpg" in urls


def test_amp_img_in_chrome_still_excluded():
    html = """<html><body>
<header><amp-img src="https://cdn.example/photos/site.jpg" alt="site photo"></amp-img></header>
<article><amp-img src="https://cdn.example/photos/story.jpg" alt="story photo"></amp-img></article>
</body></html>"""
    urls = _urls(extract_story_images_with_alt(html, BASE, limit=10))
    assert "https://cdn.example/photos/story.jpg" in urls
    assert "https://cdn.example/photos/site.jpg" not in urls


# ---------------------------------------------------------------------------
# _JUNK_RE: /uploads/ kept, ad paths dropped (issue #86 / india.com)
# ---------------------------------------------------------------------------

def _single_img_url(url):
    html = (f'<html><body><article><img src="{url}" alt="photo"></article>'
            "</body></html>")
    return _urls(extract_story_images_with_alt(html, BASE, limit=10))


@pytest.mark.parametrize("url", [
    "https://static.india.com/wp-content/uploads/2026/10/metro.jpg",
    "https://cdn.example/wp-content/uploads/photo.jpg",
    "https://example.com/downloads/guide.jpg",
    "https://example.com/photos/leads-meeting.jpg",
])
def test_junk_filter_keeps_uploads_and_legit_words(url):
    assert _single_img_url(url) == [url]


@pytest.mark.parametrize("url", [
    "https://example.com/ads/banner1.jpg",
    "https://example.com/my-ads/skyscraper.png",
    "https://example.com/banners/ads/leaderboard.jpg",
    "https://example.com/_ads/promo.jpg",
])
def test_junk_filter_still_drops_ad_paths(url):
    # The user explicitly does not want ad images.
    assert _single_img_url(url) == []


# ---------------------------------------------------------------------------
# Fallback: no article body -> whole-page scan + honest report (fail loudly)
# ---------------------------------------------------------------------------

def test_fallback_scans_page_and_reports_unscoped():
    html = """<html><body>
<header><img src="https://cdn.example/photos/site-header.jpg" alt="site header photo"></header>
<div class="random-wrap"><img src="https://cdn.example/photos/content.jpg" alt="content photo"></div>
</body></html>"""
    rep = {}
    urls = _urls(extract_story_images_with_alt(html, BASE, limit=10,
                                               scope_report=rep))
    # Honest fallback: not silent, not zero — but flagged.
    assert rep["scoped"] is False
    assert "https://cdn.example/photos/content.jpg" in urls
    # Even in fallback, site chrome is excluded by ancestor.
    assert "https://cdn.example/photos/site-header.jpg" not in urls


def test_scope_report_defaults_to_no_report():
    # Backward compatible: callers that don't pass scope_report are unaffected.
    urls = _urls(extract_story_images_with_alt(_CHROME_HTML, BASE, limit=10))
    assert "https://cdn.example/wp-content/uploads/2026/10/metro.jpg" in urls
    assert extract_story_images(_CHROME_HTML, BASE, limit=10) == urls


# ---------------------------------------------------------------------------
# refresh_images: the fallback reaches the outcome note (issue #86)
# ---------------------------------------------------------------------------

def test_refresh_images_notes_unscoped_pages(monkeypatch):
    import story_library as lib

    story = {"meta": {"image_urls": [], "image_hashes": [],
                      "image_phashes": [], "source_topic": "metro"}}
    monkeypatch.setattr(lib, "load_story", lambda sid: story)

    def _fake_fetch(story_obj, topic, tries=3, report=None):
        if report is not None:
            report["unscoped_pages"] = 2
        return []

    monkeypatch.setattr(lib, "_fetch_images_for_story", _fake_fetch)
    monkeypatch.setattr(
        lib, "_merge_story_images",
        lambda e, eh, eph, found: ([], [], [], {
            "added": 0, "rejected_alt": 0, "removed_existing_dupes": 0,
            "dup_url": 0, "dup_content": 0, "dup_visual": 0}),
    )
    changed, note = lib.refresh_images("s1", "metro")
    assert "2 article page(s) had no identifiable story body" in note
    assert "scanned page-wide" in note


def test_refresh_images_no_note_when_all_scoped(monkeypatch):
    import story_library as lib

    story = {"meta": {"image_urls": [], "image_hashes": [],
                      "image_phashes": [], "source_topic": "metro"}}
    monkeypatch.setattr(lib, "load_story", lambda sid: story)

    def _fake_fetch(story_obj, topic, tries=3, report=None):
        if report is not None:
            report["unscoped_pages"] = 0
        return []

    monkeypatch.setattr(lib, "_fetch_images_for_story", _fake_fetch)
    monkeypatch.setattr(
        lib, "_merge_story_images",
        lambda e, eh, eph, found: ([], [], [], {
            "added": 0, "rejected_alt": 0, "removed_existing_dupes": 0,
            "dup_url": 0, "dup_content": 0, "dup_visual": 0}),
    )
    changed, note = lib.refresh_images("s1", "metro")
    assert "no identifiable story body" not in note
