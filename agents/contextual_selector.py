"""Agent: Contextual Scene & Character Selector Agent.

Selects domain-grounded settings, authentic characters, and role-appropriate wardrobe based on:
1. News topic domain (e.g. SIR / Industrial Corridor / Government Bureaucracy -> Government Office,
   Hospital / Medical -> Hospital OPD, High Court -> Courtroom / Corridors, IT / Tech -> Corporate Cubicle).
2. Reference sample story (if provided, given top precedence).
3. Requirements & creative tone.

CRITICAL RULE: NOT everything is a chai tapri! Institutional topics are placed in their authentic venues.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from agents.base import BaseAgent
from agents.scene_catalog import (
    SCENE_STYLE_SETUPS,
    CREATIVE_ANGLE_SETUPS,
    DOMAIN_SETUPS,
    get_scene_style_catalog,
    get_creative_angle_catalog,
    get_domain_catalog,
)
from core.prompt_loader import load_prompt

CONTEXTUAL_SELECTOR_INSTRUCTIONS = load_prompt("contextual_selector/contextual_selector.md")


class ContextualSceneCharacterSelectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Contextual Scene & Character Selector",
            role="Domain-Grounded Setting, Persona & Wardrobe Alignment",
            icon="🎯",
            instructions=CONTEXTUAL_SELECTOR_INSTRUCTIONS,
            prompt_file="contextual_selector/contextual_selector.md",
        )

    def get_scene_style_setups(self, scene_style: str) -> List[Dict[str, Any]]:
        """Retrieve all curated setups for a Scene Style (min 6)."""
        return get_scene_style_catalog(scene_style)

    def get_angle_setups(self, angle: str) -> List[Dict[str, Any]]:
        """Retrieve all curated setups for a Creative Angle (min 6)."""
        return get_creative_angle_catalog(angle)

    def get_domain_setups(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve all curated setups for a Script Topic Domain (min 6)."""
        return get_domain_catalog(domain)

    def select_setup_for_context(
        self,
        news_topic: str = "",
        scene_style: str = "Dialogue",
        angle: str = "",
        sample_story: Optional[str] = None,
        character_count: int = 2,
    ) -> Dict[str, Any]:
        """
        Subagent selector: picks the most relevant setup matching domain, style, and angle
        with at least 5-6 setups per category available.
        """
        # First check topic domain
        domain = self.detect_domain(news_topic, sample_story)
        domain_setups = self.get_domain_setups(domain)
        if domain != "street_tapri" and domain_setups:
            return domain_setups[0]

        # Next check scene style setups
        if scene_style:
            style_setups = self.get_scene_style_setups(scene_style)
            if style_setups:
                combined = f"{news_topic} {sample_story or ''}".lower()
                for s in style_setups:
                    rel_words = [w.lower() for w in s.get("relationship", "").split() if len(w) > 2]
                    if any(w in combined for w in rel_words):
                        return s
                return style_setups[0]

        # Next check angle setups
        if angle:
            angle_setups = self.get_angle_setups(angle)
            if angle_setups:
                return angle_setups[0]

        return self.get_scene_style_setups("Dialogue")[0]

    def detect_domain(self, news_topic: str, sample_story: Optional[str] = None) -> str:
        """Classify the story into its core real-world physical domain."""
        combined = f"{news_topic} {sample_story or ''}".lower()

        def matches_any(keywords: List[str], target: str) -> bool:
            for k in keywords:
                if len(k) <= 3 and k.isalpha():
                    if re.search(rf"\b{re.escape(k)}\b", target):
                        return True
                else:
                    if k in target:
                        return True
            return False

        # 1. SIR / Industrial / Government Administration / Secretariat / Babu / Schemes / Land Registry
        if matches_any([
            "sir", "dholera", "investment region", "special investment", "industrial corridor",
            "collectorate", "secretariat", "mantralaya", "babu", "clerk", "land registry",
            "land acquisition", "government office", "सरकारी दफ्तर", "कलेक्टर", "सचिवालय", "बाबू",
            "पेंशन", "pension", "bureaucracy", "administrative", "योजना", "scheme"
        ], combined):
            return "government_sir"

        # 2. Healthcare / Medical / Hospital / Doctor / Medicine / Disease / Pharmacy
        if matches_any([
            "hospital", "doctor", "casualty", "opd", "medicine", "pharmacy", "health",
            "clinic", "nurse", "patient", "अस्पताल", "डॉक्टर", "दवा", "इलाज", "मरीज", "चिकित्सक"
        ], combined):
            return "healthcare"

        # 3. Legal / Judicial / High Court / Supreme Court / Bail / Law / Verdict / FIR / Lawyer
        if matches_any([
            "court", "judge", "lawyer", "advocate", "bail", "verdict", "supreme court",
            "high court", "कानून", "वकील", "जज", "अदालत", "मुकदमा", "जमानत", "याचिका"
        ], combined):
            return "legal"

        # 4. Tech / Corporate / IT / Software / AI / WFO / Biometric / Startup / Appraisal
        if matches_any([
            "tech", "software", "ai", "wfo", "biometric", "cubicle", "startup", "appraisal",
            "laptop", "corporate", "ऑफिस", "आईटी", "बायोमेट्रिक", "work from office"
        ], combined):
            return "tech_corporate"

        # 5. Domestic / Household / Inflation / Gas Cylinder / Ration / Grocery / Kitchen
        if matches_any([
            "ration", "gas", "cylinder", "kitchen", "grocery", "vegetable", "household",
            "महंगाई", "घरेलू", "सिलेंडर", "किचन", "सब्जी", "दाल", "patni", "pati", "पत्नी", "पति"
        ], combined):
            return "domestic"

        # 6. Education / Career / Coaching / Degree / College / Student / Exam
        if matches_any([
            "coaching", "degree", "exam", "college", "university", "student", "school",
            "teacher", "नौकरी", "डिग्री", "कोचिंग", "छात्र", "मास्टर", "परीक्षा"
        ], combined):
            return "education"

        # 7. Police / Law Enforcement / Traffic / Challan / Crime / Investigation
        if matches_any([
            "police", "thana", "challan", "traffic", "crime", "arrest", "दरोगा", "थाना", "चालान", "ट्रैफिक"
        ], combined):
            return "police"

        # 8. Politics / Election / Netaji / Corporator / Municipal / Rally
        if matches_any([
            "election", "netaji", "parshad", "corporator", "party", "rally", "vote", "चुनाव", "पार्षद", "नेताजी"
        ], combined):
            return "politics"

        # 9. Agriculture / Rural / Farming / Mandi / Kisan
        if matches_any([
            "farmer", "kisan", "mandi", "panchayat", "sarpanch", "crop", "किसान", "मंडी", "पंचायत"
        ], combined):
            return "agriculture"

        return "street_tapri"

    def select_scene_and_characters(
        self,
        news_topic: str,
        sample_story: Optional[str] = None,
        character_count: int = 2,
        duration_sec: int = 15,
        tone: str = "",
        angle: str = "",
    ) -> Dict[str, Any]:
        """
        Select coherent domain-grounded scene setting, character personas, and wardrobe.
        """
        is_fast = duration_sec <= 10
        domain = self.detect_domain(news_topic, sample_story)

        # Domain Configuration Profiles
        if domain == "government_sir":
            setting = (
                "A bustling government administrative planning office and collectorate corridor. "
                "Very fast-paced administrative action to fit the 10-second limit." if is_fast else
                "A bustling government administrative planning office and collectorate corridor. "
                "Wooden desks stacked with official files, blueprint maps of the Special Investment Region (SIR), ceiling fans, and official wall seals."
            )
            personas_2 = [
                "👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)",
                "🧑 Rajesh (Industrial Investor / Local Landowner - उद्यमी / नागरिक)"
            ]
            personas_3 = [
                "👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)",
                "🧑 Rajesh (Industrial Investor / Citizen - उद्यमी)",
                "👩 Priya (Land Planning Assistant - सहायक योजनाकार)"
            ]
            wardrobes = {
                "SHARMA JI": "Crisp half-sleeve formal collared shirt with ballpoint pens in front pocket and official government ID lanyard.",
                "OFFICER": "Crisp half-sleeve formal collared shirt with ballpoint pens in front pocket and official government ID lanyard.",
                "RAJESH": "Smart-casual collared shirt and trousers, holding a blue official document file folder.",
                "INVESTOR": "Smart-casual collared shirt and trousers, holding a blue official document file folder.",
                "PRIYA": "Formal Indian cotton kurti with office ID badge.",
            }
            props = ["Special Investment Region blueprint map", "blue official document file folder", "ink stamp"]
            sfx = "Paper File Thud + Official Stamp Press"

        elif domain == "healthcare":
            setting = (
                "Government hospital OPD corridor and consultation room. "
                "High-energy emergency movement to fit the 10-second limit." if is_fast else
                "Government hospital OPD corridor and consultation room. "
                "Stethoscopes, medicinal cabinets, official health posters on green-painted walls, and patient queue in background."
            )
            personas_2 = [
                "🩺 Dr. Rajesh (Senior Hospital Physician - वरिष्ठ चिकित्सक)",
                "🧑 Ramesh (Patient / Common Citizen - मरीज)"
            ]
            personas_3 = [
                "🩺 Dr. Rajesh (Senior Hospital Physician - वरिष्ठ चिकित्सक)",
                "🧑 Ramesh (Patient / Common Citizen - मरीज)",
                "👩 Nurse Sneha (Staff Nurse - सिस्टर / नर्स)"
            ]
            wardrobes = {
                "DR. RAJESH": "White medical lab coat over light-blue formal shirt with stethoscope around neck.",
                "DOCTOR": "White medical lab coat over light-blue formal shirt with stethoscope around neck.",
                "RAMESH": "Everyday modest cotton shirt and trousers, holding a medical prescription slip.",
                "PATIENT": "Everyday modest cotton shirt and trousers, holding a medical prescription slip.",
                "NURSE": "Hospital nursing scrubs with hospital ID badge.",
            }
            props = ["medical prescription slip", "medicine strip", "stethoscope"]
            sfx = "Hospital Murmur + Medicine Strip Pop"

        elif domain == "legal":
            setting = (
                "High Court entrance steps and pillared corridor. "
                "Rapid, high-stakes legal buzz to fit the 10-second limit." if is_fast else
                "High Court entrance steps and pillared corridor. "
                "Advocates carrying tied legal case files, official notices on notice boards, and waiting litigants in background."
            )
            personas_2 = [
                "⚖️ Advocate Verma (High Court Senior Lawyer - वरिष्ठ अधिवक्ता)",
                "🧑 Kabir (Litigant / Common Citizen - मुवक्किल / नागरिक)"
            ]
            personas_3 = [
                "⚖️ Advocate Verma (High Court Senior Lawyer - वरिष्ठ अधिवक्ता)",
                "🧑 Kabir (Litigant / Common Citizen - मुवक्किल)",
                "👔 Clerk Tripathi (Court Reader / Babu - पेशकार बाबू)"
            ]
            wardrobes = {
                "ADVOCATE VERMA": "Black legal advocate coat with white neckband over crisp white collared shirt.",
                "LAWYER": "Black legal advocate coat with white neckband over crisp white collared shirt.",
                "KABIR": "Modest formal attire, clutching a tied legal case file folder.",
                "LITIGANT": "Modest formal attire, clutching a tied legal case file folder.",
            }
            props = ["tied legal case file", "law book", "petition document"]
            sfx = "Gavel Impact + Case File Rustle"

        elif domain == "tech_corporate":
            setting = (
                "A glass-partitioned modern corporate IT office and reception. "
                "Fast-paced tech park energy to fit the 10-second limit." if is_fast else
                "A glass-partitioned modern corporate IT office and reception. "
                "RFID security turnstiles, ergonomic workstations, and indoor foliage in background."
            )
            personas_2 = [
                "👩 Priya (Senior Software Engineer / Colleague 1 - सीनियर डेवलपर)",
                "🧑 Rohan (Product Manager / Colleague 2 - प्रोडक्ट मैनेजर)"
            ]
            personas_3 = [
                "👩 Priya (Senior Software Engineer - कलीग 1)",
                "🧑 Rohan (Product Manager - कलीग 2)",
                "👔 Manager Mehra (Corporate Department Head - डायरेक्टर)"
            ]
            wardrobes = {
                "PRIYA": "Smart-casual tech park attire with corporate RFID access lanyard around neck.",
                "ROHAN": "Collared polo shirt, dark denim jeans, with corporate RFID badge clip.",
                "COLLEAGUE": "Smart-casual office attire with corporate RFID lanyard.",
            }
            props = ["corporate RFID access badge", "slim laptop", "coffee mug"]
            sfx = "RFID Turnstile Beep + Keyboard Clatter"

        elif domain == "domestic":
            setting = (
                "A cozy Indian middle-class household kitchen and living room. "
                "Very fast-paced domestic discussion to fit the 10-second limit." if is_fast else
                "A cozy Indian middle-class household kitchen and living room. "
                "Gas stove, stainless steel spice containers, handwritten grocery list, and tea cups on the counter."
            )
            personas_2 = [
                "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
                "🧑 Rajesh (Husband / Salaried Employee - नौकरीपेशा पति)"
            ]
            personas_3 = [
                "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
                "🧑 Rajesh (Husband / Salaried Employee - नौकरीपेशा पति)",
                "👴 Sharma Ji (Elder Father - पिताजी)"
            ]
            wardrobes = {
                "SUNITA": "Casual traditional printed cotton daily-wear saree or comfortable kurti.",
                "WIFE": "Casual traditional printed cotton daily-wear saree or comfortable kurti.",
                "RAJESH": "Casual collared half-sleeve home shirt and cotton trousers.",
                "HUSBAND": "Casual collared half-sleeve home shirt and cotton trousers.",
            }
            props = ["handwritten grocery budget list", "gas cylinder receipt", "steel tea cup"]
            sfx = "Stainless Steel Clink + Paper Bill Rustle"

        elif domain == "education":
            setting = (
                "A traditional Indian study room or college campus corridor. "
                "Animated academic debate to fit the 10-second limit." if is_fast else
                "A traditional Indian study room or college campus corridor. "
                "Heavy coaching modules, NCERT books, and wall calendar with marked exam dates."
            )
            personas_2 = [
                "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)",
                "🧑 Aarav (Gen-Z Son / Student - आधुनिक बेटा)"
            ]
            personas_3 = [
                "👴 Sharma Ji (Traditional Father - पिता)",
                "🧑 Aarav (Gen-Z Son / Student - बेटा)",
                "📚 Master Ji (School Teacher - शिक्षक)"
            ]
            wardrobes = {
                "SHARMA JI": "Traditional cotton kurta-pyjama with reading spectacles resting on nose.",
                "FATHER": "Traditional cotton kurta-pyjama with reading spectacles resting on nose.",
                "AARAV": "Modern college hoodie or casual t-shirt with heavy study backpack.",
                "SON": "Modern college hoodie or casual t-shirt with heavy study backpack.",
            }
            props = ["heavy coaching test module book", "coaching fee receipt", "study backpack"]
            sfx = "Book Slam onto Desk + Page Flutter"

        elif domain == "police":
            setting = (
                "City police station (Thana) reception or traffic checkpost. "
                "Urgent police action to fit the 10-second limit." if is_fast else
                "City police station (Thana) reception or traffic checkpost. "
                "Wooden barricades, official wireless walkie-talkie, and duty log register."
            )
            personas_2 = [
                "👮 Sub-Inspector Sunita (Traffic Police Officer - पुलिस दरोगा)",
                "🛵 Rohan (Citizen / Delivery Partner - नागरिक)"
            ]
            personas_3 = [
                "👮 Sub-Inspector Sunita (Traffic Police Officer - पुलिस दरोगा)",
                "🛵 Rohan (Citizen / Delivery Partner - नागरिक)",
                "🧑 Constable Verma (Police Constable - पुलिस जवान)"
            ]
            wardrobes = {
                "SUB-INSPECTOR SUNITA": "Crisp khaki police uniform with brass service badges, shoulder stars, and leather belt.",
                "POLICE": "Crisp khaki police uniform with brass service badges, shoulder stars, and leather belt.",
                "ROHAN": "Casual street wear, helmet in hand or delivery company windbreaker jacket.",
            }
            props = ["digital e-challan device", "police duty register", "helmet"]
            sfx = "Police Radio Crackle + Siren Whoosh"

        else:
            # Check if text actually warrants a chai tapri setting
            combined_text = f"{news_topic} {sample_story or ''}".lower()
            is_explicit_tapri = any(k in combined_text for k in ["chai", "tapri", "चाय", "टपरी", "tea", "street", "dhaba", "roadside", "nukkad", "नुक्कड़", "friend", "दोस्त"])
            if not is_explicit_tapri and (news_topic.strip() or (sample_story and sample_story.strip())):
                # DYNAMIC IMAGINATION: Synthesize brand new setting, personas, wardrobe, props, and SFX from current data
                return self.imagine_from_current_data(
                    news_topic=news_topic,
                    sample_story=sample_story,
                    character_count=character_count,
                    duration_sec=duration_sec,
                    tone=tone,
                    angle=angle,
                )

            # Default authentic street tapri for casual banter
            setting = (
                "A bustling local Indian street chai tapri. "
                "Very fast-paced, high-energy vibe to fit the 10-second limit." if is_fast else
                "A bustling local Indian street chai tapri. "
                "Casual, everyday public space vibe with background customers, street noise, and boiling tea."
            )
            personas_2 = [
                "👩 Ananya (College Friend 1 - कॉलेज दोस्त)",
                "🧑 Vikram (Street-Smart Friend 2 - पक्का यार)"
            ]
            personas_3 = [
                "👩 Ananya (College Friend 1 - कॉलेज दोस्त)",
                "🧑 Vikram (Street-Smart Friend 2 - पक्का यार)",
                "☕ Mohan (Chai Tapri Vendor - टपरी वाला)"
            ]
            wardrobes = {
                "ANANYA": "Casual college-going attire (e.g., jeans and a simple kurti).",
                "VIKRAM": "Everyday street casual wear (e.g., t-shirt and jeans).",
                "MOHAN": "Casual cotton shirt with a tea vendor apron.",
            }
            props = ["cutting chai glass", "smartphone", "wooden bench"]
            sfx = "Cutting Chai Clink + Tapri Murmur"

        selected_personas = personas_3 if character_count >= 3 else personas_2
        if character_count == 1:
            selected_personas = [selected_personas[0]]

        return {
            "domain": domain,
            "setting": setting,
            "setting_detail": setting,
            "personas": selected_personas,
            "wardrobes": wardrobes,
            "props": props,
            "sfx": sfx,
        }

    def extract_key_subject(self, text: str) -> str:
        """Extract a crisp 2-3 word subject noun phrase from text for dynamic imagination."""
        if not text:
            return "Current Affairs"
        clean = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)
        words = clean.split()
        stop_words = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is", "are",
            "was", "were", "with", "by", "from", "about", "into", "over", "after", "new",
            "make", "funny", "conversation", "between", "two", "reacting", "ka", "ki", "ke",
            "hai", "hain", "par", "se", "aur", "ko", "me", "mein", "pe", "yeh", "woh", "under", "per"
        }
        filtered = [w for w in words if w.lower() not in stop_words and len(w) > 2]
        if not filtered:
            return text.strip()[:30]
        return " ".join(filtered[:3]).title()

    def imagine_from_current_data(
        self,
        news_topic: str,
        sample_story: Optional[str] = None,
        character_count: int = 2,
        duration_sec: int = 15,
        tone: str = "",
        angle: str = "",
    ) -> Dict[str, Any]:
        """
        Dynamically imagine a brand new authentic setting, professional/stakeholder personas,
        role wardrobe, props, and SFX when no hardcoded domain or pair matches the current data.
        """
        combined = f"{news_topic} {sample_story or ''}".lower()
        is_fast = duration_sec <= 10
        subject = self.extract_key_subject(news_topic or sample_story or "Current Affairs")

        # 1. Space / Astronomy / ISRO / Satellite / Rocket / Cosmos
        if any(k in combined for k in ["space", "isro", "satellite", "chandrayaan", "gaganyaan", "rocket", "orbit", "astronomy", "अंतरिक्ष", "रॉकेट", "मिशन", "उपग्रह"]):
            setting = (
                f"ISRO Satellite Telemetry and Mission Operations Complex. "
                f"High-energy mission countdown urgency to fit the 10-second limit." if is_fast else
                f"ISRO Satellite Telemetry and Mission Operations Complex. "
                f"Giant wall projection displays showing orbital coordinates for {subject}, telemetry consoles, and mission status readouts."
            )
            personas_2 = [
                "🚀 Dr. Vikram (Senior ISRO Mission Scientist - मुख्य वैज्ञानिक)",
                "👩 Priya (Aerospace Flight Trajectory Engineer - मिशन इंजीनियर)"
            ]
            personas_3 = [
                "🚀 Dr. Vikram (Senior ISRO Mission Scientist - मुख्य वैज्ञानिक)",
                "👩 Priya (Aerospace Flight Trajectory Engineer - मिशन इंजीनियर)",
                "🧑 Aarav (Mission Telemetry Controller - कंट्रोलर)"
            ]
            wardrobes = {
                "DR. VIKRAM": "Crisp light-blue formal shirt with official ISRO project ID lanyard and security badge.",
                "PRIYA": "Smart-casual aerospace project blazer with communication headset and telemetry badge.",
                "AARAV": "Technical operations polo shirt with mission lanyard.",
            }
            props = [f"ISRO {subject} mission telemetry tablet", "orbital trajectory calculation dossier", "telemetry headset"]
            sfx = "Telemetry Beeps + Countdown Echo"
            domain = "space_science"

        # 2. Aviation / Airlines / Flight / Airport / Aircraft / DGCA
        elif any(k in combined for k in ["flight", "airline", "airport", "pilot", "dgca", "aircraft", "runway", "विमान", "एयरपोर्ट", "उड़ान", "हवाई"]):
            setting = (
                f"Modern international airport departure terminal and flight dispatch lounge. "
                f"Very fast-paced transit action to fit the 10-second limit." if is_fast else
                f"Modern international airport departure terminal and flight dispatch lounge. "
                f"Panoramic glass windows overlooking the runway tarmac, flight departure screens, and passenger boarding gate."
            )
            personas_2 = [
                "✈️ Captain Rajesh (Senior Commercial Airline Pilot - मुख्य पायलट)",
                "👩 Priya (Airport Duty Operations Manager - एयरपोर्ट प्रबंधक)"
            ]
            personas_3 = [
                "✈️ Captain Rajesh (Senior Commercial Airline Pilot - मुख्य पायलट)",
                "👩 Priya (Airport Duty Operations Manager - एयरपोर्ट प्रबंधक)",
                "🧑 Rohan (Stranded Passenger / Traveler - यात्री)"
            ]
            wardrobes = {
                "CAPTAIN RAJESH": "Crisp white pilot uniform shirt with four gold shoulder epaulets and aviation necktie.",
                "PRIYA": "High-visibility fluorescent operations vest over formal airline customer service blazer.",
                "ROHAN": "Casual traveler jacket with shoulder backpack and boarding pass in hand.",
            }
            props = ["flight manifest clipboard", "boarding pass scanner", "aviation walkie-talkie"]
            sfx = "Jet Engine Whine + Airport Chime Announcement"
            domain = "aviation"

        # 3. Railways / Trains / Metro / Vande Bharat / Loco Pilot / Station
        elif any(k in combined for k in ["railway", "train", "metro", "vande bharat", "station", "loco", "track", "रेलवे", "ट्रेन", "स्टेशन", "वंदे भारत", "लोको"]):
            setting = (
                f"Zonal railway locomotive dispatch room and digital signaling console. "
                f"Fast-paced signaling action to fit the 10-second limit." if is_fast else
                f"Zonal railway locomotive dispatch room and digital signaling console. "
                f"Digital track line status consoles, railway dispatch schedule boards, and radio communications."
            )
            personas_2 = [
                "🚂 Sharma Ji (Senior Loco Pilot / Safety Officer - वरिष्ठ लोको पायलट)",
                "🧑 Kabir (Railway Signaling Technician - रेलवे तकनीशियन)"
            ]
            personas_3 = [
                "🚂 Sharma Ji (Senior Loco Pilot / Safety Officer - वरिष्ठ लोको पायलट)",
                "🧑 Kabir (Railway Signaling Technician - रेलवे तकनीशियन)",
                "👩 Sunita (Station Master - स्टेशन मास्टर)"
            ]
            wardrobes = {
                "SHARMA JI": "Khaki railway service uniform with brass zonal badge and service cap.",
                "KABIR": "Bright orange reflective railway safety jacket with protective helmet.",
                "SUNITA": "Formal white station master coat with brass lapel pin.",
            }
            props = ["railway signaling tablet", "two-way railway handheld radio", "green safety signal flag"]
            sfx = "Train Horn Echo + Rail Track Clatter"
            domain = "railways"

        # 4. Gold / Silver / Bullion / Jewellery / Zaveri Bazaar
        elif any(k in combined for k in ["gold", "silver", "jewellery", "bullion", "zaveri", "carat", "सोना", "चांदी", "सर्राफा", "गहने", "ज्वैलरी"]):
            setting = (
                f"A high-end bullion showroom and traditional gold trade counter. "
                f"Snappy market excitement to fit the 10-second limit." if is_fast else
                f"A high-end bullion showroom and traditional gold trade counter. "
                f"Velvet display trays, digital carat weighing scale, wall-mounted bullion market tickers, and glass counters."
            )
            personas_2 = [
                "👑 Seth Radheshyam (Senior Bullion Merchant - सर्राफा व्यापारी)",
                "🧑 Rajesh (Gold Investor / Retail Buyer - ग्राहक / निवेशक)"
            ]
            personas_3 = [
                "👑 Seth Radheshyam (Senior Bullion Merchant - सर्राफा व्यापारी)",
                "🧑 Rajesh (Gold Investor / Retail Buyer - ग्राहक / निवेशक)",
                "👩 Sunita (Family Buyer - खरीदार महिला)"
            ]
            wardrobes = {
                "SETH RADHESHYAM": "Fine silk kurta with tailored Nehru vest and gold watch chain.",
                "RAJESH": "Smart-casual collared shirt and trousers.",
                "SUNITA": "Traditional elegant saree with gold bangles.",
            }
            props = ["digital carat weighing scale", "velvet jewellery display tray", "jewellery inspection loupe"]
            sfx = "Gold Coin Chime + Velvet Tray Tap"
            domain = "bullion_jewellery"

        # 5. Sports / Cricket / Stadium / Athletes / Tournament / Trophy
        elif any(k in combined for k in ["cricket", "ipl", "stadium", "match", "tournament", "trophy", "player", "athlete", "मैच", "क्रिकेट", "स्टेडियम", "खिलाड़ी", "खेल"]):
            setting = (
                f"Cricket stadium team pavilion and press briefing box. "
                f"High-voltage sports adrenaline to fit the 10-second limit." if is_fast else
                f"Cricket stadium team pavilion and press briefing box. "
                f"Locker benches, sports gear, floodlight glow through glass windows, and team tactical whiteboards."
            )
            personas_2 = [
                "🏏 Coach Sharma (Veteran Cricket Coach - वरिष्ठ कोच)",
                "🧑 Aarav (National Team All-Rounder - युवा खिलाड़ी)"
            ]
            personas_3 = [
                "🏏 Coach Sharma (Veteran Cricket Coach - वरिष्ठ कोच)",
                "🧑 Aarav (National Team All-Rounder - युवा खिलाड़ी)",
                "🎙️ Neha (Sports Commentator - स्पोर्ट्स एंकर)"
            ]
            wardrobes = {
                "COACH SHARMA": "Team athletic track jacket with stopwatch whistle around neck.",
                "AARAV": "Official team training jersey and athletic shorts.",
                "NEHA": "Smart-casual blazer with handheld broadcast microphone.",
            }
            props = ["cricket bat", "leather cricket ball", "team tactical strategy whiteboard marker"]
            sfx = "Stadium Crowd Roar + Bat Leather Strike"
            domain = "sports"

        # 6. Environment / Air Pollution / Smog / Climate / AQI
        elif any(k in combined for k in ["pollution", "smog", "aqi", "air quality", "environment", "climate", "smog tower", "प्रदूषण", "स्मॉग", "हवा", "पर्यावरण"]):
            setting = (
                f"City environmental monitoring control tower and air analysis lab. "
                f"Urgent ecological discussion to fit the 10-second limit." if is_fast else
                f"City environmental monitoring control tower and air analysis lab. "
                f"Digital AQI hazard index monitors flashing red, air filtration particulate gauges, and city smog horizon view."
            )
            personas_2 = [
                "🌱 Dr. Farhan (Senior Environmental Scientist - पर्यावरण वैज्ञानिक)",
                "👩 Ananya (Clean Air Citizen Activist - सामाजिक कार्यकर्ता)"
            ]
            personas_3 = [
                "🌱 Dr. Farhan (Senior Environmental Scientist - पर्यावरण वैज्ञानिक)",
                "👩 Ananya (Clean Air Citizen Activist - सामाजिक कार्यकर्ता)",
                "🧑 Rohan (Daily Commuter - आम नागरिक)"
            ]
            wardrobes = {
                "DR. FARHAN": "White laboratory coat over formal shirt with digital AQI sensor badge.",
                "ANANYA": "Cotton kurti with an N95 anti-pollution mask hanging around neck.",
                "ROHAN": "Everyday street casual wear with protective pollution bandana.",
            }
            props = ["handheld digital AQI air monitor", "smog particulate filter chart"]
            sfx = "Air Sensor Alert Beep + Traffic Hum"
            domain = "environment"

        # 7. Defence / Military / Armed Forces / Border
        elif any(k in combined for k in ["army", "defence", "defense", "military", "soldier", "border", "सेना", "फौज", "जवान", "सैन्य"]):
            setting = (
                f"Border operational observation post and tactical communications bunker. "
                f"Intense tactical focus to fit the 10-second limit." if is_fast else
                f"Border operational observation post and tactical communications bunker. "
                f"Camouflage sandbags, tactical topographical map tables, radio communications consoles, and mountain terrain view."
            )
            personas_2 = [
                "🎖️ Major Vikram (Border Regiment Officer - मेजर विक्रम)",
                "🧑 Subedar Rajesh (Tactical Communications Operator - सूबेदार)"
            ]
            personas_3 = [
                "🎖️ Major Vikram (Border Regiment Officer - मेजर विक्रम)",
                "🧑 Subedar Rajesh (Tactical Communications Operator - सूबेदार)",
                "🧑 Sepoy Aarav (Field Scout - स्काउट जवान)"
            ]
            wardrobes = {
                "MAJOR VIKRAM": "Olive-green camouflage combat fatigues with regiment crest and rank insignias.",
                "SUBEDAR RAJESH": "Tactical communications vest with radio headset and service badge.",
                "SEPOY AARAV": "Full tactical field gear with helmet.",
            }
            props = ["tactical terrain map", "military field binoculars", "ruggedized two-way radio"]
            sfx = "Radio Static Squelch + Wind Gust Whistle"
            domain = "defence"

        # 8. Real Estate / Housing / Infrastructure / Builders
        elif any(k in combined for k in ["builder", "flats", "housing", "rera", "apartment", "society", "सोसाइटी", "बिल्डर", "फ्लैट", "रियल एस्टेट"]):
            setting = (
                f"High-rise construction site project cabin and architectural blueprint lounge. "
                f"Fast-paced property discussion to fit the 10-second limit." if is_fast else
                f"High-rise construction site project cabin and architectural blueprint lounge. "
                f"Large architectural 3D project models, rolled floor plans, yellow safety helmets, and concrete tower view."
            )
            personas_2 = [
                "🏢 Builder Singhal (Real Estate Project Director - प्रोजेक्ट डायरेक्टर)",
                "🧑 Rajesh (Homebuyer / Citizen - फ्लैट खरीदार)"
            ]
            personas_3 = [
                "🏢 Builder Singhal (Real Estate Project Director - प्रोजेक्ट डायरेक्टर)",
                "🧑 Rajesh (Homebuyer / Citizen - फ्लैट खरीदार)",
                "👩 Sunita (Co-Owner / Buyer - सह-खरीदार)"
            ]
            wardrobes = {
                "BUILDER SINGHAL": "Crisp linen shirt with yellow project hardhat and site boots.",
                "RAJESH": "Smart-casual polo shirt holding home loan file folder.",
                "SUNITA": "Casual kurti reviewing apartment floor layout.",
            }
            props = ["architectural site floor plan blueprint", "yellow safety hardhat", "allotment agreement file"]
            sfx = "Blueprint Paper Rustle + Distant Construction Sound"
            domain = "real_estate"

        # 9. GENERAL DYNAMIC IMAGINATION (Infinite Fallback for Any Unlisted Topic!)
        else:
            setting = (
                f"A dedicated professional operational center focused on {subject}. "
                f"Fast-paced focused energy to fit the 10-second limit." if is_fast else
                f"A dedicated professional operational center focused on {subject}. "
                f"Modern collaborative workspace with informational monitors, reference dossiers, and active workflow."
            )
            personas_2 = [
                f"🔬 Dr. Vikram (Lead Subject Specialist - {subject} विशेषज्ञ)",
                f"🧑 Rajesh (Industry Stakeholder / Citizen - हितधारक / नागरिक)"
            ]
            personas_3 = [
                f"🔬 Dr. Vikram (Lead Subject Specialist - {subject} विशेषज्ञ)",
                f"🧑 Rajesh (Industry Stakeholder / Citizen - हितधारक / नागरिक)",
                f"👩 Priya (Operational Analyst - विश्लेषक)"
            ]
            wardrobes = {
                "DR. VIKRAM": f"Smart-casual formal shirt with {subject} project badge and pen in front pocket.",
                "SPECIALIST": f"Smart-casual formal shirt with {subject} project badge and pen in front pocket.",
                "RAJESH": "Everyday collared casual shirt and trousers, holding relevant review documents.",
                "STAKEHOLDER": "Everyday collared casual shirt and trousers, holding relevant review documents.",
                "PRIYA": "Formal Indian cotton kurti with office ID badge.",
            }
            props = [f"{subject} analysis dossier", "digital tablet computer", "official summary brief"]
            sfx = "Document Folder Rustle + Focused Keyboard Clatter"
            domain = f"imagined_{subject.lower().replace(' ', '_')}"

        selected_personas = personas_3 if character_count >= 3 else personas_2
        if character_count == 1:
            selected_personas = [selected_personas[0]]

        return {
            "domain": domain,
            "setting": setting,
            "setting_detail": setting,
            "personas": selected_personas,
            "wardrobes": wardrobes,
            "props": props,
            "sfx": sfx,
        }

    def imagine_pair_from_data(self, topic_or_script: str) -> Tuple[str, str]:
        """Imagine and return an authentic 2-character persona pair synthesized from current data."""
        res = self.imagine_from_current_data(news_topic=topic_or_script, character_count=2)
        p = res["personas"]
        return (p[0], p[1] if len(p) > 1 else p[0])

    def imagine_solo_from_data(self, topic_or_script: str) -> str:
        """Imagine and return a solo persona synthesized from current data."""
        res = self.imagine_from_current_data(news_topic=topic_or_script, character_count=1)
        return res["personas"][0]

    def imagine_trio_from_data(self, topic_or_script: str) -> Tuple[str, str, str]:
        """Imagine and return a 3-character persona trio synthesized from current data."""
        res = self.imagine_from_current_data(news_topic=topic_or_script, character_count=3)
        p = res["personas"]
        return (p[0], p[1] if len(p) > 1 else p[0], p[2] if len(p) > 2 else p[0])


contextual_selector = ContextualSceneCharacterSelectorAgent()
