"""Bluesky fetcher via native RSS. No auth needed."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from time import mktime

import feedparser
import requests

logger = logging.getLogger("briefing.fetchers.bluesky")

FETCH_TIMEOUT = 10
BSKY_RSS_TEMPLATE = "https://bsky.app/profile/{handle}/rss"


def fetch_bluesky(catalog_bluesky: dict) -> list[dict]:
    """Fetch recent posts from Bluesky accounts via native RSS.

    Args:
        catalog_bluesky: The 'bluesky' section from a source catalog,
            containing 'accounts' (list of Bluesky handles).

    Returns:
        List of items in the common format.
    """
    accounts = catalog_bluesky.get("accounts", [])
    if not accounts:
        return []

    all_items = {}

    for handle in accounts:
        feed_url = BSKY_RSS_TEMPLATE.format(handle=handle)
        try:
            resp = requests.get(
                feed_url,
                timeout=FETCH_TIMEOUT,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("Bluesky feed for %s returned %d", handle, resp.status_code)
                continue

            feed = feedparser.parse(resp.text)
            if feed.bozo and not feed.entries:
                logger.warning("Malformed Bluesky feed for %s", handle)
                continue

            for entry in feed.entries:
                item = _parse_entry(entry, handle)
                if item and item["id"] not in all_items:
                    all_items[item["id"]] = item

        except requests.RequestException as e:
            logger.warning("Failed to fetch Bluesky feed for %s: %s", handle, e)
            continue

    items = list(all_items.values())
    logger.info("Fetched %d posts from %d Bluesky accounts", len(items), len(accounts))
    return items


def _parse_entry(entry, handle: str) -> dict | None:
    link = entry.get("link", "").strip()
    if not link:
        return None

    content = ""
    if hasattr(entry, "description"):
        content = entry.description or ""
    elif hasattr(entry, "summary"):
        content = entry.summary or ""

    content = re.sub(r"<[^>]+>", "", content).strip()
    title = content[:120] + ("..." if len(content) > 120 else "")

    published = _parse_date(entry)
    item_id = hashlib.sha256(link.encode()).hexdigest()[:16]
    display_name = handle.removesuffix(".bsky.social")

    return {
        "id": item_id,
        "title": title,
        "url": link,
        "source": f"@{display_name}",
        "source_type": "bluesky",
        "published": published.isoformat() if published else None,
        "published_dt": published,
        "summary": content[:300] if len(content) > 300 else content,
        "author": display_name,
        "section": "Bluesky",
    }


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None
