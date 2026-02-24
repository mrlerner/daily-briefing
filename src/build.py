#!/usr/bin/env python3
"""Main entry point — build daily briefings for all users."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import load_user_briefing, discover_user_briefings, PROJECT_ROOT as ROOT
from fetchers.rss import fetch_feed
from fetchers.hn import fetch_hn
from fetchers.reddit import fetch_reddit
from fetchers.bluesky import fetch_bluesky
from fetchers.gnews_twitter import fetch_gnews_twitter
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

    for source in config.get("sources", []):
        if source.get("type") == "rss":
            try:
                items = fetch_feed(source)
                raw_items.extend(items)
            except Exception as e:
                logger.warning("Failed to fetch source '%s': %s", source.get("name"), e)

    catalog = config.get("_catalog")
    if catalog:
        for rss_source in catalog.get("rss", []):
            try:
                items = fetch_feed(rss_source)
                raw_items.extend(items)
            except Exception as e:
                logger.warning("Failed to fetch catalog RSS '%s': %s", rss_source.get("name"), e)

        if "hn" in catalog:
            try:
                freshness = config.get("filters", {}).get("max_age_hours", 36)
                hn_items = fetch_hn(catalog["hn"], freshness_hours=freshness)
                raw_items.extend(hn_items)
            except Exception as e:
                logger.warning("Failed to fetch HN: %s", e)

        if "reddit" in catalog:
            try:
                freshness = config.get("filters", {}).get("max_age_hours", 36)
                reddit_items = fetch_reddit(catalog["reddit"], freshness_hours=freshness)
                raw_items.extend(reddit_items)
            except Exception as e:
                logger.warning("Failed to fetch Reddit: %s", e)

        if "twitter" in catalog:
            for gnews_src in catalog["twitter"].get("google_news_rss", []):
                try:
                    items = fetch_gnews_twitter(gnews_src)
                    raw_items.extend(items)
                except Exception as e:
                    logger.warning("Failed to fetch Twitter via Google News: %s", e)

        if "bluesky" in catalog:
            try:
                bsky_items = fetch_bluesky(catalog["bluesky"])
                raw_items.extend(bsky_items)
            except Exception as e:
                logger.warning("Failed to fetch Bluesky: %s", e)

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


def build_briefing(user_id: str, briefing_file: str) -> dict:
    """Build a single briefing for a user. Returns build summary."""
    briefing_name = briefing_file.replace(".yaml", "")
    label = f"{user_id}/{briefing_name}"

    logger.info("=" * 50)
    logger.info("Building: %s", label)
    logger.info("=" * 50)

    start = datetime.now()
    result = {"user_id": user_id, "briefing": briefing_name, "success": False, "error": None}

    try:
        config = load_user_briefing(user_id, briefing_file)
    except Exception as e:
        logger.error("Failed to load config for '%s': %s", label, e)
        result["error"] = str(e)
        return result

    raw_items = fetch_all_sources(config)
    logger.info("Fetched %d raw items from all sources", len(raw_items))

    items = [normalize_item(item) for item in raw_items]
    items = deduplicate(items)
    logger.info("After dedup: %d items", len(items))

    topics = config.get("topics", [])
    filters = config.get("filters", {})
    format_config = config.get("format", {})

    items = score_items(items, topics)
    items = filter_items(items, filters)
    logger.info("After filtering: %d items", len(items))

    max_items = format_config.get("max_items", 15)
    items = rank_and_cap(items, max_items=max_items)
    logger.info("After ranking: %d items", len(items))

    blocks = fetch_all_blocks(config)
    logger.info("Fetched %d blocks", len(blocks))

    # Output to out/<user_id>/<briefing_name>/
    date_str = datetime.now().strftime("%Y-%m-%d")
    briefing_out = OUT_DIR / user_id / briefing_name
    html_path = briefing_out / f"{date_str}.html"
    json_path = briefing_out / f"{date_str}.json"
    summary_path = briefing_out / f"{date_str}.summary.txt"

    render_html(items, blocks, config, html_path)
    render_json(items, blocks, json_path)
    render_summary(items, blocks, config, summary_path)

    _write_index_redirect(briefing_out / "index.html", f"{date_str}.html")

    elapsed = (datetime.now() - start).total_seconds()
    result["success"] = True
    result["items_fetched"] = len(raw_items)
    result["items_after_filter"] = len(items)
    result["blocks"] = len(blocks)
    result["elapsed_seconds"] = round(elapsed, 1)
    result["display_name"] = config.get("_briefing_display_name", briefing_name)

    logger.info("Built %s in %.1fs — %d items, %d blocks",
                label, elapsed, len(items), len(blocks))
    return result


def _write_root_index(results: list[dict]) -> None:
    """Write root index.html listing all users and their briefings."""
    now = datetime.now()

    # Group results by user
    by_user: dict[str, list[dict]] = {}
    for r in results:
        uid = r["user_id"]
        if uid not in by_user:
            by_user[uid] = []
        by_user[uid].append(r)

    user_sections = []
    for uid, briefings in sorted(by_user.items()):
        links = []
        for b in briefings:
            if b.get("success"):
                bname = b["briefing"]
                display = b.get("display_name", bname)
                links.append(
                    f'<li><a href="{uid}/{bname}/index.html">{display}</a> '
                    f'— {b.get("items_after_filter", 0)} items</li>'
                )
            else:
                links.append(f'<li>{b["briefing"]}: build failed</li>')
        user_sections.append(
            f'<h2>{uid}</h2><ul>{"".join(links)}</ul>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Briefings</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 620px; margin: 48px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.6; }}
        h1 {{ font-size: 24px; margin-bottom: 4px; }}
        h2 {{ font-size: 16px; text-transform: uppercase; letter-spacing: 1px; color: #666; border-bottom: 1px solid #e0e0e0; padding-bottom: 6px; margin-top: 32px; }}
        a {{ color: #1a1a1a; }}
        li {{ margin: 6px 0; }}
        .date {{ color: #888; font-size: 14px; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Daily Briefings</h1>
    <p class="date">Built {now.strftime('%B %d, %Y at %H:%M')}</p>
    {''.join(user_sections) if user_sections else '<p>No briefings built yet.</p>'}
</body>
</html>"""

    index_path = OUT_DIR / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")
    logger.info("Wrote root index: %s", index_path)


