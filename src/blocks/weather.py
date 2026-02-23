"""Weather block fetcher using wttr.in (free, no API key required)."""

import logging
import time
from datetime import datetime

import requests

logger = logging.getLogger("briefing.blocks.weather")

WTTR_TIMEOUT = 20
MAX_RETRIES = 3


def fetch_weather(block_config: dict) -> dict | None:
    """Fetch weather forecast and return block output.

    Args:
        block_config: Block config from briefing.yaml with 'location', 'days', 'highlight'.

    Returns:
        Block output dict, or None if weather fetch fails.
    """
    location = block_config.get("location", "New York, NY")
    num_days = block_config.get("days", 7)
    highlight_condition = block_config.get("highlight", "sunny")
    label = block_config.get("label", "Weather")

    data = _fetch_wttr(location)
    if not data or "weather" not in data:
        logger.warning("No weather data available for '%s'", location)
        return None

    days = []
    highlights = []

    for day_data in data["weather"][:num_days]:
        date_str = day_data["date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = date_obj.strftime("%a")
        day_full = date_obj.strftime("%A, %b %d")

        hourly = day_data.get("hourly", [])
        conditions = [h["weatherDesc"][0]["value"] for h in hourly if h.get("weatherDesc")]
        primary_condition = max(set(conditions), key=conditions.count) if conditions else "Unknown"

        high = int(day_data.get("maxtempF", 0))
        low = int(day_data.get("mintempF", 0))

        day_entry = {
            "date": date_str,
            "day": day_name,
            "day_full": day_full,
            "high": high,
            "low": low,
            "condition": primary_condition,
        }
        days.append(day_entry)

        # Check highlight condition
        sunny_keywords = ["sunny", "clear", "fair"]
        if highlight_condition.lower() in ["sunny", "clear"]:
            match_keywords = sunny_keywords
        else:
            match_keywords = [highlight_condition.lower()]

        sunny_count = sum(1 for c in conditions if any(k in c.lower() for k in match_keywords))
        if sunny_count >= 2:
            highlights.append(day_name)

    summary_line = _build_summary(highlights, days, highlight_condition)

    result = {
        "type": "weather",
        "label": label,
        "location": location,
        "days": days,
        "highlights": highlights,
        "summary_line": summary_line,
    }

    logger.info("Weather for %s: %d days, %d highlighted", location, len(days), len(highlights))
    return result


def _fetch_wttr(location: str) -> dict | None:
    """Fetch weather JSON from wttr.in with retries."""
    url = f"https://wttr.in/{requests.utils.quote(location)}?format=j1"

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=WTTR_TIMEOUT,
                                headers={"User-Agent": "DailyBriefingBuilder/1.0"})
            resp.raise_for_status()
            data = resp.json()
            if "weather" in data:
                return data
            raise ValueError("Response missing 'weather' key")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 3 * (attempt + 1)
                logger.warning("Weather attempt %d failed: %s, retrying in %ds", attempt + 1, e, wait)
                time.sleep(wait)
            else:
                logger.error("Weather fetch failed after %d attempts: %s", MAX_RETRIES, e)
    return None


def _build_summary(highlights: list[str], days: list[dict], condition: str) -> str:
    """Build a human-readable summary line for the weather block."""
    if not highlights:
        return f"No particularly {condition} days in the forecast."

    if len(highlights) == 1:
        return f"{condition.capitalize()} {highlights[0]} \u2014 good day to be outside."

    day_list = ", ".join(highlights[:-1]) + " and " + highlights[-1]
    return f"{condition.capitalize()} {day_list} \u2014 good days to be outside."
