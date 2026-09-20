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
- Scene style is selectable as Dialogue, Argument, Speech, Narration, Interview, Debate, Monologue, or Lament.
- **Single Continuous Video Reel (No Background Repetition):** The screenplay constitutes ONE continuous vertical video reel. Scene 1 establishes the setting and primary visual prop. Subsequent scenes MUST NOT repeat or re-explain background context; they must advance camera angles, prop interactions, and character reactions smoothly.
- **Dynamic Narrative Ordering (Fun First, News Second):** The screenplay does not robotically force news into sentence 1. For funny, sarcastic, and relatable angles, Scene 1 opens with a hilarious situational hook or reaction blunder, Scene 2 reveals the verified news development as the trigger/twist, and Scene 3 delivers the punchline payoff.
- **Script-Grounded Demographic Diversity & Relational Dynamics:** Character personas are selected contextually based on the story topic, tone, and scene style, representing authentic interpersonal relationships alongside the socioeconomic diversity of India:
  - *Interpersonal Relationships (Relational Dynamics)*:
    - **Colleagues / Co-Workers**: Senior Office Colleague & Junior Colleague (workplace deadlines, WFO mandates, appraisal banter)
    - **Friends / Tapri Companions**: College Friend 1 & Street-Smart Friend 2 (lively tapri banter, friendly teasing, news debate)
    - **Husband & Wife (पति-पत्नी)**: Pragmatic Homemaker Wife & Salaried Husband (household budgets, grocery prices, government schemes, inflation)
    - **Father & Son (पिता-पुत्र)**: Traditional Father & Gen-Z Son (generational divide, career choices, coaching vs modern tech)
    - **Mother & Son (माँ-बेटा)**: Caring Mother & Ambitious Son (aspirations, family emotional stakes)
    - **Neighbors (पड़ोसी)**: Inquisitive Neighbor & Opinionated Neighbor (community debates, neighborhood banter)
  - *Socioeconomic Cross-Section Pairings*:
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
9. **`⚔️ Heated Argument & Clash (तीखी बहस / तकरार)`**: High-voltage verbal sparring, sharp counter-arguments, passionate convictions, and snappy comebacks. Characters challenge each other's assumptions aggressively yet entertainingly, trading defensive claims and emotional friction.

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
- **`Argument`**: A fiery, high-stakes verbal argument between characters with opposing convictions. Characters clash directly over the situation: trading sharp comebacks, defensive justifications, and escalating emotional stakes, concluding with a dramatic reveal, reality check, or comic twist.
- **Strict Prohibition on Commenting & Meta-CTAs**: Social media commenting, calls to comment (e.g., "कमेंट करें", "नीचे कमेंट में बताएं", "लाइक और शेयर करें"), and subscriber calls **MUST NEVER** be part of dialogue or script lines. Characters are living inside the scenario and conversing with each other, not addressing a comment section.
- **`Interview`**: Rapid-fire Q&A between an investigative host and an insider guest, revealing surprising insights in real time.
- **`Debate`**: Fiery, witty clash of two opposing perspectives with sharp counter-arguments and substantive exchanges.
- **`Speech`**: Charismatic public oration delivered with rhetorical punch, rallying cries, and direct emotional connection to the audience.
- **`Narration / Monologue`**: Solo compelling direct-to-camera monologue addressing the audience directly with magnetic energy.
- **`Lament`**: A deeply moving tribute and expression of shared sorrow, offering mutual solace and poignant remembrance across scenes.

---

## 6. Optional Reference Sample Story & Conflict Precedence Rule

- **Input Control & One-Click Clear Action:** An optional **"Sample Story (Optional Reference)"** field is available in the studio. Users can provide reference stories, dialogue snippets, or custom narrative situations. A dedicated **"🗑️ Clear"** action button immediately resets the sample story reference, clears the input field, and re-syncs master instructions dynamically without manual text backspacing.
- **Discrepancy Precedence Rule:** In case of any conflict or discrepancy between general instructions and the sample story, **THE SAMPLE STORY TAKES HIGHEST PRECEDENCE**:
  - The AI prioritizes and adapts the characters, narrative events, and tone from the sample story.
  - Spoken lines and character turns are grounded directly in the sample story while strictly adhering to the duration word count limits.
  - The active sample story is recorded in `ReelBatchResult.sample_story` and displayed in the output preview with a precedence badge.

