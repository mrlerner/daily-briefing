"""Shared fixtures for the daily briefing test suite."""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture
def make_item():
    """Factory fixture for creating test items with sensible defaults."""
    def _make(
        title="Test Article",
        url="https://example.com/article",
        source="Test Source",
        source_type="rss",
        summary="A test summary about AI and machine learning.",
        hours_ago=2,
        points=None,
        score=None,
        section=None,
    ):
        published_dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            "title": title,
            "url": url,
            "source": source,
            "source_type": source_type,
            "summary": summary,
            "published": published_dt.isoformat(),
            "published_dt": published_dt,
            "points": points,
            "score": score,
            "section": section,
        }
    return _make


@pytest.fixture
def sample_topics():
    """A typical set of topics for testing scoring."""
    return [
        {
            "name": "AI engineering",
            "keywords": ["AI", "LLM", "machine learning"],
            "priority": "high",
        },
        {
            "name": "Developer tools",
            "keywords": ["Cursor", "Copilot", "LangChain"],
            "priority": "medium",
        },
    ]
