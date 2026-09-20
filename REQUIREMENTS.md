# 📋 Product Requirements Document (PRD): Hindi Short Reel Script Agent

**Project:** Autonomous Hindi Short Reel Script Generator with Specialized Multi-Agent Architecture  
**Architecture:** **8 Dedicated Specialized Pipeline Agents with Autonomous Self-Healing Hand-offs**  
**Server & App Management:** **Auto-Starting Daemon & Native macOS Application Bundle**  
**Engine Controls:** **In-Studio Engine Selector + Smart Engine Guesser (`smart_guess_engine`)**  
**Tones:** **18+ Categorized Viral Tones (Funny & Relatable as Default)**  
**AI Video Integration:** **Google Flow / Google Veo 9:16 Prompt Generation & Feasibility Gate**  
**Interface:** Streamlit Native Web App & Terminal CLI  
**Language:** Hindi (हिंदी)  

---

## 1. Native App & Auto-Starting Server Options

To solve the issue where opening a bookmarked web app fails because the local Python server is offline, we provide two recommended auto-start solutions on macOS:

### 🌟 Solution A (Recommended Desktop App Bundle): `Hindi Reel Studio.app`
- A native macOS Application bundle (`Hindi Reel Studio.app`) and executable launcher (`HindiReelStudio.command`).
- **How it works:**
  1. Whenever you double-click the app, it instantly pings `http://127.0.0.1:8501/`.
  2. If the Python server is offline, it **automatically starts the server in the background** as a silent daemon.
  3. Once the server confirms `200 OK`, it launches the dedicated standalone application window (no browser toolbars or URL bar).
  4. Requires zero terminal commands. You can keep `Hindi Reel Studio.app` in your macOS Dock or Applications folder!

### 🔄 Solution B (Always-On Background Service): `setup_background_service.sh`
- Uses native macOS `launchd` (`~/Library/LaunchAgents/com.hindireel.studio.plist`).
- **How it works:**
  - Automatically starts the server on boot and keeps it running permanently in the background.
  - You can bookmark `http://localhost:8501` in Safari or Chrome, or use Safari's **"Add to Dock"**, and the app will **always connect instantly** because the server is kept alive automatically by macOS!
  - Run `./setup_background_service.sh` to enable.
  - Run `./stop_background_service.sh` to disable.

---

## 2. In-Studio Engine Selection & Smart Guesser

```
                    [ Input: Duration, Tone, News Story ]
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ 🤖 Smart Engine Guesser Analysis                 │
             │                                                  │
             │ • If Duration <= 15s & Casual Tone:              │
             │   ──► Recommends Local Apple FM (Ultra-fast, 0s) │
             │                                                  │
             │ • If Duration >= 45s or Analytical/Investigative:│
             │   ──► Recommends Antigravity AGY (Deep reasoning)│
             │                                                  │
             │ • Otherwise (Standard 20s - 40s):                │
             │   ──► Recommends Hybrid Mode (Local FM first,    │
             │       with automatic AGY fallback)               │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ "✨ Apply Guessed Engine" 1-Click Button          │
             │ + In-Studio Dropdown for All 3 Engine Options    │
             └──────────────────────────────────────────────────┘
```

---

## 3. The 8 Specialized Pipeline Agents

1. 🔍 **`NewsValidationAgent` (`news_validator`)**: Audits news authenticity against live RSS wire dispatches.
2. 🎯 **`HookAndAngleAgent` (`hook_strategist`)**: Crafts viral 0–3s scroll-stopping Hindi hooks and CTAs.
3. 📜 **`DialogueNarrationAgent` (`dialogue_writer`)**: Writes natural spoken Hindi dialogue matching exact tone and duration.
4. ⏱️ **`WordCountDurationAgent` (`timing_auditor`)**: Mathematical word-count & speech rate (~2.3 w/s) auditor. Triggers self-healing if limits exceed.
5. 🎬 **`SceneVisualsDirectorAgent` (`scene_director`)**: Breaks dialogue into scenes, B-roll visuals, Hindi text & SFX transitions.
6. 🎥 **`AIVideoPromptAgent` (`video_prompt_engineer`)**: Synthesizes cinematic 9:16 Google Flow / Veo / Sora prompts.
7. 🛡️ **`VideoQualityGateAgent` (`video_quality_gate`)**: Verifies 3–5s clip feasibility, continuity & safety.
8. 👑 **`ChiefEditorCoordinatorAgent` (`chief_editor`)**: Manages feedback hand-offs, aggregates artifacts, and oversees publication.

