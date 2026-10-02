"""Issue #338 (display) — the Library master list truncated titles to 38
chars, chopping the ``· v{n}`` version suffix. Two same-topic stories
("...LIVE · v1" / "...LIVE · v2") rendered byte-identically in the list
and read as "one story repeated twice", even though the data was never
duplicated. ``_short_list_title`` must never truncate the suffix away.

Run: python -m pytest tests/test_library_list_titles_338.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import library_ui as lui  # noqa: E402


LONG_V1 = ("Internet suspended around Delhi's Jantar Mantar ahead of "
           "protest against CEC Gyanesh Kumar; Dipke warns of nationwide "
           "unrest | LIVE · v1")
LONG_V2 = LONG_V1.replace("· v1", "· v2")


def test_version_suffix_survives_truncation():
    r1 = lui._short_list_title(LONG_V1)
    r2 = lui._short_list_title(LONG_V2)
    assert len(r1) <= 38 and len(r2) <= 38
    assert r1.endswith("· v1") and r2.endswith("· v2")
    assert r1 != r2, "v1/v2 rows must be distinguishable in the list"


def test_short_title_untouched():
    assert lui._short_list_title("Tiny · v1") == "Tiny · v1"
    assert lui._short_list_title("x" * 38) == "x" * 38


def test_long_title_without_suffix_truncates():
    r = lui._short_list_title("A very long headline without any version suffix at all here")
    assert len(r) <= 38
    assert r.endswith("…")


def test_empty_title():
    assert lui._short_list_title("") == "Untitled"
    assert lui._short_list_title(None) == "Untitled"
