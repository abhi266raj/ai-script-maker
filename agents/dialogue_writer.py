"""Agent 3: Dialogue & Narration Scriptwriter Agent."""

import re
import random
import logging
from typing import Optional, List, Dict, Any, Tuple
from agents.base import BaseAgent
from core.models import NewsVerificationReport
from core.metrics import get_duration_budget, count_words
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

logger = logging.getLogger(__name__)

DIALOGUE_INSTRUCTIONS = load_prompt("dialogue_writer/prompt.md")


POLITICAL_NAMES_BLACKLIST = {
    "rahul", "modi", "narendra", "kejriwal", "gandhi", "amit shah", "amit",
    "yogi", "adityanath", "sonia", "priyanka", "mamata", "stalin", "pawar",
    "fadnavis", "shinde", "thackeray", "nitish", "lalu", "tejaswi"
}


def sanitize_persona_name(name: str) -> str:
    """Ensure fictional characters never use politician names to prevent policy/misinformation flags."""
    if not name:
        return ""
    t = name
    for pol in POLITICAL_NAMES_BLACKLIST:
        if re.search(rf"\b{pol}\b", t, re.IGNORECASE):
            t = re.sub(rf"\b{pol}\b", "Rohan", t, flags=re.IGNORECASE)
            t = t.replace("राहुल", "रोहन").replace("अमित", "आरव").replace("मोदी", "कबीर")
    return t