### 🎭 Sample Script Character & Relationship Extraction Precedence
When a user provides a sample story or reference screenplay, characters and relational dynamics defined within it are strictly parsed and honored:
1. **Explicit `CHARACTERS & CLOTHING:` Blocks:** If the sample script defines characters and wardrobe (e.g., `⚬ ANANYA: Casual college-going attire...`), these characters and wardrobe descriptions are directly extracted, preserved, and reflected in the final output.
2. **Dialogue Speaker Cues:** Explicit speaker names in dialogue turns (e.g., `ANANYA: "..."`, `VIKRAM: "..."`, `Wife: "..."`, `Husband: "..."`, `पति: "..."`, `पत्नी: "..."`) are extracted and mapped into speaking personas.
3. **Interpersonal Relationships in Narrative Prose:** When the sample story establishes specific relationships, they immediately override random or generic character selection:
   - **Husband & Wife (पति-पत्नी):** Sunita (Wife / Pragmatic Homemaker) & Rajesh (Husband / Salaried Man).
   - **Father & Son (पिता-पुत्र):** Sharma Ji (Traditional Father) & Aarav (Gen-Z Son).
   - **Mother & Son / Daughter (माँ-बेटा / माँ-बेटी):** Meera (Caring Mother) & Kabir / Ananya.
   - **Colleagues / Coworkers (सहकर्मी / कलीग):** Priya (Senior Colleague) & Rohan (Junior Colleague).
   - **Friends (दोस्त / यार):** Ananya & Vikram (Tapri buddies / college friends).
   - **Doctor & Patient (डॉक्टर-मरीज):** Dr. Rajesh & Ramesh.
   - **Teacher & Student (शिक्षक-छात्र):** Master Ji & Aarav.
   - **Shopkeeper & Customer (दुकानदार-ग्राहक):** Mohan & Rajesh.
   - **Lawyer & Client (वकील-मुवक्किल):** Advocate Verma & Kabir.
   - **Neighbors (पड़ोसी):** Verma Ji & Gupta Ji.
4. **Format Fidelity:** If the sample script provides custom `SCENE DETAIL:` or custom clothing, the Screenplay Formatter uses those exact lines rather than generating generic defaults.

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

---

## 9. Script Continuity, Setting & Dialogue Target Analysis Phase

The pipeline includes an autonomous **Script Continuity, Setting & Dialogue Target Analysis Engine** (`core/script_analyzer.py`) executed across script generation, scene direction, and screenplay formatting to eliminate narrative and kinematic mismatches:

### 🏥 1. Setting Mismatch Resolution (Institutional Topics vs Street/Tapri Characters)
- **Problem:** When an institutional news topic (e.g., Government Hospital, High Court, IT Tech Park, Police Thana, Municipal Office) is paired with working-class characters (e.g., Tea Vendor, Auto Driver) or tapri SFX (cutting chai clink, tea stall clatter, vendor apron), setting the scene inside an institutional interior (e.g., casualty waiting area, courtroom, bank vault) causes a glaring environmental mismatch.
- **Harmonization Engine:** Automatically reconciles the setting to the authentic adjacent exterior / roadside hotspot:
  - **Hospital Topic + Tea Vendor / Chai SFX:** *"A bustling roadside tea stall directly outside the government hospital casualty entrance."* (Reconciles medical topic, tea vendor apron, cutting chai clink, and ambient hospital visitors).
  - **High Court Topic + Tapri / Street SFX:** *"A lively roadside tea kiosk right across the High Court entrance gate."*
  - **Tech Park Topic + Tapri / Auto Driver:** *"A bustling roadside tea stall and kiosk adjacent to the glass-facade IT tech park turnstiles."*
  - **Police Topic + Tea Vendor:** *"A street tea stall corner situated just outside the city police station."*
  - **Domestic Topic (Husband & Wife / Father & Son):** *"A cozy Indian middle-class household living room or kitchen."*

### 🎯 2. Dialogue Target & Salutation Auditor
- **Marital Vocative Validation:** In Hindi, marital vocatives like `"अरे सुनती हो!"`, `"अजी सुनती हो!"`, and `"भाग्यवान"` are culturally and linguistically restricted to a husband addressing his wife.
- **Target Healing:** If a male character (e.g., Netaji, Friend 1) addresses another male character (e.g., Rohan, a tea vendor) with marital salutations, the Dialogue Auditor intercepts and transforms the line to address the character directly (e.g., `"अरे रोहन भाई!"`, `"अरे भाई सुनो!"`).
- **Narrative Logic:** Ensures subsequent punchlines referencing wives or families are structurally logical and clearly differentiated from the addressee.

### 🎬 3. Visual Kinematics & Prop Continuity Harmonizer
- **Occupational Realism:** Eliminates awkward floating or isolated smartphone handling during physical trades:
  - **Tea Vendor:** When gesturing with or showing a smartphone, the action specifies holding a tea strainer, kettle, or wiping cloth in one hand while operating the phone with the other.
  - **Auto Driver:** Holds auto ignition keys or meter cleaning rag while pointing at the screen.
  - **Students / Aspirants:** Holds coaching notes, books, or backpack while interacting with props.