---

## 4. Studio UI Layout & Control Requirements

The Streamlit studio must keep the working area balanced and predictable:

- The main page uses a **60% Settings / 40% Output** split on wide screens.
- **Story & Topic and Generate appear first** in the settings column; the full Configuration panel appears below them.
- **Copy Script Functionality:** Complete generated screenplays and individual scene breakdowns feature a direct one-click clipboard copy action in the preview interface.
- The news refresh control is a compact text **Refresh** button beside the Story & Topic heading, with a tooltip explaining its action.
- **News Categories:** Full support for live RSS categorization including:
  - `🇮🇳 India Top Stories & Breaking`
  - `🏛️ Indian Politics, Elections & Governance` (real-time coverage of Parliament, elections, Election Commission, and national governance policies)
  - `🪔 Indian Culture, Heritage & Festivals`
  - `🚀 India Tech, Space (ISRO) & Startups`
  - `💻 Technology & AI`
  - `🌍 World News`
  - `📈 Business & Economy`
  - `🔥 India Trending & Viral` (in Trending mode)
- **Source Mode, Category & Headline Persistence:** Source mode (`chosen_source_mode`), news category (`chosen_news_cat`), and the chosen headline/topic are saved to persistent configuration (`project_config.json` and `studio_config.json`) and session state. Live headlines remain securely cached and **NEVER** re-fetch on background reruns or setting adjustments unless the user explicitly clicks the **Refresh** button or changes the Category dropdown. Changing the headline dropdown updates dynamic widget keys (`topic_input_{headline_rev}`) to guarantee immediate UI synchronization without stale client text overwriting preferences.
- Duration, Scripts, Characters, and Retries use consistent native **stepper number inputs** rather than dropdowns.
- **Max Retries Allowed:** The Retries stepper is strictly bounded to the allowed maximum (`min_value=1, max_value=5`, default 5). The multi-agent coordinator dynamically loops up to this configured maximum retry threshold during self-healing cycles.
- Stepper increments are consistent and practical:
  - Duration changes in 5-second increments.
  - Scripts, Characters, and Retries change in increments of 1.
- Scene style is selectable as Dialogue, Speech, Narration, Interview, Debate, Monologue, or Lament.
- **Single Continuous Video Reel (No Background Repetition):** The screenplay constitutes ONE continuous vertical video reel. Scene 1 establishes the setting and primary visual prop. Subsequent scenes MUST NOT repeat or re-explain background context; they must advance camera angles, prop interactions, and character reactions smoothly.
- **Dynamic Narrative Ordering (Fun First, News Second):** The screenplay does not robotically force news into sentence 1. For funny, sarcastic, and relatable angles, Scene 1 opens with a hilarious situational hook or reaction blunder, Scene 2 reveals the verified news development as the trigger/twist, and Scene 3 delivers the punchline payoff.
- **Script-Grounded Demographic Diversity:** Character personas are selected contextually based on the story topic and domain, representing the socioeconomic diversity of India:
  - *Police / Crime / Traffic*: Police Sub-Inspector & Gig Delivery Partner
  - *Court / Legal*: High Court Advocate & Kirana Trader
  - *Politics / Elections / Governance*: Ward Corporator Netaji & Street Chai Tapri Owner
  - *Corporate / Tech / WFO*: Rich Tech Founder & Working-Class Auto Driver
  - *Healthcare*: Government Hospital Doctor & Construction Worker
  - *Education*: Government School Teacher & Street Sabziwala
  - *Government Office*: Government Babu / Clerk & UPSC Aspirant
  - *Rural / Agriculture*: Village Sarpanch & City-Returned Youth
  - *Anti-Misinformation / Safety Guard*: Fictional characters are never given real living politician names (e.g. Rahul, Modi, Kejriwal) to eliminate impersonation and defamation flags.
