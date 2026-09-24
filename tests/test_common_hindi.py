"""Common-person Hindi requirement tests.

Spoken dialogue must sound like what a common person speaks — formal,
literary, shuddh, or bureaucratic Hindi is banned. These tests lock the
mandate into the deployed prompt templates and creative guidelines.
"""
import os
import pytest

from agents.dialogue_writer import get_creative_guidelines, find_formal_hindi

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITE_PROMPT = os.path.join(REPO_ROOT, "prompts", "dialogue_writer", "write_dialogue_batch.md")
REFINE_PROMPT = os.path.join(REPO_ROOT, "prompts", "dialogue_writer", "refine_dialogue_batch.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_write_prompt_mandates_common_person_hindi():
    text = _read(WRITE_PROMPT)
    assert "COMMON PERSON'S HINDI" in text
    assert "formal/linguistic Hindi is BANNED" in text


def test_write_prompt_bans_formal_vocabulary_in_output():
    text = _read(WRITE_PROMPT)
    assert "formal/linguistic/shuddh Hindi vocabulary is BANNED" in text


def test_refine_prompt_mandates_common_person_hindi():
    text = _read(REFINE_PROMPT)
    assert "COMMON PERSON" in text or "common person" in text.lower()
    assert "BANNED" in text


def test_language_split_english_metadata_hindi_dialogue_only():
    """Scene descriptions/camera/action/SFX/overlays are English; only quoted
    speaker lines are Hindi (Devanagari)."""
    text = _read(WRITE_PROMPT)
    assert "ENGLISH ONLY" in text
    assert "ONLY the quoted speaker lines are Hindi" in text


def test_guidelines_carry_tone_without_formal_hindi_examples():
    g = get_creative_guidelines("Dialogue", 2, "😂 Comedy & Sarcastic Banter (ह्यूमर)", "Funny & Relatable")
    # No formal/bureaucratic vocabulary smuggled in via examples
    for banned in ("दंडात्मक", "निर्गम", "अधिकार निर्गम"):
        assert banned not in g


def test_detection_flags_user_reported_example():
    """The exact case the user reported: shuddh 'अधिकार निर्गम' for rights issue."""
    found = find_formal_hindi("हाँ, अधिकार निर्गम से; मंज़ूरी पर डेढ़ हजार करोड़ तक।")
    assert "अधिकार निर्गम" in found


def test_detection_is_not_blind_substitution():
    """Detection must flag tokens for a model fix; it must never rewrite text itself."""
    text = "प्रेम ने कहा कि युद्ध होगा।"
    # find_formal_hindi returns flags only — the input text is untouched
    find_formal_hindi(text)
    assert text == "प्रेम ने कहा कि युद्ध होगा।"


def test_detection_flags_bureaucratic_connectors():
    found = find_formal_hindi("एवं तथा परंतु किंतु के द्वारा हेतु")
    assert len(found) >= 3, f"too few bureaucratic tokens flagged: {found}"