def _write_user_index(user_id: str, briefings: list[dict]) -> None:
    """Write per-user index listing their briefings."""
    links = []
    for b in briefings:
        if b.get("success"):
            bname = b["briefing"]
            display = b.get("display_name", bname)
            links.append(
                f'<li><a href="{bname}/index.html">{display}</a> '
                f'— {b.get("items_after_filter", 0)} items</li>'
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{user_id}'s Briefings</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 620px; margin: 48px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.6; }}
        h1 {{ font-size: 24px; }}
        a {{ color: #1a1a1a; }}
        li {{ margin: 8px 0; font-size: 18px; }}
    </style>
</head>
<body>
    <h1>{user_id.title()}'s Briefings</h1>
    <ul>{''.join(links)}</ul>
    <p><a href="../index.html">&larr; All users</a></p>
</body>
</html>"""

    index_path = OUT_DIR / user_id / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")


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
    parser.add_argument("--briefing", help="Build a specific briefing only (requires --user)")
    args = parser.parse_args()

    start = datetime.now()

    if args.user and args.briefing:
        pairs = [(args.user, f"{args.briefing}.yaml")]
    elif args.user:
        all_pairs = discover_user_briefings()
        pairs = [(u, b) for u, b in all_pairs if u == args.user]
    else:
        pairs = discover_user_briefings()

    if not pairs:
        logger.error("No briefings found")
        sys.exit(1)

    logger.info("Building %d briefing(s): %s",
                len(pairs),
                ", ".join(f"{u}/{b.replace('.yaml','')}" for u, b in pairs))

    results = []
    for user_id, briefing_file in pairs:
        try:
            result = build_briefing(user_id, briefing_file)
            results.append(result)
        except Exception as e:
            bname = briefing_file.replace(".yaml", "")
            logger.error("Build failed for '%s/%s': %s", user_id, bname, e)
            results.append({
                "user_id": user_id, "briefing": bname,
                "success": False, "error": str(e)
            })

    # Write index pages
    _write_root_index(results)

    by_user: dict[str, list[dict]] = {}
    for r in results:
        uid = r["user_id"]
        if uid not in by_user:
            by_user[uid] = []
        by_user[uid].append(r)
    for uid, user_results in by_user.items():
        _write_user_index(uid, user_results)

    # Write build log
    build_log = {
        "timestamp": datetime.now().isoformat(),
        "briefings_built": len(results),
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
        status = "\u2713" if r.get("success") else "\u2717"
        label = f"{r['user_id']}/{r['briefing']}"
        if r.get("success"):
            print(f"  {status} {label}: {r.get('items_after_filter', 0)} items, "
                  f"{r.get('blocks', 0)} blocks ({r.get('elapsed_seconds', 0)}s)")
        else:
            print(f"  {status} {label}: {r.get('error', 'unknown error')}")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nTotal: {elapsed:.1f}s")

    failed = sum(1 for r in results if not r.get("success"))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