def get_sentence_guidance(duration_sec: int, rec_w: int, max_w: int, tone: str = "", angle: str = "") -> str:
    """Return explicit structural sentence advice calibrated to target reel duration with Fun-First support."""
    combined = f"{tone} {angle}".lower()
    is_funny = any(w in combined for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी", "मजाकिया", "roast", "relatable"])

    if duration_sec <= 8:
        return (
            f"TARGET STRUCTURE: Exactly ONE punchy spoken Hindi sentence totaling ~{rec_w} words (MAX: {max_w}w).\n"
            f"- State the core shock/update immediately and conclude. Do NOT use any introductory phrases."
        )
    elif duration_sec <= 15:
        if is_funny:
            return (
                f"TARGET STRUCTURE: Exactly TWO crisp spoken Hindi sentences totaling ~{rec_w} words (MAX: {max_w}w).\n"
                f"- Sentence 1 (FUN / SITUATION FIRST): A relatable comedic hook or personal blunder (NOT dry news yet!).\n"
                f"- Sentence 2 (NEWS REVEAL & PUNCHLINE): The news fact reveal that caused it, concluding with a witty punchline."
            )
        return (
            f"TARGET STRUCTURE: Exactly TWO crisp spoken Hindi sentences totaling ~{rec_w} words (MAX: {max_w}w).\n"
            f"- Sentence 1: The core hook or breaking development.\n"
            f"- Sentence 2: The takeaway or punchline with impactful conclusion."
        )
    elif duration_sec <= 30:
        if is_funny:
            return (
                f"TARGET STRUCTURE: Exactly 3 to 4 concise spoken Hindi sentences totaling ~{rec_w} words (MAX: {max_w}w).\n"
                f"- Sentence 1 (FUN FIRST HOOK): Everyday comedic situation, confusion, or funny reaction hook.\n"
                f"- Sentence 2-3 (NEWS REVEAL): Unveiling the verified news facts and context explaining what happened.\n"
                f"- Sentence 4 (PAYOFF): Witty punchline and conclusion tying it together."
            )
        return (
            f"TARGET STRUCTURE: Exactly 3 to 4 concise spoken Hindi sentences totaling ~{rec_w} words (MAX: {max_w}w).\n"
            f"- Sentence 1: Immediate hook context.\n"
            f"- Sentence 2-3: Core facts, relatable impact, or cultural significance.\n"
            f"- Sentence 4: Engaging closing takeaway."
        )
    elif duration_sec <= 60:
        return (
            f"TARGET STRUCTURE: 5 to 7 spoken Hindi sentences totaling ~{rec_w} words (MAX: {max_w}w).\n"
            f"- Deliver informative pacing with natural cadence."
        )
    else:
        return (
            f"TARGET STRUCTURE: 8 to 12 spoken Hindi sentences totaling ~{rec_w} words (MAX: {max_w}w)."
        )


def strip_commenting_and_cta(text: str) -> str:
    """Purge social media commenting, subscriber calls, and meta-CTAs from dialogue."""
    if not text:
        return ""
    t = text
    patterns = [
        r"(?:नीचे\s*)?कमेंट\s*(?:में\s*(?:बताएं|बताओ|लिखें|लिखो)|करें|करो|सेक्शन\s*में\s*(?:बताएं|बताओ))[\s।!?]*",
        r"(?:आपकी\s*क्या\s*राय\s*है\s*[,।]?\s*)?कमेंट\s*(?:करें|करके\s*बताएं|में\s*बताएं)[\s।!?]*",
        r"(?:लाइक\s*(?:और|व)\s*)?शेयर\s*(?:करें|करो|करना\s*मत\s*भूलना)[\s।!?]*",
        r"फॉलो\s*(?:करें|करो|करना\s*मत\s*भूलना)[\s।!?]*",
        r"सब्सक्राइब\s*(?:करें|करो)[\s।!?]*",
        r"(?:comment\s*below|share\s*your\s*thoughts|like\s*and\s*subscribe)[\s।!?]*",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.IGNORECASE)
    t = " ".join(t.split())
    return t.strip()


def clean_hindi_dialogue(text: str) -> str:
    """Strip out stage directions, script markers, markdown tags, and social media commenting."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^(NARRATION|DIALOGUE|VOICEOVER|SCRIPT\s*\d*)\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\[.*?\]", "", t)
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"\*\*.*?\*\*", "", t)
    t = re.sub(r"[-*_~#]{2,}", "", t)
    t = re.sub(r"^[\"'\s\-_*~#]+|[\"'\s\-_*~#]+$", "", t.strip())
    t = strip_commenting_and_cta(t)
    t = " ".join(t.split())
    return t.strip()


def smart_trim_dialogue(text: str, max_words: int, rec_words: int, cta: str = "") -> str:
    """Intelligently trim dialogue to fit max_words while preserving complete sentences without injecting commenting or CTA."""
    cleaned = strip_commenting_and_cta(text)
    if count_words(cleaned) <= max_words:
        return cleaned

    words = cleaned.split()
    truncated_base = " ".join(words[:max_words])
    
    # Find the latest sentence boundary (। , ! , ?) within the truncated word limit
    last_punct_idx = -1
    for delim in ["।", "!", "?"]:
        pos = truncated_base.rfind(delim)
        if pos > last_punct_idx:
            last_punct_idx = pos

    # Only cut back to punctuation if it retains at least 50% of max_words
    if last_punct_idx > 0 and count_words(truncated_base[:last_punct_idx + 1]) >= int(max_words * 0.5):
        truncated_base = truncated_base[:last_punct_idx + 1]
    elif not truncated_base.endswith(("।", "!", "?", "...", "…")):
        truncated_base += "..."

    return truncated_base.strip()


class ScriptDialogue(str):
    """
    Subclass of str that behaves as a standard spoken dialogue string,
    while carrying structured scene character turns in `scene_lines`.
    """
    scene_lines: List[Dict[str, str]]

    def __new__(cls, narration: str, scene_lines: Optional[List[Dict[str, str]]] = None):
        obj = super().__new__(cls, narration)
        obj.scene_lines = scene_lines or []
        return obj


RELATIONSHIP_PAIRS = [
    # Colleagues / Office Co-workers
    ("👩 Priya (Senior Office Colleague / Colleague 1 - सीनियर कलीग)", "🧑 Rohan (Office Colleague / Colleague 2 - जूनियर कलीग)"),
    # Close Friends / Tapri Buddies
    ("👩 Ananya (College Friend 1 - कॉलेज दोस्त)", "🧑 Vikram (Street-Smart Friend 2 - पक्का यार)"),
    # Husband & Wife (पति-पत्नी)
    ("👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)", "🧑 Rajesh (Husband / Salaried Man - नौकरीपेशा पति)"),
    # Father & Son (पिता-पुत्र)
    ("👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)", "🧑 Aarav (Gen-Z Son - आधुनिक बेटा)"),
    # Mother & Son (माँ-बेटा)
    ("👩 Meera (Caring Mother - ममतामयी माँ)", "🧑 Kabir (Career-Minded Son - महत्वाकांक्षी बेटा)"),
    # Neighbors (पड़ोसी)
    ("🧑 Verma Ji (Curious Neighbor - जिज्ञासु पड़ोसी)", "🧑 Gupta Ji (Opinionated Neighbor - रायचंद पड़ोसी)"),
]

RELATIONSHIP_TRIOS = [
    # Family Trio: Father, Mother, Son
    (
        "👴 Sharma Ji (Traditional Father - पिता)",
        "👩 Sunita (Pragmatic Mother - माँ)",
        "🧑 Aarav (Gen-Z Son - बेटा)",
    ),
    # Office Colleagues Trio: Manager & 2 Team Members
    (
        "👔 Manager Mehra (Corporate Boss - मैनेजर)",
        "👩 Priya (Senior Colleague - कलीग 1)",
        "🧑 Rohan (Junior Colleague - कलीग 2)",
    ),
    # 3 Close Friends
    (
        "👩 Ananya (College Friend 1 - दोस्त 1)",
        "🧑 Vikram (Street-smart Friend 2 - दोस्त 2)",
        "🧑 Rohan (Witty Friend 3 - दोस्त 3)",
    ),
]

DIVERSE_SOCIOECONOMIC_PAIRS = [
    # Rich & Working-Class Contrast
    ("👩 Priya (Rich Tech Founder / Friend 1 - अमीर टेक फाउंडर)", "🧑 Rohan (Working-Class Auto Driver / Friend 2 - मेहनती ऑटो चालक)"),
    # Police & Gig Worker / Common Citizen
    ("👮 Sub-Inspector Sunita (Traffic Police / Friend 1 - पुलिस दरोगा)", "🛵 Rohan (Gig Delivery Partner / Friend 2 - डिलीवरी राइडर)"),
    # Local Fictional Politician / Ward Corporator & Tapri Vendor
    ("🏛️ Netaji Tiwari (Ward Corporator / Friend 1 - स्थानीय पार्षद)", "☕ Rohan (Street Chai Tapri Owner / Friend 2 - टपरी वाला)"),
    # Government Servant (Babu) & Young Citizen / Student
    ("👔 Sharma Ji (Government Clerk / Friend 1 - सरकारी बाबू)", "🧑 Rohan (UPSC Aspirant / Friend 2 - छात्र)"),
    # SIR / Special Investment Region / Government Officer & Industrial Investor
    ("👔 Sharma Ji (Government Administrative Officer / Friend 1 - वरिष्ठ अधिकारी)", "🧑 Rajesh (Industrial Investor / Friend 2 - उद्यमी / भूस्वामी)"),
    # Corporate Executive & Grassroots Citizen
    ("💼 Ananya (Corporate Banker / Friend 1 - कॉर्पोरेट एग्जीक्यूटिव)", "🧑 Kabir (Street-Smart Youth / Friend 2 - देसी युवा)"),
    # High Court Advocate & Small Trader
    ("⚖️ Advocate Verma (High Court Lawyer / Friend 1 - वकील साहब)", "🛒 Mohan (Local Kirana Trader / Friend 2 - दुकानदार)"),
    # Doctor & Daily Wage Worker
    ("🩺 Dr. Rajesh (Government Hospital Doctor / Friend 1 - डॉक्टर साहब)", "👷 Ramesh (Construction Worker / Friend 2 - दिहाड़ी मजदूर)"),
    # School Principal & Vegetable Vendor
    ("📚 Master Ji (Government School Teacher / Friend 1 - सरकारी मास्टर जी)", "🥦 Rohan (Street Sabziwala / Friend 2 - सब्जी विक्रेता)"),
    # Real Estate Investor & Auto Rickshaw Driver
    ("🏢 Seth Radheshyam (Property Investor / Friend 1 - अमीर व्यापारी)", "🛺 Rohan (Auto Rickshaw Driver / Friend 2 - ऑटो चालक)"),
    # Rural & City Contrast
    ("🌾 Sarpanch Harpal (Village Pradhan / Friend 1 - ग्राम प्रधान)", "🧑 Rohan (City-Returned Youth / Friend 2 - युवा)"),
    # Everyday Relatable Companions
    ("👩 Priya / Friend 1 (प्रिया - दोस्त 1)", "🧑 Rohan / Friend 2 (रोहन - दोस्त 2)"),
    # Relationship Pairings (Colleagues, Friends, Husband-Wife, Father-Son, Neighbors)
    *RELATIONSHIP_PAIRS,
]

DIVERSE_SOCIOECONOMIC_TRIOS = [
    (
        "🏛️ Netaji Tiwari (Local Corporator / Friend 1 - स्थानीय पार्षद)",
        "🧑 Rohan (Auto Driver / Friend 2 - ऑटो चालक)",
        "☕ Mohan (Chai Tapri Owner / Elder - टपरी वाला बुजुर्ग)",
    ),
    (
        "💼 Ananya (Rich Corporate VP / Friend 1 - अमीर बैंकर)",
        "🛵 Kabir (Delivery Rider / Friend 2 - डिलीवरी पार्टनर)",
        "👮 Inspector Vikram (Police Sub-Inspector / Elder - पुलिस दरोगा)",
    ),
    (
        "👔 Sharma Ji (Government Clerk / Friend 1 - सरकारी बाबू)",
        "👩 Priya (Young Citizen / Friend 2 - नागरिक)",
        "👴 Chacha Ji / Elder (चाचा जी - अनुभवी बुजुर्ग)",
    ),
    (
        "🩺 Dr. Rajesh (Hospital Doctor / Friend 1 - वरिष्ठ चिकित्सक)",
        "🧑 Rohan (Medical Representative / Friend 2 - युवा प्रतिनिधि)",
        "👵 Amma (Elder Citizen / Witness - बुजुर्ग महिला)",
    ),
    (
        "⚖️ Advocate Verma (Senior Lawyer / Friend 1 - वरिष्ठ अधिवक्ता)",
        "👔 Clerk Tripathi (Court Babu / Friend 2 - पेशकार बाबू)",
        "🧑 Kabir (Common Citizen / Friend 3 - आम नागरिक)",
    ),
    # Relational Trios
    *RELATIONSHIP_TRIOS,
]



def select_script_grounded_solo(topic_or_script: str) -> str:
    """Select the best-fitting solo persona grounded in the script's topic domain."""
    text = (topic_or_script or "").lower()
    if any(k in text for k in ["police", "दरोगा", "ट्रैफिक", "traffic", "challan", "fir", "arrest"]):
        return "😂 Desi Creator Vikram (Beat Police Constable / Creator - देसी क्रिएटर विक्रम)"
    if any(k in text for k in ["babu", "बाबू", "clerk", "सरकारी", "upsc", "pension"]):
        return "😂 Desi Creator Sharma Ji (Government Clerk / Babu - देसी क्रिएटर सरकारी बाबू)"
    if any(k in text for k in ["election", "नेता", "netaji", "पार्षद", "corporator", "party", "vote"]):
        return "😂 Desi Creator Netaji Tiwari (Local Corporator - देसी क्रिएटर पार्षद)"
    if any(k in text for k in ["chai", "चाय", "tapri", "टपरी", "पोहा", "poha"]):
        return "😂 Desi Creator Mohan (Chai Tapri Owner - देसी क्रिएटर टपरी वाला)"
    if any(k in text for k in ["auto", "ऑटो", "रिक्शा", "cab", "driver"]):
        return "😂 Desi Creator Rohan (Outspoken Auto Driver / Creator - देसी क्रिएटर रोहन)"

    # Dynamic Imagination from current data if topic is provided
    if text.strip():
        from agents.contextual_selector import contextual_selector
        return contextual_selector.imagine_solo_from_data(topic_or_script)
    return "😂 Desi Creator Priya (Tech Professional / Creator - देसी क्रिएटर प्रिया)"


def select_script_grounded_pair(topic_or_script: str) -> Tuple[str, str]:
    """Select the best-fitting socioeconomic pair or relationship pair grounded in the script's topic domain."""
    text = (topic_or_script or "").lower()

    # 0. Interpersonal Relationships (Husband & Wife, Father & Son, Colleagues, Friends, Neighbors)
    if any(k in text for k in ["husband", "wife", "patni", "pati", "marriage", "shaadi", "शादी", "पत्नी", "पति", "household", "ration", "gas", "cylinder", "महंगाई", "घरेलू", "सब्जी", "दाल"]):
        return RELATIONSHIP_PAIRS[2]  # Sunita (Wife) & Rajesh (Husband)
    if any(k in text for k in ["father", "son", "baap", "beta", "generation", "career", "study", "coaching", "डिग्री", "नौकरी", "पिता", "बेटा", "कोचिंग"]):
        return RELATIONSHIP_PAIRS[3]  # Sharma Ji (Father) & Aarav (Son)
    if any(k in text for k in ["colleague", "coworker", "appraisal", "cubicle", "कलीग", "सहकर्मी", "बॉस", "boss", "promotion"]):
        return RELATIONSHIP_PAIRS[0]  # Priya (Senior Colleague) & Rohan (Junior Colleague)
    if any(k in text for k in ["neighbor", "neighbour", "padosi", "पड़ोसी", "mohalla", "मोहल्ला", "society", "सोसाइटी", "colony", "कॉलोनी", "parking", "gossip"]):
        return RELATIONSHIP_PAIRS[5]  # Verma Ji & Gupta Ji (Neighbors)
    if any(k in text for k in ["friend", "dost", "yaar", "दोस्त", "यार", "tapri"]):
        return RELATIONSHIP_PAIRS[1]  # Ananya & Vikram (Friends)

    # 0.5 SIR / Special Investment Region / Dholera / Industrial Corridor / Government Administrative Office
    if any(k in text for k in ["sir", "dholera", "investment region", "special investment", "industrial corridor", "collectorate", "secretariat", "mantralaya", "land acquisition", "land registry", "सरकारी दफ्तर", "कलेक्टर", "सचिवालय"]):
        return ("👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)", "🧑 Rajesh (Industrial Investor / Local Landowner - उद्यमी / नागरिक)")

    # 1. Court / Legal / Justice / Lawyer / High Court / Supreme Court / Bail
    if any(k in text for k in ["court", "कोर्ट", "कानून", "judge", "vakeel", "lawyer", "वकील", "मुकदमा", "justice", "फैसला", "पीठ", "bail", "बेल", "legal", "याचिका", "plea"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[6]  # High Court Lawyer vs Kirana Trader


    # 2. Police / Law Enforcement / Traffic / Challan / FIR / Crime / Jail
    if any(k in text for k in ["police", "दरोगा", "थाना", "गिरफ्तार", "arrest", "fir", "ट्रैफिक", "traffic", "challan", "चालान", "crime", "जेल", "scam"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[1]  # Police Sub-Inspector vs Gig Delivery Partner

    # 3. Politics / Election / Netaji / Corporator / Municipal / Government / Scheme
    if any(k in text for k in ["election", "चुनाव", "नेता", "netaji", "पार्षद", "corporator", "party", "पार्टी", "सरकार", "government", "mantri", "मंत्री", "योजना", "scheme", "नगर निगम"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[2]  # Ward Corporator Netaji vs Chai Tapri Owner

    # 4. Government Servant / Babu / Clerk / Exam / UPSC / Pension
    if any(k in text for k in ["babu", "बाबू", "clerk", "सरकारी बाबू", "upsc", "pension", "दफ्तर", "सरकारी"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[3]  # Government Clerk Sharma Ji vs UPSC Aspirant

    # 5. Tech / Corporate / IT / Office / Work From Office / WFO / AI / Startup / Software / Laptop
    if any(k in text for k in ["wfo", "rto", "office", "ऑफिस", "tech", "ai", "startup", "software", "बायोमेट्रिक", "biometric", "laptop", "कंप्यूटर", "developer", "engineer", "corporate"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[0]  # Rich Tech Founder vs Working-Class Auto Driver

    # 6. Corporate Finance / Banking / Investment / Stock / Market
    if any(k in text for k in ["bank", "बैंक", "invest", "share", "शेयर", "crypto", "fund", "finance", "करोड़"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[5]  # Corporate Banker vs Street-Smart Youth

    # 7. Healthcare / Hospital / Doctor / Medical / Patient / Medicine / Clinic
    if any(k in text for k in ["hospital", "अस्पताल", "doctor", "डॉक्टर", "nurse", "medicine", "दवा", "मरीज", "patient", "health", "स्वास्थ्य", "बीमारी", "clinic"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[7]  # Hospital Doctor vs Construction Worker

    # 8. Education / School / Teacher / Master Ji / College / Student / Exam
    if any(k in text for k in ["school", "स्कूल", "college", "कॉलेज", "exam", "परीक्षा", "student", "छात्र", "teacher", "मास्टर", "university", "cbse"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[8]  # School Teacher vs Vegetable Vendor

    # 9. Real Estate / Property / Investor / Auto / Rickshaw
    if any(k in text for k in ["property", "जमीन", "मकान", "builder", "auto", "ऑटो", "rickshaw", "किराया"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[9]  # Property Investor vs Auto Rickshaw Driver

    # 10. Rural / Village / Agriculture / Farmer / Sarpanch / Panchayat / Mandi
    if any(k in text for k in ["village", "गाँव", "गांव", "farmer", "किसान", "kheti", "खेती", "mandi", "मंडी", "panchayat", "sarpanch", "सरपंच", "प्रधान"]):
        return DIVERSE_SOCIOECONOMIC_PAIRS[10]  # Village Pradhan vs City-Returned Youth

    # Dynamic Imagination Fallback: If no predefined pair matches, imagine a brand new pair from current data!
    if text.strip():
        from agents.contextual_selector import contextual_selector
        return contextual_selector.imagine_pair_from_data(topic_or_script)

    # Default fallback: random choice across all diverse pairs
    return random.choice(DIVERSE_SOCIOECONOMIC_PAIRS)


def select_script_grounded_trio(topic_or_script: str) -> Tuple[str, str, str]:
    """Select the best-fitting socioeconomic or relationship trio grounded in the script's topic domain."""
    text = (topic_or_script or "").lower()

    # Relational trios
    if any(k in text for k in ["family", "parivar", "परिवार", "father", "mother", "son", "माता", "पिता", "बेटा", "ghar"]):
        return RELATIONSHIP_TRIOS[0]  # Family Trio: Father, Mother, Son
    if any(k in text for k in ["office", "colleague", "boss", "manager", "सहकर्मी", "कलीग"]):
        return RELATIONSHIP_TRIOS[1]  # Office Trio: Manager, Colleague 1, Colleague 2
    if any(k in text for k in ["friend", "dost", "दोस्त", "यार", "tapri"]):
        return RELATIONSHIP_TRIOS[2]  # Friends Trio: Ananya, Vikram, Rohan

    # SIR / Government Planning Office Trio
    if any(k in text for k in ["sir", "dholera", "investment region", "special investment", "industrial corridor", "collectorate", "secretariat"]):
        return (
            "👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)",
            "🧑 Rajesh (Industrial Investor / Citizen - उद्यमी)",
            "👩 Priya (Land Planning Assistant - सहायक योजनाकार)"
        )

    if any(k in text for k in ["election", "नेता", "netaji", "पार्षद", "corporator", "party", "सरकार", "chai", "चाय"]):
        return DIVERSE_SOCIOECONOMIC_TRIOS[0]  # Netaji, Auto Driver, Chai Tapri Elder
    if any(k in text for k in ["police", "दरोगा", "tech", "corporate", "delivery", "राइडर"]):
        return DIVERSE_SOCIOECONOMIC_TRIOS[1]  # Corporate VP, Delivery Rider, Inspector
    if any(k in text for k in ["babu", "बाबू", "clerk", "सरकारी", "citizen", "पेंशन", "छात्र"]):
        return DIVERSE_SOCIOECONOMIC_TRIOS[2]  # Government Clerk, Citizen, Elder
    if any(k in text for k in ["hospital", "doctor", "डॉक्टर", "स्वास्थ्य", "दवा", "मरीज"]):
        return DIVERSE_SOCIOECONOMIC_TRIOS[3]  # Doctor, Med Rep, Amma
    if any(k in text for k in ["court", "कोर्ट", "वकील", "lawyer", "कानून", "जज"]):
        return DIVERSE_SOCIOECONOMIC_TRIOS[4]  # Advocate, Clerk Babu, Citizen

    # Dynamic Imagination Fallback: If no predefined trio matches, imagine a brand new trio from current data!
    if text.strip():
        from agents.contextual_selector import contextual_selector
        return contextual_selector.imagine_trio_from_data(topic_or_script)

    return random.choice(DIVERSE_SOCIOECONOMIC_TRIOS)


def format_sample_personas(personas: List[str], character_count: int) -> List[str]:
    """Ensure sample personas match requested character count with rich, sanitized tags."""
    if not personas:
        return []
    if character_count == 1:
        return [sanitize_persona_name(personas[0])]
    if character_count == 2:
        if len(personas) >= 2:
            return [sanitize_persona_name(personas[0]), sanitize_persona_name(personas[1])]
        first = personas[0]
        f_lower = first.lower()
        if "wife" in f_lower or "पत्नी" in f_lower or "homemaker" in f_lower:
            partner = "🧑 Rajesh (Husband / Salaried Man - नौकरीपेशा पति)"
        elif "husband" in f_lower or "पति" in f_lower:
            partner = "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)"
        elif "father" in f_lower or "पिता" in f_lower:
            partner = "🧑 Aarav (Gen-Z Son - आधुनिक बेटा)"
        elif "son" in f_lower or "बेटा" in f_lower:
            partner = "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)"
        elif "doctor" in f_lower or "डॉक्टर" in f_lower:
            partner = "🧑 Ramesh (Patient - मरीज)"
        elif "teacher" in f_lower or "मास्टर" in f_lower:
            partner = "🧑 Aarav (Student - छात्र)"
        elif "colleague" in f_lower or "कलीग" in f_lower:
            partner = "🧑 Rohan (Office Colleague / Colleague 2 - जूनियर कलीग)"
        else:
            partner = "🧑 Vikram (Street-Smart Friend 2 - पक्का यार)"
        return [sanitize_persona_name(first), sanitize_persona_name(partner)]
    if character_count >= 3:
        res = [sanitize_persona_name(p) for p in personas[:character_count]]
        while len(res) < character_count:
            res.append(sanitize_persona_name(f"👤 Character {len(res)+1} (साक्षी / साथी)"))
        return res
    return [sanitize_persona_name(p) for p in personas]


def format_speaker_names_to_personas(speaker_names: List[str], character_count: int) -> List[str]:
    """Map raw speaker names extracted from sample script to rich, properly tagged personas."""
    role_map = {
        "wife": "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
        "patni": "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
        "पत्नी": "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
        "husband": "🧑 Rajesh (Husband / Salaried Man - नौकरीपेशा पति)",
        "pati": "🧑 Rajesh (Husband / Salaried Man - नौकरीपेशा पति)",
        "पति": "🧑 Rajesh (Husband / Salaried Man - नौकरीपेशा पति)",
        "father": "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)",
        "baap": "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)",
        "pita": "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)",
        "पिता": "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)",
        "son": "🧑 Aarav (Gen-Z Son - आधुनिक बेटा)",
        "beta": "🧑 Aarav (Gen-Z Son - आधुनिक बेटा)",
        "बेटा": "🧑 Aarav (Gen-Z Son - आधुनिक बेटा)",
        "mother": "👩 Meera (Caring Mother - ममतामयी माँ)",
        "maa": "👩 Meera (Caring Mother - ममतामयी माँ)",
        "माँ": "👩 Meera (Caring Mother - ममतामयी माँ)",
        "daughter": "👩 Ananya (College Daughter - समझदार बेटी)",
        "beti": "👩 Ananya (College Daughter - समझदार बेटी)",
        "बेटी": "👩 Ananya (College Daughter - समझदार बेटी)",
        "colleague": "👩 Priya (Senior Office Colleague / Colleague 1 - सीनियर कलीग)",
        "coworker": "👩 Priya (Senior Office Colleague / Colleague 1 - सीनियर कलीग)",
        "कलीग": "👩 Priya (Senior Office Colleague / Colleague 1 - सीनियर कलीग)",
        "doctor": "🩺 Dr. Rajesh (Hospital Doctor - वरिष्ठ चिकित्सक)",
        "डॉक्टर": "🩺 Dr. Rajesh (Hospital Doctor - वरिष्ठ चिकित्सक)",
        "patient": "🧑 Ramesh (Patient - मरीज)",
        "मरीज": "🧑 Ramesh (Patient - मरीज)",
        "teacher": "📚 Master Ji (School Teacher - सरकारी शिक्षक)",
        "मास्टर": "📚 Master Ji (School Teacher - सरकारी शिक्षक)",
        "शिक्षक": "📚 Master Ji (School Teacher - सरकारी शिक्षक)",
        "student": "🧑 Aarav (Student - छात्र)",
        "छात्र": "🧑 Aarav (Student - छात्र)",
        "police": "👮 Sub-Inspector Sunita (Police Officer - पुलिस दरोगा)",
        "दरोगा": "👮 Sub-Inspector Sunita (Police Officer - पुलिस दरोगा)",
    }
    personas = []
    female_names = {"ananya", "priya", "sunita", "meera", "sneha", "pooja", "neha", "kavita", "shreya"}
    for idx, raw_name in enumerate(speaker_names):
        n_lower = raw_name.lower().strip()
        if n_lower in role_map:
            personas.append(role_map[n_lower])
        else:
            emoji = "👩" if any(f in n_lower for f in female_names) else "🧑"
            personas.append(f"{emoji} {raw_name.strip().title()} (Character {idx+1})")
    return format_sample_personas(personas, character_count)


def extract_sample_story_personas(sample_story: str, character_count: int = 2) -> Optional[List[str]]:
    """
    Extract and construct authentic character personas directly from a sample story or sample script.
    Follows sample story discrepancy precedence:
    1. Direct 'CHARACTERS & CLOTHING:' or 'CHARACTERS:' blocks.
    2. Explicit dialogue speaker headings (e.g. 'ANANYA: ...', 'VIKRAM: ...', 'WIFE: ...', 'HUSBAND: ...').
    3. Interpersonal relationships explicitly mentioned in narrative prose:
       (Husband & Wife, Father & Son, Mother & Son, Colleagues, Friends, Doctor & Patient, etc.).
    """
    if not sample_story or not sample_story.strip():
        return None

    raw_text = sample_story.strip()
    lower_text = raw_text.lower()

    # 1. Check for CHARACTERS & CLOTHING: or CHARACTERS: section
    m_chars = re.search(r"CHARACTERS(?:\s*&\s*CLOTHING)?\s*:(.*?)(?:\[Time|\n\s*\n\s*\[|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    if m_chars:
        char_lines = re.findall(r"(?:[⚬•\-\*]|\d+\.)?\s*([A-Za-z\u0900-\u097F\s/()\-]+?)\s*:\s*([^\n\r]+)", m_chars.group(1))
        extracted = []
        female_names = {"ananya", "priya", "sunita", "meera", "sneha", "pooja", "neha", "kavita", "shreya", "wife", "mother", "daughter"}
        for name, role in char_lines:
            c_name = sanitize_persona_name(name.strip())
            role_clean = role.strip()
            if c_name and c_name.lower() not in ["format", "scene detail", "audio", "camera", "time", "text overlay"]:
                emoji = "👩" if any(f in c_name.lower() or f in role_clean.lower() for f in female_names) else "🧑"
                extracted.append(f"{emoji} {c_name.title()} ({role_clean})")
        if extracted:
            return format_sample_personas(extracted, character_count)

    # 2. Check for explicit dialogue speaker cues (e.g., 'ANANYA: "..."', 'VIKRAM: "..."', 'Wife: "..."', 'पति: "..."')
    RESERVED_HEADERS = {
        "time", "camera", "camera focus & action", "audio/sfx", "audio", "sfx",
        "text overlay", "text overlay (optional)", "visual", "action", "scene", "scene detail",
        "characters & clothing", "format", "format requirement", "note", "hook", "angle", "title"
    }
    speaker_matches = re.findall(r"^(?:\[.*?\]\s*)?([A-Za-z\u0900-\u097F\s]{2,25})\s*:\s*[\"“']?([^\n\r]+)", raw_text, re.MULTILINE)
    detected_speakers = []
    seen = set()
    for spk, line in speaker_matches:
        spk_clean = spk.strip().title()
        spk_lower = spk_clean.lower()
        if spk_lower not in RESERVED_HEADERS and not any(h in spk_lower for h in ["camera", "audio", "overlay", "scene"]):
            if spk_lower not in seen:
                seen.add(spk_lower)
                detected_speakers.append(spk_clean)

    if detected_speakers:
        return format_speaker_names_to_personas(detected_speakers, character_count)

    # 3. Explicit relationship or role mentions in narrative prose
    # A. Husband & Wife / पति-पत्नी
    if any(k in lower_text for k in ["husband and wife", "husband & wife", "husband wife", "pati patni", "pati aur patni", "पति-पत्नी", "पति और पत्नी", "दंपति", "couple"]):
        return format_sample_personas([
            "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
            "🧑 Rajesh (Husband / Salaried Man - नौकरीपेशा पति)",
            "👵 Amma (Elder Mother-in-Law - सास जी)"
        ], character_count)

    # B. Father & Son / पिता-पुत्र
    if any(k in lower_text for k in ["father and son", "father & son", "father son", "pita aur beta", "पिता और बेटा", "पिता-पुत्र", "बाप-बेटा"]):
        return format_sample_personas([
            "👴 Sharma Ji (Traditional Father - पुराने खयालात के पिता)",
            "🧑 Aarav (Gen-Z Son - आधुनिक बेटा)",
            "👩 Sunita (Mother - माँ)"
        ], character_count)

    # C. Mother & Son / माँ-बेटा
    if any(k in lower_text for k in ["mother and son", "mother & son", "mother son", "maa aur beta", "माँ और बेटा", "माँ-बेटा", "माता-पुत्र"]):
        return format_sample_personas([
            "👩 Meera (Caring Mother - ममतामयी माँ)",
            "🧑 Kabir (Career-Minded Son - महत्वाकांक्षी बेटा)",
            "👴 Chacha Ji (Elder Uncle - चाचा जी)"
        ], character_count)

    # D. Mother & Daughter / माँ-बेटी
    if any(k in lower_text for k in ["mother and daughter", "mother & daughter", "mother daughter", "maa aur beti", "माँ और बेटी", "माँ-बेटी"]):
        return format_sample_personas([
            "👩 Meera (Caring Mother - ममतामयी माँ)",
            "👩 Ananya (College Daughter - समझदार बेटी)",
            "👵 Dadi (Grandmother - दादी)"
        ], character_count)

    # E. Colleagues / Coworkers / सहकर्मी / कलीग
    if any(k in lower_text for k in ["colleague", "coworker", "office colleagues", "दो कलीग", "सहकर्मी", "कलीग"]):
        return format_sample_personas([
            "👩 Priya (Senior Office Colleague / Colleague 1 - सीनियर कलीग)",
            "🧑 Rohan (Office Colleague / Colleague 2 - जूनियर कलीग)",
            "👔 Manager Mehra (Corporate Boss - मैनेजर)"
        ], character_count)

    # F. Friends / Tapri Buddies / दोस्त
    if any(k in lower_text for k in ["two friends", "friends", "दो दोस्त", "मित्र", "tapri buddies"]):
        return format_sample_personas([
            "👩 Ananya (College Friend 1 - कॉलेज दोस्त)",
            "🧑 Vikram (Street-Smart Friend 2 - पक्का यार)",
            "🧑 Rohan (Witty Friend 3 - दोस्त 3)"
        ], character_count)

    # G. Doctor & Patient / डॉक्टर और मरीज
    if any(k in lower_text for k in ["doctor and patient", "doctor patient", "doctor & patient", "डॉक्टर और मरीज", "डॉक्टर और पेशेंट"]):
        return format_sample_personas([
            "🩺 Dr. Rajesh (Hospital Doctor - वरिष्ठ चिकित्सक)",
            "🧑 Ramesh (Patient - मरीज)",
            "👩 Nurse Sneha (Staff Nurse - नर्स)"
        ], character_count)

    # H. Teacher & Student / शिक्षक और छात्र
    if any(k in lower_text for k in ["teacher and student", "teacher student", "teacher & student", "मास्टर और छात्र", "शिक्षक और छात्र"]):
        return format_sample_personas([
            "📚 Master Ji (School Teacher - सरकारी शिक्षक)",
            "🧑 Aarav (Student - छात्र)",
            "👵 Amma (Parent - अभिभावक)"
        ], character_count)

    # I. Shopkeeper & Customer / दुकानदार और ग्राहक
    if any(k in lower_text for k in ["shopkeeper and customer", "shopkeeper customer", "shopkeeper & customer", "दुकानदार और ग्राहक"]):
        return format_sample_personas([
            "🛒 Mohan (Local Shopkeeper - किराना दुकानदार)",
            "🧑 Rajesh (Customer - ग्राहक)",
            "🛵 Kabir (Delivery Guy - डिलीवरी राइडर)"
        ], character_count)

    # J. Lawyer & Client / वकील और मुवक्किल
    if any(k in lower_text for k in ["lawyer and client", "lawyer client", "lawyer & client", "वकील और मुवक्किल"]):
        return format_sample_personas([
            "⚖️ Advocate Verma (Senior Lawyer - वरिष्ठ वकील)",
            "🧑 Kabir (Client - मुवक्किल)",
            "👔 Clerk Tripathi (Court Clerk - पेशकार)"
        ], character_count)

    # K. Neighbors / पड़ोसी
    if any(k in lower_text for k in ["neighbor", "neighbour", "दो पड़ोसी", "पड़ोसी"]):
        return format_sample_personas([
            "🧑 Verma Ji (Curious Neighbor - पड़ोसी 1)",
            "🧑 Gupta Ji (Opinionated Neighbor - पड़ोसी 2)",
            "👵 Amma (Elder Neighbor - बुजुर्ग पड़ोसी)"
        ], character_count)

    # L. Police & Citizen / Driver / Suspect
    if any(k in lower_text for k in ["police and citizen", "police and driver", "पुलिस और नागरिक", "पुलिस और ड्राइवर"]):
        return format_sample_personas([
            "👮 Sub-Inspector Sunita (Traffic Police - पुलिस दरोगा)",
            "🛵 Rohan (Citizen / Delivery Partner - नागरिक)",
            "🧑 Kabir (Eyewitness - प्रत्यक्षदर्शी)"
        ], character_count)

    return None


def get_character_personas(
    scene_style: str,
    character_count: int,
    tone: str,
    angle: str,
    topic_or_script: str = "",
    sample_story: Optional[str] = None,
) -> List[str]:
    """Generate rich, socioeconomically diverse character personas grounded in the script topic and representing India."""
    # ⭐ HIGHEST PRECEDENCE: Check if sample story/script defines characters or relationships
    if sample_story and sample_story.strip():
        sample_personas = extract_sample_story_personas(sample_story.strip(), character_count)
        if sample_personas:
            return sample_personas

    import random
    combined = f"{tone} {angle}".lower()
    context_text = f"{topic_or_script} {sample_story or ''}"
    is_sad = any(w in combined for w in ["sad", "heartbreak", "tragedy", "दुख", "दर्द", "शोक", "lament", "loss", "grief", "भावुक", "tragic"])
    is_funny = any(w in combined for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी", "मजाकिया", "रोस्ट", "edgy", "relatable"])
    is_culture = any(w in combined for w in ["culture", "heritage", "pride", "गौरव", "धरोहर", "traditional", "wisdom"])
    style_lower = scene_style.lower()
    is_argument = style_lower == "argument" or any(w in combined for w in ["argument", "बहस", "तकरार", "clash"])

    if character_count <= 1:
        if is_sad or style_lower == "lament":
            return ["💔 Grieving Citizen Meera (भावुक सूत्रधार मीरा)"]
        elif is_funny or style_lower in ["dialogue", "argument"]:
            chosen_solo = select_script_grounded_solo(context_text)
            return [sanitize_persona_name(chosen_solo)]
        elif is_culture:
            return ["🪔 Cultural Storyteller Shastri Ji (सांस्कृतिक सूत्रधार)"]
        elif style_lower == "speech":
            return [sanitize_persona_name("📢 Orator Vikrant (वक्ता विक्रांत)")]
        else:
            return [sanitize_persona_name("🎙️ Presenter Neha (मुख्य वक्ता नेहा)")]

    if character_count == 2:
        if is_sad or style_lower == "lament":
            return [
                sanitize_persona_name("👩 Ananya / Bereaved Person (शोकाकुल साथी अनन्या)"),
                sanitize_persona_name("🤝 Vikram / Consoling Companion (सहयोगी विक्रम)")
            ]
        elif style_lower == "interview":
            return [
                sanitize_persona_name("🎙️ Journalist / Host Neha (पत्रकार नेहा)"),
                sanitize_persona_name("👤 Guest / Insider Dr. Farhan (सरकारी अधिकारी / अतिथि डॉ. फरहान)")
            ]
        elif style_lower == "debate":
            return [
                sanitize_persona_name("🗣️ Speaker A - Sunita (पक्ष - सुनीता)"),
                sanitize_persona_name("👥 Speaker B - Vikrant (विपक्ष - विक्रांत)")
            ]
        elif style_lower == "argument" or is_argument:
            chosen_pair = select_script_grounded_pair(context_text)
            return [sanitize_persona_name(chosen_pair[0]), sanitize_persona_name(chosen_pair[1])]
        elif is_culture:
            return [
                sanitize_persona_name("🪔 Senior Scholar Shastri Ji (गुरु / शास्त्री जी)"),
                sanitize_persona_name("👩 Curious Youth Meera (जिज्ञासु युवा मीरा)")
            ]
        elif is_funny or style_lower == "dialogue":
            # Contextual script-grounded selection of diverse Indian socioeconomic pairings
            if context_text.strip():
                chosen_pair = select_script_grounded_pair(context_text)
                return [sanitize_persona_name(chosen_pair[0]), sanitize_persona_name(chosen_pair[1])]
            return [
                sanitize_persona_name("👩 Priya / Friend 1 (प्रिया - दोस्त 1)"),
                sanitize_persona_name("🧑 Rohan / Friend 2 (रोहन - दोस्त 2)")
            ]
        else:
            chosen_pair = select_script_grounded_pair(context_text)
            return [sanitize_persona_name(chosen_pair[0]), sanitize_persona_name(chosen_pair[1])]

    # 3 or more characters (Multi-generational, gender-balanced, socioeconomic diversity)
    if is_sad or style_lower == "lament":
        return [
            sanitize_persona_name("👩 Ananya / Bereaved Person (शोकाकुल साथी अनन्या)"),
            sanitize_persona_name("🤝 Vikram / Consoling Friend (सहयोगी विक्रम)"),
            sanitize_persona_name("👵 Amma / Elder Witness (बुजुर्ग अभिभावक अम्मा)"),
        ]
    elif style_lower == "interview":
        return [
            sanitize_persona_name("🎙️ Host Neha (होस्ट नेहा)"),
            sanitize_persona_name("👤 Guest Dr. Imran (वरिष्ठ विशेषज्ञ डॉ. इमरान)"),
            sanitize_persona_name("👩‍💼 Analyst Lakshmi (अर्थशास्त्री लक्ष्मी)"),
        ]
    elif style_lower == "debate":
        return [
            sanitize_persona_name("🎙️ Moderator Anita (मध्यस्थ अनीता)"),
            sanitize_persona_name("🗣️ Speaker A - Vikrant (पक्ष - विक्रांत)"),
            sanitize_persona_name("👥 Speaker B - Fatima (विपक्ष - फातिमा)"),
        ]
    elif style_lower == "argument" or is_argument:
        chosen_trio = select_script_grounded_trio(context_text)
        return [sanitize_persona_name(chosen_trio[0]), sanitize_persona_name(chosen_trio[1]), sanitize_persona_name(chosen_trio[2])]

    else:
        # Contextual script-grounded selection of diverse socioeconomic trios
        chosen_trio = select_script_grounded_trio(context_text)
        return [sanitize_persona_name(c) for c in chosen_trio]


NARRATIVE_MODES = [
    {
        "name": "Fun & Banter First (ह्यूमर पहले, खबर बाद में)",
        "mode_key": "fun_first",
        "description": "Start with hilarious relatable banter, boasting, or misunderstanding in Beat 1. Drop the actual verified news as a sudden revelation in Beat 2. Deliver a sharp punchline in Beat 3.",
    },
    {
        "name": "Breaking News First (सीधी खबर और धरातलीय बहस)",
        "mode_key": "news_first",
        "description": "Start with an urgent breaking news hook in Beat 1. Examine facts and counterpoints in Beat 2. Conclude with a witty or thoughtful takeaway in Beat 3.",
    },
    {
        "name": "Mid-Conversation Discovery (चर्चा के बीच में खबर की एंट्री)",
        "mode_key": "mid_conversation",
        "description": "Start with an everyday work or life debate in Beat 1. Suddenly discover/read the news on phone/newspaper in Beat 2. React with shock and comic resolution in Beat 3.",
    },
    {
        "name": "Curiosity & Mystery First (जिज्ञासा और रहस्य)",
        "mode_key": "curiosity_first",
        "description": "Start with a curious observation or puzzling event in Beat 1. Unpack the verified news backstory explaining it in Beat 2. Land an eye-opening satirical takeaway in Beat 3.",
    },
]


def get_creative_guidelines(scene_style: str, character_count: int, tone: str, angle: str) -> str:
    """Generate explicit directives to ensure AI respects Angle (creative situation), Tone (jokes/emotions), and Style."""
    combined = f"{tone} {angle}".lower()
    is_sad = any(w in combined for w in ["sad", "heartbreak", "tragedy", "दुख", "दर्द", "शोक", "lament", "loss", "grief", "भावुक", "tragic"])

    # Angle Guidance
    angle_guidance = (
        f"🎨 EDITORIAL ANGLE DIRECTIVE ({angle or 'Creative Angle'}):\n"
        f"- The angle dictates HOW you imagine and set up the scene!\n"
        f"- Do NOT just report dry news. Create an imaginary relatable situation, sketch, or scenario:\n"
        f"  * If Tragic & Heartbreaking: Frame through a quiet, solemn moment of personal loss, deep empathy, and emotional vulnerability.\n"
        f"  * If Funny & Relatable: Create an everyday situation (e.g. friends at a chai tapri, dealing with hilarious daily absurdities).\n"
        f"  * If Sarcastic & Edgy: Roast the ironies and contrast expectations vs reality with sharp wit.\n"
        f"  * If Bollywood Masala: Inject dramatic Hindi cinema flair, punchy one-liners, and dramatic tension.\n"
        f"  * If Gen-Z Hinglish: Use modern viral slang, relatable meme references, and casual conversational flow.\n"
        f"  * If Investigative Deep-Dive: Frame as uncovering startling behind-the-scenes curiosity.\n"
        f"  * If Inspirational & Uplifting: Frame as a triumphant journey of courage, hard work, and national pride."
    )

    # Tone Guidance
    if is_sad:
        tone_guidance = (
            f"😢 TONE DIRECTIVE ({tone}):\n"
            f"- Infuse deep emotional weight, quiet sorrow, and heartfelt empathy.\n"
            f"- Spoken dialogue must honor human grief with tender sensitivity and solemn dignity.\n"
            f"- Avoid loud, sensational, or rushed delivery."
        )
    elif any(w in combined for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी"]):
        tone_guidance = (
            f"😂 TONE DIRECTIVE ({tone}):\n"
            f"- THIS MUST BE GENUINELY FUNNY! Use real jokes, witty banter, humorous metaphors, and comedic punchlines.\n"
            f"- Characters should react with funny shock, tease each other, or make hilarious relatable comparisons.\n"
            f"- Avoid flat, boring news reciting. Be entertaining, witty, and creative!"
        )
    elif any(w in combined for w in ["viral", "high energy", "धमाकेदार"]):
        tone_guidance = (
            f"🔥 TONE DIRECTIVE ({tone}):\n"
            f"- High-voltage excitement! Deliver shock-value hooks, explosive energy, and dramatic pacing."
        )
    elif any(w in combined for w in ["culture", "heritage", "pride", "गौरव"]):
        tone_guidance = (
            f"🪔 TONE DIRECTIVE ({tone}):\n"
            f"- Celebrate timeless Indian heritage, deep cultural pride, and respectful desi swag with authentic idioms."
        )
    elif any(w in combined for w in ["argument", "बहस", "तकरार", "clash"]):
        tone_guidance = (
            f"⚔️ TONE DIRECTIVE ({tone}):\n"
            f"- High-voltage heated argument & verbal clash! Characters passionately disagree, trade sharp witty counter-punches,\n"
            f"- Emotional friction and defensive comebacks grounded in realistic relationship stakes (colleagues, friends, husband-wife, father-son).\n"
            f"- Build up escalating tension and conclude with an unexpected reality check or punchline!"
        )
    else:
        tone_guidance = f"🎙️ TONE DIRECTIVE ({tone}):\n- Embody the spirit of {tone} with authentic spoken Hindi."

    # Style Guidance
    style_lower = scene_style.lower()
    if style_lower == "lament":
        style_guidance = (
            "💔 SCENE STYLE DIRECTIVE: LAMENT / EULOGY:\n"
            "- A deeply moving tribute and expression of shared sorrow, offering mutual solace and poignant remembrance across scenes."
        )
    elif style_lower in ["dialogue", "argument"] and character_count > 1:
        style_label = "ARGUMENT (HEATED CLASH)" if style_lower == "argument" else "DIALOGUE"
        style_guidance = (
            f"👥 SCENE STYLE DIRECTIVE: {style_label} ({character_count} Characters):\n"
            f"- This is an active in-universe conversation/argument between {character_count} people!\n"
            f"- Characters must speak back-and-forth across the scenes, reacting to each other's words, bantering, questioning, and dropping punchlines.\n"
            f"- STRICT FORBIDDEN RULE: NO social media commenting, NO CTA, NO asking viewers to comment ('कमेंट करें', 'लाइक करें', 'कमेंट में बताओ'). Characters are having a real conversation with each other in their world—they DO NOT talk about comments!\n"
            f"- Each scene must have a designated character speaking their exact line."
        )
    elif style_lower == "interview":
        style_guidance = (
            "🎤 SCENE STYLE DIRECTIVE: INTERVIEW:\n"
            "- The interviewer asks sharp, engaging questions; the guest responds with exciting, funny, or deep revelations."
        )
    elif style_lower == "debate":
        style_guidance = (
            "⚔️ SCENE STYLE DIRECTIVE: DEBATE:\n"
            "- Two opposing viewpoints clash with witty counter-points, lively banter, and engaging arguments."
        )

    elif style_lower == "speech":
        style_guidance = (
            "📢 SCENE STYLE DIRECTIVE: SPEECH:\n"
            "- A charismatic public address delivered directly to an audience with rhetorical questions and impact."
        )
    else:
        style_guidance = (
            "🎙️ SCENE STYLE DIRECTIVE: MONOLOGUE / NARRATION:\n"
            "- Direct-to-camera storytelling with punchy, energetic delivery addressing the viewer directly."
        )

    insta_story_guidance = (
        "📱 REAL INSTAGRAM STORY / REEL VIBE & CADENCE:\n"
        "- The dialogue MUST feel like a genuine, viral Instagram Story or Reel shot on a phone camera!\n"
        "- Spontaneous, snappy, highly conversational spoken Hindi/Hinglish.\n"
        "- Natural conversational openers & reactions: 'अरे यार सुनो!', 'सच में?', 'तू मज़ाक कर रहा है क्या?', 'भाई ये क्या सीन है?!', 'अरे यार दिमाग खराब हो गया!'\n"
        "- Authentic back-and-forth rhythm with quick interruptions, funny expressions, and real-life camaraderie.\n"
        "- NEVER sound like a formal television news anchor, textbook lecture, or rehearsed speech. Sound like real people talking on an Insta story!"
    )

    diversity_guidance = (
        "🌍 DEMOGRAPHIC & GENDER DIVERSITY:\n"
        "- Characters represent an authentic mix of genders (men, women) and diverse demographic backgrounds across India.\n"
        "- Characters have distinct voices, unique cultural viewpoints, and natural colloquial warmth reflecting their background."
    )

    no_commenting_rule = (
        "🚫 STRICT PROHIBITION ON COMMENTING & CTAs IN SCRIPT DIALOGUE:\n"
        "- Spoken dialogue MUST NEVER contain social media meta-commentary, such as 'कमेंट करें', 'कमेंट में बताएं', 'लाइक करें', 'शेयर करें', or asking viewers to comment.\n"
        "- Characters must remain 100% inside the scene and talk to each other naturally without breaking character."
    )

    single_video_flow_rule = (
        "🎬 ONE CONTINUOUS VIDEO FLOW (ZERO REPETITION OF BACKGROUND CONTEXT):\n"
        "- This is ONE single continuous video reel, not multiple separate videos.\n"
        "- The setting, location, and news premise are established ONCE in Scene 1.\n"
        "- Scene 2, Scene 3, and subsequent scenes MUST NOT re-explain the background, re-summarize what happened, or repeat context.\n"
        "- Every turn must advance the story forward: direct reactions, sharp dialogue banter, prop interaction, and logical punchy resolution."
    )

    return f"{angle_guidance}\n\n{tone_guidance}\n\n{style_guidance}\n\n{insta_story_guidance}\n\n{diversity_guidance}\n\n{no_commenting_rule}\n\n{single_video_flow_rule}"


class DialogueNarrationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Dialogue & Narration Scriptwriter",
            role="Spoken Dialogue Writing & Timeline Calibration",
            icon="🎙️",
            instructions=DIALOGUE_INSTRUCTIONS,
            prompt_file="dialogue_writer/prompt.md",
        )

    def write_dialogue(
        self,
        news_input: str,
        hook: str,
        cta: str,
        tone: str,
        duration_sec: int,
        verification: NewsVerificationReport,
        correction_feedback: Optional[str] = None,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> str:
        """Craft spoken Hindi dialogue strictly calibrated to word budget."""
        budget = get_duration_budget(duration_sec)
        guidance = get_sentence_guidance(duration_sec, budget["recommended_words"], budget["max_words"])

        correction_note = ""
        if correction_feedback:
            correction_note = f"\n[CRITICAL CORRECTION FROM TIMING AUDITOR: {correction_feedback}]\n"

        sub_directive = f"\nChief Editor Directive & Dialogue Word Limits:\n{sub_instruction}\n" if sub_instruction else ""
        facts_list = "\n".join(["- " + f for f in verification.verified_facts[:3]])

        prompt = render_prompt(
            "dialogue_writer/write_dialogue.md",
            news_input=news_input,
            hook=hook,
            duration_sec=duration_sec,
            rec_words=budget["recommended_words"],
            max_words=budget["max_words"],
            min_words=budget["min_words"],
            sub_directive=sub_directive,
            guidance=guidance,
            tone=tone,
            cta=cta,
            correction_note=correction_note,
            facts_list=facts_list,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
            cleaned = clean_hindi_dialogue(raw_output)
            final_text = smart_trim_dialogue(cleaned, budget["max_words"], budget["recommended_words"], cta)
            return final_text or f"{hook} {news_input}. {cta}"
        except ModelGenerationError:
            raise
        except Exception:
            fallback = f"{hook} {news_input}. {cta}"
            return smart_trim_dialogue(fallback, budget["max_words"], budget["recommended_words"], cta)

    def write_dialogues_batch(
        self,
        news_input: str,
        items: List[Dict[str, str]],
        tone: str,
        duration_sec: int,
        verification: NewsVerificationReport,
        character_count: int = 1,
        scene_style: str = "Dialogue",
        preferred_angle: str = "",
        sample_story: Optional[str] = None,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
        num_scenes: Optional[int] = None,
    ) -> List[str]:
        """Craft spoken Hindi dialogues for all items scene-by-scene respecting character count, style, tone, and angle."""
        budget = get_duration_budget(duration_sec)
        guidance = get_sentence_guidance(duration_sec, budget["recommended_words"], budget["max_words"])
        personas = get_character_personas(
            scene_style, character_count, tone, preferred_angle,
            topic_or_script=news_input, sample_story=sample_story
        )
        creative_rules = get_creative_guidelines(scene_style, character_count, tone, preferred_angle)

        # Dynamic scene count: respect user override or calculate from duration, style, and character count
        if num_scenes is not None and 1 <= num_scenes <= 5:
            actual_scenes = num_scenes
        elif duration_sec <= 8 and (scene_style.lower() in ["speech", "monologue"] or character_count == 1):
            actual_scenes = 1
        elif duration_sec <= 15:
            actual_scenes = 2
        elif duration_sec <= 35:
            actual_scenes = 3
        else:
            actual_scenes = budget.get("scenes", 3)

        per_scene_words = max(6, budget["recommended_words"] // actual_scenes)
        per_scene_max = max(8, budget["max_words"] // actual_scenes + 2)

        sample_directive = ""
        if sample_story and sample_story.strip():
            sample_directive = (
                f"\n⭐ SAMPLE STORY (HIGHEST PRECEDENCE OVER GENERAL INSTRUCTIONS):\n"
                f"\"{sample_story.strip()}\"\n"
                f"DISCREPANCY PRECEDENCE RULE: In case of any conflict between general instructions and this sample story, "
                f"THE SAMPLE STORY TAKES PRECEDENCE! Adapt the characters, plot points, and dialogue from this sample story.\n"
            )

        items_desc = "\n\n".join([
            f"SCRIPT {i+1}:\nAngle: {it['angle']}\nHook: {it['hook']}"
            for i, it in enumerate(items)
        ])

        facts_text = "\n".join(['- ' + f for f in (verification.verified_facts if verification else [])[:3]]) if (verification and verification.verified_facts) else f"- {news_input[:80]}"
        props_text = ", ".join(verification.physical_props) if (verification and verification.physical_props) else ""
        locs_text = ", ".join(verification.key_locations) if (verification and verification.key_locations) else ""
        conflict_text = verification.core_conflict_or_irony if (verification and verification.core_conflict_or_irony) else ""

        sub_directive = f"\nChief Editor Directive & Dialogue Word Limits:\n{sub_instruction}\n" if sub_instruction else ""

        # Dynamic narrative mode selection: randomly decide position of news and flow per script run
        chosen_narrative = random.choice(NARRATIVE_MODES)
        n_mode = chosen_narrative["mode_key"]

        # Dynamically build continuous-shot beat templates for 1 to 5 scenes
        scene_templates = []
        for s_idx in range(1, actual_scenes + 1):
            char_s = personas[(s_idx - 1) % len(personas)]
            if actual_scenes == 1:
                label = f"BEAT 1 (Continuous Master Shot: Complete Story - ~{per_scene_words} words, max {per_scene_max}w)"
                act = f"Single continuous vertical shot in {locs_text or 'the setting'}; character holds {props_text or 'key prop'}, delivering complete narrative fluidly"
                dial = "Dynamic Hindi dialogue stating what happened, the context, and key takeaway in one fluid take"
            elif n_mode == "fun_first":
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Hilarious Banter / Misunderstanding - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Continuous shot starts in {locs_text or 'the setting'}; characters engaged in witty relatable banter or comedic misconception"
                    dial = "Witty, humorous Hindi conversational opener establishing a relatable premise (NO direct news drop yet)"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: The Shocking News Reveal - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera smoothly pivots/refocuses; character pulls out {props_text or 'smartphone/document'} revealing the verified news facts"
                    dial = "Sharp Hindi reality check dropping the actual news facts and context, shattering the previous illusion"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Humorous Punchline & Resolution - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera holds continuous framed reaction; crowd or companions react as character lands the punchline"
                    dial = "Logical concluding Hindi line delivering witty punchline, satirical twist, or meme takeaway"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Escalation & Fact Evidence - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera reframes; examining {props_text or 'the physical object'} with verified details"
                    dial = "Conversational Hindi counterpoint or startling fact"
            elif n_mode == "mid_conversation":
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Everyday Life Routine & Banter - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Continuous shot begins in {locs_text or 'the setting'}; characters debating daily life, work, or routine matters"
                    dial = "Relatable conversational Hindi dialogue reflecting daily Indian hustle or workplace debate"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: Sudden News Bombshell Discovery - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera tracks over shoulder as character notices breaking news on {props_text or 'smartphone screen/paper'} with wide-eyed shock"
                    dial = "Urgent Hindi line interrupting the banter with the shocking verified news headline and fact"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Mutual Shock & Comic Resolution - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera captures both characters in continuous two-shot sharing mutual disbelief and reaction"
                    dial = "Witty concluding Hindi line re-evaluating their situation in light of the news"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Examining the Evidence - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera continuously pans; verifying {props_text or 'the details'} together"
                    dial = "Conversational Hindi detail verifying the bizarre fact"
            elif n_mode == "curiosity_first":
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Puzzling Observation / Mystery - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Continuous shot opens in {locs_text or 'the setting'}; character points out a puzzling event or strange crowd behavior"
                    dial = "Intriguing Hindi observation questioning what on earth is happening"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: Unpacking the News Mystery - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera reframes smoothly; second character reveals the real verified news backstory holding {props_text or 'key prop'}"
                    dial = "Hindi explanation revealing the verified facts and why this event is actually taking place"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Satirical Realization & Payoff - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera holds the final reaction framed against the ongoing backdrop"
                    dial = "Memorable Hindi punchline or eye-opening satirical takeaway"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Deeper Revelation - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera reframes dynamically to show public reaction"
                    dial = "Surprising Hindi supporting fact or evidence"
            else:  # news_first default
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Breaking Hook & Disruption - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Continuous shot starts in {locs_text or 'the setting'}; character disrupts with breaking news holding {props_text or 'the news'}"
                    dial = "Attention-grabbing Hindi hook line clearly introducing what happened and where"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: Fact Counterpoint & Interaction - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera continuously refocuses; second character responds directly examining {props_text or 'the physical object'}"
                    dial = "Hindi dialogue answering Beat 1 with verified facts and contextual depth"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Payoff & Resolution - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera captures concluding two-shot; characters deliver final verdict"
                    dial = "Logical concluding Hindi line delivering witty payoff, punchline, or impact"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Evidence & Escalation - ~{per_scene_words} words, max {per_scene_max}w)"
                    act = f"Camera pivots continuously; revealing startling evidence"
                    dial = "Conversational Hindi counterpoint or startling fact"

            scene_templates.append(
                f"{label}:\n"
                f"CHARACTER: {char_s}\n"
                f"ACTION: [{act}]\n"
                f"DIALOGUE: [{dial}]"
            )
        sample_scenes = "\n\n".join(scene_templates)

        prompt = render_prompt(
            "dialogue_writer/write_dialogue_batch.md",
            news_input=news_input,
            duration_sec=duration_sec,
            actual_scenes=actual_scenes,
            rec_words=budget["recommended_words"],
            max_words=budget["max_words"],
            min_words=budget["min_words"],
            per_scene_words=per_scene_words,
            per_scene_max=per_scene_max,
            narrative_name=chosen_narrative["name"],
            narrative_desc=chosen_narrative["description"],
            character_count=len(personas),
            personas_list="\n".join(["- " + p for p in personas]),
            setting_location=locs_text or "Authentic Indian street or workplace setting",
            physical_props=props_text or "Specific physical objects in the news story",
            core_conflict=conflict_text or "The central viral story hook",
            facts_text=facts_text,
            creative_rules=creative_rules,
            sample_directive=sample_directive,
            sub_directive=sub_directive,
            guidance=guidance,
            items_desc=items_desc,
            sample_scenes=sample_scenes,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            logger.warning(f"Dialogue generation execution failed ({e}), initiating intelligent Hindi fallback")
            raw_output = ""

        parsed_map = {}
        # Parse blocks by SCRIPT header (supporting markdown like **SCRIPT 1:**, ### SCRIPT 1, etc.)
        blocks = re.split(r"(?:###|\*\*|##)?\s*SCRIPT\s*(\d+)\s*(?:\*\*)?\s*:\s*", raw_output, flags=re.IGNORECASE)

        def parse_scene_block(content: str) -> List[Dict[str, str]]:
            scene_chunks = re.split(r"(?:###|\*\*|##)?\s*(?:SCENE|PART|BEAT)\s*(\d+)[^:]*:\s*", content, flags=re.IGNORECASE)
            script_scenes = []
            if len(scene_chunks) > 1:
                for s_idx in range(1, len(scene_chunks), 2):
                    s_num = int(scene_chunks[s_idx])
                    s_body = scene_chunks[s_idx + 1]
                    char_name = personas[(s_num - 1) % len(personas)]
                    dial_text = ""
                    action_text = ""
                    for line in s_body.split("\n"):
                        ls = line.strip()
                        clean_ls = re.sub(r"^\*+|\*+$", "", ls).strip()
                        upper_ls = clean_ls.upper()
                        if upper_ls.startswith("CHARACTER:"):
                            char_name = clean_ls.split(":", 1)[-1].strip("[] \"'*")
                        elif upper_ls.startswith("ACTION:") or upper_ls.startswith("BACKGROUND & ACTION:") or upper_ls.startswith("BACKGROUND & VISUAL ACTION:") or upper_ls.startswith("BACKGROUND:") or upper_ls.startswith("VISUAL:"):
                            action_text = clean_ls.split(":", 1)[-1].strip("[] \"'*")
                        elif upper_ls.startswith("DIALOGUE:") or upper_ls.startswith("LINE:"):
                            dial_text = clean_hindi_dialogue(clean_ls.split(":", 1)[-1].strip("[] \"'*"))
                        elif not any(upper_ls.startswith(k) for k in ["SCENE", "SCRIPT", "PART", "BEAT", "TIME", "SHOT"]) and dial_text:
                            dial_text += " " + clean_hindi_dialogue(clean_ls)
                    if dial_text:
                        script_scenes.append({
                            "scene_number": s_num,
                            "character": char_name,
                            "dialogue": dial_text,
                            "action": action_text,
                        })
            return script_scenes

        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                idx = int(blocks[i]) - 1
                content = blocks[i + 1]
                script_scenes = parse_scene_block(content)
                if script_scenes:
                    combined_text = " ".join(s["dialogue"] for s in script_scenes)
                    parsed_map[idx] = (combined_text, script_scenes)
                else:
                    # Fallback to NARRATION line if model used legacy format
                    narration_text = ""
                    for line in content.split("\n"):
                        ls = line.strip()
                        if ls.startswith("NARRATION:") or ls.startswith("DIALOGUE:"):
                            narration_text = ls.split(":", 1)[-1].strip("[] \"'*")
                        elif narration_text and not ls.startswith("SCRIPT"):
                            narration_text += " " + ls
                    if narration_text:
                        parsed_map[idx] = (clean_hindi_dialogue(narration_text), [])
        elif raw_output:
            # If no SCRIPT 1 header, parse scenes directly from raw_output for index 0
            direct_scenes = parse_scene_block(raw_output)
            if direct_scenes:
                combined_text = " ".join(s["dialogue"] for s in direct_scenes)
                parsed_map[0] = (combined_text, direct_scenes)

        narrations: List[str] = []
        for i, it in enumerate(items):
            entry = parsed_map.get(i)
            if entry and len(entry[0]) > 10:
                raw_text, scene_lines = entry
                final_text = smart_trim_dialogue(raw_text, budget["max_words"], budget["recommended_words"], it["cta"])

                # If no structured scene lines parsed, split sentences evenly across characters
                if not scene_lines:
                    sentences = [s.strip() for s in re.split(r"[।!?]", final_text) if s.strip()]
                    scene_lines = []
                    for s_idx in range(actual_scenes):
                        char_for_scene = personas[s_idx % len(personas)]
                        if s_idx < len(sentences):
                            line_text = sentences[s_idx] + "।"
                        elif s_idx == actual_scenes - 1:
                            line_text = it["cta"]
                        else:
                            line_text = final_text
                        scene_lines.append({
                            "scene_number": s_idx + 1,
                            "character": char_for_scene,
                            "dialogue": line_text,
                        })

                narrations.append(ScriptDialogue(final_text, scene_lines=scene_lines))
            else:
                # Intelligent Hindi fallback: NEVER use raw English headlines as spoken dialogue!
                fact_detail = ""
                if verification and verification.verified_facts:
                    fact_detail = verification.verified_facts[0]
                elif verification and verification.verification_summary:
                    fact_detail = verification.verification_summary

                # Construct authentic, meaningful Hindi dialogue lines aligned with narrative mode
                clean_hook = it.get("hook") or "अरे सुनो भाई! आज की सबसे बड़ी खबर सामने आ गई है।"

                if n_mode == "fun_first":
                    beat_pool = [
                        "अरे भाई सुनो, आज तो गजब ही ड्रामा हो गया, यकीन नहीं करोगे!",
                        f"अरे ड्रामा छोड़ो, असली बात तो ये है कि {fact_detail or 'इस मामले का सबसे बड़ा सच अब सबके सामने आ चुका है।'}",
                        "कागजातों और सबूतों से साफ है कि कहानी में जो दिख रहा है, बात उससे कहीं ज्यादा गहरी है।",
                        "सड़कों पर लोगों और सोशल मीडिया पर अब इसी बात की जोरदार चर्चा चल रही है।",
                        "अब देखना ये होगा कि इस पूरे सियासी घटनाक्रम का क्या मजेदार असर होता है!",
                    ]
                elif n_mode == "mid_conversation":
                    beat_pool = [
                        "रोज़-रोज़ की वही भागदौड़ और वही झंझट, इंसान करे तो क्या करे!",
                        f"अरे रुको! ज़रा फोन पर ये खबर तो देखो—{clean_hook}",
                        f"इस मामले में सबसे बड़ा मोड़ ये है कि {fact_detail or 'सारी सच्चाई अब सबके सामने खुल चुकी है।'}",
                        "सड़कों से लेकर सोशल मीडिया तक अब इसी का शोर है!",
                        "लो कर लो बात! अब तो पूरा खेल ही पलट गया!",
                    ]
                elif n_mode == "curiosity_first":
                    beat_pool = [
                        "भाई ज़रा इधर देखो, आज अचानक हर तरफ इतनी हलचल क्यों मची हुई है?",
                        f"तुम्हें नहीं पता? सबसे बड़ी वजह ये है कि {clean_hook}",
                        f"असली पेंच ये है कि {fact_detail or 'सबूतों के बाद अब प्रशासन में हड़कंप मच गया है।'}",
                        "लोग हैरान हैं कि आखिर ये सब इतनी जल्दी कैसे हो गया!",
                        "वाह भाई वाह! इसे कहते हैं असली ट्विस्ट, अब बात पूरी समझ आई!",
                    ]
                else:  # news_first
                    beat_pool = [
                        clean_hook,
                        "इस पूरे मामले में सबसे बड़ा मोड़ ये आया है कि सच्चाई अब सबके सामने खुल चुकी है।",
                        f"कागजातों और सबूतों से साफ है कि {fact_detail or 'बात उससे कहीं ज्यादा गहरी है।'}",
                        "सड़कों पर लोगों और सोशल मीडिया पर अब इसी बात की जोरदार चर्चा चल रही है।",
                        "अब देखना ये होगा कि इस पूरे घटनाक्रम का क्या नतीजा निकलता है!",
                    ]

                fallback_scenes = []
                if actual_scenes == 1:
                    fallback_scenes.append({"scene_number": 1, "character": personas[0], "dialogue": clean_hook})
                else:
                    for s_i in range(actual_scenes):
                        c_p = personas[s_i % len(personas)]
                        if s_i == 0:
                            d_p = beat_pool[0]
                        elif s_i == actual_scenes - 1:
                            d_p = beat_pool[4]
                        elif s_i == 1:
                            d_p = beat_pool[1]
                        elif s_i == 2:
                            d_p = beat_pool[2]
                        else:
                            d_p = beat_pool[3]
                        fallback_scenes.append({"scene_number": s_i + 1, "character": c_p, "dialogue": d_p})

                combined_fallback = " ".join(s["dialogue"] for s in fallback_scenes)
                trimmed_default = smart_trim_dialogue(combined_fallback, budget["max_words"], budget["recommended_words"], it["cta"])
                narrations.append(ScriptDialogue(trimmed_default, scene_lines=fallback_scenes))

        return narrations


dialogue_writer = DialogueNarrationAgent()