### 🔄 4. Common Sense Realism Validator & Self-Healing Retry Loop
- **Dedicated Common Sense Validator (`CommonSenseRealismValidator`):** Audits assembled screenplays for physical setting realism, dialogue target coherence, and occupational prop handling.
- **Feedback Back-Propagation:** When common sense or physical realism violations are detected, structured feedback is passed directly back to upstream pipeline stages:
  - **Dialogue Target Feedback -> Dialogue Narration & Formatting:** Heals salutations, ensures proper character targeting, and preserves Hindi Devanagari purity.
  - **Setting Incoherence Feedback -> Scene Director & Screenplay Formatter:** Moves institutional interiors to authentic adjacent exterior tea kiosks / road-side spots.
  - **Kinematics Feedback -> Scene Visuals Director:** Adds multi-prop coordination (tea cloth, strainer, keys).
- **Autonomous Retry Integration:** Loops through self-healing modification and re-validation up to `max_retries` (default 5). All healing events are recorded in `ReelScript.self_healing_notes`.
- **Compliance Gate Integration:** Included as Check #5 in `ChiefEditorCoordinatorAgent.audit_configuration_compliance`. If unresolvable violations persist after max retries, clear retry recommendations are provided to the user.

---

## 10. Dynamic Imagination Engine for Missing Pairs & Settings (Grounded in Current Data)

### 🎨 1. Core Principle: No Generic Fallback (Everything is NOT a Chai Tapri!)
- When a user's news topic, wire verification data, or sample story does not match any predefined domain or static character pairing, the pipeline **MUST NOT** blindly default to a street chai tapri or an unrelated persona (like an auto driver or tea vendor).
- Instead, the autonomous **Dynamic Imagination Engine** (`ContextualSceneCharacterSelectorAgent.imagine_from_current_data`) analyzes the current data and **dynamically imagines and creates a brand-new, customized set of scene venues, complementary character personas, role wardrobes, physical props, and sound effects**.

### 🔍 2. Subject Extraction & Entity Grounding
- The engine extracts key subject nouns, sectors, institutions, and topics from the current headline, verified facts, and story text (e.g. *"ISRO Satellite Halo Orbit"*, *"Zaveri Bazaar Gold Bullion"*, *"Northern Railway Vande Bharat Signaling"*, *"World Cup Cricket Pavilion"*, *"Smog & AQI Monitoring"*, *"Quantum Computing Initiative"*).
- It categorizes the topic into specialized real-world sectors or executes **General Dynamic Imagination** for any arbitrary emerging domain.

### 🎭 3. Synthesized Persona Dynamics
- **Complementary Dual/Trio Archetypes:**
  - **Character 1 (Domain Specialist / Practitioner):** Leading expert, officer, or professional directly engaged in the field (e.g., `🚀 Dr. Vikram (Senior ISRO Mission Scientist)`, `✈️ Captain Rajesh (Senior Commercial Airline Pilot)`, `👑 Seth Radheshyam (Senior Bullion Merchant)`, `🏏 Coach Sharma (Veteran Cricket Coach)`, `🔬 Dr. Vikram (Lead Subject Specialist)`).
  - **Character 2 (Stakeholder / Affected Citizen):** Counterpart, colleague, or citizen with a direct stake in the outcome (e.g., `👩 Priya (Aerospace Flight Trajectory Engineer)`, `🧑 Rajesh (Gold Investor / Retail Buyer)`, `🧑 Aarav (National Team All-Rounder)`, `🧑 Rajesh (Industry Stakeholder / Citizen)`).
  - **Character 3 (Trio Expansion):** Station master, sports commentator, field controller, or domain analyst.

### 👔 4. Role-Authentic Wardrobes, Concrete Props & SFX
- **Wardrobes:** Generated to match the specific profession without tone clashes (e.g., ISRO mission lanyard and blue project shirt, airline pilot four-stripe epaulets, railway safety jacket with helmet, silk kurta with bullion watch chain, team track jacket with stopwatch whistle, lab coat with digital AQI sensor).
- **Physical Props:** Concrete objects characters physically handle (telemetry tablets, flight manifest clipboards, railway signaling flags, carat weighing scales, cricket bats, air quality meters, blueprint dossiers).
- **Sound Effects (SFX):** Spatial audio grounding (telemetry countdown beeps, jet engine tarmac hum, train horn echo, gold coin clink, stadium crowd roar, air sensor alerts).

### ⚡ 5. Seamless Pipeline Integration
- **Screenplay Formatter:** Renders the customized scene details and wardrobes in the final vertical screenplay.

---

## 11. Screenplay Coherence Sub-Agent & Spoken Dialogue-Action Synchronization

### 🎯 1. Mission: Eliminating Randomness in Screenplay Beats
- Screenplay visual actions must **NEVER** feature random, generic filler movements (like aimless head scratching or staring at walls) when the spoken dialogue explicitly discusses concrete physical objects, actions, or props.
- If a character's dialogue mentions sipping tea, leaving tea, an official newspaper, a bill, a smartphone video, counting currency, or a study book, the **Scene Focus & Camera Action MUST directly lock onto that exact physical interaction**.

