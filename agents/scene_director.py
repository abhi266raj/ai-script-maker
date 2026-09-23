"""Agent 5: Scene & Visuals Director Agent."""

import re
from typing import List, Optional, Dict, Any, Tuple
from agents.base import BaseAgent
from core.models import SceneItem
from core.metrics import get_duration_budget
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

def clean_beat_action(text: str) -> str:
    """Strip camera framing and background setting preamble from running beat action."""
    if not text:
        return ""
    t = text.strip()
    # Match preamble ending with semicolon, e.g. "Handheld dynamic 9:16 shot at...; "
    t = re.sub(
        r"^(?:Handheld|Dynamic|Cinematic|Low-angle|Wide|Close-up|Medium|Tight|Seamless|Intimate|Aesthetic|High-energy|High-contrast|Over-the-shoulder|Reverse-angle|POV|Cut\s+to)?\s*(?:vertical\s*)?(?:\(?9:16\)?\s*)?(?:establishing\s*)?(?:hook\s*)?(?:shot|take|push-in|cut|tracking\s*shot|whip-pan|split-screen|opening\s*hook\s*tracking\s*shot)?\s*(?:at|on|outside|inside|in|near|with)?\s*[^;.]+;\s*",
        "",
        t,
        flags=re.IGNORECASE
    )
    # Match establishing shot sentence if followed by Character action
    t = re.sub(
        r"^(?:Low-angle|Wide|Close-up|Medium|Tight|Seamless|Handheld|Dynamic|Cinematic)\s*(?:vertical\s*)?(?:\(?9:16\)?\s*)?(?:establishing\s*)?(?:hook\s*)?shot\s+(?:at|outside|inside|in|near)\s+[^.]+\.\s+(?=[A-Z\u0900-\u097F])",
        "",
        t,
        flags=re.IGNORECASE
    )
    # Remove leading labels
    t = re.sub(r"^(?:VISUAL|ACTION|B-ROLL|CAMERA)\s*:\s*", "", t, flags=re.IGNORECASE)
    return t.strip()


SCENE_DIRECTOR_INSTRUCTIONS = load_prompt("scene_director/direct_scenes.md")


