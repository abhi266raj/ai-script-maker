"""Agent: Screenplay Coherence Sub-Agent.

Enforces deep physical, thematic, and visual coherence between spoken dialogue cues and scene action:
1. Spoken Object & Kinematic Action Locking:
   - If dialogue mentions sipping, drinking, or leaving tea ("चाय", "घूंट", "sip", "tea", "कटिंग", "कुल्हड़"):
     -> Visual action locks onto sipping cutting chai, holding the glass, or setting it down.
     -> SFX syncs to tea sipping / glass clinking.
   - If dialogue mentions paper, newspaper, official files, bills ("अखबार", "कागज़", "file", "बिल", "दस्तावेज़", "ऑर्डर"):
     -> Visual action locks onto unfolding newspaper, pointing to clauses in official file, or reviewing bill.
     -> SFX syncs to paper rustling / folder thud.
   - If dialogue mentions phone, screen, viral clip, QR, photo ("फोन", "स्क्रीन", "वीडियो", "मैसेज", "फोटो", "स्कैन", "qr"):
     -> Visual action locks onto thrusting phone forward or pointing at screen.
     -> SFX syncs to phone notification chime / screen tap.
   - If dialogue mentions money, price, cash, coins ("रुपये", "पैसे", "करोड़", "नोट", "कैश", "फीस", "लाख"):
     -> Visual action locks onto counting currency notes or inspecting wallet/bill.
     -> SFX syncs to currency note flap / cash register chime.
   - If dialogue mentions books, degree, coaching notes ("किताब", "डिग्री", "कोचिंग", "नोट्स", "सिलेबस"):
     -> Visual action locks onto slamming book onto the counter or clutching coaching notes.
     -> SFX syncs to heavy book slam / whoosh.
   - If dialogue mentions medicine, prescription, report ("दवा", "पर्चा", "रिपोर्ट", "इलाज"):
     -> Visual action locks onto reviewing clinical prescription slip or medical file.
     -> SFX syncs to prescription paper rustle.
   - If dialogue mentions official stamp, seal, sign ("मुहर", "स्टैंप", "दस्तखत", "साइन"):
     -> Visual action locks onto firmly pressing official ink stamp onto the clearance document.
     -> SFX syncs to official stamp press echo.
2. Eliminates Randomness:
   - Guarantees scene camera focus and actor kinematics are tightly coupled to the words spoken in the dialogue.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from agents.base import BaseAgent
from core.models import SceneItem, ReelScript


COHERENCE_INSTRUCTIONS = """You are the Chief Screenplay Coherence & Kinematics Auditor.
Your sole mission is guaranteeing that whatever characters talk about in spoken dialogue is directly mirrored in the visual action, camera focus, and sound effects.
If a character says 'चाय छोड़' or 'चाय का घूंट', the actor must physically interact with the tea glass.
If a character mentions an 'अखबार' or 'सरकारी फाइल', the actor must hold, unfold, or point at the newspaper or file.
Never allow disconnected, random gestures when physical objects are referenced in dialogue."""


class ScreenplayCoherenceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Screenplay Coherence Auditor",
            role="Dialogue-Action Physical Synchronization & Prop Coherence",
            icon="🎯",
            instructions=COHERENCE_INSTRUCTIONS,
        )

    def extract_character_clean_name(self, char_str: str) -> str:
        """Extract primary character name without emojis or parenthetical tags."""
        if not char_str:
            return "Speaker"
        cleaned = re.sub(r"[^\w\s/()-]", "", char_str).strip()
        base = cleaned.split("/")[0].split("(")[0].strip()
        tokens = [t for t in base.split() if len(t) > 1 and not t.isdigit()]
        if tokens:
            if len(tokens) > 1 and tokens[0].lower() in ["dr", "mr", "ms", "advocate", "inspector", "sub-inspector", "seth", "master"]:
                return tokens[-1].strip()
            elif len(tokens) > 1 and tokens[1].lower() == "ji":
                return f"{tokens[0]} {tokens[1]}".strip()
            return tokens[0].strip()
        return "Speaker"

    def audit_and_align_scene_coherence(
        self,
        scene: SceneItem,
        prev_scene: Optional[SceneItem] = None,
        tone: str = "",
    ) -> SceneItem:
        """
        Analyze the scene's spoken dialogue for concrete physical objects and verbs,
        and lock the visual action and SFX to what is spoken, eliminating random actions.
        """
        dial = (scene.dialogue or "").lower()
        vis = scene.visual_b_roll or ""
        char_name = self.extract_character_clean_name(scene.character)

        # 1. TEA / CHAI / SIPPING / LEAVING TEA
        if any(k in dial for k in ["चाय", "घूंट", "sip", "tea", "कटिंग", "कुल्हड़", "प्याली", "चाय छोड़"]):
            if any(k in vis.lower() for k in ["chai", "tea", "cutting", "कुल्हड़", "cup", "glass", "sip"]):
                return scene
            if "चाय छोड़" in dial or "छोड़" in dial:
                scene.visual_b_roll = f"{char_name} abruptly sets down the half-finished cutting chai glass on the wooden bench, leaning in with urgent animated emotion."
                scene.audio_sfx = "Chai Glass Clink + Urgent Whoosh"
            elif any(k in dial for k in ["घूंट", "sip", "पी", "गरम"]):
                scene.visual_b_roll = f"{char_name} takes a steaming sip from the cutting chai glass, exhaling with relatable animated expression before speaking."
                scene.audio_sfx = "Cutting Chai Sip + Steam Whoosh"
            else:
                scene.visual_b_roll = f"{char_name} gestures with the cutting chai glass in hand, holding it steady while delivering spoken lines."
                scene.audio_sfx = "Cutting Chai Clink + Ambient Tapri Clatter"
            return scene

        # 2. PAPER / NEWSPAPER / OFFICIAL FILE / BILL / GAZETTE
        if any(k in dial for k in ["अखबार", "कागज़", "कागज", "paper", "file", "दस्तावेज़", "ऑर्डर", "गजट", "सर्कुलर", "पर्चा", "रिपोर्ट"]):
            if any(k in vis.lower() for k in ["newspaper", "अखबार", "paper", "file", "bill", "receipt", "document", "clause"]):
                return scene
            if any(k in dial for k in ["अखबार", "newspaper", "हेडलाइन"]):
                scene.visual_b_roll = f"{char_name} sharply unfolds the morning Hindi newspaper, pointing an index finger directly at the front-page headline with wide-eyed reaction."
                scene.audio_sfx = "Newspaper Snap + Low Paper Rustle"
            elif any(k in dial for k in ["बिल", "bill", "खर्चा", "रसीद"]):
                scene.visual_b_roll = f"{char_name} waves the paper billing receipt with frantic disbelief, tapping the total amount figure emphatically."
                scene.audio_sfx = "Paper Bill Rustle + Dramatic Hit"
            else:
                scene.visual_b_roll = f"{char_name} taps a ballpoint pen emphatically on the official document file folder spread across the table, highlighting the critical clause."
                scene.audio_sfx = "Pen Tap on Desk + Paper Rustle"
            return scene

        # 3. SMARTPHONE / PHONE SCREEN / VIRAL VIDEO / QR CODE / MESSAGE
        if any(k in dial for k in ["फोन", "स्क्रीन", "phone", "मोबाइल", "वीडियो", "video", "मैसेज", "फोटो", "स्कैन", "qr", "रील", "ग्रुप"]):
            if any(k in vis.lower() for k in ["phone", "screen", "mobile", "qr", "smartphone", "video"]):
                return scene
            if any(k in dial for k in ["स्कैन", "qr", "scan"]):
                scene.visual_b_roll = f"{char_name} points smartphone camera at the bold QR code; phone screen locks on with a visible confirmation beep."
                scene.audio_sfx = "Smartphone QR Scan Beep + Record Scratch"
            elif any(k in dial for k in ["देख", "देखा", "स्क्रीन", "वीडियो"]):
                scene.visual_b_roll = f"{char_name} thrusts mobile phone screen into the frame, showing the viral video playback with animated disbelief."
                scene.audio_sfx = "Smartphone Screen Tap + Notification Chime"
            else:
                scene.visual_b_roll = f"{char_name} checks incoming notifications on mobile phone, reacting with animated facial expressions."
                scene.audio_sfx = "Subtle Phone Buzz + Whoosh"
            return scene

        # 4. MONEY / CASH / RUPEES / CRORES / PRICE HIKE / WALLET
        if any(k in dial for k in ["रुपये", "पैसे", "करोड़", "नोट", "कैश", "फीस", "लाख", "price", "महंगा", "महंगाई"]):
            if any(k in vis.lower() for k in ["currency", "note", "cash", "money", "wallet", "रुपये", "पैसे"]):
                return scene
            scene.visual_b_roll = f"{char_name} counts paper currency notes with quick thumb motions, looking up in shock at the steep monetary figure."
            scene.audio_sfx = "Currency Note Flap + Sub Impact"
            return scene

        # 5. BOOKS / DEGREE / COACHING / STUDY MODULES
        if any(k in dial for k in ["किताब", "डिग्री", "कोचिंग", "नोट्स", "book", "सिलेबस", "एग्जाम", "पढ़ाई"]):
            if any(k in vis.lower() for k in ["book", "किताब", "notes", "डिग्री", "notebook"]):
                return scene
            if "डिग्री" in dial or "कोचिंग" in dial:
                scene.visual_b_roll = f"{char_name} slams a heavy coaching book down onto the counter with exasperated comedic disbelief."
                scene.audio_sfx = "Fast Whoosh + Heavy Book Slam"
            else:
                scene.visual_b_roll = f"{char_name} clutches coaching notes tightly to chest, gesturing mockingly while delivering lines."
                scene.audio_sfx = "Paper Book Rustle + Chuckle Beat"
            return scene

        # 6. STAMP / OFFICIAL SEAL / APPROVAL
        if any(k in dial for k in ["मुहर", "स्टैंप", "stamp", "दस्तखत", "साइन"]):
            if any(k in vis.lower() for k in ["stamp", "मुहर", "seal"]):
                return scene
            scene.visual_b_roll = f"{char_name} firmly presses the official ink stamp onto the clearance document, stamping it with sharp bureaucratic finality."
            scene.audio_sfx = "Official Ink Stamp Press + Sharp Echo"
            return scene

        # 7. FOOD / BREAKFAST / POHA / SAMOSA / SNACK
        if any(k in dial for k in ["पोहा", "समोसा", "जलेबी", "नाश्ता", "स्नैक", "खिला"]):
            if any(k in vis.lower() for k in ["poha", "samosa", "plate", "spoon", "नाश्ता"]):
                return scene
            scene.visual_b_roll = f"{char_name} picks up a bite with a spoon from the paper plate of poha, pausing mid-air in funny surprise."
            scene.audio_sfx = "Snack Plate Clink + Comedic Chime"
            return scene

        return scene

    def align_screenplay_coherence(self, script: ReelScript) -> ReelScript:
        """
        Audit and align all scenes in the screenplay to enforce dialogue-action physical coherence.
        """
        if not script or not script.scenes:
            return script

        prev_sc = None
        for sc in script.scenes:
            self.audit_and_align_scene_coherence(sc, prev_sc, getattr(script, "angle", ""))
            prev_sc = sc

        return script

    def audit_screenplay_coherence(self, script: ReelScript) -> Tuple[bool, List[str], List[str]]:
        """
        Audit whether dialogue-mentioned props and actions are coherent with the visual beat action.
        Returns: (is_coherent, issues, suggestions)
        """
        issues = []
        suggestions = []
        if not script or not script.scenes:
            return True, [], []

        for idx, sc in enumerate(script.scenes):
            dial = (sc.dialogue or "").lower()
            vis = (sc.visual_b_roll or "").lower()
            beat_num = idx + 1

            # Check tea mentioned in dialogue but missing from visuals
            if any(k in dial for k in ["चाय", "घूंट", "sip", "tea"]) and not any(k in vis for k in ["chai", "tea", "glass", "sip"]):
                issues.append(f"Scene {beat_num}: Dialogue mentions tea/sipping but visual action lacks tea glass interaction.")
                suggestions.append(f"Scene {beat_num}: Depict character holding or sipping cutting chai glass.")

            # Check paper/newspaper mentioned in dialogue but missing from visuals
            if any(k in dial for k in ["अखबार", "कागज़", "newspaper", "file", "बिल", "bill"]) and not any(k in vis for k in ["paper", "newspaper", "file", "bill", "clause"]):
                issues.append(f"Scene {beat_num}: Dialogue mentions newspaper/paper/file but visual action lacks paper interaction.")
                suggestions.append(f"Scene {beat_num}: Depict character unfolding newspaper or pointing at official paper/file.")

            # Check phone mentioned in dialogue but missing from visuals
            if any(k in dial for k in ["फोन", "स्क्रीन", "phone", "वीडियो", "qr"]) and not any(k in vis for k in ["phone", "screen", "mobile", "qr", "smartphone"]):
                issues.append(f"Scene {beat_num}: Dialogue mentions phone/video/QR but visual action lacks phone screen interaction.")
                suggestions.append(f"Scene {beat_num}: Depict character thrusting phone screen forward or scanning QR.")

        is_coherent = len(issues) == 0
        return is_coherent, issues, suggestions


screenplay_coherence_agent = ScreenplayCoherenceAgent()
