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
    "hn": {"icon": "🟠", "unit": "posts", "sort_label": "by points"},
    "reddit": {"icon": "🔵", "unit": "posts", "sort_label": "by score"},
    "rss": {"icon": "📰", "unit": "headlines", "sort_label": "headlines"},
}

SOURCE_DISPLAY_NAMES = {
    "hn": "Hacker News",
    "reddit": "Reddit",
}

RSS_SECTION_ORDER = ["TechCrunch", "Blogs"]
DEFAULT_RSS_SECTION = "Blogs"


import re as _re


def first_sentences(text: str, n: int = 2, max_chars: int = 300) -> str:
    """Extract the first n sentences from text, capped at max_chars."""
    if not text:
        return ""
    text = text.strip()
    parts = _re.split(r'(?<=[.!?])\s+', text, maxsplit=n)
    result = " ".join(parts[:n])
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0] + "…"
    return result


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
    """Group items by source_type into display sections with rendering metadata.

    Section order: Hacker News, Reddit, then RSS grouped by the 'section'
    field from the source catalog (e.g. "TechCrunch", "Blogs").
    """
    groups: dict[str, list[dict]] = {}

    for item in items:
        source_type = item.get("source_type", "rss")
        if source_type not in groups:
            groups[source_type] = []

        item["time_ago"] = time_ago(item.get("published_dt"))
        item["summary_short"] = first_sentences(item.get("summary", ""))
        groups[source_type].append(item)

    sections = []

    # HN and Reddit as single sections
    for stype in ("hn", "reddit"):
        if stype not in groups:
            continue
        cfg = SECTION_CONFIG[stype]
        group_items = groups[stype]
        if stype == "hn":
            group_items.sort(key=lambda x: x.get("points", 0), reverse=True)
        elif stype == "reddit":
            group_items.sort(key=lambda x: x.get("score", 0), reverse=True)

        sections.append({
            "id": stype.replace("_", "-"),
            "name": SOURCE_DISPLAY_NAMES.get(stype, stype),
            "icon": cfg["icon"],
            "unit": cfg["unit"],
            "sort_label": cfg["sort_label"],
            "entries": group_items[:10],
            "source_type": stype,
        })

    # RSS items grouped by their 'section' tag
    if "rss" in groups:
        cfg = SECTION_CONFIG["rss"]
        rss_by_section: dict[str, list[dict]] = {}
        for item in groups["rss"]:
            section_name = item.get("section") or DEFAULT_RSS_SECTION
            if section_name not in rss_by_section:
                rss_by_section[section_name] = []
            rss_by_section[section_name].append(item)

        ordered = list(RSS_SECTION_ORDER)
        for name in rss_by_section:
            if name not in ordered:
                ordered.append(name)

        for section_name in ordered:
            if section_name not in rss_by_section:
                continue
            section_items = rss_by_section[section_name]
            section_id = section_name.lower().replace(" ", "-").replace("/", "-")
            sections.append({
                "id": section_id,
                "name": section_name,
                "icon": cfg["icon"],
                "unit": cfg["unit"],
                "sort_label": cfg["sort_label"],
                "entries": section_items[:10],
                "source_type": "rss",
            })

    return sections


VALID_THEMES = {"dashboard", "print"}
DEFAULT_THEME = "print"


def render_html(
    items: list[dict],
    blocks: list[dict],
    user_config: dict,
    output_path: Path,
) -> None:
    """Render the full HTML briefing."""
    theme = user_config.get("format", {}).get("theme", DEFAULT_THEME)
    if theme not in VALID_THEMES:
        logger.warning("Unknown theme %r, falling back to %s", theme, DEFAULT_THEME)
        theme = DEFAULT_THEME
    template_name = f"briefing-{theme}.html.j2"

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template(template_name)

    now = datetime.now()
    format_title = user_config.get("format", {}).get("title", "")
    display_name = user_config.get("_briefing_display_name", "")
    if format_title:
        briefing_title = format_title
    elif display_name:
        briefing_title = display_name
    else:
        user = user_config.get("user", user_config.get("cohort", {}))
        briefing_title = f"{user.get('name', 'User')}\u2019s Briefing"

    sections = build_sections(items)

    html = template.render(
        briefing_title=briefing_title,
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
        briefing_name = user_config.get("_briefing_name", "briefing")
        date_str = datetime.now().strftime("%Y-%m-%d")
        briefing_url = f"https://mrlerner.github.io/daily-briefing/{user_id}/{briefing_name}/{date_str}.html"

    summary = template.render(
        blocks=blocks,
        top_items=top_items,
        briefing_url=briefing_url,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary.strip() + "\n", encoding="utf-8")
    logger.info("Wrote summary: %s", output_path)