### 🤖 2. Dedicated Screenplay Coherence Sub-Agent (`ScreenplayCoherenceAgent`)
- The pipeline incorporates a specialized **Screenplay Coherence Sub-Agent** (`ScreenplayCoherenceAgent` / `screenplay_coherence_agent`) operating within the screenplay generation and analysis phase.
- **Auditing & Alignment Pipeline:**
  1. **Spoken Dialogue Object & Action Scanner:** Scans spoken Hindi / Hinglish lines for physical objects and interaction verbs:
     - **Tea / Chai / Sipping / Leaving Tea (`चाय`, `घूंट`, `sip`, `कटिंग`, `चाय छोड़`):**
       - If *"चाय छोड़"*: Character abruptly sets down the half-finished cutting chai glass on the wooden bench, leaning in with urgent animated emotion.
       - If *"घूंट / sip / पी"*: Character takes a steaming sip from the cutting chai glass, exhaling with relatable animated expression.
       - Audio/SFX: Synchronizes to *"Cutting Chai Sip + Steam Whoosh"* or *"Chai Glass Clink + Urgent Whoosh"*.
     - **Paper / Newspaper / Official File / Billing Receipt (`अखबार`, `कागज़`, `file`, `बिल`, `ऑर्डर`):**
       - If *"अखबार / newspaper"*: Character sharply unfolds the morning Hindi newspaper, pointing an index finger directly at the front-page headline.
       - If *"बिल / bill"*: Character waves the paper billing receipt with frantic disbelief, tapping the total amount figure.
       - If *"सरकारी फाइल / ऑर्डर"*: Character taps a ballpoint pen emphatically on the official document file folder.
       - Audio/SFX: Synchronizes to *"Newspaper Snap + Low Paper Rustle"* or *"Pen Tap on Desk + Paper Rustle"*.
     - **Smartphone / Video / QR Code (`फोन`, `स्क्रीन`, `वीडियो`, `मैसेज`, `qr`):**
       - Action: Thrusts mobile phone screen into frame showing the viral video playback, or aims camera to scan the QR code.
       - Audio/SFX: Synchronizes to *"Smartphone Screen Tap + Notification Chime"* or *"QR Scan Beep"*.
     - **Money / Currency / Price (`रुपये`, `पैसे`, `करोड़`, `नोट`, `कैश`, `फीस`):**
       - Action: Counts paper currency notes with quick thumb motions or inspects fee receipt.
       - Audio/SFX: Synchronizes to *"Currency Note Flap + Sub Impact"*.
     - **Books / Degree / Coaching (`किताब`, `डिग्री`, `कोचिंग`, `नोट्स`):**
       - Action: Slams heavy coaching book down onto the counter with exasperated comedic disbelief.
       - Audio/SFX: Synchronizes to *"Fast Whoosh + Heavy Book Slam"*.
     - **Official Stamp / Seal (`मुहर`, `स्टैंप`, `stamp`):**
       - Action: Firmly presses the official ink stamp onto the clearance document.
       - Audio/SFX: Synchronizes to *"Official Ink Stamp Press + Sharp Echo"*.
     - **Food / Snacks (`पोहा`, `समोसा`, `जलेबी`, `नाश्ता`):**
       - Action: Picks up a bite with spoon from paper plate of poha, pausing mid-air in surprise.
       - Audio/SFX: Synchronizes to *"Snack Plate Clink + Comedic Chime"*.

### 🎬 3. Grammatically Coherent Vertical Camera Cues
- The Screenplay Formatter converts aligned physical actions into natural, grammatical participle camera cues:
  - `"Fast whip-pan to Priya abruptly setting down the half-finished cutting chai glass on the wooden bench, leaning in with urgent animated emotion."`
  - `"Fast pull back to frame both. Rohan sharply unfolds the morning Hindi newspaper, pointing an index finger directly at the front-page headline with wide-eyed reaction."`

### 🔄 4. Multi-Agent Audit & Self-Healing Retry Integration
- Embedded within `CommonSenseRealismValidator.audit_screenplay`: verifies dialogue-action coherence across all scenes.
- If physical dialogue interactions are missing, structured feedback is passed to `screenplay_coherence_agent.align_screenplay_coherence`, dynamically self-healing the screenplay before final rendering.

---

## 🎭 Section 12: Comprehensive Scene, Character, Location & Relationship Matrix (Minimum 5-6 Setups per Category)

To guarantee variety, eliminate repetitive defaults (such as always falling back to a chai tapri), and ensure authentic storytelling, the subagents (`ContextualSceneCharacterSelectorAgent`, `DialogueWriterAgent`, and `SceneVisualsDirectorAgent`) maintain and curate a rich matrix of **at least 5-6 authentic setups** across every:
1. **Scene Style**
2. **Creative Angle**
3. **Script Topic Domain**

