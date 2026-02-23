"""Reddit fetcher via public JSON API. Returns items in the common format."""

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger("briefing.fetchers.reddit")

FETCH_TIMEOUT = 15
USER_AGENT = "DailyBriefingBuilder/1.0 (AI Engineering Digest)"


def fetch_reddit(catalog_reddit: dict, freshness_hours: int = 24) -> list[dict]:
    """Fetch Reddit posts matching catalog config.

    Args:
        catalog_reddit: The 'reddit' section from a source catalog.
        freshness_hours: Only include posts from the last N hours.

    Returns:
        List of items in the common format, sorted by score descending.
    """
    subreddits = catalog_reddit.get("subreddits", [])
    keywords = [kw.lower() for kw in catalog_reddit.get("keywords", [])]
    search_queries = catalog_reddit.get("search_queries", [])
    search_subs = catalog_reddit.get("search_subreddits", subreddits[:2])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
    cutoff_ts = cutoff.timestamp()
    all_posts = {}
    headers = {"User-Agent": USER_AGENT}

    # Top posts from each subreddit, keyword-filtered
    for sub in subreddits:
        posts = _fetch_subreddit_top(sub, headers)
        for post in posts:
            pid = post.get("id")
            if not pid or pid in all_posts:
                continue
            if post.get("created_utc", 0) < cutoff_ts:
                continue
            if keywords and not _matches_keywords(post.get("title", ""), keywords):
                continue
            all_posts[pid] = _normalize_post(post)
        time.sleep(0.5)

    # Targeted search queries
    for query in search_queries:
        for sub in search_subs:
            posts = _search_subreddit(sub, query, headers)
            for post in posts:
                pid = post.get("id")
                if not pid or pid in all_posts:
                    continue
                if post.get("created_utc", 0) < cutoff_ts:
                    continue
                all_posts[pid] = _normalize_post(post)
            time.sleep(0.5)

    result = sorted(all_posts.values(), key=lambda x: x.get("score", 0), reverse=True)
    logger.info("Fetched %d Reddit posts from %d subreddits", len(result), len(subreddits))
    return result


def _fetch_subreddit_top(subreddit: str, headers: dict, limit: int = 30) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}"
    return _fetch_reddit_listing(url, headers)


def _search_subreddit(subreddit: str, query: str, headers: dict, limit: int = 15) -> list[dict]:
    url = (f"https://www.reddit.com/r/{subreddit}/search.json"
           f"?q={requests.utils.quote(query)}&sort=top&t=day&limit={limit}&restrict_sr=1")
    return _fetch_reddit_listing(url, headers)


def _fetch_reddit_listing(url: str, headers: dict) -> list[dict]:
    try:
        resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]
    except Exception as e:
        logger.warning("Reddit fetch failed for %s: %s", url[:80], e)
        return []


def _matches_keywords(title: str, keywords: list[str]) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)


def _normalize_post(post: dict) -> dict:
    title = post.get("title", "").strip()
    reddit_url = f"https://reddit.com{post.get('permalink', '')}"
    url = reddit_url
    created_utc = post.get("created_utc", 0)
    published = datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None
    item_id = hashlib.sha256(url.encode()).hexdigest()[:16]

    return {
        "id": item_id,
        "title": title,
        "url": url,
        "source": f"r/{post.get('subreddit', '')}",
        "source_type": "reddit",
        "published": published.isoformat() if published else None,
        "published_dt": published,
        "summary": (post.get("selftext", "") or "")[:300],
        "subreddit": post.get("subreddit", ""),
        "score": post.get("score", 0),
        "comments": post.get("num_comments", 0),
        "author": post.get("author", ""),
    }
