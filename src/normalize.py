"""Normalize raw fetcher output into the common item format."""

import hashlib
from datetime import datetime, timezone


def normalize_item(raw: dict) -> dict:
    """Ensure an item has all required common-format fields with correct types.

    Fetchers already produce near-common-format output. This function fills
    in defaults and normalizes field types for anything that's missing.
    """
    url = raw.get("url", "")
    item_id = raw.get("id") or hashlib.sha256(url.encode()).hexdigest()[:16]

    return {
        "id": item_id,
        "title": raw.get("title", "").strip(),
        "url": url,
        "source": raw.get("source", "Unknown"),
        "source_type": raw.get("source_type", "unknown"),
        "published": raw.get("published"),
        "published_dt": raw.get("published_dt"),
        "summary": raw.get("summary", ""),
        # Platform-specific metadata (preserved for rendering)
        "points": raw.get("points"),
        "score": raw.get("score"),
        "comments": raw.get("comments"),
        "author": raw.get("author"),
        "subreddit": raw.get("subreddit"),
        "hn_url": raw.get("hn_url"),
        # Ranking fields (set later by rank.py)
        "topics_matched": [],
        "relevance_score": 0.0,
    }


def deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicate items by URL, keeping the first occurrence."""
    seen_urls = set()
    unique = []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(item)
    return unique