Each setup is fully specified with:
- **Characters & Archetypes:** Specific persona names, socioeconomic roles, and authentic wardrobe descriptions.
- **Relational Dynamics:** Concrete relationships (e.g. Friends, Husband & Wife, Father & Son, Senior & Junior Colleagues, Shopkeeper & Customer, Doctor & Attendant, Litigant & Counsel, Whistleblower & Reporter).
- **Tangible Location & Setting:** Physical venues with atmospheric detail (e.g. Corporate Cafeteria Pod, District Collectorate, High Court Portico, Metro Turnstile Concourse, Wholesale Sabzi Mandi, ICU Doctors' Duty Room, Zaveri Bazaar Bullion Vault).
- **Physical Props & Audio SFX:** Real-world tools, trade objects, documents, and synchronized audio soundscapes.

### 🎬 1. Scene Styles Matrix (Min 6 Curated Setups per Style)

| Scene Style | Setup ID | Relationship | Location & Setting | Core Physical Props & SFX |
| :--- | :--- | :--- | :--- | :--- |
| **Dialogue** | `dialogue_college_friends` | College Friends (कॉलेज दोस्त) | Campus Banyan Tree & Tea Tapri | Spiral college notebook, cutting chai glass, smartphone \| *Cutting Chai Clink* |
| | `dialogue_husband_wife` | Husband & Wife (पति-पत्नी) | Middle-Class Kitchen & Dining Counter | Monthly ration expense sheet, grocery bill, steel tumbler \| *Steel Tumbler Clink* |
| | `dialogue_father_son` | Father & Son (पिता-पुत्र) | Ancestral Veranda & Study Corner | Reading spectacles, coaching prospectus, folded Hindi newspaper \| *Newspaper Snap* |
| | `dialogue_corporate_colleagues` | Senior & Junior Colleagues (कलीग्स) | Corporate IT Park Cafeteria Pod | RFID access lanyard, slim laptop, paper coffee cup \| *RFID Turnstile Beep* |
| | `dialogue_trader_customer` | Shopkeeper & Regular Customer (दुकानदार-ग्राहक) | Neighborhood Kirana Store Front | Steel grocery scoop, canvas jhola, counter ledger \| *UPI Payment Chime* |
| | `dialogue_doctor_patient_relative` | Physician & Patient Relative (डॉक्टर-तीमारदार) | Civil Hospital OPD Consultation Chamber | Medical prescription slip, medicine blister pack, stethoscope \| *Prescription Pen Scratch* |
| **Narration** | `narration_street_citizen` | Solo Citizen Monologue (आम नागरिक) | Urban Public Crossroad & Paper Stall | Unfolded morning newspaper, metallic ballpoint pen \| *City Traffic Drone + Paper Unfold* |
| | `narration_tech_insider` | Solo Industry Insider (टेक विश्लेषक) | Tech Park Glass Skybridge | Corporate digital tablet, smartwatch notification \| *Subtle Digital Chime* |
| | `narration_pragmatic_homemaker` | Solo Economic Anchor (गृहलक्ष्मी) | Home Living Room with Ledger Table | Monthly electricity bill, plastic desk calculator \| *Calculator Button Click* |
| | `narration_field_reporter` | Solo Field Reporter (खोजी पत्रकार) | Outside Ministry Bhavan Security Gate | Lapel mic with transmitter box, spiral field notebook \| *Camera Shutter Click* |
| | `narration_exam_aspirant` | Solo Youth Aspirant (प्रतियोगी छात्र) | Coaching Hub Library Cubicle | Thick standard reference book, yellow highlighter \| *Highlighter Glide + Page Turn* |
| | `narration_rural_elder` | Solo Grassroots Elder (गांव के बुजुर्ग) | Village Panchayat Chaupal & Well | Wooden walking staff, cotton gamchha on shoulder \| *Breeze Through Leaves + Tractor Chug* |
| **Debate** | `debate_economist_vs_citizen` | Economist vs Ground Citizen (नीति बनाम यथार्थ) | Studio Debate Desk with Split-Screen | Printed GDP bar chart report, actual shopping receipt strip \| *Debate Gavel Chime* |
| | `debate_elder_vs_genz` | Traditional Elder vs Gen-Z (परंपरा बनाम आधुनिकता) | Community Park Jogging Track Bench | Hardbound Sanskrit text, smartphone streaming short video \| *Park Bird Song + Swipe Sound* |
| | `debate_bureaucrat_vs_whistleblower` | Spokesperson vs RTI Activist (प्रवक्ता बनाम कार्यकर्ता) | Secretariat Media Briefing Room | Embossed government gazette notification, RTI reply documents \| *Mic Feedback + Slap* |
| | `debate_founder_vs_gig_worker` | Startup Founder vs Gig Worker (फाउंडर बनाम वर्कर) | Commercial High-Street Curb Outside Coworking Hub | Algorithm efficiency graph, deducted payout slip \| *Bike Idle Rumble + App Ping* |
| | `debate_builder_vs_environmentalist` | Developer vs Ecologist (बिल्डर बनाम पर्यावरणविद्) | Overlook Ridge by Wetland Construction Zone | Masterplan blueprint, digital air/water testing meter \| *Earth-Mover Roar + Sensor Beep* |
| | `debate_prosecutor_vs_defence` | Public Prosecutor vs Defence Counsel (सरकारी बनाम बचाव वकील) | High Court Portico Pillars | Bound IPC commentary, certified High Court bail petition \| *Heavy Law Book Thud* |
| **Interview** | `interview_whistleblower_investigator` | Journalist & Whistleblower (पत्रकार और सूत्र) | Secluded Archive Corner in Public Library | Compact voice recording device, sealed confidential dossier \| *Recorder Click + Whispered Tone* |
| | `interview_podcaster_tech_innovator` | Podcaster & AI Scientist (पॉडकास्टर और वैज्ञानिक) | Acoustic Foam Sound Studio | Boom studio microphone, semiconductor silicon wafer sample \| *Studio Acoustic Mic Hit* |
| | `interview_ground_reporter_citizen` | Field Correspondent & Flood Victim (रिपोर्टर और नागरिक) | Temporary Flood Relief Embankment Tent | Handheld channel microphone, ration token card \| *Wind in Lapel Mic + Water Splash* |
| | `interview_financial_anchor_merchant` | Financial Anchor & Bullion Merchant (एंकर और व्यापारी) | Zaveri Bazaar Gold Trade Vault | Hallmarked 100g gold bar replica, micro-carat balance scale \| *Gold Metal Clink + Ticker Chime* |
| | `interview_sports_reporter_athlete` | Sports Bureau Chief & Sprinter (खेल पत्रकार और धावक) | National Sports Stadium Running Track | Metallic winner medal on ribbon, spiked running shoes \| *Stadium PA + Cleats Crunch* |
| | `interview_consumer_host_regulatory` | Consumer Host & Regulatory Chief (प्रहरी और नियामक) | Standards & Safety Regulatory Laboratory | Tested FMCG product with defect tag, official regulatory notice \| *Lab Centrifuge + Seal Stamp* |
| **Street Reaction** | `street_metro_turnstile` | Daily Urban Commuters (दैनिक यात्री) | Metro Station Smartcard Turnstile Concourse | Metro smartcard, smartphone QR ticket screen \| *Turnstile Beep + Metro PA Chime* |
| | `street_auto_bus_stand` | Commuter & Auto Driver (सवारी और ऑटो चालक) | City Bus Shelter & Auto Stand Curb | Auto ignition keys, paper bus fare ticket \| *Two-Stroke Throttle + Air Brake Hiss* |
| | `street_mandi_shoppers` | Shopper & Vegetable Hawker (खरीदार और विक्रेता) | Weekly Morning Wholesale Sabzi Mandi | Fresh coriander bundle, metal counter-weight balance \| *Vendor Street Call + Scale Clatter* |
| | `street_coaching_hub_students` | Competitive Batchmates (कोचिंग छात्र संगी) | Narrow Lane Outside Test Center | Printed exam question paper, transparent clipboard \| *Paper Rustle + Crowd Murmur* |
| | `street_temple_ghat_promenade` | Pilgrim & Riverside Shopkeeper (श्रद्धालु और दुकानदार) | Holy River Ghat Stone Steps | Brass puja diya, clay pot of river water \| *Temple Bell Toll + River Lap* |
| | `street_cinema_lobby_exit` | Moviegoers & Pop Culture Fans (सिनेमा दर्शक) | Multiplex Concourse & Poster Hall | Large tub of cinema popcorn, ticket stub slips \| *Surround Sound Bass + Popcorn Crunch* |
| **Satirical Skit** | `skit_netaji_and_chaiwala` | Politician & Chaiwala (नेताजी और चायवाला) | Campaign Street Corner Tea Tapri | Heavy marigold garland, tea strainer, unpaid chai bill \| *Car Horn + Kettle Hiss* |
| | `skit_bureaucrat_and_citizen` | Red-Tape Babu & Citizen (बाबूजी और नागरिक) | Municipal Clearance Window | Rubber ink stamp, stamp ink pad, 12 photocopied forms \| *Ceiling Fan Squeak + Stamp Thud* |
| | `skit_fintech_bro_and_dadi` | FinTech Salesman & Dadi (फिनटेक और दादीजी) | Traditional Living Room Divan | Glowing crypto graph phone, vintage biscuit tin of cash \| *App Chime + Metallic Biscuit Tin* |
| | `skit_corporate_hr_and_coder` | HR 'Wellness' & Sleepy Coder (एचआर और कोडर) | Corporate Relaxation Beanbag Corner | Mindfulness singing bell, caffeinated energy drink can \| *Singing Bowl Hum + Keyboard Frenzy* |
| | `skit_coaching_salesman_parent` | Coaching Pitchman & Frugal Father (काउंसलर और पिता) | Air-Conditioned Admission Seminar Desk | 40-page gold brochure, chequebook with worn pen \| *Smooth Jazz + Cheque Tear* |
| | `skit_traffic_cop_excuse_artist` | Traffic Cop & Excuse Artist (पुलिस और बहानेबाज) | Major Traffic Junction Barricade | Digital e-challan POS device, broken scooter helmet \| *Traffic Whistle + POS Beep* |
| **Lament** | `lament_bereaved_relatives` | Bereaved Kin & Consoling Elder (शोकाकुल परिजन) | Courtyard of Tragedy-Hit Residence | Framed garlanded photo, untouched brass cup of water \| *Muffled Sob + Wind Whistle* |
| | `lament_laid_off_employee_spouse` | Laid-Off Tech Worker & Spouse (हताश कर्मी और पत्नी) | Midnight Kitchen Dining Table | Printed termination letter, deactivated plastic ID card \| *Ticking Clock + Exhale of Grief* |
| | `lament_displaced_farmers` | Debt-Hit Farmer & Peer (कर्जदार किसान और साथी) | Cracked Dry Reservoir Basin | Handful of parched soil, bank debt recovery notice \| *Dry Earth Crumble + Summer Wind* |
| | `lament_retiring_craftsman_son` | Aging Weaver & Apprentice Son (बुनकर पिता और पुत्र) | Fading Handloom Workshop Loft | Wooden loom shuttle, woven pure silk border bundle \| *Creaking Loom + Melancholic Flute* |
| | `lament_old_age_resident_volunteer` | Care Home Elder & Volunteer (वृद्धाश्रम निवासी) | Care Home Sunlit Garden Veranda | Faded B&W family photograph, crocheted wool shawl \| *Rustling Leaves + Bell Toll* |
| | `lament_healthcare_night_shift` | Exhausted ICU Doctors (थके हुए चिकित्सक) | Hospital Night-Shift Duty Room | Pulled-down N95 surgical mask, flatline ECG report \| *Monitor Beep Fade + Exhausted Sigh* |
| **Argument** | `argument_domestic_budget` | Husband & Wife (दंपति में तकरार) | Middle-Class Kitchen Counter | Gas cylinder red booking slip, empty steel wallet box \| *Lid Clatter on Pan + Sigh* |
| | `argument_father_son_career` | Father & Rebellious Son (पिता और बेटे में बहस) | Drawing Room Dining Table | Government exam form, angel investment pitch deck \| *Table Fist Slam + Chair Scrape* |
| | `argument_neighbors_parking` | Apartment Neighbors (पड़ोसी विवाद) | Apartment Stilt Parking Lot | Car key bunch, yellow parking wheel clamp \| *Car Lock Beep + Echoing Argument* |
| | `argument_appraisal_colleagues` | Competitive Peers (कॉर्पोरेट प्रतिद्वंद्वी) | Conference Room Glass Enclosure | Printed annual appraisal sheet, whiteboard marker \| *Marker Snap + Chair Swivel Creak* |
| | `argument_landowner_contractor` | Plot Owner & Contractor (मकान मालिक और ठेकेदार) | Unfinished Brickwork Building Site | Steel measuring tape, cracked sub-standard brick \| *Tape Measure Snap + Brick Thud* |
| | `argument_commuter_conductor` | Commuter & Bus Conductor (यात्री और बस कंडक्टर) | Overcrowded Public City Bus Aisle | Torn 50-rupee note, metal ticket punch machine \| *Conductor Bell Whistle + Engine Grunt* |

---

### 💡 2. Creative Angles Matrix (Min 6 Setups per Angle)
- **Contrast & Comparison:** Luxury AC showroom vs unshaded pushcart; High-tech EV vs manual cycle rickshaw; Private corporate hospital vs crowded district clinic; Smart international school vs single-teacher rural school; 40th-floor executive boardroom vs basement guard cabin; Space rocket telemetry vs waterlogged city pothole.
- **The Untold Truth / Hidden Angle:** Industrial e-commerce sorting conveyor with 10-second quotas; Government chemical lab testing adulterated spices; Trackman hammer-tapping railway fishplates at 2 AM; High-density server farm groundwater cooling; Secret whistleblower meeting legal counsel at dusk; Municipal drainage worker operating without respirator mask.
- **Common Citizen Impact:** Two-wheeler commuter watching digital petrol pump price tick up; Homemaker recalculating grocery bill over tomato price surge; Salaried father confronting private school admission fee hike; Auto drivers queued at midnight for CNG fuel refills; Retired pensioner verifying monthly life certificate on biometric teller; Patient buying generic substitutes at Jan Aushadhi medical store.
- **Satire & Irony:** Glowing 'Smart City' flex banner hanging directly over knee-deep monsoon waterlogging; Ultra-expensive smog tower operating in hazardous AQI 480 grey smog; '100% Paperless Digital Office' requiring three physical photocopies of Aadhaar; Keto diet luxury clinic selling detox juice next to fair price ration shop; Aerodynamic Vande Bharat train halted by grazing stray cattle; Citizen balancing on terrace water tank to find mobile network.
- **Future Forecast & What Next:** Tech incubator whiteboard debating AI coding automation in 2028; City flood risk projection table showing 2035 sea-level contours; High-voltage electric grid operations room handling evening EV charging surge; Commercial satellite telemetry constellation launch; Drone agri-tech specialist monitoring crop moisture heatmaps; Biometric palm-vein contactless retail checkout.
- **Follow the Money / Economic Audit:** Chartered accountant analyzing corporate transfer pricing ledgers; Luxury villa private lounge discussing circle rates vs cash components; PWD corridor tender bidding kickback percentages; Customs cargo bay X-ray revealing concealed gold cylinders; Commercial coaching consortium reviewing student fee revenues; Airline pricing desk surge algorithm quadrupling holiday fares.
- **Emotional & Human Story:** Returning migrant worker embraced by young daughter on dawn railway platform; Agrarian farmer placing calloused hands on daughter's medical merit list; Returning soldier welcomed home by mother at village bus shelter; Varanasi silk master passing wooden shuttle to grandson; NDRF rescue specialist wrapping thermal blanket around recovered child; Community gurdwara langar serving steaming food with equal dignity.
- **Actionable Advice / Life Hack:** Smartphone settings tutorial to block unauthorized fraud APKs; Jewelers' 6-digit BIS Care HUID code verification guide; Step-by-step virtual court dispute guide for faulty camera traffic challans; EPFO member portal KYC mismatch correction walk-through; Jan Aushadhi / 1mg salt composition generic drug finder; Sub-Registrar 30-year non-encumbrance certificate (EC) title check guide.

---

### 🏢 3. Script Topic Domains Matrix (Min 6 Setups per Domain)
1. **Government Administration & SIR:** District Collectorate planning office; Tehsil land revenue patwari desk; Municipal Corporation town planning cell; State Secretariat (Mantralaya) corridor; Social welfare & pension window; Sub-Registrar deed registration hall.
2. **Healthcare & Medicine:** Civil hospital OPD corridor; 24x7 emergency casualty ward; Jan Aushadhi generic pharmacy; Diagnostic pathology blood lab; Primary Health Centre (PHC) immunization room; AYUSH traditional wellness clinic.
3. **Legal & Judiciary:** High Court portico entrance steps; District Court notary & affidavit shed; Bar Association law library; Police station duty officer desk; District Consumer Disputes Redressal Commission; Central prison visitor barrier.
4. **Technology & Corporate:** Modern glass corporate IT office; Tech park cafeteria breakout terrace; Open-desk startup coworking hub; Enterprise cloud server room; Urban home office remote WFH desk; HR performance review glass pod.
5. **Economy, Markets & Commodities:** Zaveri Bazaar gold trade bullion vault; APMC wholesale vegetable auction yard; Dalal Street multi-monitor equity trading desk; Commercial bank cash teller counter; Neighborhood provision store checkout; Inland container depot customs shed.
6. **Education & Career:** High-density competitive coaching lecture hall; Central university student canteen; University examination controller inquiry window; Campus placement waiting corridor; Cramped two-bed student hostel room; Rural primary school courtyard.
7. **Infrastructure & Transit:** International airport departure boarding gate; Zonal railway locomotive dispatch console; Urban metro operations command center; National expressway FASTag toll barrier; Elevated expressway flyover construction deck; Intermodal inland port container terminal.
8. **Environment & Climate:** City environmental monitoring control tower; Mega solar power plant substation; Organic agriculture demonstration collective; River flood early-warning embankment; Municipal solid waste biomethanation facility; Native tree forestry nursery.
9. **Police & Public Safety:** Urban traffic junction barricade; City police station helpdesk (Thana); District cyber crime investigation cell; Night highway border inter-state checkpost; Forensic crime scene investigation van; Neighborhood community policing mohalla camp.
10. **Domestic Household:** Middle-class kitchen ration counter; Traditional household study veranda; Festive Diwali decorated living room; Sunset apartment balcony tea corner; Kitchen utility LPG gas cylinder corner; Dining table under ceiling fan analyzing power bills.


