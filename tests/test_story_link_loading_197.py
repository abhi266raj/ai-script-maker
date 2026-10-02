"""v1.7 (#197) — "Fetch story link" / "Verify same story" must own their
loading state (HIG §3).

Regression test: both buttons used to run their network work inside the
click handler with a detached ``with st.spinner(...)`` — neither button
disabled nor showed progress while its own work ran. The fix uses the
two-phase in-flight pattern (same shape as #191's fine-tune fix):

  phase 1 (click):  ``_inflight_claim(session, key, url)`` + ``st.rerun()``
                    so the button repaints disabled with the native spinner;
  phase 2 (rerun):  ``_inflight_take(session, key, url)`` gates the network
                    work; the marker is always cleared in a ``finally`` and
                    failures are persisted in session state so the clearing
                    rerun cannot swallow them.

``app.py`` is a top-level Streamlit script (not importable), so these tests
do two things:

1. Exec the REAL ``_inflight_*`` helpers from ``app.py`` source (verbatim)
   and unit-test the state machine with plain dicts.
2. Assert structurally via the AST that each button wires
   ``disabled=``/``icon="spinner"`` to its own in-flight flag, that the
   network work moved out of the click handler into the phase-2 block, and
   that phase 2 always clears its marker and persists failures loudly.

Run: python -m pytest tests/test_story_link_loading_197.py -q
"""
import ast
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "app.py"


def _load_inflight_helpers():
    """Exec the real _inflight_* helpers from app.py source (verbatim)."""
    src = APP_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    wanted = {"_inflight_claim", "_inflight_take", "_inflight_clear"}
    segs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            segs[node.name] = ast.get_source_segment(src, node)
    missing = wanted - set(segs)
    assert not missing, f"in-flight helpers missing from app.py: {missing}"
    ns = {}
    for name in wanted:
        exec(segs[name], ns)  # noqa: S102 - test harness on trusted repo code
    return ns


_helpers = _load_inflight_helpers()
_inflight_claim = _helpers["_inflight_claim"]
_inflight_take = _helpers["_inflight_take"]
_inflight_clear = _helpers["_inflight_clear"]


# ---------------------------------------------------------------------------
# Part 1 — the in-flight state machine (real helpers, plain-dict session)
# ---------------------------------------------------------------------------

def test_claim_then_take_same_url_runs_work():
    session = {}
    _inflight_claim(session, "k", "https://example.com/a")
    assert _inflight_take(session, "k", "https://example.com/a") is True


def test_take_without_claim_does_not_run():
    assert _inflight_take({}, "k", "https://example.com/a") is False


def test_stale_claim_for_other_url_is_cleared_and_skipped():
    session = {}
    _inflight_claim(session, "k", "https://example.com/a")
    # Selection changed before the rerun landed: must NOT run work for the
    # stale URL, and the stale marker must be gone.
    assert _inflight_take(session, "k", "https://example.com/b") is False
    assert "k" not in session
    assert _inflight_take(session, "k", "https://example.com/a") is False


def test_clear_releases_button_after_phase2():
    # Simulates phase 2's `finally`: the marker is dropped even if the
    # network call raised, so the button never sticks disabled.
    session = {}
    _inflight_claim(session, "k", "https://example.com/a")
    assert _inflight_take(session, "k", "https://example.com/a") is True
    try:
        try:
            raise RuntimeError("boom")
        finally:
            _inflight_clear(session, "k")
    except RuntimeError:
        pass
    assert _inflight_take(session, "k", "https://example.com/a") is False


def test_latest_claim_wins():
    session = {}
    _inflight_claim(session, "k", "https://example.com/a")
    _inflight_claim(session, "k", "https://example.com/b")
    assert _inflight_take(session, "k", "https://example.com/a") is False
    # 'a' was superseded and its (stale) claim cleared by the take above.
    _inflight_claim(session, "k", "https://example.com/b")
    assert _inflight_take(session, "k", "https://example.com/b") is True


def test_claim_preserves_unrelated_session_keys():
    session = {"other": 1}
    _inflight_claim(session, "k", "https://example.com/a")
    _inflight_clear(session, "k")
    assert session == {"other": 1}


# ---------------------------------------------------------------------------
# Part 2 — structural: each button owns its loading state
# ---------------------------------------------------------------------------

def _verifier_fn():
    tree = ast.parse(APP_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_render_story_link_verifier":
            return node
    raise AssertionError("_render_story_link_verifier not found in app.py")


def _button_calls(fn):
    """All `st.button(...)` calls inside the verifier: (call, key_substring)."""
    found = []
    for node in ast.walk(fn):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "button"
        ):
            continue
        key_dump = ""
        for kw in node.keywords:
            if kw.arg == "key":
                key_dump = ast.dump(kw.value)
        found.append((node, key_dump))
    return found


def _button_for(calls, marker):
    for call, key_dump in calls:
        if marker in key_dump:
            return call
    raise AssertionError(f"no st.button with key containing {marker!r}")


def _kw(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    raise AssertionError(f"st.button missing keyword {name!r}: {ast.dump(call)}")


def _click_handler_body(fn, button_call):
    """Body statements of `if st.button(...):` — the button call is the If's
    *test*, the click handler is its body."""
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and any(
            n is button_call for n in ast.walk(node.test)
        ):
            return node.body
    raise AssertionError("could not find click-handler if-body")


def _calls_named(stmts, *names):
    found = []
    for node in ast.walk(ast.Module(body=list(stmts), type_ignores=[])):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
            found.append(node)
    return found


def _spinner_withs(stmts, text):
    found = []
    for node in ast.walk(ast.Module(body=list(stmts), type_ignores=[])):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            call = item.context_expr
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "spinner"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == text
            ):
                found.append(node)
    return found


