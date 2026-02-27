"""Tests for src/render.py — text helpers and section building."""

from datetime import datetime, timezone, timedelta

from normalize import normalize_item
from render import first_sentences, time_ago, build_sections


class TestFirstSentences:
    def test_extracts_two_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        result = first_sentences(text, n=2)
        assert "First sentence." in result
        assert "Second sentence." in result
        assert "Third" not in result

    def test_handles_single_sentence(self):
        result = first_sentences("Only one sentence here.", n=2)
        assert result == "Only one sentence here."

    def test_truncates_at_max_chars(self):
        long_text = "A" * 400 + ". Second."
        result = first_sentences(long_text, n=2, max_chars=100)
        assert len(result) <= 101  # +1 for the ellipsis character

    def test_empty_string_returns_empty(self):
        assert first_sentences("") == ""
        assert first_sentences(None) == ""

    def test_strips_whitespace(self):
        result = first_sentences("  Padded sentence.  Another one.  ", n=2)
        assert result.startswith("Padded")


class TestTimeAgo:
    def test_just_now(self):
        dt = datetime.now(timezone.utc) - timedelta(seconds=30)
        assert time_ago(dt) == "just now"

    def test_minutes_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(minutes=45)
        assert time_ago(dt) == "45m ago"

    def test_hours_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=3)
        assert time_ago(dt) == "3h ago"

    def test_days_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(days=2)
        assert time_ago(dt) == "2d ago"

    def test_none_returns_empty(self):
        assert time_ago(None) == ""


class TestBuildSections:
    def test_groups_hn_items_into_section(self, make_item):
        items = [
            normalize_item(make_item(title="HN Post 1", source_type="hn", url="https://hn.com/1", points=50)),
            normalize_item(make_item(title="HN Post 2", source_type="hn", url="https://hn.com/2", points=30)),
        ]
        sections = build_sections(items)
        hn_sections = [s for s in sections if s["source_type"] == "hn"]
        assert len(hn_sections) == 1
        assert hn_sections[0]["name"] == "Hacker News"
        assert len(hn_sections[0]["entries"]) == 2

    def test_groups_reddit_items_into_section(self, make_item):
        items = [
            normalize_item(make_item(title="Reddit Post", source_type="reddit", url="https://reddit.com/1")),
        ]
        sections = build_sections(items)
        reddit_sections = [s for s in sections if s["source_type"] == "reddit"]
        assert len(reddit_sections) == 1
        assert reddit_sections[0]["name"] == "Reddit"

    def test_social_items_combined(self, make_item):
        items = [
            normalize_item(make_item(title="Tweet", source_type="twitter_gnews", url="https://x.com/1")),
            normalize_item(make_item(title="Skeet", source_type="bluesky", url="https://bsky.app/1")),
        ]
        sections = build_sections(items)
        social = [s for s in sections if s["id"] == "social"]
        assert len(social) == 1
        assert len(social[0]["entries"]) == 2

    def test_empty_items_returns_empty_sections(self):
        assert build_sections([]) == []

    def test_rss_items_grouped_by_section_tag(self, make_item):
        items = [
            normalize_item(make_item(
                title="TC Article", source_type="rss",
                section="TechCrunch", url="https://tc.com/1",
            )),
            normalize_item(make_item(
                title="Blog Post", source_type="rss",
                section="Blogs", url="https://blog.com/1",
            )),
        ]
        sections = build_sections(items)
        rss_sections = [s for s in sections if s["source_type"] == "rss"]
        assert len(rss_sections) == 2
        section_names = [s["name"] for s in rss_sections]
        assert "TechCrunch" in section_names
        assert "Blogs" in section_names
