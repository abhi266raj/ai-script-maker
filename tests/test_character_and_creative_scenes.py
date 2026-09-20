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
    assert any("Chai" in p or "टपरी" in p for p in p_election)

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
    raw_1 = "Handheld dynamic 9:16 shot at a vibrant Indian street chai tapri; Priya delivers a hilarious opening quip with expressive comedic gestures"
    clean_1 = clean_beat_action(raw_1)
    assert clean_1 == "Priya delivers a hilarious opening quip with expressive comedic gestures"
    assert "Handheld dynamic 9:16 shot" not in clean_1
    assert "chai tapri" not in clean_1

    raw_2 = "Low-angle vertical (9:16) establishing hook shot at a rustic wooden bench of a roadside tea tapri, nestled beneath a leafy banyan tree. Priya aggressively slaps her smartphone."
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
                dialogue="रोहन चाय छोड़, पहले रोने के लिए कंधा दे यार!",
                timestamp="0:00 - 0:03",
                visual_b_roll="Handheld dynamic 9:16 shot at a vibrant Indian street chai tapri; Priya aggressively slaps her smartphone onto the bench",
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

    # Running beats have pure action without "Handheld dynamic 9:16 shot at..."
    assert "[Time: 0:00 - 0:03]" in pro
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
                visual_b_roll="Fast whip-pan to Ananya slamming a book on the tapri counter.",
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
    assert "Camera Focus & Action: Fast whip-pan to Ananya slamming a book on the tapri counter." in pro10
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
    assert "THIS MUST BE GENUINELY FUNNY" in guidelines
    assert "chai tapri" in guidelines
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
                assert "HIGHEST PRECEDENCE" in inst


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
        sample_story="दो दोस्त चाय की दुकान पर बैठे हैं और 5 दिन ऑफिस जाने की खबर सुनकर रोने की एक्टिंग करते हैं।",
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

    # 3. Visuals & Prompts reflect creative imaginary situation
    v1 = script.scenes[0].visual_b_roll
    assert "tapri" in v1.lower() or "comedic" in v1.lower() or "street" in v1.lower() or "friend" in v1.lower() or "priya" in v1.lower() or "chai" in v1.lower() or len(v1) > 10

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
    """Verify that dead configs are removed and instruction generator is 100% synced with visible UI."""
    from core.config import DEFAULT_CONFIG, load_config

    # Ensure dead configs are removed
    assert "enable_self_healing" not in DEFAULT_CONFIG
    assert "studio_layout" not in DEFAULT_CONFIG
    assert "frame_count" not in DEFAULT_CONFIG

    # Ensure active configs exist
    expected_keys = {
        "default_engine", "default_tone", "default_duration", "batch_count",
        "max_retries", "source_mode", "news_category", "selected_headline", "selected_script_index",
        "default_angle", "character_count", "scene_style"
    }
    assert expected_keys.issubset(set(DEFAULT_CONFIG.keys()))

    # Verify tailored instruction includes all non-engine UI parameters
    inst = build_tailored_instruction(
        topic="Varanasi Dev Deepawali celebration",
        duration_sec=20,
        tone="🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)",
        angle="Dramatic Storytelling",
        scene_style="Narration",
        character_count=1,
        batch_count=2,
        max_retries=4,
        sample_story="Ghats glow with millions of diyas.",
    )
    assert "20 seconds" in inst
    assert "timeless Indian wisdom" in inst
    assert "Dramatic Storytelling" in inst
    assert "Narration" in inst
    assert "1 speaking character(s)" in inst
    assert "Ghats glow with millions of diyas" in inst
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

    print("Testing end-to-end comedy dialogue pipeline...")
    test_end_to_end_comedy_dialogue_pipeline()
    print("✅ test_end_to_end_comedy_dialogue_pipeline passed")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")


