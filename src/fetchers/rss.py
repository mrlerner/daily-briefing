"""RSS and Atom feed fetcher. Returns items in the common format."""

import hashlib
import logging
from datetime import datetime, timezone
from time import mktime

import feedparser
import requests

logger = logging.getLogger("briefing.fetchers.rss")

FETCH_TIMEOUT = 15
USER_AGENT = "DailyBriefingBuilder/1.0"


def fetch_feed(source: dict) -> list[dict]:
    """Fetch an RSS/Atom feed and return normalized items.

    Args:
        source: dict with at least 'name' and 'url' keys.

    Returns:
        List of items in the common format.
    """
    name = source["name"]
    url = source["url"]
    items = []

    try:
        resp = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except requests.RequestException as e:
        logger.warning("Failed to fetch RSS feed '%s': %s", name, e)
        return []
    except Exception as e:
        logger.warning("Error parsing feed '%s': %s", name, e)
        return []

    if feed.bozo and not feed.entries:
        logger.warning("Malformed feed '%s': %s", name, feed.bozo_exception)
        return []

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary or ""
        elif hasattr(entry, "description"):
            summary = entry.description or ""
        # Strip HTML tags from summary
        import re
        summary = re.sub(r"<[^>]+>", "", summary).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        published = _parse_entry_date(entry)

        item_id = hashlib.sha256(link.encode()).hexdigest()[:16]

        items.append({
            "id": item_id,
            "title": title,
            "url": link,
            "source": name,
            "source_type": "rss",
            "published": published.isoformat() if published else None,
            "published_dt": published,
            "summary": summary,
        })

    logger.info("Fetched %d items from RSS feed '%s'", len(items), name)
    return items


def _parse_entry_date(entry) -> datetime | None:
    """Extract and parse the publication date from a feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None
