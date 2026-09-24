"""Agent 3: Dialogue & Narration Scriptwriter Agent."""

import re
import random
import logging
from typing import Optional, List, Dict, Any, Tuple
from agents.base import BaseAgent
from core.models import NewsVerificationReport, CharacterProfile, StoryBeatStep, SceneSettingOption
from core.metrics import get_duration_budget, count_words
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

logger = logging.getLogger(__name__)

DIALOGUE_INSTRUCTIONS = load_prompt("dialogue_writer/write_dialogue.md")


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


def clean_hook_for_dialogue(hook: str) -> str:
    """Strip emojis and template filler from a hook before it reaches the dialogue
    writer. The hook is an IDEA for the model to express in natural spoken
    Hindi — it must never be quotable verbatim (no character may 'speak' an
    emoji or a 'bada update' template line)."""
    if not hook:
        return ""
    h = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]+", "", hook)
    # Strip "X को लेकर बड़ा अपडेट/खबर!" template filler on EVERY line
    # (MULTILINE: without it only the last line was cleaned).
    h = re.sub(r"\s*को\s+लेकर\s+बड़[ािीे]*\s*(?:अपडेट|खबर)\s*!?\s*$", "", h, flags=re.MULTILINE)
    # Collapse spaces/tabs within each line, drop emptied lines, keep line breaks.
    lines = [re.sub(r"[ \t]+", " ", ln).strip(" -–—:;,") for ln in h.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def get_sentence_guidance(duration_sec: int, rec_w: int, max_w: int, tone: str = "", angle: str = "") -> str:
    """Return explicit structural sentence advice calibrated to target reel duration with Fun-First support."""
    combined = f"{tone} {angle}".lower()
    is_funny = any(w in combined for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी", "मजाकिया", "roast", "relatable", "joke"])

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
    # Close Friends
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
    # Local Fictional Politician / Ward Corporator & Common Citizen
    ("🏛️ Netaji Tiwari (Ward Corporator / Friend 1 - स्थानीय पार्षद)", "🧑 Rohan (Common Citizen / Friend 2 - आम नागरिक)"),
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
        "📰 Mohan (Newspaper Vendor / Elder - अखबार वाला)",
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
    if any(k in text for k in ["friend", "dost", "yaar", "दोस्त", "यार"]):
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
        return DIVERSE_SOCIOECONOMIC_PAIRS[2]  # Ward Corporator Netaji vs Common Citizen

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
    if any(k in text for k in ["friend", "dost", "दोस्त", "यार"]):
        return RELATIONSHIP_TRIOS[2]  # Friends Trio: Ananya, Vikram, Rohan

    # SIR / Government Planning Office Trio
    if any(k in text for k in ["sir", "dholera", "investment region", "special investment", "industrial corridor", "collectorate", "secretariat"]):
        return (
            "👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)",
            "🧑 Rajesh (Industrial Investor / Citizen - उद्यमी)",
            "👩 Priya (Land Planning Assistant - सहायक योजनाकार)"
        )

    if any(k in text for k in ["election", "नेता", "netaji", "पार्षद", "corporator", "party", "सरकार"]):
        return DIVERSE_SOCIOECONOMIC_TRIOS[0]  # Netaji, Auto Driver, Newspaper Vendor Elder
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

    # F. Friends / दोस्त
    if any(k in lower_text for k in ["two friends", "friends", "दो दोस्त", "मित्र"]):
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
    # NOTE: a sample story is only a style/tone EXAMPLE — it never overrides
    # character selection. Characters come from finalized Stage-2 output or
    # from news-grounded creative generation below. The news always comes first.

    import random
    combined = f"{tone} {angle}".lower()
    context_text = f"{topic_or_script} {sample_story or ''}"
    is_sad = any(w in combined for w in ["sad", "heartbreak", "tragedy", "दुख", "दर्द", "शोक", "lament", "loss", "grief", "भावुक", "tragic", "emotional"])
    is_funny = any(w in combined for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "देसी", "मजाकिया", "रोस्ट", "edgy", "relatable", "joke"])
    is_culture = any(w in combined for w in ["culture", "heritage", "pride", "गौरव", "धरोहर", "traditional", "wisdom", "desi", "swag"])
    style_lower = scene_style.lower()
    is_argument = style_lower == "argument" or any(w in combined for w in ["argument", "बहस", "तकरार", "clash", "heated"])

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


# Styles where exactly ONE voice may speak (each with a distinct structure).
_SOLO_STYLES = {"speech", "monologue", "narration", "solo"}
# All styles with deterministic structural rules (everything except freeform dialogue).
_STRUCTURAL_STYLES = {"debate", "interview", "argument", "lament"} | _SOLO_STYLES


def _clean_speaker_names(speaker_names) -> list:
    names = [sanitize_persona_name(n or "").strip().upper() for n in (speaker_names or [])]
    return [n for n in names if n]


def get_dialogue_type_directive(scene_style: str, character_count: int, speaker_names=None) -> str:
    """Structural directive forcing the dialogue to honor the user's chosen dialogue type.

    Eight structurally distinct styles (never merged):
    - dialogue: reactive ping-pong conversation
    - argument: heated escalation, direct reactions
    - speech: ONE public speaker addressing a CROWD/audience (stage, rally, mic)
    - narration: ONE narrator telling a coherent third-person STORY
    - interview: fixed host/guest Q&A
    - debate: opposing positions, alternating rebuttals, final verdict
    - monologue: ONE speaker addressing the CAMERA/viewer intimately
    - lament: grief-focused, no jokes or laughter
    Roles are pinned to actual character names so the model never guesses who does what.
    """
    style = (scene_style or "dialogue").strip().lower()
    real = _clean_speaker_names(speaker_names)
    names = list(real)
    while len(names) < 2:
        names.append(f"SPEAKER {len(names) + 1}")
    A, B = names[0], names[1]
    solo_note = ""
    if len(real) < 2:
        solo_note = (
            "\n- Only one character is available: voice BOTH sides yourself, "
            "clearly switching stance from beat to beat."
        )

    if style == "interview":
        return (
            "DIALOGUE TYPE: INTERVIEW (strict Q&A)\n"
            f"- {A} is the HOST: asks ONLY sharp, short questions. Every host line MUST end with '?'.\n"
            f"- {B} is the GUEST: answers using the verified facts. The guest NEVER asks a question (no '?' in guest lines).\n"
            "- Beat order is law: odd beats (1, 3, 5) = host question; even beats (2, 4) = guest answer. No exceptions."
            + solo_note
        )
    if style == "debate":
        return (
            "DIALOGUE TYPE: DEBATE (structured for-vs-against)\n"
            f"- {A} DEFENDS the news development; {B} ATTACKS it. Sides NEVER swap, NEVER agree.\n"
            "- ONE speaker per beat. Beats strictly alternate: "
            f"{A}, {B}, {A}, {B}, ...\n"
            f"- Beat 1 ({A}): bold opening claim built on one verified fact.\n"
            "- Every later beat must FIRST directly rebut the previous beat's point, THEN add its own claim or fact.\n"
            "- Final beat: knockout verdict line for your side. No neutral filler, no changing the subject."
            + solo_note
        )
    if style == "argument":
        return (
            "DIALOGUE TYPE: HEATED ARGUMENT\n"
            f"- {A} and {B} alternate strictly, one speaker per beat.\n"
            "- Every line must DIRECTLY react to and escalate what the previous speaker just said.\n"
            "- Short, punchy, interruptive lines with high personal stakes. No calm exposition, no subject changes."
            + solo_note
        )
    if style == "speech":
        return (
            "DIALOGUE TYPE: SPEECH (one public speaker, live audience)\n"
            f"- ONLY {A} speaks \u2014 every single beat. This is a PUBLIC ADDRESS: a stage, rally, or gathering with a live crowd.\n"
            "- Address the CROWD ('doston', 'bhaiyon-behenon'), not the camera. Use rally cadence: slogans, pauses for applause, call-and-response.\n"
            "- Camera/action may show the cheering crowd; SFX may include applause/cheers. No second speaker, no dialogue exchange."
        )
    if style == "narration":
        return (
            "DIALOGUE TYPE: NARRATION (one storyteller, third-person story)\n"
            f"- ONLY {A} speaks \u2014 every single beat. {A} is a NARRATOR telling a coherent STORY about the news, in third person.\n"
            "- Story arc across beats: setup (what happened) \u2192 rising action (twist/impact) \u2192 payoff (what it means).\n"
            "- The narrator describes events and people ('phir kya hua...', 'wahan maujood log...'); never breaks into first-person direct address."
        )
    if style == "monologue":
        return (
            "DIALOGUE TYPE: MONOLOGUE (one speaker, intimate direct-to-camera)\n"
            f"- ONLY {A} speaks \u2014 every single beat, looking straight into the lens. This is PERSONAL, not a public rally.\n"
            "- Speak to the viewer as a confidant: open with a hook, use rhetorical questions as setups, land punchy payoffs.\n"
            "- First-person voice ('main aapko bata raha hoon...'). No crowd, no second voice, nobody answering back."
        )
    if style == "lament":
        return (
            "DIALOGUE TYPE: LAMENT (somber grief)\n"
            "- Slow, heavy lines of sorrow and solidarity about the news.\n"
            "- Absolutely NO jokes, banter, punchlines, or laughter \u2014 not in dialogue, not in SFX, nowhere."
        )
    return (
        "DIALOGUE TYPE: NATURAL CONVERSATION\n"
        "- Two people talking like real friends \u2014 relaxed, reactive ping-pong.\n"
        "- Balance humor with the verified news facts; every joke must come from a real fact."
    )


def _norm_speaker(name) -> str:
    return re.sub(r"\s*\(.*$", "", name or "").strip().upper()


def validate_dialogue_structure(scene_lines, scene_style: str, speaker_names=None) -> list:
    """Deterministic structural check of parsed beats against the dialogue type.

    Returns human-readable issue strings; empty means compliant. Only checks
    what is verifiable in code (speaker order, coverage, question marks,
    solo-voice, lament laughter ban) \u2014 never tone or wit.
    """
    style = (scene_style or "dialogue").strip().lower()
    if style == "dialogue":
        return []
    if not scene_lines:
        return ["no dialogue beats were parsed"]
    known = [_norm_speaker(n) for n in (speaker_names or [])]
    known = [k for k in known if k]
    beats = [(_norm_speaker(s.get("character")), (s.get("dialogue") or "").strip())
             for s in scene_lines]
    issues: list = []

    for i, (spk, _dlg) in enumerate(beats):
        if not spk:
            issues.append(f"beat {i + 1} has no speaker label")
        # NOTE: Unknown speaker names are NOT errors — the model is allowed
        # creative naming. We only require that every beat HAS a speaker.
        # The actual names are collected and propagated to downstream stages.

    if style in _SOLO_STYLES:
        uniq = [u for u in dict.fromkeys(b[0] for b in beats) if u]
        if len(uniq) > 1:
            issues.append(
                f"solo style '{style}' uses {len(uniq)} speakers ({', '.join(uniq)}); only ONE voice may speak"
            )
        return issues

    if style in ("debate", "interview", "argument", "lament"):
        if len(beats) > 1 and len(known) >= 2:
            for i in range(1, len(beats)):
                if beats[i][0] and beats[i][0] == beats[i - 1][0]:
                    issues.append(
                        f"beats {i} and {i + 1} are both spoken by {beats[i][0]}; "
                        f"'{style}' requires strict speaker alternation"
                    )
            if len(beats) >= len(known):
                # Check speaker COUNT, not specific names — the model may use
                # creative names. We need the right NUMBER of distinct voices.
                _uniq_speakers = set(b[0] for b in beats if b[0])
                if len(_uniq_speakers) < len(known):
                    issues.append(
                        f"only {len(_uniq_speakers)} distinct speaker(s) found, "
                        f"but {len(known)} characters required for '{style}'"
                    )
        if style == "interview":
            for i, (_spk, dlg) in enumerate(beats):
                is_q = dlg.rstrip().endswith("?")
                if i % 2 == 0 and not is_q:
                    issues.append(f"beat {i + 1} must be a HOST question ending with '?'")
                elif i % 2 == 1 and is_q:
                    issues.append(f"beat {i + 1} must be a GUEST answer and must not ask a question")
        if style == "lament":
            for i, (_spk, dlg) in enumerate(beats):
                # Latin laughter needs word boundaries; Devanagari vowel signs
                # (U+093E etc.) are not \w chars so \b fails there — match
                # the Devanagari runs directly instead.
                _laugh = re.search(r"(?i)\b(h[ae]){2,}\b", dlg)
                _laugh_hi = re.search(r"(\u0939\u093e){2,}|\u0939\u0902\u0938\u0940", dlg)
                if _laugh or _laugh_hi:
                    issues.append(f"beat {i + 1} contains laughter; lament forbids all jokes and laughter")
    return issues


# ---------------------------------------------------------------------------
# FORMAL-HINDI DETECTION (deterministic) + ONE corrective model pass.
# The model is instructed to write common-person Hindi, but it still slips in
# shuddh/bureaucratic phrasing (e.g. "अधिकार निर्गम" for "rights issue").
# find_formal_hindi() DETECTS those tokens. It never rewrites anything itself:
# blind global substitutions are unsafe (e.g. "युद्ध" -> "जंग" can corrupt a
# proper noun or fixed phrase). Instead, one corrective model pass receives the
# EXACT failed draft plus the flagged tokens, and rewrites ONLY the flagged
# lines in common-person Hindi while preserving everything else.
# ---------------------------------------------------------------------------
_FORMAL_HINDI_TOKENS = [
    # Literal shuddh translations of English terms -> what people actually say
    "अधिकार निर्गम", "प्राथमिकी", "आरोपपत्र", "अनुबंध",
    # Newsreader passive voice -> active spoken Hindi
    "जारी किया गया", "घोषणा की गई", "किया गया", "की गई", "किए गए",
    "दिया गया", "दी गई", "दिए गए", "बताया गया", "बताई गई",
    "लिया गया", "ली गई", "के द्वारा",
    # Bureaucratic connectors and connectors
    "के अंतर्गत", "का निधन हो गया", "के निधन", "हेतु", "एवं",
    "तथा", "परंतु", "किंतु", "तथापि", "यद्यपि", "अथवा", "अतः",
    "अतएव", "चूंकि", "इत्यादि", "फलस्वरूप", "परिणामस्वरूप",
    # Shuddh nouns common people replace with everyday words
    "दंडात्मक", "अर्थदंड", "धनराशि", "प्रारम्भ", "प्रारंभ",
    "स्वीकृति", "आवश्यकता", "महत्वपूर्ण", "अत्यंत", "अत्यधिक",
    "समाचारपत्र", "पुस्तकालय", "दूरभाष", "गृह मंत्रालय",
    "प्रदान करना", "उपयोग", "अनुमति", "नागरिक", "निवासी",
    "दुर्घटना", "घटनाक्रम", "विफल", "शीघ्र", "मात्र", "संपूर्ण",
    "प्रत्येक", "विभिन्न", "समीप", "निकट", "महोदय", "अनुरोध",
    "निवेदन", "सूचना", "मृतक", "शव", "चिकित्सक", "औषधि",
    "शल्य", "परीक्षा", "परिणाम", "विद्यालय", "महाविद्यालय",
    "वेतन", "रोज़गार", "कार्यालय", "सहकर्मी", "ऋण", "आयकर",
    "अर्थव्यवस्था", "उपभोक्ता", "गुणवत्ता", "विक्रेता",
]

_HI_LEFT = r"(?:(?<=^)|(?<=[\s\"\'\"\'(\[\-—]))"
_HI_RIGHT = r"(?=$|[\s\"\'\"\'.,!?।…\[\]\-:;)\-—])"

_formal_hindi_res = None


def _formal_hindi_patterns():
    global _formal_hindi_res
    if _formal_hindi_res is None:
        toks = sorted(_FORMAL_HINDI_TOKENS, key=len, reverse=True)
        _formal_hindi_res = [re.compile(_HI_LEFT + re.escape(t) + _HI_RIGHT) for t in toks]
    return _formal_hindi_res


def find_formal_hindi(text: str) -> list:
    """Return the distinct formal/bureaucratic Hindi tokens present in text.

    Detection only \u2014 never rewrites. The caller triggers one corrective
    model pass with the exact failed draft when this returns non-empty.
    """
    found = []
    if not text:
        return found
    for rx in _formal_hindi_patterns():
        for m in rx.finditer(text):
            if m.group(0) not in found:
                found.append(m.group(0))
    return found


_COMEDY_KEYWORDS = ["funny", "humor", "humour", "humorous", "comedy", "comic", "sarcasm", "satire", "satirical", "witty", "fun", "joke", "\u0939\u094d\u092f\u0942\u092e\u0930", "\u0926\u0947\u0938\u0940", "\u092e\u091c\u093e\u0915", "\u0939\u0902\u0938\u0940"]


def is_comedy_request(tone: str, angle: str) -> bool:
    """True when the requested tone/angle demands comedy — jokes become mandatory, not optional."""
    combined = f"{tone or ''} {angle or ''}".lower()
    return any(w in combined for w in _COMEDY_KEYWORDS)


# --- Generic clothing ban list (code-enforced, not just prompt) ---
_GENERIC_CLOTHING_PHRASES = [
    "everyday wear",
    "casual clothes",
    "t-shirt and jeans",
    "street casual wear",
    "everyday street casual",
    "normal clothes",
    "regular clothes",
    "daily wear",
]


def validate_clothing_specificity(characters: list) -> list:
    """Code-enforced: reject generic clothing descriptions.

    Checks each character's attire field for banned generic phrases.
    Returns issue strings; empty means all clothing is specific.
    """
    issues = []
    for idx, char in enumerate(characters or []):
        attire = ""
        if isinstance(char, dict):
            attire = str(char.get("attire", "") or char.get("clothing", ""))
        else:
            attire = str(getattr(char, "attire", "") or getattr(char, "clothing", ""))
        attire_lower = attire.lower()
        for banned in _GENERIC_CLOTHING_PHRASES:
            if banned in attire_lower:
                name = char.get("name", f"Character {idx + 1}") if isinstance(char, dict) else getattr(char, "name", f"Character {idx + 1}")
                issues.append(
                    f"{name}: clothing is generic ('{banned}'). "
                    "Must be situation-specific: job + news situation + scene, with colors, fabric, accessories."
                )
                break
    return issues


# --- SFX tone mismatch ban (code-enforced) ---
_COMEDIC_SFX_IN_SERIOUS = [
    "party horn",
    "slide whistle",
    "boing",
    "womp womp",
    "sad trombone",
    "record scratch",
    "fart",
]
_SERIOUS_TONES = ["sad", "sorrow", "grief", "tragic", "heartbreaking", "lament", "serious", "urgent", "breaking", "emotional"]


def validate_sfx_tone_match(scene_lines: list, tone: str) -> list:
    """Code-enforced: SFX must match the tone.

    Comedic SFX in serious/sad tones is a mismatch.
    Returns issue strings; empty means SFX tone is OK.
    """
    tone_lower = (tone or "").lower()
    is_serious = any(t in tone_lower for t in _SERIOUS_TONES)
    if not is_serious:
        return []
    issues = []
    for idx, beat in enumerate(scene_lines or []):
        sfx = ""
        if isinstance(beat, dict):
            sfx = str(beat.get("sfx", "") or beat.get("audio", ""))
        else:
            sfx = str(getattr(beat, "sfx", "") or getattr(beat, "audio", ""))
        sfx_lower = sfx.lower()
        for banned_sfx in _COMEDIC_SFX_IN_SERIOUS:
            if banned_sfx in sfx_lower:
                issues.append(
                    f"Beat {idx + 1}: SFX '{banned_sfx}' mismatches serious tone '{tone}'. "
                    "Use tone-appropriate SFX: somber ambience, silence, or subtle dramatic beats."
                )
                break
    return issues



def ai_judge_news_coverage(
    agent,
    scene_lines: List[Dict[str, str]],
    news_topic: str,
    hook: str,
    engine_mode: str = "first_local_then_agy",
) -> Tuple[bool, str]:
    """Ask the AI directly: does this dialogue state the news?

    This is the SOLE news-coverage validator (FR-16.1). There is NO
    token/regex matching: the judge reads ONLY the short news title /
    basic news content plus the dialogue, and verdicts whether a viewer
    can understand what happened in the news. The full verified-facts
    list is deliberately NOT passed here — facts belong to the writer's
    prompt and retry feedback, not to this basic-content check.

    Returns (verdict_ok, reason). The REASON is surfaced in the 3.2.2 UI
    output so the decision is verifiable, never a hidden black box.

    If the judge engine errors, returns (False, "\u26a0\ufe0f ...") — a
    visible warning carrying the error detail. It never silently passes
    and never silently fails: the check reports the warning, and the
    user decides whether to retry or accept via the normal retry/failure
    UI.
    """
    dialogue_text = "\n".join(
        f"Beat {i+1} ({sl.get('character', '?')}): {sl.get('dialogue', '')}"
        for i, sl in enumerate(scene_lines or [])
    )
    prompt = (
        "You are a news coverage validator. Determine if the dialogue below clearly communicates the news.\n\n"
        f"NEWS: {news_topic}\n"
        f"ANGLE: {hook}\n\n"
        f"DIALOGUE:\n{dialogue_text}\n\n"
        "QUESTION: Would a viewer who ONLY hears this dialogue (no visuals, no captions) understand WHAT news this is about — "
        "the key event and what happened?\n\n"
        "Consider: short-form mentions (e.g. 'Ola' for 'Ola Electric'), paraphrases, and Hindi transliterations all COUNT as stating the news. "
        "Generic filler ('\u092f\u0947 \u092c\u0921\u093c\u0940 \u0916\u092c\u0930 \u0939\u0948', '\u0939\u0932\u091a\u0932 \u0939\u094b \u0930\u0939\u0940 \u0939\u0948') with no specific event does NOT count.\n\n"
        "Answer in exactly this format:\n"
        "VERDICT: YES or NO\n"
        "REASON: one sentence explaining why"
    )
    try:
        response = agent.execute(prompt, engine_mode=engine_mode)
        # Parse verdict: look for "VERDICT: YES" or "VERDICT: NO"
        verdict_match = re.search(r"VERDICT:\s*(YES|NO)", response, re.IGNORECASE)
        reason_match = re.search(r"REASON:\s*(.+)", response, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else "No reason given by the judge"
        if verdict_match:
            is_ok = verdict_match.group(1).upper() == "YES"
            return is_ok, f"AI judge: VERDICT={'YES' if is_ok else 'NO'} \u2014 {reason}"
        # Fallback: check if response starts with YES/affirmative
        first_line = response.strip().split("\n")[0].upper()
        fallback_ok = "YES" in first_line and "NO" not in first_line.split("YES")[0]
        return fallback_ok, f"AI judge (free-form response, no VERDICT line): {reason}"
    except Exception as e:
        # Engine error: visible warning, never a silent pass or silent fail.
        # The calling check fails with this reason so the user sees exactly
        # what happened and decides whether to retry or accept.
        return False, (
            f"\u26a0\ufe0f AI news-coverage judge engine error ({type(e).__name__}: {e}). "
            "Coverage could not be verified \u2014 retry or accept manually."
        )


def ai_judge_tone_compliance(
    agent,
    scene_lines: List[Dict[str, str]],
    tone: str,
    angle: str,
    engine_mode: str = "first_local_then_agy",
) -> Tuple[bool, str]:
    """Ask the AI directly: does this dialogue maintain the required tone?

    Keyword matching for tone (funny/sad/etc.) is brittle — the AI judge
    understands humor, emotion, and tone semantically.

    Returns (is_compliant, feedback). If not compliant, feedback describes
    the specific issue so it can be fed back to the AI for regeneration.
    """
    dialogue_text = "\n".join(
        f"Beat {i+1} ({sl.get('character', '?')}): {sl.get('dialogue', '')}"
        for i, sl in enumerate(scene_lines or [])
    )
    total_beats = len(scene_lines or [])
    required_beats = (total_beats * 7 + 9) // 10  # 70% rounded up

    prompt = (
        "You are a tone compliance validator for short Hindi comedy/drama reels.\n\n"
        f"REQUIRED TONE: {tone}\n"
        f"ANGLE: {angle}\n"
        f"TOTAL BEATS: {total_beats} (at least {required_beats} beats must clearly embody the tone)\n\n"
        f"DIALOGUE:\n{dialogue_text}\n\n"
        "QUESTION: Does this dialogue maintain the required tone?\n\n"
        "For FUNNY/HUMOROUS tone: at least 70% of beats must have genuine humor — "
        "a real setup and punchline, witty observations, funny exaggerations, relatable comedy. "
        "Mild amusement or neutral fact-delivery does NOT count as funny.\n"
        "For SAD/LAMENT/SORROW tone: at least 70% of beats must be CLEARLY emotional, "
        "grief-stricken, sorrowful, or heartbreaking — not just neutral or informational. "
        "A beat that is merely 'hopeful' or 'informational' does NOT count as sad. "
        "ZERO jokes, ZERO laughter, ZERO comedic beats. Somber throughout.\n"
        "For other tones: the emotional quality must be present in most beats, never contradicted.\n\n"
        "Answer in exactly this format:\n"
        "VERDICT: YES or NO\n"
        "FUNNY_BEATS: <count> out of <total> (for funny tone; else N/A)\n"
        "ISSUE: <one sentence describing the specific problem, or 'None' if compliant>"
    )
    try:
        response = agent.execute(prompt, engine_mode=engine_mode)
        verdict_match = re.search(r"VERDICT:\s*(YES|NO)", response, re.IGNORECASE)
        is_ok = verdict_match.group(1).upper() == "YES" if verdict_match else False
        issue_match = re.search(r"ISSUE:\s*(.+)", response, re.IGNORECASE)
        issue = issue_match.group(1).strip() if issue_match else "Tone not maintained"
        if is_ok:
            return True, ""
        return False, issue
    except Exception:
        # If AI judge fails, fall back to assuming non-compliance so the
        # corrective pass can attempt a fix rather than shipping silently.
        return False, "Tone compliance could not be verified"


def get_role_identity(scene_style: str, tone: str, angle: str) -> str:
    """Role priming for the dialogue writer: a funny screenwriter identity when comedy is requested."""
    if is_comedy_request(tone, angle):
        return (
            "You are a FUNNY SCREENWRITER for viral Hindi comedy reels \u2014 a joke writer, not a news reporter. "
            f"You are writing a {angle or 'Funny'} {scene_style or 'Dialogue'} reel. "
            "Your job is making people LAUGH while delivering the verified news \u2014 every funny beat needs a real joke."
        )
    return "You are a master Hindi Dialogue & Voiceover Scriptwriter for short reels and videos."


def get_creative_guidelines(scene_style: str, character_count: int, tone: str, angle: str) -> str:
    """Generate explicit directives to ensure AI respects Angle (creative situation), Tone (jokes/emotions), and Style."""
    combined = f"{tone} {angle}".lower()
    is_sad = any(w in combined for w in ["sad", "heartbreak", "tragedy", "दुख", "दर्द", "शोक", "lament", "loss", "grief", "भावुक", "tragic", "emotional"])

    # Angle Guidance
    angle_guidance = (
        f"🎨 EDITORIAL ANGLE DIRECTIVE ({angle or 'Creative Angle'}):\n"
        f"- The angle dictates HOW you imagine and set up the scene!\n"
        f"- Do NOT just report dry news. Create an imaginary relatable situation, sketch, or scenario:\n"
        f"  * If Tragic & Heartbreaking: Frame through a quiet, solemn moment of personal loss, deep empathy, and emotional vulnerability.\n"
        f"  * If Funny & Relatable: Create an everyday situation (e.g. friends dealing with hilarious daily absurdities at home or at work).\n"
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
    elif is_comedy_request(tone, angle):
        tone_guidance = (
            f"😂 TONE DIRECTIVE ({tone}) — COMPLIANCE IS MANDATORY, NOT OPTIONAL:\n"
            f"- AT LEAST 70% OF BEATS (round up) must be GENUINELY FUNNY. A comedy reel that is mostly dry news recitation is a SYSTEM BUG.\n"
            f"- JOKE MANDATE: every funny beat must contain at least one REAL JOKE — a setup followed by a punchline. A 'humorous tone' with no actual joke is a FAILURE.\n"
            f"- Joke tools (use at least 2 across the reel): exaggerate the news absurdity, rule of three, callback to an earlier beat, misdirection, relatable everyday comparison (rent, traffic, relatives, jugaad).\n"
            f"- Solo Speech/Monologue: speak directly to the viewer — rhetorical question as setup, then punchline; callback the opening joke in the final beat.\n"
            f"- The remaining beats may deliver straight facts but must stay NEUTRAL — never somber, never dark, never contradicting the comedy.\n"
            f"- Characters react with funny shock, tease each other mercilessly, and make hilarious relatable comparisons to everyday Indian life.\n"
            f"- Comedy comes FROM the news facts: exaggerate the absurdity, roast the irony, land meme-worthy punchlines grounded in verified facts.\n"
            f"- Audio/SFX for comedic tone MUST include comedic background music AND laughter in beats where humor lands.\n"
            f"- SELF-CHECK: count your beats — at least 70% funny, zero beats contradicting the tone. Rewrite failures before emitting."
        )
    elif any(w in combined for w in ["viral", "high energy", "धमाकेदार"]):
        tone_guidance = (
            f"🔥 TONE DIRECTIVE ({tone}):\n"
            f"- High-voltage excitement! Deliver shock-value hooks, explosive energy, and dramatic pacing."
        )
    elif any(w in combined for w in ["culture", "heritage", "pride", "desi", "swag", "गौरव"]):
        tone_guidance = (
            f"🪔 TONE DIRECTIVE ({tone}):\n"
            f"- Celebrate timeless Indian heritage, deep cultural pride, and respectful desi swag with authentic idioms."
        )
    elif any(w in combined for w in ["argument", "बहस", "तकरार", "clash", "heated"]):
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
    elif style_lower == "monologue":
        style_guidance = (
            "🎙️ SCENE STYLE DIRECTIVE: MONOLOGUE:\n"
            "- Intimate direct-to-camera address: ONE speaker talking to the viewer as a confidant, "
            "first-person voice, hook → build → payoff."
        )
    else:
        style_guidance = (
            "📖 SCENE STYLE DIRECTIVE: NARRATION:\n"
            "- ONE narrator telling a coherent third-person STORY about the news: setup → twist → payoff. "
            "The narrator describes events and people; never breaks into first-person direct address."
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


def run_validation_checks_fail_fast(check_specs, stage_prefix, val_num, emit=None):
    """Generic fail-fast ordered validation runner.

    check_specs: list of dicts, each with:
        "sub": str          - sub-check number, e.g. "1" -> key "3.2.1"
        "name": str         - display name, e.g. "Structure check"
        "input": str        - input description shown in the UI
        "start_detail": str - optional live detail emitted on start
        "run": callable     - () -> {"problems": [str], "pass_output": str,
                                     "feedback": str}
    stage_prefix: e.g. "3" -> check keys "3.2.1".."3.2.4".
    val_num: validation step number, e.g. 2.
    emit: optional callable(stage, name, phase, **details) for live progress.

    Checks run in list order -- the caller orders them by failure likelihood,
    most failure-prone first, so fail-fast catches the likeliest problem
    immediately. On the first failure the remaining checks are NOT executed:
    they are recorded as skipped ("passed": None, "skipped": True,
    "skipped_due_to": "<stage key> <name>") and the caller should proceed
    directly to retry. Re-validation then runs all checks fresh.

    Returns (sub_checks, feedback_parts): recorded check dicts
    (passed True / False / None for skipped) and retry feedback for the
    FIRST failure only.
    """
    sub_checks = []
    feedback_parts = []
    failed_ref = None
    for spec in check_specs:
        stage_key = f"{stage_prefix}.{val_num}.{spec['sub']}"
        name = spec["name"]
        if failed_ref is not None:
            # Fail-fast: do not execute -- record explicitly as skipped.
            skip_note = f"Skipped ({failed_ref} failed)"
            sub_checks.append({
                "stage": stage_key,
                "name": name,
                "input": spec.get("input", ""),
                "output": skip_note,
                "passed": None,
                "skipped": True,
                "skipped_due_to": failed_ref,
            })
            if emit is not None:
                emit(stage_key, name, "complete", status="skipped",
                     detail=f"{failed_ref} failed",
                     input=spec.get("input", "")[:300],
                     output=skip_note)
            continue
        if emit is not None:
            _start_kw = {"detail": spec["start_detail"]} if spec.get("start_detail") else {}
            emit(stage_key, name, "start", **_start_kw)
        result = spec["run"]() or {}
        problems = result.get("problems") or []
        passed = not problems
        output = result.get("pass_output", "Passed") if passed else "; ".join(problems)
        sub_checks.append({
            "stage": stage_key,
            "name": name,
            "input": spec.get("input", ""),
            "output": output,
            "passed": passed,
        })
        if emit is not None:
            emit(stage_key, name, "complete",
                 status="pass" if passed else "fail",
                 detail=output[:200],
                 input=spec.get("input", "")[:300],
                 output=output[:300])
        if not passed:
            failed_ref = f"{stage_key} {name}"
            if result.get("feedback"):
                feedback_parts.append(result["feedback"])
    return sub_checks, feedback_parts


class DialogueNarrationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Dialogue & Narration Scriptwriter",
            role="Spoken Dialogue Writing & Timeline Calibration",
            icon="🎙️",
            instructions=DIALOGUE_INSTRUCTIONS,
            prompt_file="dialogue_writer/write_dialogue.md",
        )

    def _enrich_new_speakers(self, new_names, narrations, news_input):
        """Generate character profiles for speaker names the model invented.
        Uses deterministic defaults (no blocking AI calls) to avoid hangs.
        Downstream stages get complete profiles immediately."""
        if not hasattr(self, '_enriched_profiles'):
            self._enriched_profiles = {}
        for _name in new_names:
            # Use the name as-is with sensible defaults — no AI call, no hang risk.
            self._enriched_profiles[_name] = {
                "name": _name,
                "role_or_job": "Key Character / Speaker",
                "attire": "Authentic everyday attire",
                "emotional_stance": "Engaged & authentic",
            }

    def _emit_substep(self, on_substep, substep, name, phase, **details):
        """Emit a live Stage 3 substep event (no-op when on_substep is None)."""
        if on_substep is None:
            return
        try:
            on_substep({"substep": substep, "name": name, "phase": phase,
                        "stage": 3, **details})
        except Exception:
            pass

    def _record_stage_step(self, stage, name, input_text, output_text, passed, sub_checks=None):
        """Record a Stage 3 step with linear numbering (3.1, 3.2, 3.3...).

        - 3.1, 3.3, 3.5... = generation steps (odd numbers)
        - 3.2, 3.4, 3.6... = validation steps (even numbers)
        - Validation steps contain sub_checks: 3.2.1, 3.2.2, 3.2.3, 3.2.4
        Each step records its input and output for UI display.
        """
        if not hasattr(self, 'last_validation_steps') or self.last_validation_steps is None:
            self.last_validation_steps = []
        self.last_validation_steps.append({
            "stage": stage,
            "name": name,
            "input": input_text or "",
            "output": output_text or "",
            "passed": passed,
            "sub_checks": sub_checks or [],
        })

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
            if not final_text:
                raise ModelGenerationError(
                    f"Stage 3 dialogue generation failed: model returned empty output. "
                    f"Raw output snippet: {(raw_output or '')[:500]!r}",
                    partial_output=raw_output or "",
                )
            return final_text
        except ModelGenerationError:
            raise
        except Exception as e:
            # Fail loudly: never silently fall back to hook+topic concatenation.
            raise ModelGenerationError(
                f"Stage 3 dialogue generation failed: {type(e).__name__}: {e}",
                partial_output="",
            )

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
        previous_draft: Optional[str] = None,
        feedback: Optional[str] = None,
        finalized_characters: Optional[List[CharacterProfile]] = None,
        finalized_scenes: Optional[List[SceneSettingOption]] = None,
        story_steps: Optional[List[StoryBeatStep]] = None,
        _retry_round: int = 0,
        _max_retries: int = 3,
        attempt_history: Optional[List[str]] = None,
        on_substep=None,
    ) -> List[ScriptDialogue]:
        """Craft spoken Hindi dialogues for all items scene-by-scene respecting character count, style, tone, and angle.

        Linear retry flow with three-level numbering:
        - 3.1, 3.3, 3.5... = generation steps (odd)
        - 3.2, 3.4, 3.6... = validation steps (even), each with 3.x.1-3.x.4 sub-checks
        """
        # Retry tracking: attempt_history collects every attempt's raw_output.
        # last_validation_steps collects linear 3.1/3.2/3.3... steps for UI.
        if attempt_history is None:
            attempt_history = []
            # Outermost call: reset linear step tracking.
            self.last_validation_steps = []
        self.last_attempt_history = list(attempt_history)
        self.last_retry_count = _retry_round
        budget = get_duration_budget(duration_sec)
        guidance = get_sentence_guidance(duration_sec, budget["recommended_words"], budget["max_words"])

        if finalized_characters and len(finalized_characters) > 0:
            personas = [
                f"{c.name} ({c.role_or_job}, Attire: {c.attire}, Emotional Stance: {c.emotional_stance})"
                for c in finalized_characters[:character_count]
            ]
        else:
            personas = get_character_personas(
                scene_style, character_count, tone, preferred_angle,
                topic_or_script=news_input, sample_story=sample_story
            )
        creative_rules = get_creative_guidelines(scene_style, character_count, tone, preferred_angle)

        # Defensive: never enter generation with fewer personas than configured.
        if len(personas) < character_count:
            _need = character_count - len(personas)
            _have_first = set()
            for _pp in personas:
                _t = re.findall(r"[\w]+", _pp.lower(), flags=re.UNICODE)
                if _t:
                    _have_first.add(_t[0])
            for _gp in get_character_personas(
                scene_style, character_count + _need, tone, preferred_angle,
                topic_or_script=news_input, sample_story=sample_story,
            ):
                _gt = re.findall(r"[\w]+", _gp.lower(), flags=re.UNICODE)
                if _gt and _gt[0] in _have_first:
                    continue
                personas.append(_gp)
                if _gt:
                    _have_first.add(_gt[0])
                if len(personas) >= character_count:
                    break

        # Dynamic scene count: respect user override, story steps count, or calculate from duration
        if num_scenes is not None and 1 <= num_scenes <= 5:
            actual_scenes = num_scenes
        elif story_steps and len(story_steps) > 0:
            actual_scenes = min(len(story_steps), 5)
        elif duration_sec <= 8 and (scene_style.lower() in ["speech", "monologue"] or character_count == 1):
            actual_scenes = 1
        elif duration_sec <= 15:
            actual_scenes = 2
        elif duration_sec <= 35:
            actual_scenes = 3
        else:
            actual_scenes = budget.get("scenes", 3)

        # Every configured character must speak at least once: never run fewer
        # beats than speaking characters (capped at 5 scenes max).
        if character_count > 1:
            actual_scenes = max(actual_scenes, min(character_count, 5))

        per_scene_words = max(6, budget["recommended_words"] // actual_scenes)
        per_scene_max = max(8, budget["max_words"] // actual_scenes + 2)

        sample_directive = ""
        if sample_story and sample_story.strip():
            sample_directive = (
                f"\n📌 SAMPLE EXAMPLE (style/format reference ONLY \u2014 lowest precedence):\n"
                f"\"{sample_story.strip()}\"\n"
                f"Generate from the NEWS facts above with your own creativity. This sample is ONLY an "
                f"example of tone and format \u2014 do NOT copy its characters, plot points, or dialogue lines. "
                f"If the sample conflicts with the verified news facts or the locked characters above, "
                f"the NEWS and the LOCKED decisions win.\n"
            )

        items_desc = "\n\n".join([
            f"SCRIPT {i+1}:\nAngle: {it['angle']}\nHook idea (express in your own natural spoken Hindi — NEVER quote verbatim): {clean_hook_for_dialogue(it['hook'])}"
            for i, it in enumerate(items)
        ])

        facts_text = "\n".join(['- ' + f for f in (verification.verified_facts if verification else [])[:3]]) if (verification and verification.verified_facts) else f"- {news_input[:80]}"
        props_text = ", ".join(verification.physical_props) if (verification and verification.physical_props) else ""
        locs_text = ", ".join(verification.key_locations) if (verification and verification.key_locations) else ""
        conflict_text = verification.core_conflict_or_irony if (verification and verification.core_conflict_or_irony) else ""

        # --- New pipeline order: scenes are DERIVED from the dialogue afterwards ---
        # When finalized_scenes is provided (legacy path) the dialogue setting uses
        # them; when it is None (current pipeline) no locations are fixed yet and
        # the model is instructed to paint concrete, filmable settings in every
        # beat so the scene-derivation stage has real material to extract.
        beat_scene_settings: List[Dict[str, str]] = []
        if finalized_scenes:
            for sc in finalized_scenes:
                beat_scene_settings.append({
                    "location": sc.location_name,
                    "atmosphere": sc.atmosphere or "",
                    "lighting": sc.lighting_mood or "",
                    "props": ", ".join(sc.props) if sc.props else "",
                })
        setting_location_text = locs_text or "Authentic Indian street or workplace setting"
        if beat_scene_settings:
            scene_setting_lines = "\n".join([
                f"- Beat {i + 1} setting: {s['location']}"
                + (f" | Atmosphere: {s['atmosphere']}" if s["atmosphere"] else "")
                + (f" | Lighting: {s['lighting']}" if s["lighting"] else "")
                + (f" | Props in frame: {s['props']}" if s["props"] else "")
                for i, s in enumerate(beat_scene_settings)
            ])
            setting_location_text = "; ".join(s["location"] for s in beat_scene_settings)
        else:
            scene_setting_lines = (
                "- SCENE DERIVATION NOTICE: No shoot locations are fixed yet. A scene designer "
                "will build the shoot locations FROM your dialogue beats after this step. Therefore "
                "every beat's Camera Focus & Action line MUST paint a CONCRETE, specific, filmable "
                "location (a particular shop, office cabin, street corner, home room - never vague like "
                "'the setting') with visible props and character actions. Vague settings will be "
                "flagged as errors in validation."
            )

        # --- Respect the user's chosen dialogue type (scene_style) structurally ---
        # Extract speaker names from personas so the directive pins roles to real names.
        _speaker_names = []
        for _p in personas:
            _m = re.match(r"\s*([^(\n]+)", _p or "")
            if _m and _m.group(1).strip():
                _speaker_names.append(_m.group(1).strip())
        dialogue_type_directive = get_dialogue_type_directive(scene_style, character_count, _speaker_names)

        # --- Role priming: funny screenwriter identity when comedy is requested ---
        _eff_angle = (items[0].get("angle") if items else "") or preferred_angle or ""
        role_identity = get_role_identity(scene_style, tone, _eff_angle)

        sub_directive = f"\nChief Editor Directive & Dialogue Word Limits:\n{sub_instruction}\n" if sub_instruction else ""

        # Dynamic narrative mode selection: randomly decide position of news and flow per script run
        chosen_narrative = random.choice(NARRATIVE_MODES)
        n_mode = chosen_narrative["mode_key"]

        # Dynamically build continuous-shot beat templates for 1 to 5 scenes
        scene_templates = []
        for s_idx in range(1, actual_scenes + 1):
            matching_step = story_steps[s_idx - 1] if (story_steps and s_idx <= len(story_steps)) else None
            # Each beat plays in its Stage 2 finalized scene (cycled if fewer scenes than beats)
            _beat_setting = beat_scene_settings[(s_idx - 1) % len(beat_scene_settings)] if beat_scene_settings else None
            if _beat_setting:
                beat_setting_text = _beat_setting["location"]
                beat_setting_line = (
                    f"{_beat_setting['location']}"
                    + (f" | {_beat_setting['atmosphere']}" if _beat_setting["atmosphere"] else "")
                    + (f" | Lighting: {_beat_setting['lighting']}" if _beat_setting["lighting"] else "")
                    + (f" | Props: {_beat_setting['props']}" if _beat_setting["props"] else "")
                )
            else:
                beat_setting_text = locs_text or "the setting"
                beat_setting_line = beat_setting_text
            if matching_step:
                char_s = matching_step.character_name
            else:
                char_s = personas[(s_idx - 1) % len(personas)]

            if matching_step:
                label = f"BEAT {s_idx} (Shot {s_idx})"
                act = f"{matching_step.action_step}"
                dial = f"Conversational Hindi dialogue fulfilling goal: {matching_step.speech_objective}"
            elif actual_scenes == 1:
                label = f"BEAT 1 (Continuous Master Shot: Complete Story)"
                act = f"Single continuous vertical shot in {beat_setting_text}; character holds {props_text or 'key prop'}, delivering complete narrative fluidly"
                dial = "Dynamic Hindi dialogue stating what happened, the context, and key takeaway in one fluid take"
            elif n_mode == "fun_first":
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Hilarious Banter / Misunderstanding)"
                    act = f"Continuous shot starts in {beat_setting_text}; characters engaged in witty relatable banter or comedic misconception"
                    dial = "Witty, humorous Hindi conversational opener establishing a relatable premise (NO direct news drop yet)"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: The Shocking News Reveal)"
                    act = f"Camera smoothly pivots/refocuses; character pulls out {props_text or 'smartphone/document'} revealing the verified news facts"
                    dial = "Sharp Hindi reality check dropping the actual news facts and context, shattering the previous illusion"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Humorous Punchline & Resolution)"
                    act = f"Camera holds continuous framed reaction; crowd or companions react as character lands the punchline"
                    dial = "Logical concluding Hindi line delivering witty punchline, satirical twist, or meme takeaway"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Escalation & Fact Evidence)"
                    act = f"Camera reframes; examining {props_text or 'the physical object'} with verified details"
                    dial = "Conversational Hindi counterpoint or startling fact"
            elif n_mode == "mid_conversation":
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Everyday Life Routine & Banter)"
                    act = f"Continuous shot begins in {beat_setting_text}; characters debating daily life, work, or routine matters"
                    dial = "Relatable conversational Hindi dialogue reflecting daily Indian hustle or workplace debate"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: Sudden News Bombshell Discovery)"
                    act = f"Camera tracks over shoulder as character notices breaking news on {props_text or 'smartphone screen/paper'} with wide-eyed shock"
                    dial = "Urgent Hindi line interrupting the banter with the shocking verified news headline and fact"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Mutual Shock & Comic Resolution)"
                    act = f"Camera captures both characters in continuous two-shot sharing mutual disbelief and reaction"
                    dial = "Witty concluding Hindi line re-evaluating their situation in light of the news"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Examining the Evidence)"
                    act = f"Camera continuously pans; verifying {props_text or 'the details'} together"
                    dial = "Conversational Hindi detail verifying the bizarre fact"
            elif n_mode == "curiosity_first":
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Puzzling Observation / Mystery)"
                    act = f"Continuous shot opens in {beat_setting_text}; character points out a puzzling event or strange crowd behavior"
                    dial = "Intriguing Hindi observation questioning what on earth is happening"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: Unpacking the News Mystery)"
                    act = f"Camera reframes smoothly; second character reveals the real verified news backstory holding {props_text or 'key prop'}"
                    dial = "Hindi explanation revealing the verified facts and why this event is actually taking place"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Satirical Realization & Payoff)"
                    act = f"Camera holds the final reaction framed against the ongoing backdrop"
                    dial = "Memorable Hindi punchline or eye-opening satirical takeaway"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Deeper Revelation)"
                    act = f"Camera reframes dynamically to show public reaction"
                    dial = "Surprising Hindi supporting fact or evidence"
            else:  # news_first default
                if s_idx == 1:
                    label = f"BEAT 1 (Shot 1: Breaking Hook & Disruption)"
                    act = f"Continuous shot starts in {beat_setting_text}; character disrupts with breaking news holding {props_text or 'the news'}"
                    dial = "Attention-grabbing Hindi hook line clearly introducing what happened and where"
                elif s_idx == 2:
                    label = f"BEAT 2 (Shot 2: Fact Counterpoint & Interaction)"
                    act = f"Camera continuously refocuses; second character responds directly examining {props_text or 'the physical object'}"
                    dial = "Hindi dialogue answering Beat 1 with verified facts and contextual depth"
                elif s_idx == actual_scenes:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Payoff & Resolution)"
                    act = f"Camera captures concluding two-shot; characters deliver final verdict"
                    dial = "Logical concluding Hindi line delivering witty payoff, punchline, or impact"
                else:
                    label = f"BEAT {s_idx} (Shot {s_idx}: Evidence & Escalation)"
                    act = f"Camera pivots continuously; revealing startling evidence"
                    dial = "Conversational Hindi counterpoint or startling fact"

            spk = sanitize_persona_name(char_s.split("(")[0].strip()).upper() or f"SPEAKER{s_idx}"
            scene_templates.append(
                f"BEAT {s_idx}:\n"
                f"Camera Focus & Action: [{act}]\n"
                f"Audio/SFX: [Background music bed fitting the tone + ambient scene SFX + laughter where the beat is funny]\n"
                f"Text Overlay (Optional): [Short punchy ENGLISH popup text only if it adds punch]\n"
                f"{spk}: \"[{dial}]\""
            )
        _cast_lines = "\n".join(
            f"\u26ac [{sanitize_persona_name(p.split('(')[0].strip()).upper()} ({sanitize_persona_name(p.split('(')[0].strip())}): English clothing/appearance description]"
            for p in personas[:character_count]
        )
        sample_scenes = (
            "[Format Requirement: All scene descriptions in English, Dialogues strictly in Hindi]\n\n"
            "SCENE DETAIL:\n"
            f"\u26ac [{setting_location_text} \u2014 vivid English description of the location, vibe and energy]\n\n"
            "CHARACTERS & CLOTHING:\n"
            f"{_cast_lines}\n\n"
            + "\n\n".join(scene_templates)
        )

        revision_directive = ""
        if previous_draft and previous_draft.strip():
            fb_text = feedback.strip() if feedback and feedback.strip() else (sub_instruction or "Improve character interconnectedness and reactive flow.")
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING and REFINING an existing dialogue draft based on user feedback.\n"
                f"Do NOT generate disconnected lines. Use this previous draft as the reference baseline and directly resolve the user's critique:\n\n"
                f"PREVIOUS DRAFT:\n{previous_draft.strip()}\n\n"
                f"USER CORRECTION FEEDBACK:\n{fb_text}\n\n"
                f"CORRECTION MANDATE:\n"
                f"- Directly address and fix the issues in the user's feedback.\n"
                f"- Make character lines tightly INTERCONNECTED: use rapid reactive ping-pong, emotional replies, and direct rebuttals to what the previous speaker said.\n"
                f"- Keep total spoken dialogue strictly within ~{budget['recommended_words']} words (max {budget['max_words']} words).\n"
            )
        elif feedback and feedback.strip():
            # First run carrying a user instruction (no previous draft yet): apply
            # it to the fresh generation. On retry the dedicated refine prompt
            # above is the sole feedback carrier instead.
            revision_directive = (
                f"\n# ⭐ USER EXTRA INSTRUCTION (HIGH PRIORITY):\n"
                f"{feedback.strip()}\n"
                f"Apply this instruction while writing the dialogue below.\n"
            )

        prompt = render_prompt(
            "dialogue_writer/write_dialogue_batch.md",
            role_identity=role_identity,
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
            character_count=character_count,
            personas_list="\n".join(["- " + p for p in personas]),
            setting_location=setting_location_text,
            scene_setting_lines=scene_setting_lines,
            dialogue_type_directive=dialogue_type_directive,
            physical_props=props_text or "Specific physical objects in the news story",
            core_conflict=conflict_text or "The central viral story hook",
            facts_text=facts_text,
            creative_rules=creative_rules,
            sample_directive=sample_directive,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
            guidance=guidance,
            items_desc=items_desc,
            sample_scenes=sample_scenes,
            tone=tone,
        )

        # --- RETRY PATH: dedicated refine prompt (not the generation prompt) ---
        # A retry refines the exact previous visible draft with the user's custom
        # instruction. All creative decisions are LOCKED: same characters, same
        # count, same angle/hook meaning, same dialogue type, same word budget.
        # No narrative re-roll, no persona re-selection — a surgical refinement.
        if previous_draft and previous_draft.strip():
            if finalized_characters and len(finalized_characters) > 0:
                speaker_names = [c.name for c in finalized_characters[:character_count]]
            else:
                speaker_names = [
                    re.sub(r"^[^\w\u0900-\u097F]+", "", p).split("(")[0].strip() or p
                    for p in personas[:character_count]
                ]
            retry_angle = (items[0].get("angle") if items else "") or preferred_angle or ""
            retry_hook = clean_hook_for_dialogue(items[0].get("hook", "")) if items else ""
            prompt = render_prompt(
                "dialogue_writer/refine_dialogue_batch.md",
                character_count=character_count,
                speaker_names_list="\n".join(f"- {n}" for n in speaker_names),
                angle=retry_angle,
                tone=tone,
                hook_idea=retry_hook,
                dialogue_type_name=scene_style or "Dialogue",
                dialogue_type_directive=dialogue_type_directive,
                rec_words=budget["recommended_words"],
                max_words=budget["max_words"],
                previous_draft=previous_draft.strip(),
                feedback=(feedback.strip() if feedback and feedback.strip()
                          else "Improve character interconnectedness and reactive flow."),
            )

        _gen_num_early = 2 * _retry_round + 1
        _gen_name_early = "Dialogue generation" if _retry_round == 0 else f"Retry generation {_retry_round}"
        self._emit_substep(on_substep, f"3.{_gen_num_early}", _gen_name_early, "start",
                           detail=f"Writing dialogue (attempt {_retry_round + 1})",
                           input=f"News: {(news_input or '')[:150]}\nVibe: {tone} | Style: {scene_style}")
        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            # Fail loudly: never substitute silent synthetic output for a
            # model failure. The stage reports the error and the UI keeps
            # the previous stages' output visible for retry.
            raise ModelGenerationError(
                f"Stage 3 dialogue generation failed (engine={engine_mode}): "
                f"{type(e).__name__}: {e}"
            ) from e

        # Record this attempt's raw output. Recursive retry calls re-enter this
        # function, so attempt_history accumulates [attempt1, attempt2, ...].
        if raw_output:
            attempt_history.append(raw_output)
        self.last_attempt_history = list(attempt_history)

        parsed_map = {}
        # Parse blocks by SCRIPT header (supporting markdown like **SCRIPT 1:**, ### SCRIPT 1, etc.)
        blocks = re.split(r"(?:###|\*\*|##)?\s*SCRIPT\s*(\d+)\s*(?:\*\*)?\s*:\s*", raw_output, flags=re.IGNORECASE)

        def _beat_timestamp(s_num: int) -> str:
            # Beat timings are computed deterministically in code — the model is
            # never asked to write timestamps (it gets clock arithmetic wrong).
            per = duration_sec / max(1, actual_scenes)
            start = (s_num - 1) * per
            end = s_num * per
            def _fmt(t):
                return f"{int(t // 60)}:{int(t % 60):02d}"
            return f"{_fmt(start)} - {_fmt(end)}"

        def _match_persona(name: str) -> str:
            nl = name.strip().lower()
            for p in personas:
                pl = p.split("(")[0].strip()
                pll = pl.lower()
                if nl == pll or nl in pll or pll in nl:
                    return pl
            return name.strip()

        def parse_scene_block(content: str) -> List[Dict[str, str]]:
            # Tolerate legacy/alternative [Time: 0:00 - 0:04] headers: when no
            # BEAT/SCENE headers exist, convert them to sequential BEAT markers.
            if not re.search(r"(?:SCENE|PART|BEAT)\s*\d+", content, flags=re.IGNORECASE):
                _bc = [0]
                def _time_to_beat(m):
                    _bc[0] += 1
                    return f"\nBEAT {_bc[0]}:"
                content = re.sub(r"\[Time:[^\]\n]*\]", _time_to_beat, content, flags=re.IGNORECASE)
            scene_chunks = re.split(r"(?:###|\*\*|##)?\s*(?:SCENE|PART|BEAT)\s*(\d+)[^:]*:\s*", content, flags=re.IGNORECASE)
            script_scenes = []
            if len(scene_chunks) > 1:
                for s_idx in range(1, len(scene_chunks), 2):
                    s_num = int(scene_chunks[s_idx])
                    s_body = scene_chunks[s_idx + 1]
                    char_name = _match_persona(personas[(s_num - 1) % len(personas)]) if personas else ""
                    dial_text = ""
                    action_text = ""
                    sfx_text = ""
                    overlay_text = ""
                    for line in s_body.split("\n"):
                        ls = line.strip()
                        if not ls or ls.startswith("\u26ac"):
                            continue
                        clean_ls = re.sub(r"^\*+|\*+$", "", ls).strip()
                        upper_ls = clean_ls.upper()
                        if upper_ls.startswith("CAMERA FOCUS"):
                            action_text = clean_ls.split(":", 1)[-1].strip("[] \"'*")
                        elif upper_ls.startswith("AUDIO/SFX:") or upper_ls.startswith("SFX:") or upper_ls.startswith("AUDIO:"):
                            sfx_text = clean_ls.split(":", 1)[-1].strip("[] \"'*")
                        elif upper_ls.startswith("TEXT OVERLAY"):
                            overlay_text = clean_ls.split(":", 1)[-1].strip("[] \"'*\u201c\u201d")
                        elif upper_ls.startswith("CHARACTER:"):
                            char_name = _match_persona(clean_ls.split(":", 1)[-1].strip("[] \"'*"))
                        elif upper_ls.startswith("ACTION:") or upper_ls.startswith("BACKGROUND & ACTION:") or upper_ls.startswith("BACKGROUND & VISUAL ACTION:") or upper_ls.startswith("BACKGROUND:") or upper_ls.startswith("VISUAL:"):
                            action_text = clean_ls.split(":", 1)[-1].strip("[] \"'*")
                        elif upper_ls.startswith("DIALOGUE:") or upper_ls.startswith("LINE:"):
                            dial_text = clean_hindi_dialogue(clean_ls.split(":", 1)[-1].strip("[] \"'*"))
                        elif upper_ls.startswith("TIME:") or upper_ls.startswith("SETTING:"):
                            continue
                        else:
                            # New inline speaker format:  NAME: "dialogue"
                            m = re.match(r"^([A-Za-z][A-Za-z .'\-]*):\s*[\"“](.+?)[\"”]\s*$", clean_ls)
                            if not m:
                                m = re.match(r"^([A-Za-z][A-Za-z .'\-]*):\s*(.+)$", clean_ls)
                            if m:
                                spk, spoken = m.group(1).strip(), m.group(2).strip().strip("\"“”")
                                if spk.upper() not in ("SCENE DETAIL", "CHARACTERS", "CLOTHING", "BEAT", "SCRIPT", "FORMAT REQUIREMENT"):
                                    char_name = _match_persona(spk)
                                    if spoken:
                                        dial_text = clean_hindi_dialogue(spoken)
                            elif dial_text and not any(upper_ls.startswith(k) for k in ["SCENE", "SCRIPT", "PART", "BEAT", "SHOT"]):
                                dial_text += " " + clean_hindi_dialogue(clean_ls)
                    if dial_text:
                        script_scenes.append({
                            "scene_number": s_num,
                            "character": char_name,
                            "dialogue": dial_text,
                            "action": action_text,
                            "sfx": sfx_text,
                            "overlay": overlay_text,
                            "timestamp": _beat_timestamp(s_num),
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

                # Code-enforced: never allow 0-beat output to slip through.
                # If scene_lines is empty, fail loudly immediately.
                if not scene_lines:
                    _snippet = (raw_output or "")[:500]
                    raise ModelGenerationError(
                        f"Stage 3 dialogue generation failed: 0 beats parsed for "
                        f"Script {i + 1} of {len(items)} (style={scene_style}). "
                        f"Raw output snippet: {_snippet!r}",
                        partial_output=raw_output or "",
                    )
                narrations.append(ScriptDialogue(final_text, scene_lines=scene_lines))
            else:
                # Fail loudly: the model returned no usable dialogue for this
                # script. Never substitute silent synthetic scenes — the stage
                # reports the error and the UI keeps previous stages visible.
                _snippet = (raw_output or "")[:500]
                raise ModelGenerationError(
                    f"Stage 3 dialogue generation failed: model returned no usable "
                    f"dialogue for Script {i + 1} of {len(items)} (style={scene_style}). "
                    f"Raw output snippet: {_snippet!r}",
                    partial_output=raw_output or "",
                )

        # === STAGE 3.x GENERATION STEP (3.1, 3.3, 3.5... odd numbers) ===
        # Record what went in and what came out for UI display.
        _gen_num = 2 * _retry_round + 1
        _gen_name = "Dialogue generation" if _retry_round == 0 else f"Retry generation {_retry_round}"
        _gen_input = (
            f"News: {(news_input or '')[:150]}\n"
            f"Vibe: {tone} | Angle: {preferred_angle or '—'}\n"
            f"Style: {scene_style} | Characters: {character_count} | Duration: {duration_sec}s\n"
            f"Speakers: {', '.join(_speaker_names) if _speaker_names else 'N/A'}"
        )
        if _retry_round > 0 and feedback:
            _gen_input += f"\n\nRetry feedback applied:\n{(feedback or '')[:500]}"
        self._record_stage_step(
            stage=f"3.{_gen_num}",
            name=_gen_name,
            input_text=_gen_input,
            output_text=raw_output or "",
            passed=True,
        )
        self._emit_substep(on_substep, f"3.{_gen_num}", _gen_name, "complete",
                           status="pass",
                           detail=f"Draft {_retry_round + 1} written ({len(raw_output or '')} chars)",
                           input=_gen_input[:400],
                           output=(raw_output or "")[:600])

        # === STAGE 3.x VALIDATION STEP (3.2, 3.4, 3.6... even numbers) ===
        # FAIL-FAST, ordered by failure likelihood (most failure-prone first):
        #   3.x.1 Structure -> 3.x.2 News coverage -> 3.x.3 Tone -> 3.x.4 Language
        # The first failure stops the remaining checks: they are recorded as
        # "Skipped (<failed check> failed)" -- never executed -- and the
        # single retry fixes only the first failure. Re-validation then runs
        # all checks fresh. This saves time and model calls (news/tone use
        # the AI judge). One combined retry after the first failure, not one
        # retry per validation type.
        _val_num = 2 * _retry_round + 2
        _val_name = "Validation checks" if _retry_round == 0 else f"Re-validate {_retry_round}"
        self._emit_substep(on_substep, f"3.{_val_num}", _val_name, "start",
                           detail=f"Running checks on draft {_retry_round + 1} (fail-fast: Structure, News, Tone, Language)")

        # --- Check runners: each returns
        #     {"problems": [...], "pass_output": str, "feedback": str} ---
        def _check_structure():
            _problems = []
            if raw_output and raw_output.strip():
                for _idx, _nar in enumerate(narrations):
                    _sl = getattr(_nar, "scene_lines", None) or []
                    _iss = validate_dialogue_structure(_sl, scene_style, _speaker_names)
                    if _iss:
                        _problems.append(f"Script {_idx + 1}: " + "; ".join(_iss))
            _fb = ""
            if _problems:
                _fb = (
                    "STRUCTURE FIX (HIGHEST PRIORITY — the draft below violates the chosen dialogue type):\n"
                    + "\n".join(f"- {p}" for p in _problems)
                    + "\nRepair ONLY the structure so every beat obeys the dialogue type below. "
                      "Keep the same facts, jokes, characters, and word budget; change nothing else.\n"
                    + get_dialogue_type_directive(scene_style, character_count, _speaker_names)
                )
            return {"problems": _problems, "pass_output": "Passed", "feedback": _fb}

        def _check_language():
            # Detection is deterministic (find_formal_hindi). Blind global
            # substitutions are banned: they corrupt proper nouns and fixed phrases.
            _problems = []
            if raw_output and raw_output.strip():
                for _idx, _nar in enumerate(narrations):
                    _text = str(_nar)
                    _found = find_formal_hindi(_text)
                    if _found:
                        _problems.append(f"Script {_idx + 1} flagged formal tokens: {', '.join(_found)}")
            _fb = ""
            if _problems:
                _fb = (
                    "COMMON-HINDI FIX (HIGHEST PRIORITY — some spoken lines use formal/bureaucratic Hindi):\n"
                    + "\n".join(f"- {p}" for p in _problems)
                    + "\nRewrite ONLY the lines containing those flagged words, replacing them with the "
                      "words a common person would actually say. "
                      "Keep every other line, fact, joke, character, and the word budget EXACTLY as-is; "
                      "change nothing except the flagged formal words."
                )
            return {"problems": _problems, "pass_output": "Passed - common Hindi", "feedback": _fb}

        def _check_news():
            # News coverage is validated by the AI judge ONLY (FR-16.1) — no
            # token/regex matching. The judge sees ONLY the short news title /
            # basic news content + the dialogue (never the full facts list).
            # Its VERDICT + REASON are surfaced in the 3.2.2 output so the
            # decision is verifiable, never a hidden black box.
            _problems = []
            _judge_notes = []
            if raw_output and raw_output.strip():
                for _idx, _nar in enumerate(narrations):
                    _sl = getattr(_nar, "scene_lines", None) or []
                    _it = items[_idx] if _idx < len(items) else {}
                    _ith = (_it.get("hook") if isinstance(_it, dict) else "") or ""
                    _hook = clean_hook_for_dialogue(_ith)
                    _ok, _reason = ai_judge_news_coverage(
                        self, _sl, news_input, _hook,
                        engine_mode=engine_mode,
                    )
                    _judge_notes.append(f"Script {_idx + 1}: {_reason}")
                    if not _ok:
                        _problems.append(f"Script {_idx + 1}: {_reason}")
            _pass_output = "Passed - news clearly stated"
            if _judge_notes:
                _pass_output += ". " + " | ".join(_judge_notes)
            _fb = ""
            if _problems:
                _must_state: list = []
                for _it2 in (items or []):
                    _h2 = clean_hook_for_dialogue((_it2.get("hook") if isinstance(_it2, dict) else "") or "")
                    if _h2 and _h2 not in _must_state:
                        _must_state.append(_h2)
                _vvf = getattr(verification, "verified_facts", None) if verification else None
                for _f in (_vvf or [])[:2]:
                    _fs = str(_f or "").strip()
                    if _fs and _fs not in _must_state:
                        _must_state.append(_fs)
                _facts_block = ("\nThe verified facts that MUST be understandable from the dialogue:\n"
                                + "\n".join(f"- {_f}" for _f in _must_state)) if _must_state else ""
                _fb = (
                    "NEWS COVERAGE FIX (HIGHEST PRIORITY — the draft below never states the news):\n"
                    + "\n".join(f"- {p}" for p in _problems)
                    + "\nThe viewer must understand WHAT happened from the dialogue alone. "
                      "Rewrite so the beats state these verified facts in the characters' own words. "
                      "State the core what-happened in the FIRST beat."
                    + _facts_block
                    + "\nIMPORTANT: Do NOT write a new script from scratch. Take the previous draft and "
                      "UPDATE ONLY the beats that fail to state the news. Keep what works, fix what doesn't."
                )
            return {"problems": _problems, "pass_output": _pass_output, "feedback": _fb}

        def _check_tone():
            # AI judge verifies the tone is maintained (keyword matching is brittle).
            _problems = []
            if raw_output and raw_output.strip():
                for _idx, _nar in enumerate(narrations):
                    _sl = getattr(_nar, "scene_lines", None) or []
                    _t_ok, _t_issue = ai_judge_tone_compliance(
                        self, _sl, tone, preferred_angle,
                        engine_mode=engine_mode,
                    )
                    if not _t_ok:
                        _problems.append(f"Script {_idx + 1}: {_t_issue}")
            _fb = ""
            if _problems:
                _fb = (
                    "TONE CORRECTION REQUIRED:\n"
                    + "\n".join(f"- {p}" for p in _problems)
                    + f"\n\nThe required tone is '{tone}'. "
                      f"At least 70% of beats must clearly embody this tone. "
                      "\nIMPORTANT: Do NOT write a new script from scratch. Take the previous draft and "
                      "UPDATE ONLY the beats that failed. Keep what works, fix what doesn't."
                )
            return {"problems": _problems, "pass_output": "Passed - tone maintained", "feedback": _fb}

        # Fail-fast spec list: ORDER IS THE CONTRACT -- Structure, News, Tone,
        # Language (most failure-prone first). The helper stops at the first
        # failure; later checks are recorded as skipped, never executed.
        _news_input_desc = f"News: {(news_input or '')[:120]} (judge sees title + dialogue only, FR-16.1)"
        _check_specs = [
            {"sub": "1", "name": "Structure check", "run": _check_structure,
             "input": f"Dialogue type: {scene_style} | Speakers: {', '.join(_speaker_names) if _speaker_names else 'N/A'}"},
            {"sub": "2", "name": "News coverage check", "run": _check_news,
             "input": _news_input_desc},
            {"sub": "3", "name": "Tone check", "run": _check_tone,
             "input": f"Required vibe: {tone} | Angle: {preferred_angle or '—'} (70% of beats must embody it)",
             "start_detail": f"Required vibe: {tone}"},
            {"sub": "4", "name": "Language check", "run": _check_language,
             "input": "Scanned dialogue for formal/bureaucratic Hindi (common-person Hindi required)"},
        ]
        _sub_checks, _retry_feedback_parts = run_validation_checks_fail_fast(
            _check_specs,
            stage_prefix="3",
            val_num=_val_num,
            emit=lambda _s, _n, _p, **_kw: self._emit_substep(on_substep, _s, _n, _p, **_kw),
        )

        # === Record validation step, then decide: retry / fail / proceed ===
        # Fail-fast: skipped checks (passed is None) are recorded but do NOT
        # count as failures for reporting; the stage still fails overall
        # because the first executed check failed.
        _val_passed = all(c.get("passed") for c in _sub_checks)
        _failed_names = [c["name"] for c in _sub_checks if c.get("passed") is False]
        self._record_stage_step(
            stage=f"3.{_val_num}",
            name=_val_name,
            input_text=f"Validating draft {_retry_round + 1} ({len(raw_output or '')} chars, {len(narrations)} script(s))",
            output_text=(
                "All 4 checks passed" if _val_passed
                else f"Failed: {', '.join(_failed_names)}"
            ),
            passed=_val_passed,
            sub_checks=sorted(_sub_checks, key=lambda c: c["stage"]),
        )
        self._emit_substep(on_substep, f"3.{_val_num}", _val_name, "complete",
                           status="pass" if _val_passed else "fail",
                           detail=("All 4 checks passed" if _val_passed
                                   else f"Failed: {', '.join(_failed_names)}"))

        if not _val_passed:
            if _retry_round < _max_retries:
                # Single retry with combined feedback for ALL failed checks.
                _combined_fb = ((feedback or "").strip() + "\n\n" + "\n\n".join(_retry_feedback_parts)).strip()
                return self.write_dialogues_batch(
                    news_input=news_input,
                    items=items,
                    tone=tone,
                    duration_sec=duration_sec,
                    verification=verification,
                    character_count=character_count,
                    scene_style=scene_style,
                    preferred_angle=preferred_angle,
                    sample_story=sample_story,
                    sub_instruction=sub_instruction,
                    engine_mode=engine_mode,
                    num_scenes=num_scenes,
                    previous_draft=raw_output,
                    feedback=_combined_fb,
                    finalized_characters=finalized_characters,
                    finalized_scenes=finalized_scenes,
                    story_steps=story_steps,
                    _retry_round=_retry_round + 1,
                    _max_retries=_max_retries,
                    attempt_history=attempt_history,
                    on_substep=on_substep,
                )
            # Retry budget exhausted — fail loudly with evidence.
            _attempt_evidence = ""
            if attempt_history:
                _attempt_evidence = " | ".join(
                    f"Attempt {i + 1} ({len(a or '')} chars)" for i, a in enumerate(attempt_history)
                )
            raise ModelGenerationError(
                f"Stage 3 dialogue validation failed after {_retry_round} retr{'y' if _retry_round == 1 else 'ies'}: "
                + "; ".join(f"{c['name']}: {c['output']}" for c in _sub_checks if not c.get("passed"))
                + (" | " + _attempt_evidence if _attempt_evidence else ""),
                partial_output=raw_output or "",
            )

        # --- Final gate: fail loudly, never ship silently-broken output ---
        # All 4 validations passed above. Final gate double-checks plus
        # clothing/SFX (not part of the numbered 3.x checks).
        #
        # For news coverage: the AI judge is the sole validator (FR-16.1).
        # It reads only the short news title / basic news content + dialogue
        # and verdicts whether the viewer can understand what happened.
        _final_problems: list = []
        for _idx, _nar in enumerate(narrations):
            _sl = getattr(_nar, "scene_lines", None) or []
            _s_iss = validate_dialogue_structure(_sl, scene_style, _speaker_names)
            if _s_iss:
                _final_problems.append(f"Script {_idx + 1} structure: " + "; ".join(_s_iss))
            _h_found = find_formal_hindi(str(_nar))
            if _h_found:
                _final_problems.append(f"Script {_idx + 1} formal Hindi: " + ", ".join(_h_found))
            _it = items[_idx] if _idx < len(items) else {}
            _ith = (_it.get("hook") if isinstance(_it, dict) else "") or ""
            # News coverage: the AI judge is the sole validator (FR-16.1) —
            # no token/regex matching. It reads only the short news title /
            # basic news content + the dialogue, and its VERDICT + REASON are
            # recorded so the decision stays verifiable.
            _n_ok, _n_reason = ai_judge_news_coverage(
                self, _sl, news_input, clean_hook_for_dialogue(_ith),
                engine_mode=engine_mode,
            )
            if not _n_ok:
                _final_problems.append(f"Script {_idx + 1} news coverage: {_n_reason}")
            # Tone compliance: ask the AI judge directly (keyword matching is brittle).
            # The judge understands humor, emotion, and tone semantically.
            _tone_ok, _tone_issue = ai_judge_tone_compliance(
                self, _sl, tone, preferred_angle,
                engine_mode=engine_mode,
            )
            if not _tone_ok:
                _final_problems.append(f"Script {_idx + 1} tone ({tone}): {_tone_issue}")
            # Code-enforced: generic clothing ban
            _chars = getattr(_nar, "characters", None) or []
            _c_iss = validate_clothing_specificity(_chars)
            if _c_iss:
                _final_problems.append(f"Script {_idx + 1} clothing: " + "; ".join(_c_iss))
            # Code-enforced: SFX tone match
            _sfx_iss = validate_sfx_tone_match(_sl, tone)
            if _sfx_iss:
                _final_problems.append(f"Script {_idx + 1} SFX: " + "; ".join(_sfx_iss))
        if _final_problems:
            # Attach all attempt outputs as evidence: the user wants to see
            # what attempt 1, 2, 3 produced. Snippets only — full outputs
            # are already visible via self.last_attempt_history in the UI.
            _attempt_evidence = ""
            if attempt_history:
                _attempt_evidence = " | ".join(
                    f"Attempt {i + 1} ({len(a or '')} chars): {(a or '')[:200]!r}"
                    for i, a in enumerate(attempt_history)
                )
            raise ModelGenerationError(
                "Stage 3 dialogue validation failed after automatic correction: "
                + " | ".join(_final_problems)
                + (" | " + _attempt_evidence if _attempt_evidence else ""),
                partial_output=raw_output or "",
            )

        # Enrich: for any speaker name the model used that wasn't in the
        # finalized list, generate a full character profile (job, attire, etc.)
        # so downstream stages (4, 5) have complete character details.
        _known_names = set(_norm_speaker(n) for n in _speaker_names if n)
        _used_names = set()
        for _nar in narrations:
            for _sl in (getattr(_nar, "scene_lines", None) or []):
                _sn = _norm_speaker(_sl.get("character"))
                if _sn:
                    _used_names.add(_sn)
        _new_names = _used_names - _known_names
        if _new_names and hasattr(self, '_enrich_new_speakers'):
            self._enrich_new_speakers(list(_new_names), narrations, news_input)

        return narrations


dialogue_writer = DialogueNarrationAgent()
