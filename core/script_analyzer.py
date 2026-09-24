"""Script Continuity, Setting & Dialogue Target Analysis Engine.

Performs deep analysis on generated screenplays to audit and heal:
1. Setting Mismatch: Keeps settings grounded in the verified news topic (hospitals,
   courts, tech parks stay institutional); reconciles character trades and props/SFX
   with that setting instead of relocating to a default street stall.
2. Dialogue Target & Salutation Auditor: Validates Hindi vocatives against addressee gender and role
   (e.g. prevents marital vocatives like 'सुनती हो' when speaking to male peers or friends).
3. Visual Kinematics & Prop Continuity: Ensures authentic occupational multi-prop handling
   (e.g. a vendor holds work tools in one hand while gesturing with a phone in the other).

Tea-stall / tapri settings are NEVER introduced by this module. They appear only
when the generated script itself (from news-grounded Stage 2 scenes) already
contains them.
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from core.models import SceneItem, ReelScript


def extract_character_core_name_and_role(char_str: str) -> Tuple[str, str, str]:
    """
    Extract (clean_first_name, gender_hint, role_hint) from character string.
    e.g. '🏛️ Netaji Tiwari (Ward Corporator / Friend 1)' -> ('Netaji', 'unknown', 'netaji')
         '☕ Rohan (Street Chai Tapri Owner / Friend 2)' -> ('Rohan', 'unknown', 'tea_vendor')
         '👩 Sunita (Wife / Pragmatic Homemaker)' -> ('Sunita', 'female', 'wife')
    Gender is only ever a hint: unknown defaults to "unknown", never "male".
    """
    if not char_str:
        return ("Speaker", "unknown", "unknown")

    c_lower = char_str.lower()

    # Determine gender hint — unknown stays "unknown" (never default to male).
    female_names = {"sunita", "ananya", "priya", "meera", "sneha", "pooja", "neha", "kavita", "shreya", "wife", "patni", "mother", "daughter", "गृहिणी", "महिला", "पत्नी", "माँ", "बेटी"}
    gender = "female" if any(f in c_lower for f in female_names) or "👩" in char_str else "unknown"

    # Determine role hint
    if any(k in c_lower for k in ["tapri", "tea", "chai", "चाय", "टपरी", "vendor"]):
        role = "tea_vendor"
    elif any(k in c_lower for k in ["auto", "driver", "रिक्शा", "चालक"]):
        role = "driver"
    elif any(k in c_lower for k in ["netaji", "नेता", "corporator", "पार्षद"]):
        role = "netaji"
    elif any(k in c_lower for k in ["wife", "patni", "पत्नी", "गृहिणी", "homemaker"]):
        role = "wife"
    elif any(k in c_lower for k in ["husband", "pati", "पति"]):
        role = "husband"
    elif any(k in c_lower for k in ["father", "pita", "पिता", "बाप"]):
        role = "father"
    elif any(k in c_lower for k in ["son", "beta", "बेटा"]):
        role = "son"
    elif any(k in c_lower for k in ["doctor", "डॉक्टर", "चिकित्सक"]):
        role = "doctor"
    elif any(k in c_lower for k in ["lawyer", "advocate", "वकील"]):
        role = "lawyer"
    elif any(k in c_lower for k in ["police", "दरोगा", "कांस्टेबल"]):
        role = "police"
    elif any(k in c_lower for k in ["colleague", "coworker", "कलीग"]):
        role = "colleague"
    else:
        role = "citizen"

    # Extract name
    cleaned = re.sub(r"[^\w\s/()-]", "", char_str).strip()
    base = cleaned.split("/")[0].split("(")[0].strip()
    tokens = [t for t in base.split() if len(t) > 1 and not t.isdigit()]
    if tokens:
        if len(tokens) > 1 and tokens[0].lower() in ["dr", "mr", "ms", "advocate", "inspector", "sub-inspector", "seth", "master"]:
            name = tokens[-1]
        elif len(tokens) > 1 and tokens[1].lower() == "ji":
            name = f"{tokens[0]} {tokens[1]}"
        else:
            name = tokens[0]
    else:
        name = "Speaker"

    return (name.strip(), gender, role)


def audit_and_heal_dialogue_targets(scenes: List[SceneItem]) -> List[SceneItem]:
    """
    Audit spoken dialogue for relational salutation and target mismatches.
    Specifically:
    - 'अरे सुनती हो!', 'सुनती हो', 'अजी सुनती हो', 'भाग्यवान' are exclusively used by husbands for wives.
      If addressed to a male peer (e.g. Netaji talking to Rohan, or Friend to Friend), heal to
      'अरे {name} भाई!', 'अरे भाई सुनो!', 'अरे {name} सुनो!'.
    - 'सुनते हो', 'अजी सुनते हो' are exclusively used by wives for husbands.
      If addressed to a female, heal to 'अरे बहन सुनो!' or 'अरे सुनो!'.
    - Ensure respectful or informal vocatives match the addressee's identity.
    """
    if not scenes:
        return scenes

    num_scenes = len(scenes)

    for i in range(num_scenes):
        sc = scenes[i]
        speaker_name, speaker_gender, speaker_role = extract_character_core_name_and_role(sc.character)

        # Determine target addressee (the next character, or the previous one)
        other_sc = scenes[(i + 1) % num_scenes] if num_scenes > 1 else None
        target_name, target_gender, target_role = extract_character_core_name_and_role(other_sc.character if other_sc else "")

        name_hindi_map = {
            "rohan": "रोहन", "priya": "प्रिया", "ananya": "अनन्या", "vikram": "विक्रम",
            "kabir": "कबीर", "rajesh": "राजेश", "sunita": "सुनीता", "aarav": "आरव",
            "meera": "मीरा", "ramesh": "रमेश", "mohan": "मोहन", "netaji": "नेताजी",
            "sharma": "शर्मा जी", "sharma ji": "शर्मा जी", "verma": "वर्मा जी",
            "verma ji": "वर्मा जी", "gupta": "गुप्ता जी", "gupta ji": "गुप्ता जी"
        }
        target_hindi = name_hindi_map.get(target_name.lower(), target_name)

        dial = sc.dialogue or ""
        orig_dial = dial

        # Case 1: Male or non-wife addressee addressed with marital wife vocatives
        is_target_wife = (target_role == "wife") and (speaker_role == "husband")

        if not is_target_wife:
            # Check for marital wife vocatives
            wife_vocative_patterns = [
                (r"^(?:अरे\s*)?सुनती\s*हो\s*([!,?।])?", f"अरे {target_hindi} भाई\\1"),
                (r"^(?:अजी\s*)?सुनती\s*हो\s*([!,?।])?", f"अरे {target_hindi} सुनो\\1"),
                (r"\bअरे\s*सुनती\s*हो\b", f"अरे {target_hindi} भाई"),
                (r"\bसुनती\s*हो\b", f"{target_hindi} भाई सुनो"),
                (r"\bभाग्यवान\b", f"{target_hindi}"),
            ]
            for pat, repl in wife_vocative_patterns:
                if re.search(pat, dial):
                    dial = re.sub(pat, repl, dial).strip()

        # Case 2: Female or non-husband addressee addressed with marital husband vocatives
        is_target_husband = (target_role == "husband") and (speaker_role == "wife")
        if not is_target_husband:
            husband_vocative_patterns = [
                (r"^(?:अरे\s*)?सुनते\s*हो\s*([!,?।])?", f"अरे {target_hindi} सुनो\\1"),
                (r"^(?:अजी\s*)?सुनते\s*हो\s*([!,?।])?", f"अरे {target_hindi}\\1"),
            ]
            for pat, repl in husband_vocative_patterns:
                if re.search(pat, dial):
                    dial = re.sub(pat, repl, dial).strip()

        # Case 3: Netaji addressing common citizen/vendor -> "अरे रोहन भाई!"
        if speaker_role == "netaji" and target_role in ["tea_vendor", "driver", "citizen"]:
            dial = re.sub(r"^अरे\s*साथी\b", f"अरे {target_hindi} भाई", dial)

        if dial != orig_dial:
            sc.dialogue = dial

    return scenes


def audit_and_enhance_visual_kinematics(scenes: List[SceneItem]) -> List[SceneItem]:
    """
    Visual kinematics & prop continuity checkpoint.

    Fail-loud rule: this step must NOT invent replacement actions (e.g. handing
    a tea vendor a strainer/cloth, or an auto driver ignition keys) when a
    prop looks missing. Invented actions put words in the video generator's
    mouth. Mismatches are reported by
    CommonSenseRealismValidator.audit_screenplay and fixed through the normal
    retry flow with model regeneration — never synthesized here. Scenes are
    returned unchanged.
    """
    return scenes


def harmonize_setting_description(script, topic_subject: str = "") -> str:
    """
    Return the setting for the SCENE DETAIL header from real pipeline data.

    Fail-loud rule: the setting must come from the sample story's explicit
    SCENE DETAIL, or from the Stage 4/5 scene_location / scene_atmosphere
    carried on each SceneItem. Keyword-guessing a setting (hospital, court,
    ISRO, airport, ...) from script text invents a location the news never
    established — that entire pool is removed. Returns "" when no real source
    exists; callers omit the header instead of printing an invented setting.
    This module NEVER introduces tea-stall / tapri settings.
    """

    # 1. Respect explicit SCENE DETAIL in sample story if provided
    sample_text = getattr(script, "sample_story_used", "") or ""
    if sample_text:
        m_scene = re.search(r"SCENE DETAIL\s*:(.*?)(?:CHARACTERS|\[Time|\n\s*\n\s*\[|\Z)", sample_text, re.DOTALL | re.IGNORECASE)
        if m_scene:
            detail_lines = [line.strip().lstrip("⚬•-* \t") for line in m_scene.group(1).splitlines() if line.strip().lstrip("⚬•-* \t")]
            if detail_lines:
                return " ".join(detail_lines)

    # 2. Real Stage 4/5 scene data carried on each SceneItem (never guessed).
    locations: List[str] = []
    atmospheres: List[str] = []
    for sc in (getattr(script, "scenes", None) or []):
        loc = (getattr(sc, "scene_location", "") or "").strip()
        if loc and loc not in locations:
            locations.append(loc)
        atm = (getattr(sc, "scene_atmosphere", "") or "").strip()
        if atm and atm not in atmospheres:
            atmospheres.append(atm)
    parts = []
    if locations:
        parts.append("; ".join(locations))
    if atmospheres:
        parts.append("; ".join(atmospheres))
    return ". ".join(parts)



def analyze_and_heal_script(script: ReelScript) -> ReelScript:
    """
    Execute full analysis and healing phase on a generated screenplay:
    1. Dialogue Target & Vocative healing (fixing marital salutations used with friends/vendors).
    2. Visual Kinematics & Prop Continuity enhancement (occupational multi-prop realism).
    """
    if not script or not getattr(script, "scenes", None):
        return script

    # 1. Audit & heal dialogue targets
    script.scenes = audit_and_heal_dialogue_targets(script.scenes)

    # 2. Audit & enhance visual kinematics
    script.scenes = audit_and_enhance_visual_kinematics(script.scenes)

    # 3. Align Screenplay Coherence between spoken dialogue cues and scene action
    from agents.screenplay_coherence import screenplay_coherence_agent
    script = screenplay_coherence_agent.align_screenplay_coherence(script)

    return script


class CommonSenseRealismValidator:
    """
    Dedicated Common Sense & Physical Realism Validator step.
    Validates:
    1. Setting vs Character Trade & Props (e.g. tea stall vendor/props clashing
       with a hospital casualty setting - flagged for alignment with the
       verified news topic, never "fixed" by relocating to a tea stall).
    2. Dialogue Target & Gender/Vocative Realism (e.g. calling male friend/vendor 'सुनती हो').
    3. Visual Kinematics & Prop Handling Realism (e.g. a vendor operating a
       smartphone without occupational trade props).

    Produces structured findings and actionable feedback passed to previous pipeline steps for modification and retry.
    """
    @staticmethod
    def audit_screenplay(script: ReelScript) -> Tuple[bool, List[str], str]:
        issues: List[str] = []

        if not script or not getattr(script, "scenes", None):
            # Fail-loud: an empty storyboard is invalid input, not a pass.
            msg = "Script has no scenes to audit — the pipeline produced an empty storyboard."
            return False, [msg], msg

        all_chars = " ".join([sc.character.lower() for sc in script.scenes])
        all_vis = " ".join([(sc.visual_b_roll or "").lower() for sc in script.scenes])
        all_sfx = " ".join([(sc.audio_sfx or "").lower() for sc in script.scenes])
        combined_text = f"{all_chars} {all_vis} {all_sfx}".lower()

        # 1. Setting Mismatch Audit: flag vendor/stall props that clash with the
        # news-grounded institutional setting. The fix is to align characters /
        # props with the verified news topic - never to relocate the scene to a
        # tea stall.
        has_stall_props = any(k in combined_text for k in [
            "tapri", "tea vendor", "chai", "चाय", "टपरी", "apron", "strainer", "cutting chai", "glass clink"
        ])
        s1_vis = (script.scenes[0].visual_b_roll or "").lower()
        if "casualty waiting area" in s1_vis or ("hospital" in s1_vis and "ward" in s1_vis):
            if has_stall_props:
                issues.append("Setting mismatch: Tea stall vendor/props clash with the hospital casualty setting. Align the characters/props with the verified hospital news topic (e.g. visitor, staff) instead of introducing a tea stall.")

        if "courtroom" in s1_vis or ("court" in s1_vis and "steps" in s1_vis):
            if has_stall_props:
                issues.append("Setting mismatch: Tea stall elements clash with the court setting. Align the characters/props with the verified legal news topic (e.g. litigant, advocate) instead of introducing a tea stall.")

        # 2. Dialogue Target Audit
        num_scenes = len(script.scenes)
        for i, sc in enumerate(script.scenes):
            speaker_name, speaker_gender, speaker_role = extract_character_core_name_and_role(sc.character)
            other_sc = script.scenes[(i + 1) % num_scenes] if num_scenes > 1 else None
            target_name, target_gender, target_role = extract_character_core_name_and_role(other_sc.character if other_sc else "")

            dial = sc.dialogue or ""
            is_target_wife = (target_role == "wife") and (speaker_role == "husband")
            if not is_target_wife:
                if any(w in dial for w in ["सुनती हो", "अजी सुनती हो", "भाग्यवान"]):
                    issues.append(f"Dialogue target mismatch in Scene #{i+1}: {speaker_name} addressed {target_name} with marital vocative 'सुनती हो'. Address {target_name} directly.")

            is_target_husband = (target_role == "husband") and (speaker_role == "wife")
            if not is_target_husband:
                if any(w in dial for w in ["सुनते हो", "अजी सुनते हो"]):
                    issues.append(f"Dialogue target mismatch in Scene #{i+1}: {speaker_name} addressed {target_name} with marital vocative 'सुनते हो'. Address {target_name} directly.")

        # 3. Visual Kinematics Audit
        for i, sc in enumerate(script.scenes):
            name, gender, role = extract_character_core_name_and_role(sc.character)
            vis = sc.visual_b_roll or ""
            if role == "tea_vendor":
                has_phone = any(k in vis.lower() for k in ["phone", "smartphone", "screen"])
                has_tea_prop = any(k in vis.lower() for k in ["strainer", "cloth", "rag", "kettle", "glass", "कपड़ा", "छन्नी", "केतली"])
                if has_phone and not has_tea_prop:
                    issues.append(f"Visual kinematics mismatch in Scene #{i+1}: Tea vendor {name} handles phone without occupational props (strainer/cloth).")

        # 4. Dialogue-Action Physical Coherence Audit
        from agents.screenplay_coherence import screenplay_coherence_agent
        is_coh, coh_issues, coh_suggs = screenplay_coherence_agent.audit_screenplay_coherence(script)
        if not is_coh:
            issues.extend(coh_issues)

        is_valid = (len(issues) == 0)
        feedback = "; ".join(issues)
        return is_valid, issues, feedback

    @staticmethod
    def heal_and_revalidate(script: ReelScript, feedback: str = "") -> Tuple[ReelScript, bool, str]:
        """
        Pass validation feedback back to previous generation steps (dialogue targets,
        visual kinematics, setting harmonization), modify the script, and re-validate.
        """
        healed_script = analyze_and_heal_script(script)
        is_valid, issues, new_feedback = CommonSenseRealismValidator.audit_screenplay(healed_script)
        return healed_script, is_valid, new_feedback


common_sense_validator = CommonSenseRealismValidator()
