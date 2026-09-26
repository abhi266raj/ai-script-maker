# Sub-Feature 02: Timestamp Scoping & Cadence Specification

> **Parent Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/V3.md) — *Timestamp Scoping & Precision* & *Performance & Delivery Direction*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-02-timestamp-cadence`

---

## 1. Objective & Scope

Implement high-precision, scene-scoped timing and actor delivery cues:
1. **Per-Scene Reset:** Reset all audio, dialogue, and SFX timestamps to `[0:00]` at the start of each individual scene.
2. **Line-Level & SFX Timestamps:** Attach explicit start-to-end timestamps `[0:XX – 0:XX]` directly to every spoken dialogue line and sound effect cue.
3. **Performance Delivery Cues:** Accompany every spoken dialogue line with an emotional energy tag and words-per-second (wps) cadence metric (e.g. `[Frantic delivery ~2.8 wps]` or `[Deadpan comedic shrug ~2.0 wps]`).

---

## 2. Functional Requirements & User Stories

### FR-02.1: Per-Scene Timestamp Reset to 0:00
- Every scene begins its timing context from zero: `0:00`.
- All events within Scene $X$ occur between `[0:00]` and `[0:XX]` where $XX \le 10$ seconds.
- Cumulative whole-reel timestamps (e.g. `0:15 - 0:22`) are strictly prohibited within scene bodies.

### FR-02.2: Line-Level Direct Timestamps
- Timestamps must NOT be detached in arbitrary section blocks. They must precede or attach directly to dialogue lines and SFX cues:
  - SFX format: `Audio/SFX [0:00 – 0:02]: <Description>`
  - Dialogue format: `<CHARACTER> [0:01 – 0:06] [<Delivery Cue>]: "<Dialogue>"`
- The duration of the line (`end_time - start_time`) must be mathematically feasible for the syllable and word count at the indicated cadence.

### FR-02.3: Performance & Speed Cadence Cues
- Update Stage 3 Dialogue Writer prompt to lift the blanket ban on brackets for delivery cues.
- Require every dialogue line to include:
  - Emotional energy descriptor (e.g., `Frantic delivery`, `Deadpan comedic shrug`, `Breathless realization`, `Sharp sarcastic smirk`).
  - Speed cadence estimate: `~X.X wps` (words per second, typically 2.0 to 3.2 wps for Hindi speech).
- Syntax: `[<Emotional Energy> ~X.X wps]`.

---

## 3. Screenplay Formatter Rendering Example

```markdown
### SCENE 1: The Inflation Shock [7 Seconds]

#### Shot 1
Camera Focus & Action: Dynamic push-in on Ramesh inspecting the grocery receipt.
Audio/SFX [0:00 – 0:02]: Receipt paper snap + muted market murmur
Text Overlay: BILL CHECK

RAMESH [0:01 – 0:06] [Frantic delivery ~2.8 wps]:
"सिर्फ चार टमाटर और बिल सीधा ढाई सौ पार कर गया!"
```

---

## 4. Deterministic Code Validators

1. **`validate_scene_timestamp_scoping(scene)`:**
   - Verifies all timestamps in the scene start $\ge \text{0:00}$ and end $\le \text{scene.duration\_sec}$.
   - Flags any timestamp exceeding the scene's declared duration.
2. **`validate_delivery_cue_format(dialogue_line)`:**
   - Regex matches `r"\[[\w\s/]+~\d+\.\d+\s*wps\]"`.
   - Validates that wps falls within physiological Hindi speech limits ($1.8 \le \text{wps} \le 3.8$).
3. **`validate_cadence_consistency(dialogue_text, start_sec, end_sec, wps)`:**
   - Calculates actual words in `dialogue_text`.
   - Expected duration $\approx \text{word\_count} / \text{wps}$.
   - Flags discrepancies where dialogue duration differs from timestamp window by $> 1.5\text{s}$.

---

## 5. Acceptance Criteria & Test Plan

- [ ] Unit tests in `tests/test_v3_timestamp_cadence.py` verify per-scene `[0:00]` resets.
- [ ] Test line-level and SFX timestamp parser.
- [ ] Test delivery cue parser and wps validator.
- [ ] Automated regression tests ensure no empty or malformed timestamps are emitted.