def calculate_scene_timestamps(duration_sec: int, num_scenes: int) -> List[str]:
    """
    Dynamically calculate non-overlapping, continuous timestamp intervals for N scenes.
    Ensures seamless temporal continuity for Google Flow / Veo generative clips (~3-6s each).
    """
    d = max(3, duration_sec)
    n = max(1, min(num_scenes, 5))
    if n == 1:
        return [f"0:00 - 0:{d:02d}"]

    # Hook duration (Scene 1) is calibrated to 2-3s for reels (the crucial 0-3s hook window)
    t_hook = min(3, max(2, d // 3))
    if n == 2:
        return [f"0:00 - 0:{t_hook:02d}", f"0:{t_hook:02d} - 0:{d:02d}"]

    # Allocate intermediate intervals proportionally
    rem_time = d - t_hook
    rem_scenes = n - 1
    step = rem_time / rem_scenes

    times = [f"0:00 - 0:{t_hook:02d}"]
    prev = t_hook
    for i in range(1, rem_scenes):
        curr = int(t_hook + i * step)
        times.append(f"0:{prev:02d} - 0:{curr:02d}")
        prev = curr
    times.append(f"0:{prev:02d} - 0:{d:02d}")
    return times


class SceneVisualsDirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Scene & Visuals Director",
            role="Scene Breakdown, Visual B-Roll & SFX Direction",
            icon="🎬",
            instructions=SCENE_DIRECTOR_INSTRUCTIONS,
            prompt_file="scene_director/direct_scenes.md",
        )

    def direct_scenes(
        self,
        news_topic: str,
        hook: str,
        narration: str,
        duration_sec: int,
        scene_lines: Optional[List[Dict[str, str]]] = None,
        verified_facts: Optional[List[str]] = None,
        physical_props: Optional[List[str]] = None,
        key_locations: Optional[List[str]] = None,
        core_conflict_or_irony: str = "",
        tangible_actions: Optional[List[str]] = None,
        tone: str = "Funny & Relatable",
        angle: str = "Funny & Relatable",
        scene_style: str = "Dialogue",
        personas: Optional[List[str]] = None,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        preferred_frames: Optional[int] = None,
        previous_scenes: Optional[List[SceneItem]] = None,
        feedback: Optional[str] = None,
    ) -> List[SceneItem]:
        """
        Direct and break down the narration into visual scenes with strict prop and dialogue coordination.
        Scene count is completely dynamic (1 to 5 scenes) driven by content complexity,
        story structure, upstream dialogue beats, and generative video clip feasibility.
        """
        # Dynamic scene allocation:
        # 1. User/caller explicit preference (1..5)
        # 2. Upstream dialogue scene count (scene_lines)
        # 3. Pacing budget based on target duration & style
        if preferred_frames is not None and 1 <= preferred_frames <= 5:
            target_frames = preferred_frames
        elif scene_lines and len(scene_lines) > 0:
            target_frames = min(len(scene_lines), 5)
        else:
            budget = get_duration_budget(duration_sec)
            target_frames = budget.get("scenes", 3)
            # Short 5-8s reels with speech/monologue naturally work best as 1 continuous dynamic master shot
            if duration_sec <= 8 and (scene_style.lower() in ["speech", "monologue"] or (personas and len(personas) == 1)):
                target_frames = 1

        # Format upstream context from previous agents
        facts_summary = "\n".join([f"- {f}" for f in (verified_facts or [])[:3]])
        props_text = ", ".join(physical_props) if physical_props else "Key physical props and objects"
        locs_text = ", ".join(key_locations) if key_locations else "Authentic Indian urban street setting"
        actions_text = ", ".join(tangible_actions) if tangible_actions else "Character actions and interactions"
        
        lines_summary = ""
        if scene_lines:
            for idx, line in enumerate(scene_lines, 1):
                c = line.get("character", f"Character {idx}")
                d = line.get("dialogue", "")
                lines_summary += f"Scene {idx} ({c}): \"{d}\"\n"
        else:
            lines_summary = f"Full Narration: {narration}"

        sub_directive = f"\nChief Editor Directive for Scene Direction:\n{sub_instruction}\n" if sub_instruction else ""

        revision_directive = ""
        if previous_scenes:
            prev_scenes_text = "\n\n".join([
                f"SCENE {sc.scene_number} [{sc.timestamp}]:\nCHARACTER: {sc.character}\nACTION: {sc.visual_b_roll}\nDIALOGUE: {sc.dialogue}"
                for sc in previous_scenes
            ])
            fb = feedback.strip() if feedback and feedback.strip() else (sub_instruction or "Improve scene visual framing and continuity.")
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING existing storyboard scenes based on user feedback.\n"
                f"PREVIOUS SCENES:\n{prev_scenes_text}\n\n"
                f"USER CORRECTION FEEDBACK:\n{fb}\n\n"
                f"MANDATE: Directly address the user's critique. Refine the actor actions, prop interactions, and visual framing accordingly.\n"
            )

        timestamps_text = ", ".join(calculate_scene_timestamps(duration_sec, target_frames))

        prompt = render_prompt(
            "scene_director/direct_scenes.md",
            news_topic=news_topic,
            hook=hook,
            narration=narration,
            duration_sec=duration_sec,
            target_frames=target_frames,
            timestamps_text=timestamps_text,
            props_text=props_text,
            locs_text=locs_text,
            actions_text=actions_text,
            lines_summary=lines_summary,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
        )

        raw_output = ""
        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        scenes: List[SceneItem] = []
        blocks = re.split(r"SCENE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                s_num = int(blocks[i])
                content = blocks[i + 1]

                time_val = f"Scene {s_num}"
                visual = ""
                character = ""
                dialogue = ""
                text = ""
                sfx = "Whoosh + Beat"

                for line in content.split("\n"):
                    l_str = line.strip()
                    if l_str.startswith("TIME:"):
                        time_val = l_str.replace("TIME:", "").strip("[] ")
                    elif l_str.startswith("ACTION:"):
                        visual = l_str.replace("ACTION:", "").strip("[] ")
                    elif l_str.startswith("VISUAL:"):
                        visual = l_str.replace("VISUAL:", "").strip("[] ")
                    elif l_str.startswith("CHARACTER:"):
                        character = l_str.replace("CHARACTER:", "").strip("[] ")
                    elif l_str.startswith("DIALOGUE:"):
                        dialogue = l_str.replace("DIALOGUE:", "").strip("[] \"'")
                    elif l_str.startswith("TEXT:"):
                        text = l_str.replace("TEXT:", "").strip("[] \"'")
                    elif l_str.startswith("SFX:"):
                        sfx = l_str.replace("SFX:", "").strip("[] ")

                if visual:
                    cleaned_act = clean_beat_action(visual)
                    scenes.append(
                        SceneItem(
                            scene_number=s_num,
                            character=character or (personas[(s_num - 1) % len(personas)] if personas else "Creator"),
                            dialogue=dialogue,
                            timestamp=time_val,
                            visual_b_roll=cleaned_act or visual,
                            on_screen_text=text or dialogue[:25],
                            audio_sfx=sfx,
                        )
                    )

        # If LLM did not return complete scenes or fallback is needed, run Coordinated Semantic Storyboard Synthesizer
        if len(scenes) < target_frames:
            scenes = self._synthesize_coordinated_storyboard(
                news_topic=news_topic,
                hook=hook,
                narration=narration,
                duration_sec=duration_sec,
                scene_lines=scene_lines,
                verified_facts=verified_facts,
                physical_props=physical_props,
                key_locations=key_locations,
                core_conflict_or_irony=core_conflict_or_irony,
                tangible_actions=tangible_actions,
                tone=tone,
                angle=angle,
                scene_style=scene_style,
                personas=personas,
                preferred_frames=target_frames,
            )

        from core.script_analyzer import audit_and_heal_dialogue_targets, audit_and_enhance_visual_kinematics
        scenes = audit_and_heal_dialogue_targets(scenes)
        scenes = audit_and_enhance_visual_kinematics(scenes)
        return scenes

    def _synthesize_coordinated_storyboard(
        self,
        news_topic: str,
        hook: str,
        narration: str,
        duration_sec: int,
        scene_lines: Optional[List[Dict[str, str]]],
        verified_facts: Optional[List[str]],
        physical_props: Optional[List[str]],
        key_locations: Optional[List[str]],
        core_conflict_or_irony: str,
        tangible_actions: Optional[List[str]],
        tone: str,
        angle: str,
        scene_style: str,
        personas: Optional[List[str]],
        preferred_frames: int,
    ) -> List[SceneItem]:
        """
        Intelligent rule-based storyboard synthesizer ensuring physical prop continuity,
        dialogue synchronization, and narrative coherence across all themes.
        """
        clean_topic = " ".join(news_topic.replace('"', '').replace("'", "").split())
        if len(clean_topic) > 75 and " " in clean_topic[:75]:
            topic_subject = clean_topic[:75].rsplit(" ", 1)[0]
        else:
            topic_subject = clean_topic[:75]

        # Researched entities fallback values
        loc_setting = key_locations[0] if key_locations else "vibrant Indian street tapri setting"
        prop_main = physical_props[0] if physical_props else "controversial headline posters"
        prop_sub = physical_props[1] if (physical_props and len(physical_props) > 1) else "smartphone screen"
        action_main = tangible_actions[0] if tangible_actions else f"gesturing toward {prop_main}"
        action_sub = tangible_actions[1] if (tangible_actions and len(tangible_actions) > 1) else f"actively examining {prop_sub}"
        action_crowd = tangible_actions[2] if (tangible_actions and len(tangible_actions) > 2) else "curious crowd gathered reacting"

        combined_context = f"{clean_topic} {hook} {narration}".lower()
        combined_vibe = f"{tone} {angle}".lower()

        is_funny = any(w in combined_vibe for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी", "मजाकिया", "रोस्ट", "edgy", "relatable"])
        is_sad = any(w in combined_vibe for w in ["sad", "heartbreak", "tragedy", "दुख", "दर्द", "शोक", "lament", "loss", "grief", "भावुक", "tragic"])
        is_debate = "debate" in scene_style.lower()
        is_culture = any(w in combined_vibe for w in ["culture", "heritage", "pride", "गौरव", "धरोहर"])

        # Detect concrete physical props & environmental settings
        has_qr_or_poster = any(k in combined_context for k in ["qr", "कोड", "स्कैन", "scan", "poster", "पोस्टर"])
        has_poha = any(k in combined_context for k in ["पोहा", "पोहे", "poha", "नाश्ता", "जलेबी"])
        has_court_or_legal = any(k in combined_context for k in ["court", "सुप्रीम कोर्ट", "जज", "कानून", "फैसला", "गिरफ्तार", "police", "fir"])
        has_sir_or_gov = any(k in combined_context for k in ["sir", "dholera", "investment region", "special investment", "industrial corridor", "collectorate", "secretariat", "babu", "clerk", "land acquisition", "land registry", "सरकारी दफ्तर", "कलेक्टर", "सचिवालय"])
        has_hospital_or_medical = any(k in combined_context for k in ["hospital", "casualty", "opd", "डॉक्टर", "doctor", "medicine", "मरीज", "patient", "अस्पताल"])
        has_money_or_scam = any(k in combined_context for k in ["करोड़", "रुपये", "घोटाला", "scam", "bank", "tax", "शेयर", "crypto", "fraud"])
        has_tech_or_ai = any(k in combined_context for k in ["ai", "tech", "robot", "phone", "apple", "google", "software", "इंटरनेट", "app"])

        # Resolve dialogue lines and character personas
        active_personas = [p.replace("Rahul", "Rohan").replace("राहुल", "रोहन") for p in (personas or ["👩 Priya (प्रिया)", "🧑 Rohan (रोहन)", "👴 Chacha Ji (चाचा जी)"])]

        def get_line(idx: int, default: str) -> Tuple[str, str, str]:
            if scene_lines and idx < len(scene_lines):
                c = scene_lines[idx].get("character", "").strip()
                d = scene_lines[idx].get("dialogue", "").strip()
                a = scene_lines[idx].get("action", "").strip()
                if not c:
                    c = active_personas[idx % len(active_personas)]
                return c, d or default, a
            return active_personas[idx % len(active_personas)], default, ""

        timestamps = calculate_scene_timestamps(duration_sec, preferred_frames)
        num_scenes = len(timestamps)

        if is_funny:
            if has_poha or has_qr_or_poster:
                default_payoff = "इंदौरियों को पोहे का लालच देकर कुछ भी स्कैन करवा लो यार!"
            else:
                default_payoff = "ऐसी अनोखी खबरें ही तो दिन बना देती हैं, आपका क्या कहना है?!"
        elif is_sad:
            default_payoff = "यह सचमुच एक अत्यंत भावुक और विचारणीय पल है।"
        elif is_culture:
            default_payoff = "हमारी समृद्ध संस्कृति और इस पावन उत्सव को सादर नमन।"
        else:
            default_payoff = "इस पूरे मामले पर अब आगे की कार्रवाई पर सबकी नज़रें टिकी हैं।"

        char1, dial1, act1 = get_line(0, hook)
        char2, dial2, act2 = get_line(1, narration.replace(hook, "").strip() or "इस घटना से जुड़ी सबसे बड़ी सच्चाई अब सामने आ चुकी है।")
        char3, dial3, act3 = get_line(2, default_payoff)
        # Define 5-tier visual beat templates per theme to support 1 to 5 scenes dynamically
        # STRICT RULE: Pure actor kinematics & prop interactions ONLY — NO camera/setting preamble!
        if has_qr_or_poster and is_funny:
            vis_pool = [
                f"{{char}} points toward the weathered brick wall plastered with bold 'झूठ की गूंज' QR posters with animated comedic disbelief",
                f"{{char}} points smartphone camera at the poster QR code; phone viewfinder actively locks on and beeps, revealing sarcastic political video instead of food offer; {{char}} cracks up in disbelief",
                f"{{char}} whips phone around, showing the funny scanned video on smartphone screen to friends at the tapri while laughing uncontrollably",
                f"Curious locals and students gathered along the wall scan the poster QR codes with their phones and share laughs",
                f"Friends and tapri crowd share a laugh over cutting chai, concluding the viral poster saga with witty banter",
            ]
            sfx_pool = [
                "Cutting Chai Clink + Comedic Whoosh",
                "Smartphone QR Scan Beep + Record Scratch + Chuckle Beat",
                "Comedic Riser + Chuckle Beat",
                "Crowd Chatter & Laughter + Camera Clicks",
                "Trending Laugh Chime + Upbeat Tapri Outro Beat",
            ]
        elif has_court_or_legal:
            vis_pool = [
                f"{{char}} holds legal case brief on the court steps, urgently delivering the breaking legal update on {topic_subject}",
                f"{{char}} points to critical legal clauses and official stamp seals on the case documents with intense focus",
                f"{{char}} gestures toward legal precedents as digital court graphics animate on screen",
                f"Journalists and microphones lean in intently outside court pillars as citizens react with intense interest",
                f"{{char}} delivers the decisive closing verdict statement with solemn gravitas",
            ]
            sfx_pool = [
                "Urgent Gavel Strike + Low Sub-Bass",
                "Paper Rustle + Investigative Pulse",
                "Tense Synth Riser + Sub Drop",
                "Camera Shutter Flashes + Reporter Murmurs",
                "Dramatic Impact Hit + Legal Outro Chime",
            ]
        elif has_sir_or_gov:
            vis_pool = [
                f"{{char}} taps an index finger emphatically on a blueprint map of the Special Investment Region laid out across a wooden desk, speaking with animated bureaucratic urgency on {topic_subject}",
                f"{{char}} gestures with a ballpoint pen toward official red-taped clearance files and industrial land acquisition demarcations with sharp focus",
                f"{{char}} firmly presses an official ink stamp onto the approval documents, looking up with decisive clarity",
                f"Government clerks and assistants in background arrange files and verify survey maps along the collectorate corridor",
                f"{{char}} slides the signed file across the desk, delivering the final conclusion on the industrial roadmap with authoritative certainty",
            ]
            sfx_pool = [
                "Paper File Thud + Sub Bass Hit",
                "Pen Tap on Desk + Paper Rustle",
                "Official Stamp Press + Sharp Echo",
                "Corridor Murmurs + Ceiling Fan Whir",
                "Desk Slide Whoosh + Decisive Impact Beat",
            ]
        elif has_hospital_or_medical:
            vis_pool = [
                f"{{char}} adjusts stethoscope around neck while reviewing a clinical patient chart file, speaking with clinical focus on {topic_subject}",
                f"{{char}} points to medical prescription details and diagnostic report numbers with focused concern",
                f"{{char}} consults medical monitors and medicinal inventory cabinets, emphasizing key healthcare updates",
                f"Nurses and medical staff move swiftly along the hospital corridor in background",
                f"{{char}} delivers the concluding health guidance, looking directly forward with reassuring bedside authority",
            ]
            sfx_pool = [
                "Hospital Pager Beep + Ambience",
                "Paper Prescription Rustle + Heart Monitor Pulse",
                "Medicine Cabinet Clink + Soft Whoosh",
                "Stethoscope Movement + Footstep Pacing",
                "Gentle Reassuring Chime + Medical Fade",
            ]
        elif has_money_or_scam:
            vis_pool = [
                f"{{char}} points frantically to falling digital market tickers and bank transaction graphs on {topic_subject}",
                f"{{char}} reviews digital account statements on a tablet, breaking down the startling money trail",
                f"{{char}} throws hands up in disbelief as kinetic fraud transaction numbers flash red on screen",
                f"Citizens in the background check mobile banking apps on phones with stunned expressions",
                f"{{char}} delivers the key financial warning, locking eyes with the camera with authoritative urgency",
            ]
            sfx_pool = [
                "Digital Market Glitch + Urgent Whoosh",
                "Data Beeps + Tense Synth Rise",
                "Warning Buzzer + Fast Percussion",
                "ATM Ambient Beeps + Crowd Murmurs",
                "Sub-Bass Drop + Resolution Beat",
            ]
        elif is_sad:
            vis_pool = [
                f"{{char}} delivers a poignant opening on {topic_subject} with quiet vulnerability and tender sorrow",
                f"{{char}} reflects on the heartbreaking reality of {topic_subject} with mutual comfort and empathy",
                f"{{char}} pauses as gentle candle flame flickers, reflecting in quiet solemnity on the human loss",
                f"Family or community members stand in quiet, respectful solidarity behind {{char}}",
                f"{{char}} delivers a heartfelt tribute and call for empathy, looking upward with quiet solace",
            ]
            sfx_pool = [
                "Gentle Rain Ambience + Somber Piano Note",
                "Soulful Acoustic Sarangi / Violin Swell",
                "Warm Wind Chime + Melancholic Strings",
                "Quiet Ambient Room Tone + Soft Heartbeat",
                "Fading Acoustic Chime + Rain Fade-out",
            ]
        elif is_funny:
            vis_pool = [
                f"{{char}} delivers a hilarious opening quip about {topic_subject} with expressive comedic gestures, slamming cutting chai glass onto the wooden bench",
                f"{{char}} turns to friends with wide-eyed disbelief and laughter, thrusting mobile phone forward showing visuals of {topic_subject}",
                f"{{char}} acts out the absurdity of the situation with exaggerated comedic facial expressions and gestures",
                f"Amused bystanders and tapri customers overhear, nodding along and chuckling at the conversation",
                f"Friends laugh together over hot cutting chai, enjoying the hilarious moment with witty comedic energy",
            ]
            sfx_pool = [
                "Comedic Whoosh + Funny Drum Kick",
                "Record Scratch + Quip Beat",
                "Funny Boing + Chuckle Beat",
                "Bystander Laughter + Street Tapri Clatter",
                "Trending Laugh Chime + Outro Beat",
            ]
        elif is_debate:
            vis_pool = [
                f"{{char}} passionately makes the opening case on {topic_subject} with assertive rhetorical gestures",
                f"{{char}} fiercely counters with documented evidence and data charts on {topic_subject} with intense focus",
                f"{{char}} directly challenges the opposing viewpoint with sharp rhetoric and assertive gestures",
                f"Both speakers engage in an intense intellectual clash as dynamic counters animate on screen",
                f"{{char}} delivers the definitive closing counterpoint with intense dramatic conviction",
            ]
            sfx_pool = [
                "Heavy Gavel Hit + Tense Bass Sub-Drop",
                "Dramatic Thud + Investigative Pulse",
                "Studio Bell + Rapid Whoosh",
                "Dual Riser + Tension Pulse",
                "Tense Riser + Impact Outro",
            ]
        elif is_culture:
            vis_pool = [
                f"{{char}} warmly welcomes viewers into the sacred heritage of {topic_subject} with folded hands in respectful namaste",
                f"{{char}} showcases sacred cultural artifacts and traditional festive emblems bathed in warm golden diya glow",
                f"{{char}} traces authentic Indian artisanal craftsmanship, sacred motifs, and traditional elements with reverence",
                f"Devotees and community members celebrate cultural roots together with joyous expressions",
                f"{{char}} delivers a heartfelt appeal to cherish our timeless roots, gesturing with graceful cultural pride",
            ]
            sfx_pool = [
                "Soulful Sitar Strum + Temple Bell Chime",
                "Flute Ambient Swell + Traditional Tabla Groove",
                "Santoor Arpeggio + Golden Chime",
                "Celebratory Dhol Beats + Joyful Ambience",
                "Inspirational Crescendo + Temple Chime Outro",
            ]
        else:
            vis_pool = [
                f"{{char}} presents {topic_subject} with high-energy, engaging hand gestures and clear focus",
                f"{{char}} explains verified facts, gesturing to key visual evidence and real-world implications",
                f"{{char}} breaks down the critical turning point with heightened expression and animated delivery",
                f"Citizens and commuters react to the real-world development in the background",
                f"{{char}} delivers the memorable final takeaway line, leaning forward with confident finality",
            ]
            sfx_pool = [
                "Whoosh + Bass Hit",
                "Dynamic Investigative Beat",
                "Digital Riser + Data Pulse",
                "Urban Ambience + Rhythmic Beat",
                "Chime + Outro Swell",
            ]

        # Construct scenes dynamically for num_scenes (1 to 5)
        scenes: List[SceneItem] = []

        if num_scenes == 1:
            # Single continuous master shot for short reels, speeches, or monologues
            char1, dial1, _ = get_line(0, f"{hook} {narration}".strip() or hook)
            master_vis = f"Handheld continuous 9:16 master tracking shot at {loc_setting}; slow cinematic push-in as {char1} holds {prop_main}, delivering the complete story on {topic_subject} with high-energy expression"
            scenes.append(
                SceneItem(
                    scene_number=1,
                    act_name=f"{scene_style}: Master Frame - Hook & Punchline ({char1})",
                    character=char1,
                    dialogue=dial1,
                    timestamp=timestamps[0],
                    visual_b_roll=master_vis,
                    on_screen_text=dial1[:28],
                    audio_sfx=sfx_pool[0],
                )
            )
            return scenes

        # Multi-scene dynamic synthesis (2 to 5 scenes)
        # Select pool indices mapping to narrative structure: Hook -> Detail -> Escalation -> Reaction -> Payoff
        if num_scenes == 2:
            pool_indices = [0, 1]
            act_names = ["Frame 1 - Setup & Hook", "Frame 2 - Core Story & Payoff"]
        elif num_scenes == 3:
            pool_indices = [0, 1, 3]
            act_names = ["Frame 1 - The 0-3s Hook", "Frame 2 - Core Action & Prop", "Frame 3 - Twist & Payoff"]
        elif num_scenes == 4:
            pool_indices = [0, 1, 2, 4]
            act_names = ["Frame 1 - The Hook & Setting", "Frame 2 - Evidence & Prop", "Frame 3 - Conflict & Twist", "Frame 4 - Public Reaction & Payoff"]
        else:  # 5 scenes
            pool_indices = [0, 1, 2, 3, 4]
            act_names = ["Frame 1 - The Hook", "Frame 2 - Core Evidence", "Frame 3 - Conflict & Climax", "Frame 4 - Public Reaction", "Frame 5 - Definitive Payoff"]

        for s_idx in range(num_scenes):
            p_idx = pool_indices[s_idx]
            if s_idx == 0:
                def_line = hook
            elif s_idx == num_scenes - 1:
                def_line = default_payoff
            elif s_idx == 1:
                def_line = narration.replace(hook, "").strip() or topic_subject
            else:
                def_line = f"सच सामने आ गया है!"

            char, dial, act = get_line(s_idx, def_line)
            vis = vis_pool[p_idx].format(char=char)
            sfx = sfx_pool[p_idx]
            act_label = f"{scene_style}: {act_names[s_idx]} ({char})"

            # Text overlay is optional and context-driven: hook for beat 1, punchline for last beat, reaction turns clean
            if s_idx == 0:
                ost = dial[:22] if len(dial) > 5 else "बड़ी खबर!"
            elif s_idx == num_scenes - 1:
                ost = dial[:22] if len(dial) > 5 else "अहम मोड़!"
            else:
                ost = ""  # Intermediate conversation beats keep visual focus on actors without overlay clutter

            scenes.append(
                SceneItem(
                    scene_number=s_idx + 1,
                    act_name=act_label,
                    character=char,
                    dialogue=dial,
                    timestamp=timestamps[s_idx],
                    visual_b_roll=vis,
                    on_screen_text=ost,
                    audio_sfx=sfx,
                )
            )

        return scenes



scene_director = SceneVisualsDirectorAgent()
