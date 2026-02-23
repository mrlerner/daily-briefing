"""Render briefing output: HTML, JSON, and summary text."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("briefing.render")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"

SECTION_CONFIG = {
    "rss": {"icon": "📰", "unit": "headlines", "sort_label": "headlines"},
    "hn": {"icon": "🟠", "unit": "posts", "sort_label": "by points"},
    "reddit": {"icon": "🔵", "unit": "posts", "sort_label": "by score"},
}

SOURCE_DISPLAY_NAMES = {
    "hn": "Hacker News",
    "reddit": "Reddit",
}


def time_ago(published_dt: datetime | None) -> str:
    """Convert a datetime to a human-readable relative timestamp."""
    if not published_dt:
        return ""
    now = datetime.now(timezone.utc)
    diff = now - published_dt
    seconds = diff.total_seconds()

    if seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins}m ago" if mins > 0 else "just now"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    else:
        days = int(seconds / 86400)
        return f"{days}d ago"


def build_sections(items: list[dict]) -> list[dict]:
    """Group items by source_type into display sections with rendering metadata."""
    groups: dict[str, list[dict]] = {}

    for item in items:
        source_type = item.get("source_type", "rss")
        if source_type not in groups:
            groups[source_type] = []

        item["time_ago"] = time_ago(item.get("published_dt"))
        groups[source_type].append(item)

    section_order = ["rss", "hn", "reddit"]
    sections = []

    for stype in section_order:
        if stype not in groups:
            continue
        cfg = SECTION_CONFIG.get(stype, {"icon": "📰", "unit": "items", "sort_label": "items"})

        # Re-sort within section by platform-native ranking
        group_items = groups[stype]
        if stype == "hn":
            group_items.sort(key=lambda x: x.get("points", 0), reverse=True)
        elif stype == "reddit":
            group_items.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Group RSS items by source name for display
        if stype == "rss":
            # Show RSS as individual source sections
            rss_by_source: dict[str, list[dict]] = {}
            for item in group_items:
                src = item.get("source", "News")
                if src not in rss_by_source:
                    rss_by_source[src] = []
                rss_by_source[src].append(item)

            for src_name, src_items in rss_by_source.items():
                section_id = src_name.lower().replace(" ", "-").replace("/", "-")
                sections.append({
                    "id": section_id,
                    "name": src_name,
                    "icon": cfg["icon"],
                    "unit": cfg["unit"],
                    "sort_label": cfg["sort_label"],
                    "entries": src_items[:10],
                    "source_type": stype,
                })
        else:
            display_name = SOURCE_DISPLAY_NAMES.get(stype, stype)
            section_id = stype.replace("_", "-")
            sections.append({
                "id": section_id,
                "name": display_name,
                "icon": cfg["icon"],
                "unit": cfg["unit"],
                "sort_label": cfg["sort_label"],
                "entries": group_items[:10],
                "source_type": stype,
            })

    return sections


def render_html(
    items: list[dict],
    blocks: list[dict],
    user_config: dict,
    output_path: Path,
) -> None:
    """Render the full HTML briefing."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("briefing.html.j2")

    now = datetime.now()
    user = user_config.get("user", user_config.get("cohort", {}))
    user_name = user.get("name", "User")

    sections = build_sections(items)

    html = template.render(
        briefing_title=f"{user_name}\u2019s Briefing",
        date_formatted=now.strftime("%B %d, %Y"),
        time_formatted=now.strftime("%H:%M"),
        sections=sections,
        blocks=blocks,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Wrote HTML: %s", output_path)


def render_json(
    items: list[dict],
    blocks: list[dict],
    output_path: Path,
) -> None:
    """Render the JSON output (items + blocks, without non-serializable fields)."""
    clean_items = []
    for item in items:
        clean = {k: v for k, v in item.items() if k != "published_dt"}
        clean_items.append(clean)

    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "items": clean_items,
        "blocks": blocks,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote JSON: %s", output_path)


def render_summary(
    items: list[dict],
    blocks: list[dict],
    user_config: dict,
    output_path: Path,
    briefing_url: str = "",
) -> None:
    """Render the plain-text summary for chat delivery."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("summary.txt.j2")

    summary_count = user_config.get("format", {}).get("summary_items", 4)
    top_items = items[:summary_count]

    if not briefing_url:
        user = user_config.get("user", user_config.get("cohort", {}))
        user_id = user.get("id", "unknown")
        date_str = datetime.now().strftime("%Y-%m-%d")
        briefing_url = f"https://mrlerner.github.io/daily-briefing/{user_id}/{date_str}.html"

    summary = template.render(
        blocks=blocks,
        top_items=top_items,
        briefing_url=briefing_url,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary.strip() + "\n", encoding="utf-8")
    logger.info("Wrote summary: %s", output_path)
