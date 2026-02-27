"""Tests for src/config.py — config loading, merging, and discovery."""

import pytest
from config import (
    _merge_configs,
    validate_config,
    discover_user_briefings,
    load_user_briefing,
)


class TestMergeConfigs:
    def test_override_replaces_base_key(self):
        base = {"format": {"max_items": 30}, "delivery": {"time": "07:00"}}
        overrides = {"format": {"max_items": 10}}
        result = _merge_configs(base, overrides)
        assert result["format"]["max_items"] == 10

    def test_extends_key_is_stripped(self):
        base = {"topics": []}
        overrides = {"extends": "ai-engineering", "blocks": []}
        result = _merge_configs(base, overrides)
        assert "extends" not in result
        assert "blocks" in result

    def test_base_keys_preserved_when_not_overridden(self):
        base = {"topics": [{"name": "AI"}], "filters": {"max_age_hours": 48}}
        overrides = {"delivery": {"time": "08:00"}}
        result = _merge_configs(base, overrides)
        assert result["topics"] == [{"name": "AI"}]
        assert result["filters"]["max_age_hours"] == 48


class TestValidateConfig:
    def test_valid_minimal_config_passes(self):
        config = {
            "version": 1,
            "delivery": {"time": "07:00", "timezone": "UTC"},
            "sources": [
                {"name": "Test", "type": "rss", "url": "https://example.com/feed"}
            ],
        }
        validate_config(config)

    def test_missing_delivery_fails(self):
        config = {
            "version": 1,
            "sources": [
                {"name": "Test", "type": "rss", "url": "https://example.com/feed"}
            ],
        }
        with pytest.raises(Exception):
            validate_config(config)

    def test_invalid_version_fails(self):
        config = {
            "version": 99,
            "delivery": {"time": "07:00", "timezone": "UTC"},
            "sources": [
                {"name": "Test", "type": "rss", "url": "https://example.com/feed"}
            ],
        }
        with pytest.raises(Exception):
            validate_config(config)

    def test_no_sources_or_blocks_fails(self):
        config = {
            "version": 1,
            "delivery": {"time": "07:00", "timezone": "UTC"},
        }
        with pytest.raises(Exception):
            validate_config(config)

    def test_blocks_alone_is_valid(self):
        config = {
            "version": 1,
            "delivery": {"time": "07:00", "timezone": "UTC"},
            "blocks": [{"type": "weather", "location": "Seattle, WA"}],
        }
        validate_config(config)


class TestDiscoverUserBriefings:
    def test_finds_matt_briefings(self):
        pairs = discover_user_briefings()
        user_ids = [uid for uid, _ in pairs]
        assert "matt" in user_ids

    def test_skips_underscore_directories(self):
        pairs = discover_user_briefings()
        user_ids = [uid for uid, _ in pairs]
        assert not any(uid.startswith("_") for uid in user_ids)

    def test_returns_yaml_filenames(self):
        pairs = discover_user_briefings()
        for _, filename in pairs:
            assert filename.endswith(".yaml")


class TestLoadUserBriefing:
    def test_loads_matt_ai_engineering(self):
        config = load_user_briefing("matt", "ai-engineering.yaml")
        assert config["_briefing_name"] == "ai-engineering"
        assert config["_briefing_display_name"] == "AI Engineering"
        assert "topics" in config
        assert "delivery" in config

    def test_extends_merges_base_topics(self):
        config = load_user_briefing("matt", "ai-engineering.yaml")
        topic_names = [t["name"] for t in config.get("topics", [])]
        assert "AI engineering" in topic_names

    def test_user_override_takes_precedence(self):
        config = load_user_briefing("matt", "ai-engineering.yaml")
        assert config["delivery"]["time"] == "07:00"
        assert config["delivery"]["timezone"] == "America/New_York"

    def test_missing_user_raises(self):
        with pytest.raises(FileNotFoundError):
            load_user_briefing("nonexistent_user", "briefing.yaml")

    def test_catalog_is_loaded(self):
        config = load_user_briefing("matt", "ai-engineering.yaml")
        assert "_catalog" in config
