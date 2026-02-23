"""Load and validate briefing.yaml files, resolve source catalogs."""

import json
import logging
import os
from pathlib import Path

import jsonschema
import yaml

logger = logging.getLogger("briefing.config")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
SOURCES_DIR = PROJECT_ROOT / "sources"
USERS_DIR = PROJECT_ROOT / "users"


def load_schema() -> dict:
    schema_path = SCHEMAS_DIR / "briefing.schema.json"
    with open(schema_path) as f:
        return json.load(f)


def validate_config(config: dict) -> None:
    """Validate a briefing config dict against the JSON schema. Raises on failure."""
    schema = load_schema()
    jsonschema.validate(instance=config, schema=schema)


def load_catalog(catalog_name: str) -> dict:
    """Load a curated source catalog from sources/<name>.yaml."""
    catalog_path = SOURCES_DIR / f"{catalog_name}.yaml"
    if not catalog_path.exists():
        raise FileNotFoundError(f"Source catalog not found: {catalog_path}")
    with open(catalog_path) as f:
        return yaml.safe_load(f)


def load_user_config(user_id: str) -> dict:
    """Load and validate a user's briefing.yaml, resolving catalog references."""
    config_path = USERS_DIR / user_id / "briefing.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Briefing config not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    validate_config(config)

    # Resolve sources_from catalog
    if "sources_from" in config:
        catalog = load_catalog(config["sources_from"])
        config["_catalog"] = catalog
        logger.info("Loaded catalog '%s' with sections: %s",
                     config["sources_from"],
                     [k for k in catalog if k not in ("catalog", "name", "description")])

    return config


def discover_users() -> list[str]:
    """Find all user IDs in the users/ directory (skipping _cohorts)."""
    users = []
    if not USERS_DIR.exists():
        return users
    for entry in sorted(USERS_DIR.iterdir()):
        if entry.is_dir() and not entry.name.startswith("_"):
            config_path = entry / "briefing.yaml"
            if config_path.exists():
                users.append(entry.name)
    return users
