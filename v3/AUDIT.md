# V3 Requirements Audit: Critical Analysis, Practical Feasibility & Risk Assessment

> **Subject:** Comprehensive Audit of [`v3/V3.md`](file:///Users/abhiraj/Documents/news/agent/v3/V3.md) Specifications  
> **Evaluation Lenses:** 
> 1. 🗑️ **What is Nonsense / High-Risk Trap?** (Rules that contradict storytelling, hallucinate math, or set up models to fail)
> 2. 🟢 **What is Possible & High-Value?** (Practical specs that genuinely upgrade output quality & video stability)
> 3. ⚠️ **What Seems Like an Issue?** (Subtle landmines, coordination bottlenecks, and timing conflicts)

---

## 1. Executive Verdict

The V3 specifications represent a **major cinematic and technical upgrade** over legacy v1.2, particularly for **AI video generation stability** (Veo / Sora) and **eliminating rigid word budgets**.

However, **3 specific requirements will cause severe pipeline failures if implemented naively without code guardrails**:
1. Expecting an LLM to accurately calculate fractional seconds and words-per-second (`wps`) in its head.
2. Interpreting "Cast Isolation" as forcing an oversized ensemble on short 15–30s reels rather than alternating solo camera framing.
3. Completely discarding cumulative time without providing a continuous timeline for voiceover recording and video editing.

---

## 2. 🗑️ What is "Nonsense" or High-Risk Traps?

### Trap 1: Relying on the LLM to Do Precise Timestamp & WPS Math
* **The Spec:** `CHARACTER [Tone] [0:XX – 0:XX]: "Dialogue"`, pacing speech at 2 to 3 wps.
* **The Reality (Why it's a Trap):**  
  LLMs **cannot count syllables or calculate fractional speech durations reliably**. An LLM will easily write an 18-word Hindi sentence, slap `[0:01 – 0:04.5]` on it, and hallucinate that it paced it at "2.5 wps" (when in reality, 18 words in 3.5 seconds is 5.1 wps — unperformable rapid-fire gibberish).
* **The Engineering Fix:**  
  **Do NOT let the LLM generate arbitrary timestamps.** The LLM should generate the tone (`[Frantic]`, `[Sarcastic]`) and dialogue. The Python post-processor must count the Hindi words, apply the tone's pacing velocity ($3.0$ wps for urgent, $2.0$ wps for sarcastic), and **deterministically calculate the timestamps** `[start_time – end_time]`.

---

### Trap 2: Blind Literal Interpretation of "Cast Isolation" on Short Reels
* **The Spec:** *"Rotate the on-screen cast so that characters featured in one scene do not appear in the subsequent scene."*
* **The Reality (Why it's a Trap if taken literally):**  
  If a creator requests a 15-second reel (2 scenes), and the system interprets this as requiring 4 completely different people who never see each other, the reel cannot tell a coherent human story. A 15-second reel cannot introduce 4 strangers.
* **Why the Rule Exists:**  
  In generative video models (Veo, Sora, Kling), putting two people in the same shot across cuts causes faces to morph, clothes to swap, and limbs to blend.
* **The Sensible Solution:**  
  Clarify that in 2-character dialogue reels, **Cast Isolation means Alternating Solo Camera Framing**:
  - **Scene 1 (Shot 1):** Character A is solo in frame (facing camera / medium close-up).
  - **Scene 2 (Shot 1):** Character B is solo in frame (reverse angle reaction).
  - **Scene 3 (Shot 1):** Character A is solo in frame again.  
  This satisfies $\text{Cast}(N) \cap \text{Cast}(N+1) = \emptyset$ visually on-screen without requiring a confusing cast of 6 random strangers.

---

### Trap 3: Active Prop Interactions (The Old Coherence Logic)
* **The Spec:** Minimal Prop Execution — stationary props only.
* **Why Legacy Was Nonsense:**  
  Legacy `screenplay_coherence.py` used regex to force characters to *"unfold the morning newspaper"*, *"sip cutting chai"*, *"thrust phone forward"*, or *"press official ink stamp"*. In AI video engines, hands interacting with moving objects produce catastrophic generative hallucinations (6 fingers, morphing cups, floating newspapers).
* **The V3 Fix:**  
  V3 rightly identifies this as a failure mode. Props must stay stationary (resting on a counter or table) while actors react through facial expressions and body posture.

---

## 3. 🟢 What is Possible & High-Value? (The Best Parts of V3)

| Feature | Feasibility | Value to Production | Why It Works |
|---|:---:|:---:|---|
| **Eliminating Rigid Word Limits** | 🟢 **100% Feasible** | 🌟🌟🌟🌟🌟 **Huge** | No more arbitrary rejections because a sentence was 12 words instead of 11. Sentences breathe naturally. |
| **10-Second Scene Cap** | 🟢 **100% Feasible** | 🌟🌟🌟🌟🌟 **Huge** | Directly aligns with AI video model limits (Veo clips are 5s to 10s max). Prevents temporal degradation. |
| **Stationary Minimal Props** | 🟢 **100% Feasible** | 🌟🌟🌟🌟 **High** | Eliminates 80% of video generation artifacts (phantom hands, morphing objects). |
| **`### SCENE X` & `#### Shot X`** | 🟢 **100% Feasible** | 🌟🌟🌟🌟 **High** | Professional screenplay standard. Clean separation between narrative scene and camera shot. |
| **Visual Anchors Across Cuts** | 🟢 **100% Feasible** | 🌟🌟🌟 **High** | Gives the video prompt engineer a concrete background element to maintain continuity. |
| **Per-Scene `[0:00]` Reset** | 🟢 **100% Feasible** | 🌟🌟🌟 **High** | Matches the clip generation duration of AI video engines. |

---

## 4. ⚠️ What Seems Like an Issue / Potential Landmines?

### Issue 1: Cumulative vs. Scene-Local Timestamps for Voiceover & Editing
* **The Problem:**  
  While scene-local `[0:00]` is ideal for individual Veo video clip prompts, a human voiceover artist or an ElevenLabs text-to-speech audio stitcher needs to know where in the **overall reel** this scene occurs (e.g. Is Scene 2 at second 8 or second 15?).
* **The Solution:**  
  - Screenplay body uses **Scene-Local `[0:00 – 0:04.5]`** per V3 specs.
  - Teleprompter / Audio view includes the **Cumulative Reel Time** in the header:  
    `### SCENE 2: The Escalation [8 Seconds] (Cumulative: 0:08 – 0:16)`  
    This gives the video generator what it needs without breaking voiceover workflows.

---

### Issue 2: Audio Bleed Across Independent Video Clips
* **The Problem:**  
  Audio Bleed (`"Muffled market siren from Scene 1 trails into [0:00 – 0:02] under the opening beat"`) is a sound-design guideline for post-production audio mixing. If an AI video model generates silent video clips, audio bleed only takes effect if an audio synthesizer or human editor reads the screenplay.
* **The Solution:**  
  Keep Audio Bleed as an explicit sound cue in the screenplay and director prompts, but ensure deterministic code validators don't crash if an engine only generates visual prompts.

---

### Issue 3: Pacing Discrepancies Between Hindi & English Words
* **The Problem:**  
  Hindi Devanagari text contains postpositions and auxiliary verbs (e.g. *रहा है*, *गया था*, *के लिए*). Counting words in Hindi requires simple whitespace splitting, but syllable count can vary.
* **The Solution:**  
  Calibrate the pacing window:
  - 3.0 wps for Urgent/Frantic is roughly 12–15 words in a 4–5 second line.
  - 2.0 wps for Sarcastic/Deadpan is roughly 8–10 words in a 4–5 second line.
  Python can validate this in under 1 millisecond using `len(text.split()) / duration`.

---

## 5. Summary Action Checklist for Implementation

| Issue Identified | Resolution in V3 Implementation |
|---|---|
| **LLM Math Hallucination** | Python post-processor deterministically computes line duration $\Delta t$ and timestamps from words & tone. |
| **Cast Isolation Confusion** | Formalized as **Alternating Solo Camera Framing** (not requiring 4+ strangers on a 15s reel). |
| **Voiceover Timeline Confusion** | Scene-local timestamps in screenplay; cumulative duration preserved in scene headers. |
| **Rigid Word Count Elimination** | `core/metrics.py` word ceilings deleted; replaced with speech velocity ($2.0 \le \text{wps} \le 3.2$). |
| **Prop Generation Artifacts** | `screenplay_coherence.py` purged of active verbs; replaced with stationary staging. |

---

## 6. 🔥 Risk Matrix & Circuit Breakers: Which Features Can Be Stopped?

When executing V3, not all features are equally vital or safe. If a feature triggers excessive retries, degrades creative storytelling, or destabilizes generation, **the system must have explicit circuit breakers to stop or decouple that feature without stopping the rest of the V3 pipeline.**

### 🛑 Circuit Breaker Decision Table

| Sub-Feature | Risk Level | Primary Risk Mode | Can It Be Stopped If Risky? | Circuit Breaker Action & Fallback Plan |
|---|:---:|---|:---:|---|
| **05. Cast Isolation & Rotation** | 🔴 **HIGH** | **Story Destruction & Retry Loops:** Forcing 4–6 characters on short 15–30s reels destroys comedic ping-pong; hard isolation check triggers repeated validation failures. | **YES (🛑 Stop First)** | **Disable Cast Isolation Validator:**<br>• Stop enforcing $\text{Cast}(N) \cap \text{Cast}(N+1) = \emptyset$.<br>• Fall back to standard 2-person dialogue with alternating camera angles (over-the-shoulder / reverse-angle solo framing).<br>• Rest of V3 (10s cap, pacing, shots) continues unaffected. |
| **04. Audio Bleed Transitions** | 🟡 **MEDIUM** | **Acoustic Clutter & Redundancy:** Video generation engines produce silent video; audio bleed is non-functional unless audio synthesizer/human mixer is attached. | **YES (🛑 Stop Second)** | **Disable Audio Bleed Requirement:**<br>• Stop mandating trailing SFX carryover into `[0:00 – 0:02]`.<br>• SFX cues become self-contained per scene.<br>• Visual anchors and consequence carryover remain active. |
| **04. Cascade Scene Regeneration** | 🟡 **MEDIUM** | **Stepwise UX Sluggishness:** If editing Scene 1 forces regenerating all subsequent scenes because of rigid consequence links, user iteration becomes painful. | **YES (🛑 Decouple)** | **Decouple Strict Consequence Links:**<br>• In Stepwise mode, allow editing Scene 1 without forcibly invalidating Scene 2.<br>• Visual anchors become advisory rather than blocking. |
| **02. LLM-Generated Timestamps** | 🟡 **MEDIUM** | **Mathematical Hallucination:** LLM invents unrealistic fractional timestamps (e.g. 15 words in 2 seconds). | **YES (🛑 Decouple Math)** | **Decouple Timestamp Generation from LLM:**<br>• Stop asking the LLM to output timestamps.<br>• LLM outputs tone and dialogue only.<br>• Python deterministically calculates start/end times from word count and tone velocity. |
| **03. Minimal Stationary Props** | 🟢 **LOW** | **Visual Flatness:** Actors standing with no prop interaction might look slightly static. | **NO (Partial Loosening Only)** | **Do NOT Stop Entirely:**<br>• Active prop manipulation (sipping, unfolding) must stay banned to prevent video morphing.<br>• Can loosen to allow characters to point at or rest hands on stationary props. |
| **01. Scene & Shot Hierarchy (10s Cap)** | 🟢 **LOW** | **Narrative Segmentation:** Breaking longer stories into 10s chunks. | **NO (CORE FOUNDATION)** | **Cannot Be Stopped:**<br>• 10s cap is a physical hard limit of AI video generators (Veo/Sora).<br>• If dynamic derivation fails, fall back to standard math: $\text{scenes} = \lceil \text{target\_seconds} / 7.5 \rceil$. |
| **02. Elimination of Rigid Word Limits** | 🟢 **LOW** | **Overly Verbose Sentences.** | **NO (CORE UPGRADE)** | **Cannot Be Stopped:**<br>• Returning to rigid 11-word limits causes awkward truncated dialogue.<br>• Controlled via $2.0 \le \text{wps} \le 3.2$ velocity check. |

---

### 🛡️ Pipeline Failure Prevention Hierarchy

If production testing encounters blockers during V3 execution, stop features in this exact order:

```
[Level 1 Emergency]: STOP Sub-Feature 05 (Cast Isolation hard checks)
  ↳ Revert to 2-character dialogue with alternating camera focus.

[Level 2 Emergency]: STOP Sub-Feature 04 (Audio Bleed checks)
  ↳ Revert to self-contained per-scene SFX cues.

[Level 3 Emergency]: DECOUPLE Sub-Feature 02 (LLM timestamp generation)
  ↳ Compute all timestamps deterministically in Python post-processing.
```
**Under NO circumstances do we roll back:**
- The 10-second scene duration cap (Sub-Feature 01).
- The elimination of rigid word limits (Sub-Feature 02).
- The stationary minimal props rule (Sub-Feature 03).
These three form the non-negotiable core of V3 generative video stability.

