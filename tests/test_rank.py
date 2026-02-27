"""Tests for src/rank.py — scoring, filtering, and ranking."""

from datetime import datetime, timezone, timedelta

from normalize import normalize_item
from rank import score_items, filter_items, rank_and_cap


class TestScoreItems:
    def test_high_priority_keyword_match_scores_higher(self, make_item, sample_topics):
        items = [normalize_item(make_item(title="New AI breakthrough in LLM research"))]
        score_items(items, sample_topics)
        assert items[0]["relevance_score"] > 0
        assert "AI engineering" in items[0]["topics_matched"]

    def test_no_match_scores_zero(self, make_item, sample_topics):
        items = [normalize_item(make_item(
            title="Best chocolate cake recipe",
            summary="Baking tips for beginners.",
            hours_ago=24,
        ))]
        score_items(items, sample_topics)
        assert items[0]["relevance_score"] == 0.0
        assert items[0]["topics_matched"] == []

    def test_medium_priority_scores_lower_than_high(self, make_item, sample_topics):
        high_item = normalize_item(make_item(title="AI and LLM advances"))
        medium_item = normalize_item(make_item(
            title="Cursor IDE update",
            url="https://example.com/cursor",
        ))
        score_items([high_item, medium_item], sample_topics)
        assert high_item["relevance_score"] > medium_item["relevance_score"]

    def test_recency_boost_for_fresh_items(self, make_item, sample_topics):
        fresh = normalize_item(make_item(title="AI news", hours_ago=1))
        stale = normalize_item(make_item(
            title="AI news",
            url="https://example.com/stale",
            hours_ago=24,
        ))
        score_items([fresh, stale], sample_topics)
        assert fresh["relevance_score"] > stale["relevance_score"]

    def test_engagement_boost_for_high_points(self, make_item, sample_topics):
        popular = normalize_item(make_item(title="AI tool", points=600))
        unpopular = normalize_item(make_item(
            title="AI tool",
            url="https://example.com/unpopular",
            points=10,
        ))
        score_items([popular, unpopular], sample_topics)
        assert popular["relevance_score"] > unpopular["relevance_score"]

    def test_future_dated_items_get_no_recency_boost(self, make_item, sample_topics):
        """Regression: feeds with future pub dates inflated scores via negative age."""
        future_item = normalize_item(make_item(
            title="Hip replacement survival results",
            summary="Modern hip replacements last decades.",
            hours_ago=-12,
        ))
        score_items([future_item], sample_topics)
        assert future_item["relevance_score"] == 0.0
        assert future_item["topics_matched"] == []

    def test_multiple_topic_matches_accumulate(self, make_item, sample_topics):
        multi = normalize_item(make_item(
            title="AI LLM tool with Cursor and Copilot integration",
        ))
        single = normalize_item(make_item(
            title="AI breakthrough",
            url="https://example.com/single",
        ))
        score_items([multi, single], sample_topics)
        assert multi["relevance_score"] > single["relevance_score"]
        assert len(multi["topics_matched"]) == 2


class TestFilterItems:
    def test_excludes_by_keyword(self, make_item):
        items = [
            normalize_item(make_item(title="AI news")),
            normalize_item(make_item(
                title="Crypto and blockchain update",
                url="https://example.com/crypto",
            )),
        ]
        result = filter_items(items, {"exclude_keywords": ["crypto"]})
        assert len(result) == 1
        assert result[0]["title"] == "AI news"

    def test_excludes_old_items(self, make_item):
        fresh = normalize_item(make_item(title="Fresh", hours_ago=2))
        old = normalize_item(make_item(
            title="Old",
            url="https://example.com/old",
            hours_ago=72,
        ))
        result = filter_items([fresh, old], {"max_age_hours": 48})
        assert len(result) == 1
        assert result[0]["title"] == "Fresh"

    def test_excludes_below_min_relevance(self, make_item, sample_topics):
        relevant = normalize_item(make_item(title="AI and LLM research", hours_ago=24))
        irrelevant = normalize_item(make_item(
            title="Gardening tips",
            url="https://example.com/garden",
            summary="How to grow tomatoes in your backyard.",
            hours_ago=24,
        ))
        score_items([relevant, irrelevant], sample_topics)
        result = filter_items([relevant, irrelevant], {"min_relevance": 0.3})
        assert len(result) == 1
        assert result[0]["title"] == "AI and LLM research"

    def test_exclude_keyword_is_case_insensitive(self, make_item):
        items = [normalize_item(make_item(title="BLOCKCHAIN revolution"))]
        result = filter_items(items, {"exclude_keywords": ["blockchain"]})
        assert len(result) == 0

    def test_empty_filters_pass_everything(self, make_item):
        items = [normalize_item(make_item(title="Anything"))]
        result = filter_items(items, {})
        assert len(result) == 1


class TestRankAndCap:
    def test_caps_to_max_items(self, make_item):
        items = [
            normalize_item(make_item(
                title=f"Item {i}",
                url=f"https://example.com/{i}",
            ))
            for i in range(20)
        ]
        result = rank_and_cap(items, max_items=5)
        assert len(result) == 5

    def test_sorts_by_relevance_descending(self, make_item, sample_topics):
        low = normalize_item(make_item(title="Gardening tips", url="https://example.com/low"))
        high = normalize_item(make_item(title="AI LLM machine learning", url="https://example.com/high"))
        score_items([low, high], sample_topics)
        result = rank_and_cap([low, high], max_items=10)
        assert result[0]["title"] == "AI LLM machine learning"

    def test_source_diversity_caps_per_type(self, make_item):
        hn_items = [
            normalize_item(make_item(
                title=f"HN {i}",
                url=f"https://example.com/hn/{i}",
                source_type="hn",
            ))
            for i in range(15)
        ]
        rss_items = [
            normalize_item(make_item(
                title=f"RSS {i}",
                url=f"https://example.com/rss/{i}",
                source_type="rss",
            ))
            for i in range(15)
        ]
        result = rank_and_cap(hn_items + rss_items, max_items=30)
        hn_count = sum(1 for item in result if item["source_type"] == "hn")
        rss_count = sum(1 for item in result if item["source_type"] == "rss")
        assert hn_count <= 10
        assert rss_count <= 10

    def test_fewer_items_than_cap_returns_all(self, make_item):
        items = [normalize_item(make_item(title="Only one"))]
        result = rank_and_cap(items, max_items=30)
        assert len(result) == 1
