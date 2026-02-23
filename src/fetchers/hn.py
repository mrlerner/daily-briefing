"""Hacker News fetcher via Algolia API. Returns items in the common format."""

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger("briefing.fetchers.hn")

ALGOLIA_API = "https://hn.algolia.com/api/v1/search"
FETCH_TIMEOUT = 10


def fetch_hn(catalog_hn: dict, freshness_hours: int = 24) -> list[dict]:
    """Fetch HN posts matching catalog queries.

    Args:
        catalog_hn: The 'hn' section from a source catalog, containing 'queries'.
        freshness_hours: Only include posts from the last N hours.

    Returns:
        List of items in the common format, sorted by points descending.
    """
    queries = catalog_hn.get("queries", [])
    if not queries:
        return []

    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=freshness_hours)).timestamp())
    all_posts = {}

    for query in queries:
        try:
            resp = requests.get(
                ALGOLIA_API,
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff_ts}",
                    "hitsPerPage": 30,
                },
                timeout=FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as e:
            logger.warning("HN search failed for '%s': %s", query, e)
            continue

        for hit in hits:
            post_id = hit.get("objectID")
            if not post_id or post_id in all_posts:
                continue

            title = hit.get("title", "").strip()
            url = hit.get("url", "") or f"https://news.ycombinator.com/item?id={post_id}"
            points = hit.get("points", 0) or 0
            comments = hit.get("num_comments", 0) or 0
            author = hit.get("author", "")
            created_at = hit.get("created_at", "")

            published = _parse_hn_date(created_at)
            item_id = hashlib.sha256(url.encode()).hexdigest()[:16]

            all_posts[post_id] = {
                "id": item_id,
                "title": title,
                "url": url,
                "source": "Hacker News",
                "source_type": "hn",
                "published": published.isoformat() if published else None,
                "published_dt": published,
                "summary": "",
                "hn_url": f"https://news.ycombinator.com/item?id={post_id}",
                "points": points,
                "comments": comments,
                "author": author,
            }

        time.sleep(0.2)

    posts = sorted(all_posts.values(), key=lambda x: x.get("points", 0), reverse=True)
    logger.info("Fetched %d HN posts from %d queries", len(posts), len(queries))
    return posts


def _parse_hn_date(ts_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
