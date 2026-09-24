"""Tapri-leakage guard tests.

A chai tapri / tea stall must NEVER appear as a default location, persona, or
instruction example. It is allowed only when the verified news itself is
genuinely about a tea stall.
"""
import pytest

from agents.hook_strategist import sanitize_scene_location, validate_scene_locations
from agents.contextual_selector import ContextualSceneCharacterSelectorAgent
from agents.dialogue_writer import get_character_personas, get_creative_guidelines
from agents.scene_catalog import SCENE_STYLE_SETUPS
from core.prompt_matrix import build_tailored_instruction


# --- Stage 2 deterministic guard -------------------------------------------

def test_sanitize_replaces_non_topical_tapri():
    assert sanitize_scene_location("Bustling chai tapri", "WFO mandate news", "", "Corporate office") == "Corporate office"


def test_sanitize_keeps_topical_tapri():
    assert sanitize_scene_location("Bustling chai tapri", "Chai prices rise in cities", "", "Corporate office") == "Bustling chai tapri"


def test_sanitize_keeps_non_tapri_location():
    assert sanitize_scene_location("Modern corporate office", "WFO mandate", "", "") == "Modern corporate office"


def test_sanitize_devanagari_tapri_non_topical():
    out = sanitize_scene_location("Roadside टपरी", "Metro rail expansion", "", "")
    assert "टपरी" not in out


def test_validate_scene_locations_counts_replacements():
    from core.models import SceneSettingOption
    scenes = [
        SceneSettingOption(location_name="Campus chai tapri"),
        SceneSettingOption(location_name="Corporate office"),
    ]
    cleaned, replaced = validate_scene_locations(scenes, news_topic="WFO mandate", fallback_location="IT park")
    assert replaced == 1
    assert cleaned[0].location_name == "IT park"
    assert cleaned[1].location_name == "Corporate office"


# --- Contextual selector: no tapri default ----------------------------------

@pytest.fixture()
def selector():
    return ContextualSceneCharacterSelectorAgent()


def test_friends_do_not_trigger_tapri(selector):
    r = selector.select_scene_and_characters(news_topic="Two friends discuss WFO mandate", character_count=2, duration_sec=15)
    assert "tapri" not in r["setting"].lower()


def test_street_word_does_not_trigger_tapri(selector):
    r = selector.select_scene_and_characters(news_topic="Street vendors protest new rule", character_count=2, duration_sec=15)
    assert "tapri" not in r["setting"].lower()


def test_teacher_does_not_trigger_tapri(selector):
    r = selector.select_scene_and_characters(news_topic="Teacher strike over pay hike", character_count=2, duration_sec=15)
    assert "tapri" not in r["setting"].lower()


def test_genuine_chai_news_may_use_tapri(selector):
    r = selector.select_scene_and_characters(news_topic="Chai prices rise across cities", character_count=2, duration_sec=15)
    assert "tapri" in r["setting"].lower()


# --- Generated master instruction -------------------------------------------

def test_instruction_has_no_tapri_example():
    inst = build_tailored_instruction(
        topic="WFO mandate news", duration_sec=15, tone="x",
        angle="Funny & Relatable", scene_style="Dialogue", character_count=2,
    )
    assert "friends at a local chai tapri" not in inst
    assert "Do NOT default to a chai tapri" in inst


def test_instruction_has_no_operational_params():
    inst = build_tailored_instruction(
        topic="WFO mandate news", duration_sec=15, tone="x",
        angle="Funny & Relatable", scene_style="Dialogue", character_count=2,
    )
    assert "script version" not in inst
    assert "retry attempt" not in inst


# --- Personas and catalog ----------------------------------------------------

def test_no_tapri_personas_for_generic_topic():
    personas = get_character_personas("Dialogue", 2, "Funny", "Funny", topic_or_script="Municipal election rally and voting")
    assert not any("tapri" in p.lower() or "टपरी" in p or "chai" in p.lower() for p in personas)


def test_no_tapri_in_creative_guidelines():
    g = get_creative_guidelines("Dialogue", 2, "😂 Comedy & Sarcastic Banter (ह्यूमर)", "Funny & Relatable")
    assert "tapri" not in g.lower()


def test_no_tapri_setups_in_catalog():
    for style, setups in SCENE_STYLE_SETUPS.items():
        for s in setups:
            blob = " ".join(str(v) for v in s.values()).lower()
            assert "tapri" not in blob, f"tapri setup in {style}: {s.get('id')}"
            assert "टपरी" not in blob, f"टपरी setup in {style}: {s.get('id')}"
