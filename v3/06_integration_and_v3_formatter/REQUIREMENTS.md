# Sub-Feature 06: Integration, Canonical Formatter & Validation Gate Specification

> **Parent Specification:** [`V3.md`](file:///Users/abhiraj/Documents/news/agent/V3.md) — *Master Scriptwriting Guidelines (All Sections)*  
> **Status:** Pending Implementation  
> **Feature Branch:** `feature/v3-06-integration-formatter`

---

## 1. Objective & Scope

Unify all sub-features (01 through 05) into an integrated, production-grade V3 pipeline:
1. **Canonical V3 Screenplay Formatter:** Implement `format_v3_screenplay()` in [`core/screenplay_formatter.py`](file:///Users/abhiraj/Documents/news/agent/core/screenplay_formatter.py) supporting all markdown headers, delivery cues, shot structures, timestamps, visual anchors, and audio bleed.
2. **Chief Editor Pipeline Integration:** Wire V3 data structures, execution options, and stage transitions through [`agents/chief_editor.py`](file:///Users/abhiraj/Documents/news/agent/agents/chief_editor.py).
3. **Comprehensive V3 Deterministic Gate:** Implement an integrated code-level verification gate verifying 100% adherence to all V3 constraints.
4. **Studio UI Integration:** Update Streamlit Studio ([`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py)) to display V3 screenplay views, collapsible shot structures, cadence metrics, and copyable script outputs.

---

## 2. Canonical V3 Screenplay Output Format

```markdown
[Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]

SCENE DETAIL:
⚬ Government municipal licensing office, dull fluorescent lighting, quiet midday tension

CHARACTERS & CLOTHING:
⚬ VIKRAM: Junior food inspector, beige safari suit, brown leather shoulder bag
⚬ ANJALI: Commercial restaurant manager, tailored black formal trousers, emerald green silk blouse

### SCENE 1: The Surprise Inspection [8 Seconds]

#### Shot 1
Camera Focus & Action: Low-angle tracking push-in on Vikram standing at the inspection counter. Stationary clipboard resting flat on the counter edge.
Audio/SFX [0:00 – 0:02]: Dull office hum + rhythmic ceiling fan click
Text Overlay: SURPRISE AUDIT

⚬ VIKRAM [Stern] [0:01 – 0:05.5]:
  "नए फूड सेफ्टी नियमों के तहत इस किचन का लाइसेंस तुरंत प्रभाव से सस्पेंड किया जाता है!"

### SCENE 2: The Escalation Behind the Partition [8 Seconds]
Visual Anchor: Vikram's shoulder and the stationary clipboard visible through the glass serving hatch in the background.
Audio Bleed: Ceiling fan clicking echo trails across [0:00 – 0:02] behind the door.

#### Shot 1
Camera Focus & Action: Medium close-up on Anjali on the other side of the partition. She leans back abruptly with an incredulous expression.
Audio/SFX [0:00 – 0:02]: Fan click bleed + sharp intake of breath

⚬ ANJALI [Outraged] [0:01 – 0:05.5]:
  "सस्पेंड? पिछले हफ्ते ही आपकी टीम ने पूरी इंस्पेक्शन रिपोर्ट को क्लीन चिट दी थी!"
```

---

## 3. Deterministic V3 Validation Gate Checklist

The validation gate runs automatically in Stage 6 before final output sign-off:
- [ ] **V3-01:** Every scene duration $\le 10$ seconds.
- [ ] **V3-02:** Scene headings match `### SCENE X: Title [X Seconds]`.
- [ ] **V3-03:** Shot headings match `#### Shot X` without timestamps.
- [ ] **V3-04:** Audio, dialogue, and SFX timestamps start at `[0:00]` per scene.
- [ ] **V3-05:** Explicit `[0:XX – 0:XX]` attached to every dialogue line and SFX cue.
- [ ] **V3-06:** Dialogue accompanied by valid cadence cues `[... ~X.X wps]`.
- [ ] **V3-07:** Visual anchors present for all scenes $N \ge 2$.
- [ ] **V3-08:** Audio bleed specified for all scene transitions $N \ge 2$.
- [ ] **V3-09:** Cast isolation respected: no character appears in consecutive scenes.
- [ ] **V3-10:** No active prop manipulation verbs detected; props staged stationary.
- [ ] **V3-11:** Dialogue in pure Devanagari Hindi; directions and text overlays in English.

---

## 4. UI / UX Enhancements ([`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py))

- Provide a **"V3 Master Screenplay"** view tab in the final output section alongside raw director prompts and teleprompter text.
- Render Scene blocks with visual tags: `⏱️ 8s`, `🎭 Delivery Cadence`, `🔗 Visual Anchor`, `🔊 Audio Bleed`.
- Display a one-click **"Copy V3 Screenplay"** button.

---

## 5. Acceptance Criteria & Test Plan

- [ ] Complete automated test suite in `tests/test_v3_pipeline.py` verifying full end-to-end V3 script generation.
- [ ] 100% of integration checks in the V3 validation gate pass on generated scripts.
- [ ] Zero breaking changes to existing continuous/stepwise execution paths.