def test_fetch_button_disabled_with_spinner_while_running():
    fn = _verifier_fn()
    call = _button_for(_button_calls(fn), "sl_fetch")
    disabled = _kw(call, "disabled")
    assert "fetch_running" in ast.dump(disabled), (
        "Fetch button must bind disabled= to its in-flight flag")
    icon = _kw(call, "icon")
    icon_dump = ast.dump(icon)
    assert "spinner" in icon_dump and "fetch_running" in icon_dump, (
        "Fetch button must paint icon='spinner' while in-flight")
    label = call.args[0]
    label_dump = ast.dump(label)
    assert "Fetching" in label_dump and "fetch_running" in label_dump, (
        "Fetch button label must switch to a loading label while in-flight")


def test_verify_button_disabled_with_spinner_while_running():
    fn = _verifier_fn()
    call = _button_for(_button_calls(fn), "sl_verify")
    disabled = _kw(call, "disabled")
    assert "verify_running" in ast.dump(disabled), (
        "Verify button must bind disabled= to its in-flight flag")
    icon = _kw(call, "icon")
    icon_dump = ast.dump(icon)
    assert "spinner" in icon_dump and "verify_running" in icon_dump, (
        "Verify button must paint icon='spinner' while in-flight")
    label = call.args[0]
    label_dump = ast.dump(label)
    assert "Verifying" in label_dump and "verify_running" in label_dump, (
        "Verify button label must switch to a loading label while in-flight")


def test_fetch_network_work_runs_in_phase2_not_in_click_handler():
    fn = _verifier_fn()
    calls = _button_calls(fn)
    fetch_call = _button_for(calls, "sl_fetch")
    click_body = _click_handler_body(fn, fetch_call)
    assert not _calls_named(click_body, "fetch_story_page", "extract_story_images"), (
        "click handler must only claim the in-flight marker + rerun — "
        "no network work inside the button click")
    assert _calls_named(click_body, "_inflight_claim"), (
        "click handler must claim the in-flight marker (phase 1)")
    # Phase 2: the `if _fetch_running:` block holds the network work.
    phase2 = None
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and "fetch_running" in ast.dump(node.test):
            if any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "fetch_story_page"
                for n in ast.walk(node)
            ):
                phase2 = node.body
    assert phase2 is not None, "no `if _fetch_running:` phase-2 block found"
    assert _spinner_withs(phase2, "Fetching the article page…"), (
        "phase 2 must keep the status spinner while the fetch runs")


def test_verify_network_work_runs_in_phase2_not_in_click_handler():
    fn = _verifier_fn()
    calls = _button_calls(fn)
    verify_call = _button_for(calls, "sl_verify")
    click_body = _click_handler_body(fn, verify_call)
    assert not _calls_named(click_body, "verify_same_story_llm", "verify_same_story_code"), (
        "click handler must only claim the in-flight marker + rerun — "
        "no verification work inside the button click")
    assert _calls_named(click_body, "_inflight_claim"), (
        "click handler must claim the in-flight marker (phase 1)")
    phase2 = None
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and "verify_running" in ast.dump(node.test):
            if any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in ("verify_same_story_llm", "verify_same_story_code")
                for n in ast.walk(node)
            ):
                phase2 = node.body
    assert phase2 is not None, "no `if _verify_running:` phase-2 block found"
    assert _spinner_withs(phase2, "Verifying the story…"), (
        "phase 2 must keep the status spinner while verification runs")


def _phase2_try(fn, flag):
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and flag in ast.dump(node.test):
            for child in ast.walk(node):
                if isinstance(child, ast.Try):
                    return child
    raise AssertionError(f"no try/except inside `if {flag}:` phase 2")


def test_phase2_always_clears_marker_and_persists_failures():
    fn = _verifier_fn()
    for flag, err_marker in (("_fetch_running", "fetch"), ("_verify_running", "verify")):
        attempt = _phase2_try(fn, flag)
        # finally: marker cleared — the button can never stick disabled.
        assert attempt.finalbody, f"`if {flag}:` phase 2 must have a finally block"
        assert any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_inflight_clear"
            for n in ast.walk(ast.Module(body=list(attempt.finalbody), type_ignores=[]))
        ), f"`if {flag}:` finally must call _inflight_clear"
        # except: failure persisted to session state (the clearing rerun
        # would drop a bare st.error) — failures stay loud.
        assert attempt.handlers, f"`if {flag}:` phase 2 must catch exceptions"
        persisted = False
        for h in attempt.handlers:
            for stmt in h.body:
                for t in ast.walk(stmt):
                    if (
                        isinstance(t, ast.Assign)
                        and any(
                            isinstance(tg, ast.Subscript)
                            and isinstance(tg.value, ast.Attribute)
                            and tg.value.attr == "session_state"
                            for tg in t.targets
                        )
                    ):
                        persisted = True
        assert persisted, (
            f"`if {flag}:` except handler must persist the failure into "
            "st.session_state so the clearing rerun cannot swallow it")
