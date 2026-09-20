"""Script Continuity, Setting & Dialogue Target Analysis Engine.

Performs deep analysis on generated screenplays to audit and heal:
1. Setting Mismatch: Harmonizes institutional settings (hospitals, courts, tech parks)
   with character trades (tea vendors, auto drivers) and props/SFX (cutting chai, tapri clatter).
2. Dialogue Target & Salutation Auditor: Validates Hindi vocatives against addressee gender and role
   (e.g. prevents marital vocatives like 'सुनती हो' when speaking to male peers or friends).
3. Visual Kinematics & Prop Continuity: Ensures authentic occupational multi-prop handling
   (e.g. tea vendor holds strainer/cloth in one hand while gesturing with phone in the other).
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from core.models import SceneItem, ReelScript


def extract_character_core_name_and_role(char_str: str) -> Tuple[str, str, str]:
    """
    Extract (clean_first_name, gender_hint, role_hint) from character string.
    e.g. '🏛️ Netaji Tiwari (Ward Corporator / Friend 1)' -> ('Netaji', 'male', 'politician')
         '☕ Rohan (Street Chai Tapri Owner / Friend 2)' -> ('Rohan', 'male', 'tea_vendor')
         '👩 Sunita (Wife / Pragmatic Homemaker)' -> ('Sunita', 'female', 'wife')
    """
    if not char_str:
        return ("Speaker", "unknown", "unknown")

    c_lower = char_str.lower()

    # Determine gender hint
    female_names = {"sunita", "ananya", "priya", "meera", "sneha", "pooja", "neha", "kavita", "shreya", "wife", "patni", "mother", "daughter", "गृहिणी", "महिला", "पत्नी", "माँ", "बेटी"}
    gender = "female" if any(f in c_lower for f in female_names) or "👩" in char_str else "male"

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
    Ensure physical kinematics and prop handling reflect authentic occupational reality.
    Specifically:
    - Tea vendors: holding a tea strainer, kettle, or cloth in one hand while gesturing with or
      holding a smartphone with the other, rather than floating/awkward smartphone handling.
    - Auto drivers: holding meter wiping cloth or auto keys while gesturing.
    - Students: holding coaching notes/books while interacting.
    - Citizens/Netaji: natural physical posture.
    """
    if not scenes:
        return scenes

    for sc in scenes:
        name, gender, role = extract_character_core_name_and_role(sc.character)
        vis = sc.visual_b_roll or ""

        # Check for tea vendor handling phone
        if role == "tea_vendor":
            has_phone = any(k in vis.lower() for k in ["phone", "smartphone", "screen", "मोबाइल", "फोन"])
            has_tea_prop = any(k in vis.lower() for k in ["strainer", "cloth", "rag", "kettle", "glass", "कपड़ा", "छन्नी", "केतली"])
            if has_phone and not has_tea_prop:
                # Enhance action line to ground in occupational reality
                if "thrust" in vis.lower() or "shov" in vis.lower():
                    vis = re.sub(
                        r"(?:thrusting|shoving|holding|pointing)\s+(?:his\s+|her\s+)?(?:mobile\s+)?phone(?:\s+screen)?",
                        f"holding a tea strainer and wiping cloth in one hand, gesturing with {name}'s smartphone in the other",
                        vis,
                        flags=re.IGNORECASE
                    )
                else:
                    vis = f"{name} pauses wiping the counter with a cloth, showing the smartphone screen with animated reactions."
                sc.visual_b_roll = vis

        # Check for auto driver handling phone
        elif role == "driver":
            has_phone = any(k in vis.lower() for k in ["phone", "smartphone", "screen"])
            has_driver_prop = any(k in vis.lower() for k in ["keys", "rag", "meter", "चाबी"])
            if has_phone and not has_driver_prop:
                vis = f"{name} twirls auto ignition keys in one hand while tapping the smartphone screen with the other."
                sc.visual_b_roll = vis

    return scenes