- **Industry-Standard Screenplay Production Standards:**
  1. **Write Physical Action Lines:** Scene descriptions and running beats must NOT paste core themes, news summaries, or prompt instructions. Describe *only* what we physically see and hear the actors doing with their bodies, props, and facial expressions.
  2. **Remove Contradictory Camera Cues:** When specifying a "single continuous shot," camera instructions must NEVER include camera cuts, jump cuts, or reverse-angle cuts. Camera notes must be minimal unless essential to the punchline (e.g., panning smoothly from one character to another, or pulling back to frame both).
  3. **Fix Tone Clashes:** Character descriptions, wardrobe, and action lines must authentically match the genre of the scene. Tragic labels (e.g., "Bereaved", "Grieving") are strictly forbidden in comedy and relatable reels.
  4. **Delete Over-Engineered Metadata:** Rigid microsecond timestamps, speech-rate calculations (`~2.3 w/s`), and mathematical word-count formulas are internal auditing details and must NEVER appear in the user-facing screenplay. The output must provide pure visual beats and spoken Hindi dialogues.
  5. **Canonical Screenplay Structure & Reference Samples:**
     All copied screenplays and previews must strictly adhere to the canonical industry format across both standard and ultra-fast durations:

     #### Reference Sample A: Standard 20-Second Reel (Smooth Continuous Handheld Take)
     ```text
     [Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]

     SCENE DETAIL:
     ⚬	A bustling local Indian street chai tapri. Casual, everyday public space vibe with background customers, street noise, and boiling tea.

     CHARACTERS & CLOTHING:
     ⚬	ANANYA: Casual college-going attire (e.g., jeans and a simple kurti).
     ⚬	VIKRAM: Everyday street casual wear (e.g., t-shirt and jeans).

     [Time: 0:00 - 0:06]
     Camera Focus & Action: Single continuous handheld take starting on Ananya. She looks frustrated, holding a glass of cutting chai and gesturing animatedly toward Vikram.
     Text Overlay (Optional): After 3 years of studying...
     Audio/SFX: Tapri background noise, clinking glasses + Light comedic 'whoosh' sound.
     ANANYA: "यार विक्रम, तीन साल किताबें घिसने के बाद भी एक अदद नौकरी नसीब नहीं हुई!"

     [Time: 0:06 - 0:13]
     Camera Focus & Action: The camera pans smoothly to Vikram without cutting. Vikram takes a slow, dramatic sip of his tea, raises an eyebrow, and points at his phone screen.
     Text Overlay (Optional): Wait for the solution...
     Audio/SFX: Tea slurping sound + Soft comedic ding.
     VIKRAM: "चिंता मत कर, सरकार ने आज ही 50,000 नई भर्तियों का नोटिफिकेशन जारी कर दिया है!"

     [Time: 0:13 - 0:20]
     Camera Focus & Action: The camera pulls back slightly to frame both of them together. Ananya’s jaw drops in shock, dropping her biscuit into the chai, while Vikram grins mischievously.
     Text Overlay (Optional): Notification Out Now!
     Audio/SFX: Splash sound + Upbeat closing sting.
     ANANYA: "क्या बात कर रहा है! जल्दी लिंक भेज, चाय का बिल आज मेरी तरफ से!"
     ```

     #### Reference Sample B: Ultra-Fast 10-Second Reel (Fast Whip-Pan / Snappy Dynamic Take)
     ```text
     [Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]

     SCENE DETAIL:
     ⚬	A bustling local Indian street chai tapri. Very fast-paced, high-energy vibe to fit the 10-second limit.

     CHARACTERS & CLOTHING:
     ⚬	ANANYA: Casual college-going attire (e.g., jeans and a simple kurti).
     ⚬	VIKRAM: Everyday street casual wear (e.g., t-shirt and jeans).

     [Time: 0:00 - 0:03]
     Camera Focus & Action: Fast whip-pan to Ananya slamming a book on the tapri counter.
     Text Overlay (Optional): No Jobs?
     Audio/SFX: Fast whoosh + heavy book slam.
     ANANYA: "डिग्री ले ली, नौकरी कहाँ है?"

     [Time: 0:03 - 0:06]
     Camera Focus & Action: Quick pan to Vikram shoving his phone screen into the frame.
     Audio/SFX: Record scratch effect.
     VIKRAM: "सिस्टम को स्टूडेंट नहीं, अंधभक्त चाहिए!"

     [Time: 0:06 - 0:10]
     Camera Focus & Action: Fast pull back to frame both. Ananya mockingly tosses her book aside.
     Text Overlay (Optional): Need new coaching!
     Audio/SFX: Comedic drum punchline.
     ANANYA: "तो भाई, मेरा भी अंधभक्ति कोचिंग में एडमिशन करा दे!"
     ```

  6. **Context-Driven & User-Configurable Optional Visual Elements:**
     - **Context-Driven Inclusion:** Text Overlays (`Text Overlay (Optional):`) and sound effects (`Audio/SFX:`) are optional visual and audio embellishments added only when the script or narrative context calls for a specific punchline, hook, or comedic effect (e.g., Beat 1 hook question, Beat 3 punchline callout). They are omitted from intermediate reaction turns (like Beat 2 in Sample B) to keep the visual focus clean and avoid overlay clutter.
     - **User Preference Control:** The studio UI provides interactive toggles (*"Include Text Overlay (Optional)"* and *"Include Audio/SFX"*) allowing users to include or omit optional text overlays and SFX cues when copying or downloading screenplays based on preference.

