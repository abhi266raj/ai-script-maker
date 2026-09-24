"""Configuration persistence manager for studio and project preferences."""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO_CONFIG_FILE = os.path.join(BASE_DIR, "studio_config.json")
PROJECT_CONFIG_FILE = os.path.join(BASE_DIR, "project_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_engine": "first_local_then_agy",
    "default_tone": "😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)",
    "default_duration": 10,
    "batch_count": 1,
    "max_retries": 5,
    "story_source": "🇮🇳 India Top Stories & Breaking",  # merged Source+Category dropdown
    "selected_headline": "",
    "selected_script_index": 0,
    "default_angle": "Funny & Relatable",
    "character_count": 3,
    "scene_style": "Dialogue",
    "workflow_mode": "⚡ Continuous",
}


def reset_to_defaults() -> Dict[str, Any]:
    """Reset all preferences to clean defaults and synchronize across files."""
    cfg = DEFAULT_CONFIG.copy()
    save_all_config(cfg)
    return cfg


def load_config() -> Dict[str, Any]:
    """Load configuration from disk, falling back to defaults."""
    cfg = DEFAULT_CONFIG.copy()
    
    # Try studio_config.json first
    if os.path.exists(STUDIO_CONFIG_FILE):
        try:
            with open(STUDIO_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg.update(data)
                return cfg
        except Exception as e:
            # Config defaults are legitimate, but a corrupt file must be visible.
            logger.warning("Ignoring corrupt studio config %s (%s); using defaults.", STUDIO_CONFIG_FILE, e)

    # Fallback to project_config.json if available
    if os.path.exists(PROJECT_CONFIG_FILE):
        try:
            with open(PROJECT_CONFIG_FILE, "r", encoding="utf-8") as f:
                pdata = json.load(f)
                for k in DEFAULT_CONFIG:
                    if k in pdata:
                        cfg[k] = pdata[k]
                return cfg
        except Exception as e:
            logger.warning("Ignoring corrupt project config %s (%s); using defaults.", PROJECT_CONFIG_FILE, e)

    save_all_config(cfg)
    return cfg


def save_config(key: str, value: Any) -> Dict[str, Any]:
    """Save a single configuration setting and synchronize across config files."""
    cfg = load_config()
    cfg[key] = value
    save_all_config(cfg)
    return cfg


def save_all_config(cfg: Dict[str, Any]) -> None:
    """Save configuration to disk across both studio_config.json and project_config.json."""
    try:
        with open(STUDIO_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save studio_config.json: {e}")

    # Synchronize relevant keys into project_config.json if it exists
    if os.path.exists(PROJECT_CONFIG_FILE):
        try:
            with open(PROJECT_CONFIG_FILE, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            pdata.update({k: v for k, v in cfg.items() if k in pdata or k in DEFAULT_CONFIG})
            with open(PROJECT_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(pdata, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to sync project_config.json: {e}")