def _matches_any(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    for kw in keywords:
        kw_l = kw.lower()
        if len(kw_l) <= 4 or kw_l in ["coach", "match", "train", "plane", "court", "flats"]:
            if re.search(rf"\b{re.escape(kw_l)}\b", t):
                return True
        elif kw_l in t:
            return True
    return False


def harmonize_setting_description(script, topic_subject: str = "") -> str:
    """
    Harmonize the overall scene setting to prevent clashing between institutional topics
    (hospital casualty, high court, corporate tech park) and working-class character roles / tapri SFX.
    
    If characters include a tea vendor, auto driver, or street tapri presence, or if
    audio/actions feature cutting chai, clinking glasses, or tea aprons:
    Transforms an institutional interior into the authentic adjacent exterior / roadside tea stall:
    - 'Government hospital casualty waiting area' ->
      'A bustling roadside tea stall directly outside the government hospital casualty entrance.'
    - 'High Court entrance steps' ->
      'A lively tea kiosk right across the High Court entrance gate.'
    - 'Corporate tech park' ->
      'A bustling tea tapri and outdoor kiosk right adjacent to the glass-facade IT tech park.'
    """
    dur = getattr(script, "target_duration_sec", 15) or 15
    is_fast = dur <= 10

    # 1. Respect explicit SCENE DETAIL in sample story if provided
    sample_text = getattr(script, "sample_story_used", "") or ""
    if sample_text:
        m_scene = re.search(r"SCENE DETAIL\s*:(.*?)(?:CHARACTERS|\[Time|\n\s*\n\s*\[|\Z)", sample_text, re.DOTALL | re.IGNORECASE)
        if m_scene:
            detail_lines = [line.strip().lstrip("⚬•-* \t") for line in m_scene.group(1).splitlines() if line.strip().lstrip("⚬•-* \t")]
            if detail_lines:
                return " ".join(detail_lines)

    # Gather full script cues
    all_chars = " ".join([sc.character.lower() for sc in (script.scenes or [])])
    all_vis = " ".join([(sc.visual_b_roll or "").lower() for sc in (script.scenes or [])])
    all_sfx = " ".join([(sc.audio_sfx or "").lower() for sc in (script.scenes or [])])
    combined_script = f"{all_chars} {all_vis} {all_sfx}".lower()

    has_tapri_props = _matches_any(combined_script, [
        "tapri", "tea vendor", "chai", "चाय", "टपरी", "apron", "strainer",
        "cutting chai", "glass clink", "wooden bench", "clatter"
    ])
    has_hospital = _matches_any(combined_script, ["hospital", "casualty", "doctor", "ward", "अस्पताल", "मरीज"])
    has_court = _matches_any(combined_script, ["court", "lawyer", "advocate", "judge", "वकील", "कानून"])
    has_sir = _matches_any(combined_script, ["sir", "dholera", "special investment", "investment region", "industrial corridor", "collectorate", "secretariat", "mantralaya", "babu", "clerk", "land acquisition", "सरकारी दफ्तर", "कलेक्टर", "सचिवालय"])
    has_tech = _matches_any(combined_script, ["tech park", "wfo", "cyber", "corporate", "बायोमेट्रिक", "biometric"])
    has_police = _matches_any(combined_script, ["police", "thana", "challan", "थाना", "दरोगा", "ट्रैफिक"])
    has_election = _matches_any(combined_script, ["election", "netaji", "पार्षद", "rally", "नेता"])

    # Domestic settings for husband-wife or father-son
    if any(k in all_chars for k in ["wife", "husband", "patni", "pati", "पत्नी", "पति", "गृहिणी"]):
        base = "A cozy Indian middle-class household living room or kitchen."
        vibe = "Very fast-paced, high-energy domestic discussion to fit the 10-second limit." if is_fast else "Relatable domestic atmosphere with grocery bills, kitchen counter, and tea cups."
        return f"{base} {vibe}"

    if any(k in all_chars for k in ["father", "son", "pita", "beta", "पिता", "बेटा"]):
        base = "A traditional Indian household study room or veranda."
        vibe = "Animated generational debate to fit the 10-second limit." if is_fast else "Generational contrast atmosphere with reading glasses, newspapers, and study books."
        return f"{base} {vibe}"

    # Reconcile Institutional Topics with Tapri/Street Elements
    if has_hospital:
        if has_tapri_props:
            base = "A bustling roadside tea stall directly outside the government hospital casualty entrance."
            vibe = "Very fast-paced, high-energy vibe to fit the 10-second limit." if is_fast else "Ambient street noise, boiling tea, and hospital visitors in the background."
        else:
            base = "Government hospital casualty waiting area."
            vibe = "High-energy, fast-paced emergency movement to fit the 10-second limit." if is_fast else "Stethoscopes, medicinal shelves, and patients in background corridor."
        return f"{base} {vibe}"

    if has_court:
        if has_tapri_props:
            base = "A lively roadside tea kiosk right across the High Court entrance gate."
            vibe = "Very fast-paced, high-energy legal buzz to fit the 10-second limit." if is_fast else "Advocates carrying legal briefs, police escorts, and tea glasses clinking."
        else:
            base = "High Court entrance steps and pillared corridors."
            vibe = "Very fast-paced, high-energy legal buzz to fit the 10-second limit." if is_fast else "Busy legal buzz with advocates carrying files and waiting litigants."
        return f"{base} {vibe}"

    if has_sir:
        if has_tapri_props:
            base = "A roadside tea stall and kiosk right outside the government collectorate and SIR planning authority."
            vibe = "Very fast-paced administrative excitement to fit the 10-second limit." if is_fast else "Bustling with official document files, blueprint maps, and waiting citizens."
        else:
            base = "A bustling government administrative planning office and collectorate corridor."
            vibe = "Very fast-paced administrative action to fit the 10-second limit." if is_fast else "Wooden desks stacked with official files, blueprint maps of the Special Investment Region (SIR), ceiling fans, and official wall seals."
        return f"{base} {vibe}"

    if has_tech:
        if has_tapri_props:
            base = "A bustling roadside tea stall and kiosk adjacent to the glass-facade IT tech park."
            vibe = "Very fast-paced, high-energy vibe to fit the 10-second limit." if is_fast else "Corporate employees passing RFID turnstiles with lanyards in background."
        else:
            base = "Glass-facade IT tech park entrance and adjacent outdoor kiosk."
            vibe = "Very fast-paced, high-energy vibe to fit the 10-second limit." if is_fast else "Corporate employees passing RFID turnstiles with lanyards in background."
        return f"{base} {vibe}"

    if has_police:
        if has_tapri_props:
            base = "A street tea stall corner situated just outside the city police station."
            vibe = "Very fast-paced, high-energy street action to fit the 10-second limit." if is_fast else "Barricades, patrol vehicle, and busy vehicular commotion in background."
        else:
            base = "Bustling Indian urban traffic junction with barricades."
            vibe = "Very fast-paced, high-energy street action to fit the 10-second limit." if is_fast else "Barricades, police patrol vehicle, and busy vehicular commotion."
        return f"{base} {vibe}"

    if has_election:
        base = "A lively street tea tapri decorated with political buntings near the campaign corner."
        vibe = "High-voltage election banter and snappy energy to fit the 10-second limit." if is_fast else "Political posters, wooden benches, and lively neighborhood debate."
        return f"{base} {vibe}"

    # Imagined authentic settings from current data
    if _matches_any(combined_script, ["space", "isro", "satellite", "chandrayaan", "rocket", "orbit", "अंतरिक्ष", "उपग्रह"]):
        base = "ISRO Satellite Telemetry and Mission Operations Complex."
        vibe = "High-energy mission countdown urgency to fit the 10-second limit." if is_fast else "Giant projection displays showing orbital coordinates, telemetry consoles, and mission status readouts."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["flight", "airline", "airport", "pilot", "dgca", "aircraft", "विमान", "एयरपोर्ट"]):
        base = "Modern international airport departure terminal and flight dispatch lounge."
        vibe = "Very fast-paced transit action to fit the 10-second limit." if is_fast else "Panoramic glass windows overlooking the runway tarmac, flight departure screens, and boarding gate."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["railway", "train", "metro", "vande bharat", "station", "loco", "रेलवे", "ट्रेन"]):
        base = "Zonal railway locomotive dispatch room and digital signaling console."
        vibe = "Fast-paced signaling action to fit the 10-second limit." if is_fast else "Digital track line status consoles, railway dispatch schedule boards, and radio communications."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["gold", "silver", "jewellery", "bullion", "zaveri", "सोना", "चांदी", "सर्राफा"]):
        base = "A high-end bullion showroom and traditional gold trade counter."
        vibe = "Snappy market excitement to fit the 10-second limit." if is_fast else "Velvet display trays, digital carat weighing scale, wall-mounted bullion market tickers, and glass counters."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["cricket", "ipl", "stadium", "match", "tournament", "coach", "मैच", "क्रिकेट"]):
        base = "Cricket stadium team pavilion and press briefing box."
        vibe = "High-voltage sports adrenaline to fit the 10-second limit." if is_fast else "Locker benches, sports gear, floodlight glow through glass windows, and team tactical whiteboards."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["pollution", "smog", "aqi", "air quality", "environment", "climate", "प्रदूषण", "स्मॉग"]):
        base = "City environmental monitoring control tower and air analysis lab."
        vibe = "Urgent ecological discussion to fit the 10-second limit." if is_fast else "Digital AQI hazard index monitors flashing red, air filtration particulate gauges, and city smog horizon view."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["army", "defence", "defense", "military", "soldier", "border", "सेना", "फौज", "जवान"]):
        base = "Border operational observation post and tactical communications bunker."
        vibe = "Intense tactical focus to fit the 10-second limit." if is_fast else "Camouflage sandbags, tactical topographical map tables, radio communications consoles, and mountain terrain view."
        return f"{base} {vibe}"

    if _matches_any(combined_script, ["builder", "flats", "housing", "rera", "apartment", "society", "सोसाइटी", "बिल्डर", "फ्लैट"]):
        base = "High-rise construction site project cabin and architectural blueprint lounge."
        vibe = "Fast-paced property discussion to fit the 10-second limit." if is_fast else "Large architectural 3D project models, rolled floor plans, yellow safety helmets, and concrete tower view."
        return f"{base} {vibe}"

    # Default classic street tapri
    if is_fast:
        return "A bustling local Indian street chai tapri. Very fast-paced, high-energy vibe to fit the 10-second limit."
    return "A bustling local Indian street chai tapri. Casual, everyday public space vibe with background customers, street noise, and boiling tea."


