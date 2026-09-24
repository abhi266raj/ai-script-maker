# ROLE
You are refining a finalized Hindi reel dialogue draft based on a user's custom correction instruction. This is a RETRY — not a fresh generation.

# LOCKED CREATIVE DECISIONS (finalized earlier — DO NOT change, re-pick, re-roll, or re-imagine any of these)
- Speaking characters (EXACTLY {character_count} — these exact people; no additions, no removals, no renames):
{speaker_names_list}
- EVERY listed character MUST speak at least one beat. No narrator, no crowd, no extra voices.
- Angle (keep the same premise — every beat must live inside this situation): {angle}
- Tone (NON-NEGOTIABLE — at least 70% of beats must embody it, ZERO beats may contradict it): {tone}
- Hook idea (meaning only — NEVER quote it verbatim): {hook_idea}
- Dialogue type (MANDATORY structure — every beat must obey it, not just keep its name):
{dialogue_type_directive}
- Word budget (INPUT constraint only — never print it): ~{rec_words} words total, absolute max {max_words} words

# PREVIOUS DRAFT (the exact current visible output — your ONLY baseline)
{previous_draft}

# USER'S CUSTOM INSTRUCTION (HIGHEST PRIORITY)
{feedback}

# REFINE MANDATE
- This is a SURGICAL REFINEMENT, not a rewrite. Change ONLY what the custom instruction targets. Keep every line, beat, joke, and character moment that already works.
- Preserve ALL locked decisions above exactly: same characters, same count, same angle, same dialogue-type structure, same word budget.
- PURE spoken Hindi (Devanagari) only — a COMMON PERSON'S Hindi: everyday colloquial words, never formal/linguistic/shuddh vocabulary (BANNED). Translate English terms into everyday Hindi ('penal action' → 'सज़ा की कार्रवाई'), transliterate proper names ('Amazon' → 'अमेज़न'). NEVER quote headlines, hooks, or input text verbatim — paraphrase with the same meaning, in the characters' own everyday words.
- INSERT THE NEWS CREATIVELY: the refined dialogue must let the viewer absorb the actual news — key event, people/entities, core verified facts — through the scene, not a lecture. Weave the facts into the characters' voices, jokes, and reactions. Name the actual event and facts in natural Hindi (no vague allusions), but deliver them the way real people talk.
- CREATIVITY: be a creative screenwriter — fresh, specific, non-generic lines grounded in the verified facts. If a beat feels interchangeable with any other reel, make it unmistakably THIS story.
- Every line must earn its place: a verified fact, a specific question, a direct answer/rebuttal, or a news-grounded punchline. No generic filler. Characters react to each other (ping-pong), speaking as REAL PEOPLE from their listed roles — never as newsreaders.
- Stay within the word budget above.

# OUTPUT FORMAT
[Format Requirement: All scene descriptions in English, Dialogues strictly in Hindi]

Output the COMPLETE refined dialogue (same number of beats as the previous draft), structured EXACTLY like this. Beats run in order — do NOT write timestamps:

SCENE DETAIL:
⚬ <1-2 English lines: the location, vibe and energy of this reel>

CHARACTERS & CLOTHING:
⚬ <NAME (role): English clothing/appearance description — one line per character>

BEAT 1:
Camera Focus & Action: <English: camera movement + what the character physically does>
Audio/SFX: <English: ALWAYS start with the background music bed, then ambient SFX; add laughter wherever the beat is funny>
Text Overlay (Optional): <short punchy ENGLISH popup text — only when it adds a punch; otherwise omit this line>
VIKRAM: "<pure Hindi spoken line in Devanagari>"

BEAT 2:
Camera Focus & Action: <English camera + action>
Audio/SFX: <English SFX — background music + ambient sounds + laughter where fitting>
RAJESH: "<pure Hindi spoken line in Devanagari>"

(Speaker label is the bare character name in CAPS followed by the Hindi line in double quotes.)

REFINE REMINDERS: surgical refinement only — keep every locked decision above. TONE COMPLIANCE is non-negotiable: at least 70% of beats (round up) must clearly embody the required tone, and ZERO beats may contradict it (funny tone → every funny beat carries a REAL joke with setup + punchline, plus laughter where humor lands; somber tone → no jokes, no laughter anywhere). SELF-CHECK each beat before emitting.

OUTPUT BANS (a violation fails the output): never print word counts, timings, profiles, emojis, bracketed instructions, or metadata. Scene descriptions, camera, action, SFX and overlays are ENGLISH ONLY. ONLY the quoted speaker lines are Hindi (Devanagari).
