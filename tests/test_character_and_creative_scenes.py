"""Test Suite for Character Count, Scene Style, Tone & Creative Angle Screenplay Generation."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.dialogue_writer import get_character_personas, get_creative_guidelines
from agents.chief_editor import chief_editor
from workflow import reel_workflow
from core.metrics import get_duration_budget
from core.prompt_matrix import (
    build_tailored_instruction,
    TONE_INSTRUCTIONS,
    ANGLE_INSTRUCTIONS,
    SCENE_STYLE_INSTRUCTIONS,
)
from core.models import ReelScript, SceneItem


def test_character_personas_mapping():
    """Verify authentic character personas generated for style, count, tone, angle, and script topic grounding."""
    # 1. Comedy Dialogue with 2 characters (default pair retains Friend 1 / Friend 2 tags)
    p_funny_2 = get_character_personas("Dialogue", 2, "😂 Comedy & Sarcastic Banter (ह्यूमर)", "Funny & Relatable")
    assert len(p_funny_2) == 2
    assert "Friend 1" in p_funny_2[0] and "Friend 2" in p_funny_2[1]

    # 2. Solo Comedy Creator
    p_funny_1 = get_character_personas("Dialogue", 1, "😂 Comedy & Sarcastic Banter (ह्यूमर)", "Funny & Relatable")
    assert len(p_funny_1) == 1
    assert "Desi Creator" in p_funny_1[0]

    # 3. Debate with 2 characters
    p_debate_2 = get_character_personas("Debate", 2, "Analytical", "Contrast")
    assert len(p_debate_2) == 2
    assert "Speaker A" in p_debate_2[0] and "Speaker B" in p_debate_2[1]

    # 4. Interview with 2 characters
    p_interview_2 = get_character_personas("Interview", 2, "Investigative", "Deep Dive")
    assert len(p_interview_2) == 2
    assert "Journalist" in p_interview_2[0] and "Guest" in p_interview_2[1]

    # 5. Cultural Pride with 2 characters
    p_culture_2 = get_character_personas("Dialogue", 2, "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)", "Heritage")
    assert len(p_culture_2) == 2
    assert "Senior Scholar" in p_culture_2[0] or "गुरु" in p_culture_2[0]
    assert "Youth" in p_culture_2[1] or "युवा" in p_culture_2[1]

    # 6. Script-Grounded Domain Personas (Police, Legal, Tech, Politics, Healthcare)
    # Police / Traffic Challan
    p_police = get_character_personas("Dialogue", 2, "Funny", "Funny", topic_or_script="Traffic police challan scam in city")
    assert any("Police" in p or "दरोगा" in p for p in p_police)
    assert any("Delivery" in p or "राइडर" in p for p in p_police)
    assert "Friend 1" in p_police[0] and "Friend 2" in p_police[1]

    # Court / Legal Verdict
    p_court = get_character_personas("Dialogue", 2, "Funny", "Funny", topic_or_script="Supreme Court legal verdict on bail plea")
    assert any("Lawyer" in p or "वकील" in p for p in p_court)
    assert any("Trader" in p or "दुकानदार" in p for p in p_court)

    # Indian Politics / Election / Netaji
    p_election = get_character_personas("Dialogue", 2, "Funny", "Funny", topic_or_script="Municipal election Netaji rally and voting")
    assert any("Netaji" in p or "Corporator" in p or "पार्षद" in p for p in p_election)
    # Tapri personas were removed: election topics must not default to chai-tapri characters
    assert not any("tapri" in p.lower() or "टपरी" in p or "chai" in p.lower() for p in p_election)

    # Tech / WFO Mandate
    p_tech = get_character_personas("Dialogue", 2, "Funny", "Funny", topic_or_script="Tech companies mandate 5-day WFO biometric punch-in")
    assert any("Tech" in p or "फाउंडर" in p for p in p_tech)
    assert any("Auto" in p or "ऑटो" in p for p in p_tech)

    # Solo script-grounded persona
    p_solo_police = get_character_personas("Dialogue", 1, "Funny", "Funny", topic_or_script="Traffic police challan")
    assert "Police" in p_solo_police[0] or "Constable" in p_solo_police[0]

    # Trio script-grounded persona
    p_trio_gov = get_character_personas("Dialogue", 3, "Funny", "Funny", topic_or_script="Government clerk babu pension issue")
    assert len(p_trio_gov) == 3
    assert any("Babu" in p or "बाबू" in p for p in p_trio_gov)


def test_preference_persistence_and_categories():
    """Verify preference persistence (headline, retries, category) and Indian politics category support."""
    from core.config import save_config, load_config
    from tools.news_fetcher import news_fetcher

    # 1. Indian Politics NewsFetcher method exists
    assert hasattr(news_fetcher, "get_top_indian_politics_news")

    # 2. Config persistence for headline, max_retries, and politics category
    save_config("selected_headline", "Parliament passes landmark governance bill")
    save_config("max_retries", 5)
    save_config("news_category", "🏛️ Indian Politics, Elections & Governance")

    cfg = load_config()
    assert cfg["selected_headline"] == "Parliament passes landmark governance bill"
    assert cfg["max_retries"] == 5
    assert cfg["news_category"] == "🏛️ Indian Politics, Elections & Governance"


def test_professional_screenplay_scene_description_and_clean_beats():
    """Verify camera and setting preamble belong only in Scene Description, and beats contain pure action."""
    from agents.scene_director import clean_beat_action
    from core.screenplay_formatter import (
        format_industry_screenplay as format_professional_screenplay,
        format_industry_screenplay as format_plain_script,
        derive_scene_detail,
    )


    # 1. clean_beat_action removes camera/location preamble
    raw_1 = "Handheld dynamic 9:16 shot at a vibrant Indian street market; Priya delivers a hilarious opening quip with expressive comedic gestures"
    clean_1 = clean_beat_action(raw_1)
    assert clean_1 == "Priya delivers a hilarious opening quip with expressive comedic gestures"
    assert "Handheld dynamic 9:16 shot" not in clean_1
    assert "street market" not in clean_1

    raw_2 = "Low-angle vertical (9:16) establishing hook shot at a rustic wooden bench of a roadside market, nestled beneath a leafy banyan tree. Priya aggressively slaps her smartphone."
    clean_2 = clean_beat_action(raw_2)
    assert clean_2 == "Priya aggressively slaps her smartphone."

    # 2. Professional screenplay formatting
    test_script = ReelScript(
        id=1,
        title="5-Day WFO Reel",
        angle="Funny & Relatable",
        hook_hindi="रोहन सुनो!",
        narration_hindi="रोहन सुनो! WFO आ गया भाई!",
        call_to_action="शेयर करें",
        scenes=[
            SceneItem(
                scene_number=1,
                character="👩 Priya (Tech Founder / Friend 1)",
                dialogue="रोहन सुनो! 5-दिन WFO अनिवार्य कर दिया, आज़ादी छिन गई यार!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Handheld dynamic 9:16 shot at a vibrant Indian street market; Priya aggressively slaps her smartphone onto the bench",
                on_screen_text="आज़ादी छिन गई! 😭",
                audio_sfx="Cutting Chai Clink",
            ),
            SceneItem(
                scene_number=2,
                character="🧑 Rohan (Auto Driver / Friend 2)",
                dialogue="सच में, टेक कंपनियों ने बायोमेट्रिक पंच-इन अनिवार्य कर दिया!",
                timestamp="0:03 - 0:15",
                visual_b_roll="Rohan smirks, mock-presses his thumb on the RFID badge, and sips cutting chai",
                on_screen_text="बायोमेट्रिक हाजिरी! 🚨",
                audio_sfx="Tea Sip",
            ),
        ],
        word_count=18,
        max_words=34,
        target_duration_sec=15,
    )

    pro = format_professional_screenplay(test_script, "5-Day WFO Mandate")
    assert "[Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]" in pro
    assert "SCENE DETAIL:" in pro
    assert "CHARACTERS & CLOTHING:" in pro
    assert "PRIYA:" in pro
    assert "ROHAN:" in pro

    # Per FR-9.3: timestamps are omitted by default in exported screenplay
    assert "[Time:" not in pro
    assert "Camera Focus & Action: Single continuous handheld take starting on Priya." in pro
    assert "Priya aggressively slaps her smartphone onto the bench" in pro
    assert "Handheld dynamic 9:16 shot" not in pro
    # Ensure no contradictory cuts or over-engineered metadata
    assert "The camera pans smoothly to Rohan without cutting." in pro
    assert "~2.3 w/s" not in pro
    assert "speech rate" not in pro
    assert "word count" not in pro.lower()

    # Plain script matches canonical screenplay
    plain = format_plain_script(test_script)
    assert "[Format Requirement: 9:16 Vertical Reel" in plain
    assert "SCENE DETAIL:" in plain
    assert "CHARACTERS & CLOTHING:" in plain
    assert "Camera Focus & Action:" in plain
    assert "Handheld dynamic 9:16 shot" not in plain

    # 3. 10-Second Fast-Paced Screenplay Formatting
    s10 = ReelScript(
        id=2,
        title="10s Fast Reel",
        angle="Funny & Relatable",
        hook_hindi="डिग्री ले ली!",
        narration_hindi="डिग्री ले ली, नौकरी कहाँ है?",
        call_to_action="",
        scenes=[
            SceneItem(
                scene_number=1,
                character="Ananya",
                timestamp="0:00 - 0:03",
                scene_atmosphere="Very fast-paced, high-energy vibe to fit the 10-second limit.",
                visual_b_roll="Fast whip-pan to Ananya slamming a book on the library counter.",
                on_screen_text="No Jobs?",
                audio_sfx="Fast whoosh + heavy book slam.",
                dialogue="डिग्री ले ली, नौकरी कहाँ है?",
            ),
            SceneItem(
                scene_number=2,
                character="Vikram",
                timestamp="0:03 - 0:06",
                visual_b_roll="Quick pan to Vikram shoving his phone screen into the frame.",
                on_screen_text="",
                audio_sfx="Record scratch effect.",
                dialogue="सिस्टम को स्टूडेंट नहीं, अंधभक्त चाहिए!",
            ),
            SceneItem(
                scene_number=3,
                character="Ananya",
                timestamp="0:06 - 0:10",
                visual_b_roll="Fast pull back to frame both. Ananya mockingly tosses her book aside.",
                on_screen_text="Need new coaching!",
                audio_sfx="Comedic drum punchline.",
                dialogue="तो भाई, मेरा भी अंधभक्ति कोचिंग में एडमिशन करा दे!",
            ),
        ],
        word_count=18,
        max_words=22,
        target_duration_sec=10,
    )
    pro10 = format_professional_screenplay(s10)
    assert "Very fast-paced, high-energy vibe to fit the 10-second limit." in pro10
    assert "Camera Focus & Action: Fast whip-pan to Ananya slamming a book on the library counter." in pro10
    assert "Camera Focus & Action: Quick pan to Vikram shoving his phone screen into the frame." in pro10
    assert "Camera Focus & Action: Fast pull back to frame both. Ananya mockingly tosses her book aside." in pro10
    assert 'ANANYA: "डिग्री ले ली, नौकरी कहाँ है?"' in pro10
    assert 'VIKRAM: "सिस्टम को स्टूडेंट नहीं, अंधभक्त चाहिए!"' in pro10
    assert 'ANANYA: "तो भाई, मेरा भी अंधभक्ति कोचिंग में एडमिशन करा दे!"' in pro10

    # 4. User preference toggle for optional overlays and SFX
    pro_no_overlay = format_professional_screenplay(s10, include_overlays=False)
    assert "Text Overlay (Optional):" not in pro_no_overlay
    assert "Audio/SFX:" in pro_no_overlay

    pro_no_sfx = format_professional_screenplay(s10, include_sfx=False)
    assert "Audio/SFX:" not in pro_no_sfx
    assert "Text Overlay (Optional):" in pro_no_sfx





def test_creative_guidelines():
    """Verify that angle provides imaginary scene setup and comedy mandates genuine humor."""
    guidelines = get_creative_guidelines("Dialogue", 2, "😂 Comedy & Sarcastic Banter (ह्यूमर)", "Funny & Relatable")
    assert "GENUINELY FUNNY" in guidelines
    assert "JOKE MANDATE" in guidelines
    # The chai-tapri comedy example was removed from all guidance
    assert "chai tapri" not in guidelines
    assert "tapri" not in guidelines.lower()
    assert "Do NOT just report dry news" in guidelines
    assert "INSTAGRAM STORY" in guidelines
    assert "GENDER DIVERSITY" in guidelines


def test_tailored_instruction_matrix():
    """Verify instruction generator covers all tone, angle, and style combinations and sample story precedence."""
    for tone in TONE_INSTRUCTIONS:
        for angle in ANGLE_INSTRUCTIONS:
            for style in SCENE_STYLE_INSTRUCTIONS:
                inst = build_tailored_instruction(
                    topic="AI in Education",
                    duration_sec=30,
                    tone=tone,
                    angle=angle,
                    scene_style=style,
                    character_count=2,
                    sample_story="Two professors argue humorously over AI grading homework.",
                )
                assert "AI in Education" in inst
                assert "30 seconds" in inst
                assert "Recommended" in inst
                assert "SAMPLE STORY" in inst
                # Sample is a style reference only: never copied, never takes precedence
                assert "STYLE REFERENCE ONLY" in inst
                assert "DO NOT copy" in inst
                assert "HIGHEST PRECEDENCE" not in inst


def test_configuration_compliance_gate():
    """Verify testing agent checks character separation, word budget, and issues retry recommendation on failure."""
    # Compliant script
    good_script = ReelScript(
        id=1,
        title="Good Script",
        angle="Funny",
        hook_hindi="अरे सुनो!",
        narration_hindi="दोस्त 1: सुनो! दोस्त 2: क्या हुआ भाई? दोस्त 1: WFO आ गया!",
        call_to_action="कमेंट करें!",
        scenes=[
            SceneItem(scene_number=1, character="🧑 Friend 1", dialogue="अरे सुनो!", timestamp="0:00 - 0:03", visual_b_roll="Tapri setup", on_screen_text="सुनो", audio_sfx="Whoosh"),
            SceneItem(scene_number=2, character="🧔 Friend 2", dialogue="क्या हुआ भाई? WFO आ गया!", timestamp="0:03 - 0:15", visual_b_roll="Tapri reaction", on_screen_text="WFO", audio_sfx="Laugh"),
        ],
        word_count=18,
        max_words=34,
    )
    passed, notes, retry_rec = chief_editor.audit_configuration_compliance(
        scripts=[good_script],
        target_seconds=15,
        character_count=2,
        scene_style="Dialogue",
        tone="Funny",
        sample_story=None,
    )
    assert passed is True
    assert retry_rec is None

    # Non-compliant script (only 1 character when 2 were requested)
    bad_script = ReelScript(
        id=2,
        title="Bad Script",
        angle="Funny",
        hook_hindi="अरे सुनो!",
        narration_hindi="सुनो! WFO आ गया!",
        call_to_action="कमेंट करें!",
        scenes=[
            SceneItem(scene_number=1, character="🎙️ Presenter", dialogue="अरे सुनो!", timestamp="0:00 - 0:03", visual_b_roll="Solo", on_screen_text="सुनो", audio_sfx="Whoosh"),
            SceneItem(scene_number=2, character="🎙️ Presenter", dialogue="WFO आ गया!", timestamp="0:03 - 0:15", visual_b_roll="Solo", on_screen_text="WFO", audio_sfx="Whoosh"),
        ],
        word_count=18,
        max_words=34,
    )
    b_passed, b_notes, b_retry_rec = chief_editor.audit_configuration_compliance(
        scripts=[bad_script],
        target_seconds=15,
        character_count=2,
        scene_style="Dialogue",
        tone="Funny",
        sample_story=None,
    )
    assert b_passed is False
    assert b_retry_rec is not None
    assert "Recommendation" in b_retry_rec


def test_end_to_end_comedy_dialogue_pipeline():
    """Verify that the reel workflow produces a 2-character comedic dialogue with distinct scenes."""
    news_topic = "Tech companies mandate 5-day work from office with biometric punch-in."
    duration_sec = 15
    budget = get_duration_budget(duration_sec)

    pipeline = reel_workflow.run_stream(
        news_input=news_topic,
        scenario="Make a funny conversation between two friends reacting to 5-day WFO mandate.",
        batch_size=1,
        target_seconds=duration_sec,
        engine_mode="first_local_then_agy",
        max_retries=3,
        character_count=2,
        scene_style="Dialogue",
        preferred_tone="😂 Comedy & Sarcastic Banter (ह्यूमर)",
        preferred_angle="Funny & Relatable",
        sample_story="दो दोस्त 5 दिन ऑफिस जाने की खबर सुनकर रोने की एक्टिंग करते हैं।",
    )

    result = None
    for step in pipeline:
        if step.get("completed"):
            result = step["data"]["batch_result"]

    assert result is not None
    assert len(result.scripts) >= 1
    script = result.scripts[0]

    # 1. Pacing & word count verification
    assert script.word_count <= budget["max_words"], f"Word count {script.word_count} exceeded max {budget['max_words']}"

    # 2. Scene structure & Character turns
    assert len(script.scenes) >= 2, f"Expected at least 2 scenes, got {len(script.scenes)}"
    char_names = [sc.character for sc in script.scenes]
    print(f"Generated Scene Characters: {char_names}")

    # For 2 characters, scene 1 and scene 2 must feature different characters!
    assert char_names[0] != char_names[1], f"Scene 1 and Scene 2 have same character: {char_names}"
    assert "Friend" in char_names[0] or "दोस्त" in char_names[0]
    assert "Friend" in char_names[1] or "दोस्त" in char_names[1]

    # 3. Visuals & Prompts reflect creative imaginary situation (never a default tapri)
    v1 = script.scenes[0].visual_b_roll
    assert "tapri" not in v1.lower() and "टपरी" not in v1
    assert "comedic" in v1.lower() or "street" in v1.lower() or "friend" in v1.lower() or "priya" in v1.lower() or len(v1) > 10

    # 4. Google Flow / Veo Prompt synthesized
    assert script.scenes[0].video_prompt is not None
    assert "9:16" in script.scenes[0].video_prompt.aspect_ratio
    assert "Google Flow / Veo" in script.scenes[0].video_prompt.ai_engine

    # 5. Sub-instructions passed to all 7 sub-agents
    assert len(result.sub_instructions) == 7
    assert "dialogue_writer" in result.sub_instructions

    # 6. Sample story incorporated and precedence recorded
    assert result.sample_story is not None
    assert "चाय की दुकान" in result.sample_story


def test_sadness_tone_angle_and_lament_style():
    """Verify personas, guidelines, tailored instructions, and visuals for sadness/lament."""
    # 1. Personas
    p_sad_1 = get_character_personas("Lament", 1, "😢 Emotional & Heartbreaking (भावुक / दुखद)", "Tragic & Heartbreaking")
    assert len(p_sad_1) == 1
    assert "Grieving" in p_sad_1[0] or "भावुक" in p_sad_1[0]

    p_sad_2 = get_character_personas("Lament", 2, "😢 Emotional & Heartbreaking (भावुक / दुखद)", "Tragic & Heartbreaking")
    assert len(p_sad_2) == 2
    assert "Bereaved" in p_sad_2[0] or "शोकाकुल" in p_sad_2[0]
    assert "Consoling" in p_sad_2[1] or "सहयोगी" in p_sad_2[1]

    # 2. Guidelines
    g_sad = get_creative_guidelines("Lament", 2, "😢 Emotional & Heartbreaking (भावुक / दुखद)", "Tragic & Heartbreaking")
    assert "deep emotional weight" in g_sad
    assert "personal loss" in g_sad
    assert "LAMENT" in g_sad

    # 3. Tailored Instruction
    inst = build_tailored_instruction(
        topic="Tragic Bridge Collapse",
        duration_sec=20,
        tone="😢 Emotional & Heartbreaking (भावुक / दुखद)",
        angle="Tragic & Heartbreaking",
        scene_style="Lament",
        character_count=2,
    )
    assert "Tragic Bridge Collapse" in inst
    assert "Lament" in inst
    assert "Sadness & Grief" in inst or "भावुक" in inst


def test_dead_configs_purged_and_update_instruction():
    """Verify dead configs are removed; instruction generator syncs only creative fields.

    batch_count/max_retries are operational pipeline settings and must NOT leak
    into the generated creative instruction. source_mode/news_category were merged
    into a single story_source dropdown.
    """
    from core.config import DEFAULT_CONFIG, load_config

    # Ensure dead configs are removed
    assert "enable_self_healing" not in DEFAULT_CONFIG
    assert "studio_layout" not in DEFAULT_CONFIG
    assert "frame_count" not in DEFAULT_CONFIG
    assert "source_mode" not in DEFAULT_CONFIG
    assert "news_category" not in DEFAULT_CONFIG

    # Ensure active configs exist
    expected_keys = {
        "default_engine", "default_tone", "default_duration", "batch_count",
        "max_retries", "story_source", "selected_headline", "selected_script_index",
        "default_angle", "character_count", "scene_style"
    }
    assert expected_keys.issubset(set(DEFAULT_CONFIG.keys()))

    # Verify tailored instruction includes only creative parameters
    inst = build_tailored_instruction(
        topic="Varanasi Dev Deepawali celebration",
        duration_sec=20,
        tone="🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)",
        angle="Dramatic Storytelling",
        scene_style="Narration",
        character_count=1,
        sample_story="Ghats glow with millions of diyas.",
    )
    assert "20 seconds" in inst
    assert "timeless Indian wisdom" in inst
    assert "Dramatic Storytelling" in inst
    assert "Narration" in inst
    assert "1 speaking character(s)" in inst
    assert "Ghats glow with millions of diyas" in inst
    # Operational pipeline settings must not leak into the creative instruction
    assert "script version" not in inst
    assert "retry attempt" not in inst
    # Unwanted frame scenes and engine are strictly excluded from instruction
    assert "scene frame" not in inst
    assert "first_local_then_agy" not in inst
    assert "fm_only" not in inst
    assert "agy_only" not in inst


def test_no_commenting_in_dialogue_or_script():
    """Verify that commenting, social media CTAs, and viewer engagement meta are barred from dialogue."""
    from agents.dialogue_writer import strip_commenting_and_cta, smart_trim_dialogue, get_creative_guidelines
    from core.prompt_matrix import build_tailored_instruction

    dirty_dialogue = "भाई 5 दिन ऑफिस जाना पड़ेगा! नीचे कमेंट करके बताएं आपकी क्या राय है! लाइक और शेयर करें!"
    cleaned = strip_commenting_and_cta(dirty_dialogue)
    assert "कमेंट" not in cleaned
    assert "शेयर" not in cleaned
    assert "भाई 5 दिन ऑफिस जाना पड़ेगा!" in cleaned

    # smart_trim_dialogue must never append CTA
    trimmed = smart_trim_dialogue("दोस्त चाय पीओ और काम करो।", max_words=10, rec_words=8, cta="कमेंट करें!")
    assert "कमेंट करें" not in trimmed
    assert "दोस्त चाय पीओ" in trimmed

    # Creative guidelines for Dialogue must mandate in-universe conversation without commenting
    guidelines = get_creative_guidelines("Dialogue", 2, "😂 Comedy & Sarcastic Banter", "Funny & Relatable")
    assert "NO social media commenting" in guidelines
    assert "NO CTA" in guidelines

    # Master instruction must prohibit commenting in dialogue
    inst = build_tailored_instruction(
        topic="Tech WFO Mandate",
        duration_sec=15,
        tone="😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)",
        angle="Funny & Relatable",
        scene_style="Dialogue",
        character_count=2,
    )
    assert "NO social media commenting" in inst
    assert "pure conversation between characters" in inst


def test_argument_style_and_relational_characters():
    """Verify Argument scene style, Heated Argument tone, and relational character dynamics."""
    from core.screenplay_formatter import get_character_attire

    # 1. Argument Tone and Scene Style in tailored instructions
    inst = build_tailored_instruction(
        topic="Inflation in Household Budget",
        duration_sec=20,
        tone="⚔️ Heated Argument & Clash (तीखी बहस / तकरार)",
        angle="Dramatic Storytelling",
        scene_style="Argument",
        character_count=2,
    )
    assert "Argument" in inst
    assert "Heated Argument & Clash" in inst or "तीखी बहस" in inst
    assert "sharp conflict" in inst.lower() or "clash" in inst.lower()

    # 2. Creative Guidelines for Argument style
    guide = get_creative_guidelines("Argument", 2, "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)", "Dramatic Storytelling")
    assert "HEATED ARGUMENT" in guide or "ARGUMENT" in guide
    assert "sharp verbal spar" in guide.lower() or "clash" in guide.lower()

    # 3. Relational Character Grounding
    # Husband & Wife for household / gas / ration / inflation
    hw_personas = get_character_personas("Argument", 2, "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)", "Dramatic Storytelling", topic_or_script="LPG gas cylinder price hike and ration expense")
    assert any("Wife" in p or "पत्नी" in p for p in hw_personas)
    assert any("Husband" in p or "पति" in p for p in hw_personas)

    # Father & Son for coaching / degree / generation gap
    fs_personas = get_character_personas("Argument", 2, "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)", "Dramatic Storytelling", topic_or_script="Engineering degree coaching fees versus startup dreams")
    assert any("Father" in p or "पिता" in p for p in fs_personas)
    assert any("Son" in p or "बेटा" in p for p in fs_personas)

    # Colleagues for WFO / appraisal / corporate deadlines
    col_personas = get_character_personas("Dialogue", 2, "Professional", "Analytical", topic_or_script="Quarterly appraisal ratings and mandatory WFO attendance")
    assert any("Colleague" in p or "Senior" in p or "Junior" in p or "कलीग" in p for p in col_personas)

    # Neighbors for society gossip / parking
    neigh_personas = get_character_personas("Argument", 2, "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)", "Dramatic Storytelling", topic_or_script="Apartment parking spot dispute and society gossip")
    assert any("Neighbor" in p or "पड़ोसी" in p for p in neigh_personas)

    # 4. Character Attire for Relational Personas
    attire_wife = get_character_attire("Wife / गृहिणी")
    assert "saree" in attire_wife.lower() or "kurti" in attire_wife.lower()

    attire_husband = get_character_attire("Husband / पति")
    assert "shirt" in attire_husband.lower() or "trousers" in attire_husband.lower() or "casual" in attire_husband.lower()

    attire_father = get_character_attire("Father / पिता")
    assert "kurta" in attire_father.lower() or "spectacles" in attire_father.lower()

    attire_colleague = get_character_attire("Senior Colleague / कलीग")
    assert "corporate" in attire_colleague.lower() or "smart-casual" in attire_colleague.lower() or "lanyard" in attire_colleague.lower() or "shirt" in attire_colleague.lower()


def test_sample_story_is_style_reference_not_copied():
    """Verify the sample story is a STYLE REFERENCE ONLY: its names, locations,
    and situations are never copied into characters or scenes."""
    from core.screenplay_formatter import format_industry_screenplay

    # 1. Sample script with explicit CHARACTERS & CLOTHING block — names and
    #    tapri location must NOT be copied into the selected personas.
    sample_script_block = """
[Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]
SCENE DETAIL:
⚬ A bustling local Indian street chai tapri. Very fast-paced, high-energy vibe to fit the 10-second limit.
CHARACTERS & CLOTHING:
⚬ ANANYA: Casual college-going attire (e.g., jeans and a simple kurti).
⚬ VIKRAM: Everyday street casual wear (e.g., t-shirt and jeans).
[Time: 0:00 - 0:03]
ANANYA: "डिग्री ले ली, नौकरी कहाँ है?"
[Time: 0:03 - 0:06]
VIKRAM: "सिस्टम को स्टूडेंट नहीं, अंधभक्त चाहिए!"
"""
    p_block = get_character_personas("Dialogue", 2, "Funny", "Funny", sample_story=sample_script_block)
    assert len(p_block) == 2
    # Sample names are NOT copied — personas are grounded afresh
    assert "Ananya" not in p_block[0] and "Ananya" not in p_block[1]
    assert "Vikram" not in p_block[0] and "Vikram" not in p_block[1]
    # Sample tapri location is NOT copied into personas
    assert not any("tapri" in p.lower() or "टपरी" in p or "chai" in p.lower() for p in p_block)

    # 2. Sample story with dialogue cues (Wife: ... Husband: ...)
    sample_dialogue_cues = """
Wife: "सब्जी और राशन का बिल देखकर तो होश उड़ गए!"
Husband: "कमाई वही है और खर्चे दोगुने हो गए हैं!"
"""
    p_cues = get_character_personas("Argument", 2, "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)", "Dramatic", sample_story=sample_dialogue_cues)
    assert len(p_cues) == 2
    assert any("Wife" in p or "पत्नी" in p for p in p_cues)
    assert any("Husband" in p or "पति" in p for p in p_cues)

    # 3. Narrative relationship mention (Father & Son)
    sample_father_son = "Father and son heated debate regarding coaching classes fees and degree value."
    p_fs = get_character_personas("Argument", 2, "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)", "Dramatic", sample_story=sample_father_son)
    assert len(p_fs) == 2
    assert any("Father" in p or "पिता" in p for p in p_fs)
    assert any("Son" in p or "बेटा" in p for p in p_fs)

    # 4. Narrative domain mention (hospital/doctor) — the system picks a grounded
    #    socioeconomic pair for the domain; it does NOT copy roles from the sample.
    sample_doc_pat = "Hospital doctor discusses medicine costs with a visitor."
    p_dp = get_character_personas("Dialogue", 2, "Funny", "Funny", sample_story=sample_doc_pat)
    assert len(p_dp) == 2
    assert any("Doctor" in p or "चिकित्सक" in p or "डॉक्टर" in p for p in p_dp)
    assert any("Construction Worker" in p or "मजदूर" in p for p in p_dp)

    # 5. Screenplay Formatter custom clothing and scene detail extraction from sample script
    #    (neutral sample block — the formatter honors the user's own draft detail,
    #    but generation never defaults to a tapri)
    sample_neutral_block = """
[Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]
SCENE DETAIL:
⚬ A bustling college campus courtyard. Very fast-paced, high-energy vibe to fit the 10-second limit.
CHARACTERS & CLOTHING:
⚬ ANANYA: Casual college-going attire (e.g., jeans and a simple kurti).
⚬ VIKRAM: Everyday street casual wear (e.g., t-shirt and jeans).
[Time: 0:00 - 0:03]
ANANYA: "डिग्री ले ली, नौकरी कहाँ है?"
[Time: 0:03 - 0:06]
VIKRAM: "सिस्टम को स्टूडेंट नहीं, अंधभक्त चाहिए!"
"""
    test_script = ReelScript(
        id=99,
        title="10s Fast Reel Sample",
        angle="Funny & Relatable",
        hook_hindi="डिग्री ले ली!",
        narration_hindi="डिग्री ले ली, नौकरी कहाँ है?",
        call_to_action="",
        sample_story_used=sample_neutral_block,
        scenes=[
            SceneItem(
                scene_number=1,
                character="Ananya",
                timestamp="0:00 - 0:03",
                visual_b_roll="Fast whip-pan to Ananya slamming a book on the library counter.",
                dialogue="डिग्री ले ली, नौकरी कहाँ है?",
                on_screen_text="No Jobs?",
                audio_sfx="Whoosh",
            ),
            SceneItem(
                scene_number=2,
                character="Vikram",
                timestamp="0:03 - 0:06",
                visual_b_roll="Quick pan to Vikram shoving his phone screen into the frame.",
                dialogue="सिस्टम को स्टूडेंट नहीं, अंधभक्त चाहिए!",
                on_screen_text="",
                audio_sfx="Record Scratch",
            ),
        ],
        word_count=12,
        max_words=20,
        target_duration_sec=10,
    )
    formatted = format_industry_screenplay(test_script)
    # Verify custom clothing from sample script is 100% honored
    assert "ANANYA: Casual college-going attire (e.g., jeans and a simple kurti)." in formatted
    assert "VIKRAM: Everyday street casual wear (e.g., t-shirt and jeans)." in formatted
    # Verify custom scene detail from sample script is 100% honored
    assert "A bustling college campus courtyard. Very fast-paced, high-energy vibe to fit the 10-second limit." in formatted


def test_script_continuity_and_setting_analyzer():
    """Verify setting harmonization, dialogue target healing, and visual kinematics prop enhancement."""
    from core.script_analyzer import (
        audit_and_heal_dialogue_targets,
        audit_and_enhance_visual_kinematics,
        harmonize_setting_description,
        analyze_and_heal_script,
    )
    from core.models import SceneItem, ReelScript

    # 1. Dialogue Target Auditor: Netaji addressing Rohan with marital vocative
    scenes = [
        SceneItem(
            scene_number=1,
            character="🏛️ Netaji Tiwari (Ward Corporator / Friend 1)",
            dialogue="अरे सुनती हो! एक कड़क चाय बनाना!",
            timestamp="0:00 - 0:03",
            visual_b_roll="Netaji walks up to the stall.",
            on_screen_text="चाय",
            audio_sfx="Whoosh",
        ),
        SceneItem(
            scene_number=2,
            character="☕ Rohan (Street Chai Tapri Owner / Friend 2)",
            dialogue="नेताजी, चाय छोड़िए, अस्पताल की नई पॉलिसी देखिए!",
            timestamp="0:03 - 0:06",
            visual_b_roll="Rohan shows phone.",
            on_screen_text="पॉलिसी",
            audio_sfx="Clink",
        ),
    ]

    healed_scenes = audit_and_heal_dialogue_targets(scenes)
    # Ensure marital vocative 'सुनती हो' was healed to address Rohan directly
    assert "सुनती हो" not in healed_scenes[0].dialogue
    assert "रोहन भाई" in healed_scenes[0].dialogue or "रोहन सुनो" in healed_scenes[0].dialogue

    # 2. Dialogue Target Auditor: Husband addressing Wife should NOT be modified
    hw_scenes = [
        SceneItem(
            scene_number=1,
            character="🧑 Rajesh (Husband / Salaried Man)",
            dialogue="अरे सुनती हो! इस महीने का राशन का बिल देखा?",
            timestamp="0:00 - 0:03",
            visual_b_roll="Rajesh holds electricity bill.",
            on_screen_text="बिल",
            audio_sfx="Paper",
        ),
        SceneItem(
            scene_number=2,
            character="👩 Sunita (Wife / Pragmatic Homemaker)",
            dialogue="हाँ जी, दाल और गैस सिलेंडर दोनों महंगे हो गए हैं!",
            timestamp="0:03 - 0:06",
            visual_b_roll="Sunita stirs tea pot.",
            on_screen_text="सिलेंडर",
            audio_sfx="Tea",
        ),
    ]
    hw_healed = audit_and_heal_dialogue_targets(hw_scenes)
    assert "सुनती हो" in hw_healed[0].dialogue

    # 3. Visual Kinematics & Prop Handling: Tea vendor handling phone
    raw_tea_scenes = [
        SceneItem(
            scene_number=1,
            character="☕ Rohan (Street Chai Tapri Owner / Friend 2)",
            dialogue="नेताजी ये देखिए!",
            timestamp="0:00 - 0:03",
            visual_b_roll="Rohan turns with wide-eyed disbelief, thrusting mobile phone forward showing visuals of hospital",
            on_screen_text="देखो",
            audio_sfx="Phone",
        )
    ]
    enhanced_scenes = audit_and_enhance_visual_kinematics(raw_tea_scenes)
    # Verify tea vendor prop handling (strainer / cloth) is incorporated
    assert "strainer" in enhanced_scenes[0].visual_b_roll.lower() or "cloth" in enhanced_scenes[0].visual_b_roll.lower()

    # 4. Setting Mismatch Resolution: Hospital topic + Chai Tapri character/SFX
    mismatch_script = ReelScript(
        id=77,
        title="Hospital Fee Hike",
        angle="Funny & Relatable",
        hook_hindi="अरे सुनो!",
        narration_hindi="अरे सुनो! अस्पताल का बिल!",
        call_to_action="",
        scenes=[
            SceneItem(
                scene_number=1,
                character="☕ Rohan (Street Chai Tapri Owner / Friend 2)",
                dialogue="अरे सुनो!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Rohan pours cutting chai from kettle onto tea glasses at the tapri wooden bench",
                on_screen_text="अस्पताल",
                audio_sfx="Street Tapri Clatter + Chai Clink",
            ),
            SceneItem(
                scene_number=2,
                character="🏛️ Netaji Tiwari (Ward Corporator / Friend 1)",
                dialogue="अस्पताल ने इमरजेंसी फीस बढ़ा दी!",
                timestamp="0:03 - 0:06",
                visual_b_roll="Netaji wipes tea drops off his Nehru jacket",
                on_screen_text="फीस",
                audio_sfx="Shock",
            ),
        ],
        word_count=10,
        max_words=18,
        target_duration_sec=10,
    )
    harmonized_setting = harmonize_setting_description(mismatch_script)
    # Tapri-guard: the setting must stay news-grounded (hospital) and must NOT
    # be relocated to a tea stall / tapri just because the script has chai props.
    assert "hospital" in harmonized_setting.lower()
    assert "tea stall" not in harmonized_setting.lower()
    assert "tapri" not in harmonized_setting.lower()
    # Institutional setting is kept as-is.
    assert "casualty waiting area" in harmonized_setting.lower()


def test_common_sense_validator_step_and_retry_feedback():
    """Verify common sense validator step detects mismatches, passes feedback to previous steps, and heals via retry."""
    from core.script_analyzer import common_sense_validator
    from agents.chief_editor import chief_editor
    from core.models import SceneItem, ReelScript

    # 1. Script with dialogue target mismatch and kinematics issue
    problematic_script = ReelScript(
        id=88,
        title="Problematic Script",
        angle="Funny & Relatable",
        hook_hindi="अरे सुनती हो!",
        narration_hindi="अरे सुनती हो! चाय देना!",
        call_to_action="",
        scenes=[
            SceneItem(
                scene_number=1,
                character="🏛️ Netaji Tiwari (Ward Corporator / Friend 1)",
                dialogue="अरे सुनती हो! एक कप चाय देना!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Netaji walks up to tapri.",
                on_screen_text="चाय",
                audio_sfx="Whoosh",
            ),
            SceneItem(
                scene_number=2,
                character="☕ Rohan (Street Chai Tapri Owner / Friend 2)",
                dialogue="नेताजी, चाय तैयार है!",
                timestamp="0:03 - 0:06",
                visual_b_roll="Rohan thrusting mobile phone forward showing visuals",
                on_screen_text="फोन",
                audio_sfx="Phone",
            ),
        ],
        word_count=10,
        max_words=18,
        target_duration_sec=10,
    )

    # 2. Common Sense Validator audit detects issues
    is_valid, issues, feedback = common_sense_validator.audit_screenplay(problematic_script)
    assert is_valid is False
    assert any("Dialogue target mismatch" in iss for iss in issues)
    assert any("Visual kinematics mismatch" in iss for iss in issues)
    assert "feedback" in locals() and len(feedback) > 0

    # 3. Integrated into Chief Editor compliance testing gate before healing
    passed, notes, retry_rec = chief_editor.audit_configuration_compliance(
        scripts=[problematic_script],  # Problematic script before healing fails gate
        target_seconds=10,
        character_count=2,
        scene_style="Dialogue",
        tone="Funny",
    )
    # The gate caught the mismatch before healing
    assert passed is False
    assert any("Dialogue target mismatch" in n for n in notes)

    # 4. Heal and revalidate: feedback passed back to previous steps
    healed_script, re_valid, re_feedback = common_sense_validator.heal_and_revalidate(problematic_script, feedback)
    assert re_valid is True
    # Dialogue target healed: Netaji addresses Rohan directly
    assert "सुनती हो" not in healed_script.scenes[0].dialogue
    assert "रोहन" in healed_script.scenes[0].dialogue
    # Visual kinematics enhanced: Rohan holds tea strainer / cloth
    assert "strainer" in healed_script.scenes[1].visual_b_roll.lower() or "cloth" in healed_script.scenes[1].visual_b_roll.lower()

    # After healing, it passes compliance gate!
    passed_healed, notes_healed, retry_rec_healed = chief_editor.audit_configuration_compliance(
        scripts=[healed_script],
        target_seconds=10,
        character_count=2,
        scene_style="Dialogue",
        tone="Funny",
    )
    assert passed_healed is True


def test_contextual_selector_and_sir_government_domain():
    """Verify contextual selector agent, SIR government office venue, and professional wardrobe alignment."""
    from agents.contextual_selector import contextual_selector
    from agents.dialogue_writer import select_script_grounded_pair
    from core.screenplay_formatter import format_industry_screenplay, get_character_attire

    # 1. Domain Detection
    assert contextual_selector.detect_domain("Dholera SIR land acquisition and semiconductor mega project") == "government_sir"
    assert contextual_selector.detect_domain("Government hospital emergency ward and medicine shortage") == "healthcare"
    assert contextual_selector.detect_domain("Supreme Court bail hearing on public interest plea") == "legal"
    assert contextual_selector.detect_domain("IT tech park corporate WFO biometric attendance") == "tech_corporate"
    assert contextual_selector.detect_domain("LPG cylinder subsidy and kitchen ration budget") == "domestic"

    # 2. Contextual Scene & Character Selection for SIR
    sir_choice = contextual_selector.select_scene_and_characters(
        news_topic="Dholera SIR industrial zone blueprint approval",
        character_count=2,
        duration_sec=15,
    )
    assert "government administrative planning office" in sir_choice["setting_detail"].lower()
    assert "chai tapri" not in sir_choice["setting_detail"].lower()
    assert any("Officer" in p or "अधिकारी" in p for p in sir_choice["personas"])
    assert any("Investor" in p or "उद्यमी" in p for p in sir_choice["personas"])
    assert "blueprint map" in " ".join(sir_choice["props"]).lower()

    # 3. Grounded Personas from Dialogue Writer for SIR
    sir_pair = select_script_grounded_pair("Dholera SIR industrial corridor development")
    assert any("Officer" in p or "अधिकारी" in p for p in sir_pair)
    assert any("Investor" in p or "उद्यमी" in p for p in sir_pair)

    # 4. Attire Derivation for Government Officer & Investor
    attire_officer = get_character_attire("Government Administrative Officer / अधिकारी")
    assert "collared shirt" in attire_officer.lower() or "formal shirt" in attire_officer.lower()
    assert "ballpoint pens" in attire_officer.lower()
    assert "lanyard" in attire_officer.lower()

    attire_investor = get_character_attire("Industrial Investor / उद्यमी")
    assert "document file folder" in attire_investor.lower() or "shirt" in attire_investor.lower()

    # 5. Full Screenplay Formatting for SIR: Setting is Government Office, Wardrobe is Formal
    sir_script = ReelScript(
        id=99,
        title="Dholera SIR Mega Project",
        angle="Analytical & Grounded",
        hook_hindi="धोलेरा एसआईआर का नया प्लान पास!",
        narration_hindi="धोलेरा एसआईआर का नया प्लान पास! क्या जमीन अधिग्रहण तय समय पर होगा?",
        call_to_action="",
        scenes=[
            SceneItem(
                scene_number=1,
                character="👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)",
                dialogue="धोलेरा एसआईआर का नया ब्लूप्रिंट पास हो चुका है।",
                timestamp="0:00 - 0:03",
                visual_b_roll="Sharma Ji taps an index finger emphatically on a blueprint map of the Special Investment Region laid out across a wooden desk",
                on_screen_text="धोलेरा SIR पास!",
                audio_sfx="Paper File Thud + Sub Bass Hit",
            ),
            SceneItem(
                scene_number=2,
                character="🧑 Rajesh (Industrial Investor / Local Landowner - उद्यमी / नागरिक)",
                dialogue="लेकिन क्या इंडस्ट्रियल कॉरिडोर के लिए जमीन अधिग्रहण तय समय पर होगा?",
                timestamp="0:03 - 0:10",
                visual_b_roll="Rajesh reviews blue official document file folder across the desk",
                on_screen_text="जमीन अधिग्रहण?",
                audio_sfx="Desk Slide Whoosh",
            ),
        ],
        word_count=18,
        max_words=25,
        target_duration_sec=10,
    )
    formatted = format_industry_screenplay(sir_script)
    # Venue is Government Office, NOT Chai Tapri
    assert "government administrative planning office" in formatted.lower()
    assert "chai tapri" not in formatted.lower()
    # Characters attire has ballpoint pens and file folder
    assert "ballpoint pens" in formatted.lower()
    assert "file folder" in formatted.lower()
    # No tea vendor apron!
    assert "tea vendor apron" not in formatted.lower()


def test_dynamic_imagination_engine_for_missing_pairs_and_settings():
    """Verify that when no predefined pair or domain matches, new ones are dynamically imagined from current data."""
    from agents.contextual_selector import contextual_selector
    from agents.dialogue_writer import select_script_grounded_pair, select_script_grounded_solo
    from core.screenplay_formatter import format_industry_screenplay

    # 1. Space / ISRO news topic: dynamically imagined, NOT chai tapri!
    space_choice = contextual_selector.select_scene_and_characters(
        news_topic="ISRO launches solar probe satellite into halo orbit",
        character_count=2,
        duration_sec=15,
    )
    assert "isro satellite telemetry" in space_choice["setting"].lower()
    assert "chai tapri" not in space_choice["setting"].lower()
    assert any("Scientist" in p or "वैज्ञानिक" in p for p in space_choice["personas"])
    assert any("Engineer" in p or "इंजीनियर" in p for p in space_choice["personas"])
    assert "isro" in " ".join(space_choice["props"]).lower() or "telemetry" in " ".join(space_choice["props"]).lower()

    # 2. Aviation / Airport topic
    flight_choice = contextual_selector.select_scene_and_characters(
        news_topic="DGCA mandates immediate refund for delayed airline flights",
        character_count=2,
        duration_sec=10,
    )
    assert "airport" in flight_choice["setting"].lower()
    assert any("Pilot" in p or "पायलट" in p for p in flight_choice["personas"])
    assert any("Operations" in p or "Manager" in p for p in flight_choice["personas"])
    assert "epaulets" in flight_choice["wardrobes"].get("CAPTAIN RAJESH", "").lower()

    # 3. Gold / Bullion / Jewellery topic via Dialogue Writer fallback
    bullion_pair = select_script_grounded_pair("Gold prices surge at Zaveri Bazaar bullion jewellery trade counter")
    assert any("Bullion" in p or "सर्राफा" in p for p in bullion_pair)
    assert any("Gold" in p or "Investor" in p or "निवेशक" in p for p in bullion_pair)

    # 4. Completely Novel / Unlisted Topic (General Dynamic Imagination)
    quantum_choice = contextual_selector.imagine_from_current_data(
        news_topic="National Quantum Computing Mission launches ₹6000 Cr research initiative",
        character_count=2,
    )
    assert "quantum computing" in quantum_choice["setting"].lower()
    assert "chai tapri" not in quantum_choice["setting"].lower()
    assert any("Specialist" in p or "विशेषज्ञ" in p for p in quantum_choice["personas"])
    assert any("Stakeholder" in p or "हितधारक" in p for p in quantum_choice["personas"])

    # 5. Full Screenplay Formatting with Imagined Domain
    space_script = ReelScript(
        id=101,
        title="ISRO Solar Mission",
        angle="Inspirational & Uplifting",
        hook_hindi="इसरो का नया इतिहास!",
        narration_hindi="इसरो का नया इतिहास! उपग्रह हेलो ऑर्बिट में स्थापित!",
        call_to_action="",
        scenes=[
            SceneItem(
                scene_number=1,
                character="🚀 Dr. Vikram (Senior ISRO Mission Scientist - मुख्य वैज्ञानिक)",
                dialogue="उपग्रह सफलतापूर्वक हेलो ऑर्बिट में स्थापित हो चुका है!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Dr. Vikram points to the telemetry screen displaying satellite orbital trajectory coordinates",
                on_screen_text="इसरो का नया मिशन!",
                audio_sfx="Telemetry Beeps + Countdown Echo",
            ),
            SceneItem(
                scene_number=2,
                character="👩 Priya (Aerospace Flight Trajectory Engineer - मिशन इंजीनियर)",
                dialogue="सभी सेंसर सामान्य हैं और डेटा ट्रांसमिशन शुरू हो गया है।",
                timestamp="0:03 - 0:10",
                visual_b_roll="Priya adjusts communications headset and logs telemetry coordinates",
                on_screen_text="डेटा ट्रांसमिशन शुरू!",
                audio_sfx="Keypad Clatter",
            ),
        ],
        word_count=18,
        max_words=25,
        target_duration_sec=10,
    )
    space_formatted = format_industry_screenplay(space_script)
    assert "isro satellite telemetry" in space_formatted.lower()
    assert "chai tapri" not in space_formatted.lower()
    assert "lanyard and security badge" in space_formatted.lower()
    assert "tea vendor apron" not in space_formatted.lower()


def test_screenplay_coherence_sub_agent_and_dialogue_action_sync():
    """Verify screenplay coherence sub-agent synchronizes spoken dialogue (tea, paper, etc.) with visual action."""
    from agents.screenplay_coherence import screenplay_coherence_agent
    from core.screenplay_formatter import format_industry_screenplay
    from core.script_analyzer import common_sense_validator

    # 1. Initially disconnected / random actions
    sc1 = SceneItem(
        scene_number=1,
        character="👩 Priya (Friend 1)",
        dialogue="रोहन चाय छोड़, पहले रोने के लिए कंधा दे यार!",
        timestamp="0:00 - 0:03",
        visual_b_roll="Priya looks around randomly at the wall",
        on_screen_text="चाय",
        audio_sfx="Whoosh",
    )
    sc2 = SceneItem(
        scene_number=2,
        character="🧑 Rohan (Friend 2)",
        dialogue="अरे अखबार में देखो, सरकारी ऑर्डर आ चुका है!",
        timestamp="0:03 - 0:10",
        visual_b_roll="Rohan shrugs shoulders indifferently",
        on_screen_text="ऑर्डर",
        audio_sfx="Clink",
    )

    test_script = ReelScript(
        id=77,
        title="Dialogue Action Coherence Test",
        angle="Funny & Relatable",
        hook_hindi="रोहन चाय छोड़!",
        narration_hindi="रोहन चाय छोड़!",
        call_to_action="",
        scenes=[sc1, sc2],
        word_count=10,
        max_words=18,
        target_duration_sec=10,
    )

    # 2. Audit detects missing physical interaction
    is_coh, issues, suggs = screenplay_coherence_agent.audit_screenplay_coherence(test_script)
    assert is_coh is False
    assert any("tea/sipping" in iss for iss in issues)
    assert any("newspaper/paper" in iss for iss in issues)

    # 3. Sub-agent aligns and locks visual action to dialogue
    screenplay_coherence_agent.align_screenplay_coherence(test_script)
    assert "cutting chai glass" in sc1.visual_b_roll.lower() or "tea" in sc1.visual_b_roll.lower()
    assert "newspaper" in sc2.visual_b_roll.lower() or "headline" in sc2.visual_b_roll.lower()

    # Re-audit passes
    is_coh2, issues2, _ = screenplay_coherence_agent.audit_screenplay_coherence(test_script)
    assert is_coh2 is True
    assert len(issues2) == 0

    # 4. Industry screenplay formatting produces coherent camera cues and SFX
    screenplay_text = format_industry_screenplay(test_script)
    # Priya setting down cutting chai glass
    assert "setting down the half-finished cutting chai glass" in screenplay_text.lower()
    assert "chai glass clink" in screenplay_text.lower()
    # Rohan unfolding newspaper
    assert "sharply unfolds the morning hindi newspaper" in screenplay_text.lower()
    assert "newspaper snap" in screenplay_text.lower()

    # 5. Integrated Common Sense Realism Validator audit passes
    is_cs_valid, cs_issues, _ = common_sense_validator.audit_screenplay(test_script)
    assert is_cs_valid is True


def test_scene_character_location_relationship_matrix():
    """Verify that every Scene Style, Creative Angle, and Script Topic Domain has >= 5-6 setups."""
    from agents.contextual_selector import contextual_selector
    from agents.scene_catalog import (
        SCENE_STYLE_SETUPS,
        CREATIVE_ANGLE_SETUPS,
        DOMAIN_SETUPS,
    )

    # 1. Verify Scene Styles (Dialogue, Narration, Debate, Interview, Street Reaction, Satirical Skit, Lament, Argument)
    for style, setups in SCENE_STYLE_SETUPS.items():
        assert len(setups) >= 6, f"Scene Style '{style}' has only {len(setups)} setups, expected >= 6"
        for s in setups:
            assert "characters" in s and len(s["characters"]) >= 1, f"Setup in style '{style}' missing characters"
            assert "relationship" in s and len(s["relationship"]) > 0, f"Setup in style '{style}' missing relationship"
            assert "location" in s and len(s["location"]) > 0, f"Setup in style '{style}' missing location"
            assert "setting" in s and len(s["setting"]) > 0, f"Setup in style '{style}' missing setting"
            assert "props" in s and len(s["props"]) >= 1, f"Setup in style '{style}' missing props"
            assert "audio_sfx" in s and len(s["audio_sfx"]) > 0, f"Setup in style '{style}' missing audio_sfx"

    # 2. Verify Creative Angles
    for angle, setups in CREATIVE_ANGLE_SETUPS.items():
        assert len(setups) >= 6, f"Creative Angle '{angle}' has only {len(setups)} setups, expected >= 6"
        for s in setups:
            assert "characters" in s and len(s["characters"]) >= 1, f"Setup in angle '{angle}' missing characters"
            assert "relationship" in s and len(s["relationship"]) > 0, f"Setup in angle '{angle}' missing relationship"
            assert "location" in s and len(s["location"]) > 0, f"Setup in angle '{angle}' missing location"
            assert "setting" in s and len(s["setting"]) > 0, f"Setup in angle '{angle}' missing setting"
            assert "props" in s and len(s["props"]) >= 1, f"Setup in angle '{angle}' missing props"
            assert "audio_sfx" in s and len(s["audio_sfx"]) > 0, f"Setup in angle '{angle}' missing audio_sfx"

    # 3. Verify Script Topic Domains
    for domain, setups in DOMAIN_SETUPS.items():
        assert len(setups) >= 6, f"Domain '{domain}' has only {len(setups)} setups, expected >= 6"
        for s in setups:
            assert "characters" in s and len(s["characters"]) >= 1, f"Setup in domain '{domain}' missing characters"
            assert "relationship" in s and len(s["relationship"]) > 0, f"Setup in domain '{domain}' missing relationship"
            assert "location" in s and len(s["location"]) > 0, f"Setup in domain '{domain}' missing location"
            assert "setting" in s and len(s["setting"]) > 0, f"Setup in domain '{domain}' missing setting"
            assert "props" in s and len(s["props"]) >= 1, f"Setup in domain '{domain}' missing props"
            assert "audio_sfx" in s and len(s["audio_sfx"]) > 0, f"Setup in domain '{domain}' missing audio_sfx"

    # 4. Contextual Selector Subagent accessors
    dial_setups = contextual_selector.get_scene_style_setups("Dialogue")
    assert len(dial_setups) >= 6
    assert any("Husband & Wife" in s["relationship"] for s in dial_setups)
    assert any("Father & Son" in s["relationship"] for s in dial_setups)
    assert any("Colleagues" in s["relationship"] for s in dial_setups)

    angle_setups = contextual_selector.get_angle_setups("Contrast & Comparison")
    assert len(angle_setups) >= 6

    gov_setups = contextual_selector.get_domain_setups("government_sir")
    assert len(gov_setups) >= 6

    # 5. Context-aware selection
    selected_gov = contextual_selector.select_setup_for_context(
        news_topic="Cabinet approves Special Investment Region industrial development",
        character_count=2,
    )
    assert "Collectorate" in selected_gov["location"] or "administrative" in selected_gov["setting"].lower()

    selected_hw = contextual_selector.select_setup_for_context(
        news_topic="LPG cylinder price rise impacts household grocery",
        scene_style="Dialogue",
        sample_story="पति-पत्नी किचन में बजट पर बात कर रहे हैं",
    )
    assert "Kitchen" in selected_hw["location"] or "Husband & Wife" in selected_hw["relationship"]


if __name__ == "__main__":
    print("Testing character personas...")
    test_character_personas_mapping()
    print("✅ test_character_personas_mapping passed")

    print("Testing creative guidelines...")
    test_creative_guidelines()
    print("✅ test_creative_guidelines passed")

    print("Testing tailored instruction matrix...")
    test_tailored_instruction_matrix()
    print("✅ test_tailored_instruction_matrix passed")

    print("Testing sadness tone, angle, and lament style...")
    test_sadness_tone_angle_and_lament_style()
    print("✅ test_sadness_tone_angle_and_lament_style passed")

    print("Testing configuration compliance gate...")
    test_configuration_compliance_gate()
    print("✅ test_configuration_compliance_gate passed")

    print("Testing dead configs purged and update instruction...")
    test_dead_configs_purged_and_update_instruction()
    print("✅ test_dead_configs_purged_and_update_instruction passed")

    print("Testing no commenting in dialogue or script...")
    test_no_commenting_in_dialogue_or_script()
    print("✅ test_no_commenting_in_dialogue_or_script passed")

    print("Testing preference persistence and Indian politics category...")
    test_preference_persistence_and_categories()
    print("✅ test_preference_persistence_and_categories passed")

    print("Testing professional screenplay scene description and clean beats...")
    test_professional_screenplay_scene_description_and_clean_beats()
    print("✅ test_professional_screenplay_scene_description_and_clean_beats passed")

    print("Testing argument style and relational characters...")
    test_argument_style_and_relational_characters()
    print("✅ test_argument_style_and_relational_characters passed")

    print("Testing sample story is style reference, not copied...")
    test_sample_story_is_style_reference_not_copied()
    print("✅ test_sample_story_is_style_reference_not_copied passed")

    print("Testing script continuity, setting analyzer, and dialogue targets...")
    test_script_continuity_and_setting_analyzer()
    print("✅ test_script_continuity_and_setting_analyzer passed")

    print("Testing common sense validator step and retry feedback...")
    test_common_sense_validator_step_and_retry_feedback()
    print("✅ test_common_sense_validator_step_and_retry_feedback passed")

    print("Testing contextual selector, SIR domain, and government office venue...")
    test_contextual_selector_and_sir_government_domain()
    print("✅ test_contextual_selector_and_sir_government_domain passed")

    print("Testing dynamic imagination engine for missing pairs and settings...")
    test_dynamic_imagination_engine_for_missing_pairs_and_settings()
    print("✅ test_dynamic_imagination_engine_for_missing_pairs_and_settings passed")

    print("Testing screenplay coherence sub-agent and dialogue-action sync...")
    test_screenplay_coherence_sub_agent_and_dialogue_action_sync()
    print("✅ test_screenplay_coherence_sub_agent_and_dialogue_action_sync passed")

    print("Testing scene character location relationship matrix...")
    test_scene_character_location_relationship_matrix()
    print("✅ test_scene_character_location_relationship_matrix passed")

    print("Testing end-to-end comedy dialogue pipeline...")
    test_end_to_end_comedy_dialogue_pipeline()
    print("✅ test_end_to_end_comedy_dialogue_pipeline passed")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")






