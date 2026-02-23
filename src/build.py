#!/usr/bin/env python3
"""Main entry point — build daily briefings for all users."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import load_user_config, discover_users, PROJECT_ROOT as ROOT
from fetchers.rss import fetch_feed
from fetchers.hn import fetch_hn
from fetchers.reddit import fetch_reddit
from blocks.weather import fetch_weather
from normalize import normalize_item, deduplicate
from rank import score_items, filter_items, rank_and_cap
from render import render_html, render_json, render_summary

OUT_DIR = ROOT / "out"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("briefing.build")


def fetch_all_sources(config: dict) -> list[dict]:
    """Fetch items from all configured sources (inline + catalog)."""
    raw_items = []

    # Inline RSS sources
    for source in config.get("sources", []):
        if source.get("type") == "rss":
            try:
                items = fetch_feed(source)
                raw_items.extend(items)
            except Exception as e:
                logger.warning("Failed to fetch source '%s': %s", source.get("name"), e)

    # Catalog sources
    catalog = config.get("_catalog")
    if catalog:
        # RSS feeds from catalog
        for rss_source in catalog.get("rss", []):
            try:
                items = fetch_feed(rss_source)
                raw_items.extend(items)
            except Exception as e:
                logger.warning("Failed to fetch catalog RSS '%s': %s", rss_source.get("name"), e)

        # Hacker News
        if "hn" in catalog:
            try:
                freshness = config.get("filters", {}).get("max_age_hours", 36)
                hn_items = fetch_hn(catalog["hn"], freshness_hours=freshness)
                raw_items.extend(hn_items)
            except Exception as e:
                logger.warning("Failed to fetch HN: %s", e)

        # Reddit
        if "reddit" in catalog:
            try:
                freshness = config.get("filters", {}).get("max_age_hours", 36)
                reddit_items = fetch_reddit(catalog["reddit"], freshness_hours=freshness)
                raw_items.extend(reddit_items)
            except Exception as e:
                logger.warning("Failed to fetch Reddit: %s", e)

    return raw_items


def fetch_all_blocks(config: dict) -> list[dict]:
    """Fetch all content blocks."""
    blocks = []
    for block_config in config.get("blocks", []):
        block_type = block_config.get("type")
        try:
            if block_type == "weather":
                result = fetch_weather(block_config)
                if result:
                    blocks.append(result)
            else:
                logger.info("Skipping unsupported block type: %s", block_type)
        except Exception as e:
            logger.warning("Failed to fetch block '%s': %s", block_config.get("label"), e)
    return blocks


def build_user(user_id: str) -> dict:
    """Build briefing for a single user. Returns build summary."""
    logger.info("=" * 50)
    logger.info("Building briefing for: %s", user_id)
    logger.info("=" * 50)

    start = datetime.now()
    result = {"user_id": user_id, "success": False, "error": None}

    try:
        config = load_user_config(user_id)
    except Exception as e:
        logger.error("Failed to load config for '%s': %s", user_id, e)
        result["error"] = str(e)
        return result

    # Fetch sources
    raw_items = fetch_all_sources(config)
    logger.info("Fetched %d raw items from all sources", len(raw_items))

    # Normalize and deduplicate
    items = [normalize_item(item) for item in raw_items]
    items = deduplicate(items)
    logger.info("After dedup: %d items", len(items))

    # Score and filter
    topics = config.get("topics", [])
    filters = config.get("filters", {})
    format_config = config.get("format", {})

    items = score_items(items, topics)
    items = filter_items(items, filters)
    logger.info("After filtering: %d items", len(items))

    max_items = format_config.get("max_items", 15)
    items = rank_and_cap(items, max_items=max_items)
    logger.info("After ranking: %d items", len(items))

    # Fetch blocks
    blocks = fetch_all_blocks(config)
    logger.info("Fetched %d blocks", len(blocks))

    # Determine output paths
    date_str = datetime.now().strftime("%Y-%m-%d")
    user_out = OUT_DIR / user_id
    html_path = user_out / f"{date_str}.html"
    json_path = user_out / f"{date_str}.json"
    summary_path = user_out / f"{date_str}.summary.txt"
    index_path = user_out / "index.html"

    # Render outputs
    render_html(items, blocks, config, html_path)
    render_json(items, blocks, json_path)
    render_summary(items, blocks, config, summary_path)

    # Write index.html redirect
    _write_index_redirect(index_path, f"{date_str}.html")

    elapsed = (datetime.now() - start).total_seconds()
    result["success"] = True
    result["items_fetched"] = len(raw_items)
    result["items_after_filter"] = len(items)
    result["blocks"] = len(blocks)
    result["elapsed_seconds"] = round(elapsed, 1)
    result["output_html"] = str(html_path)

    logger.info("Built %s in %.1fs — %d items, %d blocks",
                user_id, elapsed, len(items), len(blocks))
    return result


def _write_root_index(results: list[dict]) -> None:
    """Write a root index.html listing all user briefings."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    user_links = []
    for r in results:
        if r.get("success"):
            uid = r["user_id"]
            user_links.append(
                f'<li><a href="{uid}/index.html">{uid}</a> '
                f'— {r.get("items_after_filter", 0)} items, '
                f'{r.get("blocks", 0)} blocks</li>'
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Briefings</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 16px; color: #1e293b; }}
        h1 {{ color: #0f172a; }}
        a {{ color: #059669; }}
        li {{ margin: 8px 0; }}
        .date {{ color: #64748b; font-size: 14px; }}
    </style>
</head>
<body>
    <h1>Daily Briefings</h1>
    <p class="date">Built {now.strftime('%B %d, %Y at %H:%M')}</p>
    <ul>
        {''.join(user_links) if user_links else '<li>No briefings built yet.</li>'}
    </ul>
</body>
</html>"""

    index_path = OUT_DIR / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")
    logger.info("Wrote root index: %s", index_path)


def _write_index_redirect(index_path: Path, target_filename: str) -> None:
    """Write an index.html that redirects to the latest briefing."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url={target_filename}">
    <title>Redirecting...</title>
</head>
<body>
    <p>Redirecting to <a href="{target_filename}">latest briefing</a>...</p>
</body>
</html>"""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build daily briefings")
    parser.add_argument("--user", help="Build for a specific user only")
    args = parser.parse_args()

    start = datetime.now()

    if args.user:
        users = [args.user]
    else:
        users = discover_users()

    if not users:
        logger.error("No users found in users/ directory")
        sys.exit(1)

    logger.info("Building briefings for %d user(s): %s", len(users), ", ".join(users))

    results = []
    for user_id in users:
        try:
            result = build_user(user_id)
            results.append(result)
        except Exception as e:
            logger.error("Build failed for '%s': %s", user_id, e)
            results.append({"user_id": user_id, "success": False, "error": str(e)})

    # Write root index page listing all users
    _write_root_index(results)

    # Write build log
    build_log = {
        "timestamp": datetime.now().isoformat(),
        "users_built": len(results),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
        "total_elapsed_seconds": round((datetime.now() - start).total_seconds(), 1),
    }

    log_path = OUT_DIR / "build-log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(build_log, indent=2), encoding="utf-8")

    # Print summary
    print()
    print("=" * 50)
    print("Build Summary")
    print("=" * 50)
    for r in results:
        status = "✓" if r.get("success") else "✗"
        user = r.get("user_id", "?")
        if r.get("success"):
            print(f"  {status} {user}: {r.get('items_after_filter', 0)} items, "
                  f"{r.get('blocks', 0)} blocks ({r.get('elapsed_seconds', 0)}s)")
        else:
            print(f"  {status} {user}: {r.get('error', 'unknown error')}")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nTotal: {elapsed:.1f}s")

    failed = sum(1 for r in results if not r.get("success"))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
