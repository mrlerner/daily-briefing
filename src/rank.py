"""Keyword-based relevance scoring, filtering, and ranking."""

import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("briefing.rank")

PRIORITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}

MAX_RECENCY_BOOST = 0.15


def score_items(items: list[dict], topics: list[dict]) -> list[dict]:
    """Score each item's relevance against the user's topics.

    Modifies items in-place (sets relevance_score and topics_matched).
    """
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        matched = []
        total_score = 0.0

        for topic in topics:
            priority = topic.get("priority", "medium")
            weight = PRIORITY_WEIGHTS.get(priority, 0.6)
            keywords = topic.get("keywords", [])

            matches = sum(1 for kw in keywords if kw.lower() in text)
            if matches > 0:
                topic_score = min(matches / max(len(keywords), 1), 1.0) * weight
                total_score += topic_score
                matched.append(topic["name"])

        # Recency boost: items from the last 6 hours get up to 0.15 extra
        published_dt = item.get("published_dt")
        if published_dt:
            age_hours = (datetime.now(timezone.utc) - published_dt).total_seconds() / 3600
            if age_hours < 6:
                total_score += MAX_RECENCY_BOOST * (1 - age_hours / 6)

        # Platform engagement boost for HN/Reddit
        points = item.get("points") or item.get("score") or 0
        if points > 100:
            total_score += 0.1
        if points > 500:
            total_score += 0.1

        item["relevance_score"] = round(min(total_score, 2.0), 3)
        item["topics_matched"] = matched

    return items


# HN/Reddit have community votes doing the curation, so they can pass with
# a weak keyword match.  RSS relies solely on keyword relevance — the user's
# min_relevance in their briefing.yaml controls the threshold.
TYPE_MIN_RELEVANCE = {
    "rss": 0.0,
    "hn": 0.0,
    "reddit": 0.0,
}


def filter_items(items: list[dict], filters: dict) -> list[dict]:
    """Apply exclusion filters, age filter, and relevance threshold."""
    exclude_keywords = [kw.lower() for kw in filters.get("exclude_keywords", [])]
    max_age_hours = filters.get("max_age_hours", 48)
    global_min = filters.get("min_relevance", 0.0)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    result = []

    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if any(kw in text for kw in exclude_keywords):
            continue

        published_dt = item.get("published_dt")
        if published_dt and published_dt < cutoff:
            continue

        stype = item.get("source_type", "rss")
        min_relevance = max(global_min, TYPE_MIN_RELEVANCE.get(stype, global_min))
        if item.get("relevance_score", 0) < min_relevance:
            continue

        result.append(item)

    filtered_count = len(items) - len(result)
    if filtered_count:
        logger.info("Filtered out %d items (excluded/old/low-relevance)", filtered_count)

    return result


def rank_and_cap(items: list[dict], max_items: int = 30) -> list[dict]:
    """Rank items with source diversity, then cap to max_items.

    Ensures each source type gets representation rather than letting
    high-engagement platforms (HN, Reddit) crowd out RSS news.
    """
    by_type: dict[str, list[dict]] = {}
    for item in items:
        stype = item.get("source_type", "unknown")
        if stype not in by_type:
            by_type[stype] = []
        by_type[stype].append(item)

    # Sort each group by relevance
    for stype in by_type:
        by_type[stype].sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    # Per-type caps: guarantee slots for each source type
    type_caps = {
        "rss": 10,
        "hn": 10,
        "reddit": 10,
    }

    result = []
    for stype, group in by_type.items():
        cap = type_caps.get(stype, 10)
        selected = group[:cap]
        result.extend(selected)
        if len(group) > cap:
            logger.info("Capped %s from %d to %d", stype, len(group), cap)

    # Final sort by relevance across all selected items
    result.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    # Apply global cap if needed
    if len(result) > max_items:
        result = result[:max_items]

    logger.info("Final ranking: %d items (%s)",
                len(result),
                ", ".join(f"{k}={len(v)}" for k, v in by_type.items()))
    return result
