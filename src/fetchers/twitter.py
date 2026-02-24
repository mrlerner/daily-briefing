"""Twitter/X search via API v2 free tier. Needs X_BEARER_TOKEN in .env."""

import hashlib
import logging
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

logger = logging.getLogger("briefing.fetchers.twitter")

SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
FETCH_TIMEOUT = 15


def fetch_twitter_search(catalog_twitter: dict) -> list[dict]:
    """Search recent tweets using the Twitter API v2 free tier.

    Args:
        catalog_twitter: The 'twitter' section from a source catalog,
            containing 'search_queries', and optionally 'min_faves'
            and 'min_retweets'.

    Returns:
        List of items in the common format, sorted by likes descending.
    """
    load_dotenv()
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        logger.info("X_BEARER_TOKEN not set — skipping Twitter API search")
        return []

    queries = catalog_twitter.get("search_queries", [])
    if not queries:
        return []

    max_results = min(catalog_twitter.get("max_results", 10), 100)
    top_k = catalog_twitter.get("top_k", 0)

    all_items = {}
    headers = {"Authorization": f"Bearer {bearer_token}"}

    for query_text in queries:
        full_query = f"{query_text} -is:retweet lang:en"
        logger.info("Twitter API search: %s (max_results=%d)", full_query, max_results)

        try:
            resp = requests.get(
                SEARCH_URL,
                params={
                    "query": full_query,
                    "max_results": max_results,
                    "sort_order": "recency",
                    "tweet.fields": "created_at,public_metrics,lang,author_id",
                    "expansions": "author_id",
                    "user.fields": "username",
                },
                headers=headers,
                timeout=FETCH_TIMEOUT,
            )

            if resp.status_code == 429:
                logger.warning("Twitter API rate limited — skipping remaining queries")
                break
            if resp.status_code != 200:
                detail = resp.json().get("detail", resp.text[:200])
                logger.warning("Twitter API %d: %s", resp.status_code, detail)
                continue

            data = resp.json()

            authors = {}
            for user in data.get("includes", {}).get("users", []):
                authors[user["id"]] = user.get("username", "")

            for tweet in data.get("data", []):
                if tweet.get("text", "").startswith("RT @"):
                    continue
                item = _parse_tweet(tweet, authors)
                if item and item["id"] not in all_items:
                    all_items[item["id"]] = item

        except requests.RequestException as e:
            logger.warning("Twitter API request failed: %s", e)
            continue

    items = sorted(all_items.values(), key=_engagement_score, reverse=True)

    if top_k > 0 and len(items) > top_k:
        logger.info("Keeping top %d of %d tweets by engagement", top_k, len(items))
        items = items[:top_k]

    if items:
        top = items[0]
        logger.info("Top tweet: %d likes, %d RT — @%s",
                     top.get("likes", 0), top.get("retweets", 0), top.get("author", "?"))

    logger.info("Returning %d tweets from Twitter API (%d queries, %d fetched)",
                len(items), len(queries), len(all_items))
    return items


def _engagement_score(item: dict) -> float:
    """Weighted engagement score: likes + 2*retweets + 0.5*replies."""
    return (item.get("likes", 0)
            + 2 * item.get("retweets", 0)
            + 0.5 * item.get("comments", 0))


def _parse_tweet(tweet: dict, authors: dict) -> dict | None:
    tweet_id = tweet.get("id", "")
    if not tweet_id:
        return None

    text = tweet.get("text", "")
    metrics = tweet.get("public_metrics", {})
    username = authors.get(tweet.get("author_id", ""), "")
    created_at = tweet.get("created_at", "")

    published = _parse_date(created_at)
    tweet_url = f"https://x.com/{username or 'i'}/status/{tweet_id}"
    item_id = hashlib.sha256(tweet_url.encode()).hexdigest()[:16]

    title = text[:120] + ("..." if len(text) > 120 else "")

    return {
        "id": item_id,
        "title": title,
        "url": tweet_url,
        "source": f"@{username}" if username else "Twitter Search",
        "source_type": "twitter_api",
        "published": published.isoformat() if published else None,
        "published_dt": published,
        "summary": text[:300] if len(text) > 300 else text,
        "author": username,
        "likes": metrics.get("like_count", 0),
        "retweets": metrics.get("retweet_count", 0),
        "comments": metrics.get("reply_count", 0),
        "section": "Twitter",
    }


def _parse_date(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
