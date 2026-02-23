"""Load and validate briefing configs, resolve extends and source catalogs."""

import json
import logging
from pathlib import Path

import jsonschema
import yaml

logger = logging.getLogger("briefing.config")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
SOURCES_DIR = PROJECT_ROOT / "sources"
BRIEFINGS_DIR = PROJECT_ROOT / "briefings"
USERS_DIR = PROJECT_ROOT / "users"


def load_schema() -> dict:
    schema_path = SCHEMAS_DIR / "briefing.schema.json"
    with open(schema_path) as f:
        return json.load(f)


def validate_config(config: dict) -> None:
    """Validate a merged briefing config against the JSON schema."""
    schema = load_schema()
    jsonschema.validate(instance=config, schema=schema)


def load_catalog(catalog_name: str) -> dict:
    """Load a curated source catalog from sources/<name>.yaml."""
    catalog_path = SOURCES_DIR / f"{catalog_name}.yaml"
    if not catalog_path.exists():
        raise FileNotFoundError(f"Source catalog not found: {catalog_path}")
    with open(catalog_path) as f:
        return yaml.safe_load(f)


def load_briefing_definition(name: str) -> dict:
    """Load a shared briefing definition from briefings/<name>.yaml."""
    path = BRIEFINGS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Briefing definition not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def _merge_configs(base: dict, overrides: dict) -> dict:
    """Merge user overrides on top of a base briefing definition.

    Top-level keys from overrides replace base keys (shallow merge).
    The 'extends' key is consumed and not passed through.
    """
    merged = dict(base)
    for key, value in overrides.items():
        if key == "extends":
            continue
        merged[key] = value
    return merged


def load_user_briefing(user_id: str, briefing_file: str) -> dict:
    """Load a user's briefing subscription, resolving extends and catalogs.

    Args:
        user_id: Directory name under users/
        briefing_file: YAML filename (e.g. "ai-engineering.yaml")

    Returns:
        Fully resolved config dict ready for the build pipeline.
    """
    config_path = USERS_DIR / user_id / briefing_file
    if not config_path.exists():
        raise FileNotFoundError(f"Briefing config not found: {config_path}")

    with open(config_path) as f:
        user_config = yaml.safe_load(f) or {}

    # Resolve extends
    if "extends" in user_config:
        base = load_briefing_definition(user_config["extends"])
        config = _merge_configs(base, user_config)
        logger.info("Resolved extends '%s' for %s/%s",
                     user_config["extends"], user_id, briefing_file)
    else:
        config = user_config

    # Ensure version is set
    config.setdefault("version", 1)

    # Inject user identity if not present
    if "user" not in config and "cohort" not in config:
        briefing_name = briefing_file.replace(".yaml", "")
        config["user"] = {"id": user_id, "name": user_id.title()}

    # Ensure delivery defaults exist
    config.setdefault("delivery", {"time": "07:00", "timezone": "UTC"})

    validate_config(config)

    # Resolve sources_from catalog
    if "sources_from" in config:
        catalog = load_catalog(config["sources_from"])
        config["_catalog"] = catalog
        logger.info("Loaded catalog '%s' with sections: %s",
                     config["sources_from"],
                     [k for k in catalog if k not in ("catalog", "name", "description")])

    # Stash the briefing name for rendering
    briefing_name = briefing_file.replace(".yaml", "")
    config["_briefing_name"] = briefing_name
    if "name" in config:
        config["_briefing_display_name"] = config["name"]
    else:
        config["_briefing_display_name"] = briefing_name.replace("-", " ").title()

    return config


def discover_user_briefings() -> list[tuple[str, str]]:
    """Find all (user_id, briefing_file) pairs in the users/ directory.

    Scans users/ for directories containing .yaml files.
    Skips directories starting with _ (like _cohorts).

    Returns:
        List of (user_id, yaml_filename) tuples.
    """
    results = []
    if not USERS_DIR.exists():
        return results
    for user_dir in sorted(USERS_DIR.iterdir()):
        if not user_dir.is_dir() or user_dir.name.startswith("_"):
            continue
        for yaml_file in sorted(user_dir.glob("*.yaml")):
            results.append((user_dir.name, yaml_file.name))
    return results
