"""Twitter/X fetcher via Nitter RSS. Tries instances in order until one works."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from time import mktime

import feedparser
import requests

logger = logging.getLogger("briefing.fetchers.nitter")

FETCH_TIMEOUT = 10
USER_AGENT = "DailyBriefingBuilder/1.0"


def fetch_nitter(catalog_twitter: dict) -> list[dict]:
    """Fetch recent tweets for configured accounts via Nitter RSS.

    Args:
        catalog_twitter: The 'twitter' section from a source catalog,
            containing 'nitter_instances' and 'accounts'.

    Returns:
        List of items in the common format.
    """
    instances = catalog_twitter.get("nitter_instances", [])
    accounts = catalog_twitter.get("accounts", [])
    if not instances or not accounts:
        return []

    working_instance = _find_working_instance(instances)
    if not working_instance:
        logger.warning("No working Nitter instances found")
        return []

    logger.info("Using Nitter instance: %s", working_instance)
    all_items = {}

    for account in accounts:
        feed_url = f"https://{working_instance}/{account}/rss"
        try:
            resp = requests.get(
                feed_url,
                timeout=FETCH_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("Nitter feed for @%s returned %d", account, resp.status_code)
                continue

            feed = feedparser.parse(resp.text)
            if feed.bozo and not feed.entries:
                logger.warning("Malformed Nitter feed for @%s", account)
                continue

            for entry in feed.entries:
                item = _parse_nitter_entry(entry, account)
                if item and item["id"] not in all_items:
                    all_items[item["id"]] = item

        except requests.RequestException as e:
            logger.warning("Failed to fetch Nitter feed for @%s: %s", account, e)
            continue

    items = list(all_items.values())
    logger.info("Fetched %d tweets from %d accounts via Nitter", len(items), len(accounts))
    return items


def _find_working_instance(instances: list[str]) -> str | None:
    """Try each Nitter instance and return the first one that responds."""
    for instance in instances:
        try:
            resp = requests.head(
                f"https://{instance}/",
                timeout=5,
                allow_redirects=True,
            )
            if resp.status_code < 400:
                return instance
        except requests.RequestException:
            continue
    return None


def _parse_nitter_entry(entry, account: str) -> dict | None:
    """Convert a Nitter RSS entry to the common item format."""
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
    tweet_url = _nitter_to_twitter_url(link)
    item_id = hashlib.sha256(tweet_url.encode()).hexdigest()[:16]

    return {
        "id": item_id,
        "title": title,
        "url": tweet_url,
        "source": f"@{account}",
        "source_type": "nitter",
        "published": published.isoformat() if published else None,
        "published_dt": published,
        "summary": content[:300] if len(content) > 300 else content,
        "author": account,
        "section": "Twitter",
    }


def _nitter_to_twitter_url(nitter_url: str) -> str:
    """Convert a Nitter URL to a canonical x.com URL."""
    match = re.search(r"/([^/]+)/status/(\d+)", nitter_url)
    if match:
        return f"https://x.com/{match.group(1)}/status/{match.group(2)}"
    return nitter_url


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None
