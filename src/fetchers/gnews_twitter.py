"""Fetch popular tweets via Google News RSS, resolving URLs to x.com links."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from time import mktime

import feedparser
import requests
from googlenewsdecoder import gnewsdecoder

logger = logging.getLogger("briefing.fetchers.gnews_twitter")

FETCH_TIMEOUT = 15
USER_AGENT = "DailyBriefingBuilder/1.0"


def fetch_gnews_twitter(source: dict) -> list[dict]:
    """Fetch tweets surfaced by Google News and resolve to x.com URLs.

    Args:
        source: dict with 'name', 'url' (Google News RSS URL), and
            optionally 'section'.

    Returns:
        List of items in the common format with direct x.com links.
    """
    name = source["name"]
    url = source["url"]

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
        logger.warning("Failed to fetch Google News RSS '%s': %s", name, e)
        return []

    if feed.bozo and not feed.entries:
        logger.warning("Malformed feed '%s': %s", name, feed.bozo_exception)
        return []

    items = []
    resolved = 0

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        gnews_link = entry.get("link", "").strip()
        if not title or not gnews_link:
            continue

        title = re.sub(r"\s*-\s*x\.com\s*$", "", title).strip()

        tweet_url = _resolve_gnews_url(gnews_link)
        if tweet_url:
            resolved += 1
        else:
            tweet_url = gnews_link

        author = _extract_author(tweet_url)
        published = _parse_date(entry)
        item_id = hashlib.sha256(tweet_url.encode()).hexdigest()[:16]

        item = {
            "id": item_id,
            "title": title[:120] + ("..." if len(title) > 120 else ""),
            "url": tweet_url,
            "source": f"@{author}" if author else name,
            "source_type": "twitter_gnews",
            "published": published.isoformat() if published else None,
            "published_dt": published,
            "summary": title,
            "author": author,
            "section": source.get("section", "Twitter"),
        }
        items.append(item)

    logger.info("Fetched %d tweets from Google News '%s' (%d URLs resolved to x.com)",
                len(items), name, resolved)
    return items


def _resolve_gnews_url(gnews_url: str) -> str | None:
    """Decode a Google News redirect URL to the original x.com URL."""
    try:
        result = gnewsdecoder(gnews_url, interval=0.2)
        if result.get("status"):
            return result["decoded_url"]
    except Exception as e:
        logger.debug("Failed to decode Google News URL: %s", e)
    return None


def _extract_author(url: str) -> str:
    """Extract the Twitter username from an x.com URL."""
    match = re.search(r"x\.com/([^/]+)/status/", url)
    if match:
        return match.group(1)
    return ""


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None
