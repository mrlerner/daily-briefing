"""Tests for src/normalize.py — item normalization and deduplication."""

from normalize import normalize_item, deduplicate


class TestNormalizeItem:
    def test_fills_defaults_for_empty_input(self):
        result = normalize_item({})
        assert result["title"] == ""
        assert result["source"] == "Unknown"
        assert result["source_type"] == "unknown"
        assert result["relevance_score"] == 0.0
        assert result["topics_matched"] == []

    def test_preserves_existing_fields(self):
        raw = {
            "title": "  Anthropic Ships Claude 4  ",
            "url": "https://anthropic.com/claude-4",
            "source": "Anthropic Blog",
            "source_type": "rss",
            "summary": "A big release.",
        }
        result = normalize_item(raw)
        assert result["title"] == "Anthropic Ships Claude 4"
        assert result["url"] == "https://anthropic.com/claude-4"
        assert result["source"] == "Anthropic Blog"

    def test_generates_id_from_url_when_missing(self):
        item_a = normalize_item({"url": "https://example.com/a"})
        item_b = normalize_item({"url": "https://example.com/b"})
        assert item_a["id"] != item_b["id"]
        assert len(item_a["id"]) == 16

    def test_uses_existing_id_when_present(self):
        result = normalize_item({"id": "custom-123", "url": "https://example.com"})
        assert result["id"] == "custom-123"

    def test_preserves_platform_metadata(self):
        raw = {
            "points": 342,
            "score": 150,
            "comments": 47,
            "author": "karpathy",
            "subreddit": "MachineLearning",
        }
        result = normalize_item(raw)
        assert result["points"] == 342
        assert result["score"] == 150
        assert result["comments"] == 47
        assert result["author"] == "karpathy"
        assert result["subreddit"] == "MachineLearning"


class TestDeduplicate:
    def test_removes_duplicate_urls(self):
        items = [
            {"url": "https://example.com/a", "title": "First"},
            {"url": "https://example.com/a", "title": "Duplicate"},
            {"url": "https://example.com/b", "title": "Second"},
        ]
        result = deduplicate(items)
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Second"

    def test_keeps_first_occurrence(self):
        items = [
            {"url": "https://example.com/x", "title": "Original"},
            {"url": "https://example.com/x", "title": "Copy"},
        ]
        result = deduplicate(items)
        assert result[0]["title"] == "Original"

    def test_empty_urls_are_skipped(self):
        items = [
            {"url": "", "title": "No URL 1"},
            {"url": "", "title": "No URL 2"},
            {"url": "https://example.com/a", "title": "Has URL"},
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0]["title"] == "Has URL"

    def test_empty_list_returns_empty(self):
        assert deduplicate([]) == []