- Character count and scene style are generation inputs, not display-only settings; the writer and scene director must honor them when assigning dialogue to scenes.
- An editable **Instruction** field appears above Generate with a dedicated **"🔄 Update Instruction"** action button. The instruction dynamically regenerates whenever any configuration or selection changes (Duration, Tone, Angle, Scripts, Retries, Characters, Scene Style, Topic, or Sample Story). Users can also click "🔄 Update Instruction" at any time to re-sync manual edits back to the current configuration and selection. Only the runtime engine choice is excluded from the instruction brief.
- Dead and unwanted configurations not visible in the UI (such as legacy `studio_layout`, `enable_self_healing`, and dead `frame_count`/`Frames`) are completely purged from config models, state, and instruction generators, guaranteeing that only active, visible UI controls influence the generation brief.
- Default generation settings are: **10 seconds**, **1 script**, **5 retries**, **3 characters**, **Funny & Relatable** angle, and **Relatable Comedy & Sarcasm** tone.
- Configuration rows use the same label/control alignment, control width, row height, and visual spacing throughout the panel. Every stepper occupies the same control position as every dropdown.
- The output preview remains adjacent to the settings panel and uses a vertical 9:16 display format, without showing “9:16” as a title label.

---

## 5. Combinatorial Instruction Matrix (Tone, Editorial Angle & Scene Style)

Every distinct option and combination of Tone, Angle, and Scene Style has a dedicated, tailored instruction directive defined in `core/prompt_matrix.py` and dynamically injected into the master generation brief:

### 🎭 Tones (Voice, Energy & Delivery)
1. **`😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)`**: Mandates authentic everyday jokes, witty banter, relatable desi observations, and playful quips. Forbids dry, robotic news reciting.
2. **`🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)`**: Celebrates timeless Indian heritage, national achievements, authentic cultural idioms, and confident patriotic energy.
3. **`🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)`**: Ancient wisdom, soulful philosophical depth, and reverence for timeless traditions.
4. **`🔥 Viral & High Energy (धमाकेदार)`**: High-voltage adrenaline, rapid punchy delivery, shock-value opening hooks, and electrifying viral pacing.
5. **`⚡ Urgent Breaking News (ताज़ा खबर)`**: Fast-paced journalistic urgency, high-stakes development framing, and crisp factual clarity.
6. **`💡 Deep Analysis & Curious (गहन पड़ताल)`**: Intellectual curiosity, unpacking hidden facts, asking "why this matters", and illuminating insights.
7. **`🎭 Cinematic Storytelling (भावुक कहानी)`**: Emotionally resonant narrative arc, cinematic tension, character-driven journey, and moving resolution.
8. **`😢 Emotional & Heartbreaking (भावुक / दुखद)`**: Deep emotional weight, tender vulnerability, quiet sorrow, and heartfelt empathy. Spoken words carry touching pathos and profound respect for human loss and struggle.

### 🎨 Editorial Angles (Imaginary Situations & Scene Framing)
- **`Funny & Relatable`**: Sets up an imaginary everyday situation (e.g., friends hanging out at a local chai tapri, reacting in comedic shock with tea cups, making funny real-world comparisons).
- **`Sarcastic & Edgy`**: Roasts ironies and contrasts expectations vs reality with sharp, clever sarcasm.
- **`Dramatic Storytelling`**: Suspenseful thriller setup with rising tension, mystery, and an unexpected plot twist.
- **`Investigative Deep-Dive`**: Frames as an insider uncovering startling behind-the-scenes facts that the headlines missed.
- **`Inspirational & Uplifting`**: Triumphant journey of resilience, innovation, and courage overcoming obstacles.
- **`Gen-Z Hinglish`**: Modern urban cadence, viral Hindi-English slang, meme references, and casual conversational flow.
- **`Bollywood Masala`**: Quintessential Bollywood flair, dramatic one-liners, cinematic punchlines, and theatrical excitement.
- **`Tragic & Heartbreaking`**: Frames the scene around the deeply human, vulnerable personal loss or emotional toll behind the news, depicting a quiet, solemn atmosphere (soft rain on glass, solitary contemplation, tender words of solace).