def analyze_and_heal_script(script: ReelScript) -> ReelScript:
    """
    Execute full analysis and healing phase on a generated screenplay:
    1. Dialogue Target & Vocative healing (fixing marital salutations used with friends/vendors).
    2. Visual Kinematics & Prop Continuity enhancement (tea vendor multi-prop realism).
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
    1. Setting vs Character Trade & Props (e.g. tea vendor clinking chai inside a hospital casualty ward).
    2. Dialogue Target & Gender/Vocative Realism (e.g. calling male friend/vendor 'सुनती हो').
    3. Visual Kinematics & Prop Handling Realism (e.g. tea vendor operating smartphone without occupational trade props).

    Produces structured findings and actionable feedback passed to previous pipeline steps for modification and retry.
    """
    @staticmethod
    def audit_screenplay(script: ReelScript) -> Tuple[bool, List[str], str]:
        issues: List[str] = []

        if not script or not getattr(script, "scenes", None):
            return True, [], "No scenes to audit"

        all_chars = " ".join([sc.character.lower() for sc in script.scenes])
        all_vis = " ".join([(sc.visual_b_roll or "").lower() for sc in script.scenes])
        all_sfx = " ".join([(sc.audio_sfx or "").lower() for sc in script.scenes])
        combined_text = f"{all_chars} {all_vis} {all_sfx}".lower()

        # 1. Setting Mismatch Audit
        has_tapri = any(k in combined_text for k in [
            "tapri", "tea vendor", "chai", "चाय", "टपरी", "apron", "strainer", "cutting chai", "glass clink"
        ])
        s1_vis = (script.scenes[0].visual_b_roll or "").lower()
        if "casualty waiting area" in s1_vis or ("hospital" in s1_vis and "ward" in s1_vis):
            if has_tapri:
                issues.append("Setting mismatch: Tea stall vendor/props located inside hospital casualty ward. Move setting to roadside tea stall outside casualty entrance.")

        if "courtroom" in s1_vis or ("court" in s1_vis and "steps" in s1_vis):
            if has_tapri:
                issues.append("Setting mismatch: Tapri elements clashing with court interior. Move setting to tea kiosk outside court gate.")

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
