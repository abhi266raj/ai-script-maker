# Sub-Feature 02: Timestamp Scoping & Cadence Specification

> **Parent Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/V3.md) — *Timestamp Scoping & Precision* & *Performance & Delivery Direction*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-02-timestamp-cadence`

---

## 1. Objective & Scope

Implement high-precision, scene-scoped timing and actor delivery cues:
1. **Per-Scene Reset:** Reset all audio, dialogue, and SFX timestamps to `[0:00]` at the start of each individual scene.
2. **Canonical Line Format:** Format every spoken line as `CHARACTER [Tone] [0:XX – 0:XX]: "Dialogue"`.
3. **Pacing Relative to Scene Runtime Without Rigid Word Limits:** Pace speech at roughly **2 to 3 words per second** (urgent/fast tones near 3 wps, calm/sarcastic tones near 2 wps) relative to the scene runtime, completely replacing rigid word limits.
4. **Fractional Second Support:** Support high-precision fractional timestamps (e.g. `[0:01 – 0:04.5]`).

---

## 2. Functional Requirements & User Stories

### FR-02.1: Per-Scene Timestamp Reset to 0:00
- Every scene begins its timing context from zero: `0:00`.
- All events within Scene $X$ occur between `[0:00]` and `[0:XX]` where $XX \le 10$ seconds.
- Cumulative whole-reel timestamps (e.g. `0:15 - 0:22`) are strictly prohibited within scene bodies.

### FR-02.2: Line-Level Direct Timestamps & Canonical Spoken Syntax
- Spoken lines MUST strictly follow the canonical syntax:
  ```text
  CHARACTER [Tone] [0:XX – 0:XX]:
    "Dialogue"
  ```
  or on a single line:
  ```text
  CHARACTER [Tone] [0:XX – 0:XX]: "Dialogue"
  ```
- Timestamps can use whole or fractional seconds (e.g., `[0:01 – 0:04.5]`, `[0:05 – 0:09]`).
- SFX format: `Audio/SFX [0:00 – 0:02]: <Description>`.

### FR-02.3: Pacing Speech at 2 to 3 WPS (No Rigid Word Limits)
- Rigid word count formulas (e.g., "max 11 words per beat", "recommended 10 words") are **REMOVED**.
- Instead, dialogue length is governed dynamically by the timestamp window duration and tone:
  - **Urgent / Frantic / Fast tones:** Paced near **3 words per second** (~2.8 to 3.2 wps).
  - **Calm / Sarcastic / Deadpan tones:** Paced near **2 words per second** (~1.8 to 2.2 wps).
- Target words for a line are determined by:
  $$\text{Target Words} \approx (\text{End Time} - \text{Start Time}) \times \text{Pacing WPS}$$

---

## 3. Screenplay Formatter Rendering Example

```markdown
### SCENE 1: The Kitchen Chaos [9 Seconds]

#### Shot 1
Camera Focus & Action: Handheld push-in on Rameshwar in the doorway looking wide-eyed at the counter. Stationary whiskey bottle lying empty on its side.
Audio/SFX [0:00 – 0:01.5]: Glass roll clink + breathless commotion

⚬ RAMESHWAR [Frantic] [0:01 – 0:04.5]:
  "अरे भगाने गए तो हाथ में काट लिया, और खुद पूरी बोतल गटक गई!"

⚬ SUNITA [Sarcastic] [0:05 – 0:09]:
  "बिना चखने के पूरी बोतल साफ, अब वन विभाग ही संभाले!"
```

---

## 4. Deterministic Code Validators

1. **`validate_scene_timestamp_scoping(scene)`:**
   - Verifies all timestamps in the scene start $\ge \text{0:00}$ and end $\le \text{scene.duration\_sec}$.
   - Flags any timestamp exceeding the scene's declared duration.
2. **`validate_spoken_line_syntax(dialogue_line)`:**
   - Validates that lines match `r"^(?:[⚬•]\s*)?[A-Z\u0900-\u097F\s]+\s*\[[\w\s/]+\]\s*\[\d+:\d+(?:\.\d+)?\s*[–\-]\s*\d+:\d+(?:\.\d+)?\]:\s*(?:\n\s*)?\"[^\"]+\"$"`.
   - Rejects unformatted, untimed, or missing-tone dialogue lines.
3. **`validate_pacing_wps(dialogue_text, start_sec, end_sec, tone)`:**
   - Computes line duration $\Delta t = \text{end\_sec} - \text{start\_sec}$.
   - Computes words in `dialogue_text`: $\text{actual\_wps} = \text{words} / \Delta t$.
   - Validates that speech rate sits naturally in the 2.0 to 3.2 wps range (urgent/fast $\approx 3$ wps, calm/sarcastic $\approx 2$ wps).
   - Flags unrealistic dialogue that would require frantic mumbling ($>3.5$ wps) or awkward pauses ($<1.6$ wps).

---

## 5. Acceptance Criteria & Test Plan

- [ ] Unit tests in `tests/test_v3_timestamp_cadence.py` verify per-scene `[0:00]` resets.
- [ ] Test line-level and SFX timestamp parser.
- [ ] Test delivery cue parser and wps validator.
- [ ] Automated regression tests ensure no empty or malformed timestamps are emitted.