### 👥 Scene Styles (Screenplay Turn Structure)
- **`Dialogue`**: An active in-universe conversational exchange between $N$ designated characters across scenes. Each scene features a designated character speaking and directly reacting to the previous turn.
- **Strict Prohibition on Commenting & Meta-CTAs**: Social media commenting, calls to comment (e.g., "कमेंट करें", "नीचे कमेंट में बताएं", "लाइक और शेयर करें"), and subscriber calls **MUST NEVER** be part of dialogue or script lines. Characters are living inside the scenario and conversing with each other, not addressing a comment section.
- **`Interview`**: Rapid-fire Q&A between an investigative host and an insider guest, revealing surprising insights in real time.
- **`Debate`**: Fiery, witty clash of two opposing perspectives with sharp counter-arguments and substantive exchanges.
- **`Speech`**: Charismatic public oration delivered with rhetorical punch, rallying cries, and direct emotional connection to the audience.
- **`Narration / Monologue`**: Solo compelling direct-to-camera monologue addressing the audience directly with magnetic energy.
- **`Lament`**: A deeply moving tribute and expression of shared sorrow, offering mutual solace and poignant remembrance across scenes.

---

## 6. Optional Reference Sample Story & Conflict Precedence Rule

- **Input Control:** An optional **"Sample Story (Optional Reference)"** field is available in the studio. Users can provide reference stories, dialogue snippets, or custom narrative situations.
- **Discrepancy Precedence Rule:** In case of any conflict or discrepancy between general instructions and the sample story, **THE SAMPLE STORY TAKES HIGHEST PRECEDENCE**:
  - The AI prioritizes and adapts the characters, narrative events, and tone from the sample story.
  - Spoken lines and character turns are grounded directly in the sample story while strictly adhering to the duration word count limits.
  - The active sample story is recorded in `ReelBatchResult.sample_story` and displayed in the output preview with a precedence badge.

---

## 7. Master Agent Instruction Decomposition & Sub-Instruction Dispatch

The Master Agent (`ChiefEditorCoordinatorAgent`) decomposes the master instruction into 7 specialized sub-instructions, dispatched to each sub-agent:
1. **`news_validator`**: Verified wire facts, entities, and rumor filtering.
2. **`hook_strategist`**: Viral 0–3s hook formulation, creative situation setup, and tone directives.
3. **`dialogue_writer`**: Character persona assignment, scene-by-scene lines, strict word count budgets (`recommended_words`, `min_words`, `max_words`), pacing asymmetry rules, and sample story precedence.
4. **`timing_auditor`**: Mathematical word count verification, speech rate (~2.0–2.3 w/s), and self-healing smart trimming.
5. **`scene_director`**: 9:16 vertical scene storyboards, B-roll visuals matching imaginary settings (chai tapri, debate studio, cultural ghats), on-screen text, and SFX.
6. **`video_prompt_engineer`**: 9:16 4K 24fps Google Flow / Veo generative prompts with specific camera movements and lighting.
7. **`video_quality_gate`**: Feasibility and safety compliance checks.

---

## 8. Configuration Acceptance Testing Gate & Self-Healing Retry Flow

The Chief Editor operates a final Testing & Acceptance Gate (`audit_configuration_compliance`) that audits whether all user-specified configurations and sample story elements are strictly honored:
1. **Word Count Compliance**: Verifies spoken dialogue across all scenes stays strictly within `max_words`.
2. **Character Count Compliance**: In multi-character setups (`character_count >= 2`), verifies scenes feature distinct, separated character personas.
3. **Scene Style Dialogue Turns**: Verifies each scene has valid spoken dialogue assigned to its respective character.
4. **Sample Story Compliance**: Confirms sample story integration when provided.
5. **Autonomous Self-Healing & Retry Prompts**:
   - If any check fails, the pipeline initiates self-healing retries dynamically looping up to `max_retries` (bounded between 1 and 5, default 5).
   - If retries are exhausted and items remain flagged, `compliance_passed=False` is recorded, and an actionable retry prompt is generated:
     `"⚠️ Configuration Acceptance Warning: [issues]. Recommendation: Click 'Generate' to re-run with current settings, or adjust Character Count / Duration in the settings panel."`
   - The UI renders a one-click **"🔄 Retry Generation with Recommended Settings"** button for immediate user recovery.
