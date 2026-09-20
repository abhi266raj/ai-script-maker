"""Comprehensive Catalog of Curated Setups for Scene Styles, Creative Angles, and Script Domains.

Guarantees at least 5-6 authentic, relevant setups (characters, scenes, locations, relationships, props, SFX, wardrobes)
per category, eliminating default chai tapri repetition and providing domain-grounded variety for subagents.
"""

from typing import Dict, List, Any, Optional

# -----------------------------------------------------------------------------
# 1. SCENE STYLES (Minimum 6 Setups per Scene Style)
# -----------------------------------------------------------------------------

SCENE_STYLE_SETUPS: Dict[str, List[Dict[str, Any]]] = {
    "Dialogue": [
        {
            "id": "dialogue_college_friends",
            "relationship": "College Friends (कॉलेज दोस्त)",
            "location": "Campus Banyan Tree & Tea Tapri",
            "setting": "A vibrant university campus perimeter roadside tea tapri beneath a shady banyan tree with college students sitting on wooden benches.",
            "characters": [
                "👩 Ananya (College Finalist - कॉलेज छात्रा / दोस्त 1)",
                "🧑 Vikram (Everyday Street-Smart Friend - पक्का यार / दोस्त 2)"
            ],
            "props": ["spiral college notebook", "cutting chai glass", "smartphone"],
            "audio_sfx": "Cutting Chai Clink + Distant Campus Murmur",
            "wardrobes": {
                "ANANYA": "Casual denim jeans and embroidered cotton kurti with backpack strap.",
                "VIKRAM": "Everyday casual printed t-shirt and worn blue jeans."
            }
        },
        {
            "id": "dialogue_husband_wife",
            "relationship": "Husband & Wife (पति-पत्नी)",
            "location": "Middle-Class Kitchen & Dining Counter",
            "setting": "A cozy Indian middle-class household kitchen with stainless steel spice canisters, gas stove, and monthly grocery slips on the table.",
            "characters": [
                "👩 Sunita (Pragmatic Homemaker - समझदार पत्नी)",
                "🧑 Rajesh (Salaried Clerk / Husband - नौकरीपेशा पति)"
            ],
            "props": ["monthly ration expense sheet", "half-filled steel water glass", "grocery bill"],
            "audio_sfx": "Steel Tumbler Clink + Utensil Rustle",
            "wardrobes": {
                "SUNITA": "Comfortable printed daily-wear cotton saree or home kurti.",
                "RAJESH": "Half-sleeve casual collared home shirt and cotton lounge trousers."
            }
        },
        {
            "id": "dialogue_father_son",
            "relationship": "Father & Son (पिता-पुत्र)",
            "location": "Ancestral Veranda & Study Corner",
            "setting": "A sunlit courtyard veranda with a wooden desk, brass tea flask, folded morning newspaper, and wall calendar.",
            "characters": [
                "👴 Sharma Ji (Retired Government Teacher / Father - बुजुर्ग पिता)",
                "🧑 Aarav (Tech Job Seeker / Son - एस्पिरेंट बेटा)"
            ],
            "props": ["reading spectacles", "coaching fee prospectus", "folded Hindi newspaper"],
            "audio_sfx": "Newspaper Snap + Spectacle Case Snap",
            "wardrobes": {
                "SHARMA JI": "Traditional white khadi kurta-pyjama with reading spectacles on bridge of nose.",
                "AARAV": "Modern casual oversized graphic tee and denim jeans."
            }
        },
        {
            "id": "dialogue_corporate_colleagues",
            "relationship": "Senior & Junior Colleagues (कलीग्स)",
            "location": "Corporate IT Park Cafeteria Pod",
            "setting": "A sleek corporate tech park cafeteria with breakout wooden pods, glass facade overlooking expressway, and espresso machine hum.",
            "characters": [
                "👩 Priya (Senior Tech Lead - सीनियर डेवलपर / कलीग 1)",
                "🧑 Rohan (Junior Product Associate - जूनियर कलीग 2)"
            ],
            "props": ["RFID corporate access lanyard", "slim work laptop", "paper coffee cup"],
            "audio_sfx": "RFID Turnstile Beep + Espresso Machine Steam",
            "wardrobes": {
                "PRIYA": "Smart-casual corporate collared shirt with company RFID lanyard badge.",
                "ROHAN": "Polo t-shirt, dark chinos, and corporate smart ID badge clip."
            }
        },
        {
            "id": "dialogue_trader_customer",
            "relationship": "Shopkeeper & Regular Customer (दुकानदार और ग्राहक)",
            "location": "Neighborhood Kirana Store Front",
            "setting": "A busy residential kirana store with sacks of grains, hanging shampoo sachets, digital UPI QR standee, and hanging weighing scale.",
            "characters": [
                "🧑 Gupta Ji (Veteran Grocery Merchant - किराना दुकानदार)",
                "👩 Meera (Neighborhood Resident / Customer - नियमित ग्राहक)"
            ],
            "props": ["steel grocery scoop", "cloth shopping jhola", "counter ledger notebook"],
            "audio_sfx": "Grain Scoop Rustle + UPI Payment Chime",
            "wardrobes": {
                "GUPTA JI": "Cotton half-sleeve shirt with fabric shop apron and wooden pencil behind ear.",
                "MEERA": "Everyday salwar-kameez carrying a reusable canvas shopping jhola."
            }
        },
        {
            "id": "dialogue_doctor_patient_relative",
            "relationship": "Physician & Patient Relative (डॉक्टर और तीमारदार)",
            "location": "Civil Hospital OPD Consultation Chamber",
            "setting": "A brightly lit civil hospital outpatient consultation room with medical anatomical charts, prescription pad, and stethoscopes on wooden desk.",
            "characters": [
                "🩺 Dr. Verma (Civil Hospital Senior Medical Officer - मुख्य चिकित्सक)",
                "🧑 Ramesh (Anxious Patient Attendant - तीमारदार / नागरिक)"
            ],
            "props": ["official medical prescription slip", "medicine blister pack", "stethoscope"],
            "audio_sfx": "Prescription Pen Scratch + Hospital Corridor Announcement",
            "wardrobes": {
                "DR. VERMA": "Crisp white medical apron over formal collared shirt with stethoscope around neck.",
                "RAMESH": "Simple checked cotton shirt and worn trousers clutching hospital file folder."
            }
        }
    ],

    "Narration": [
        {
            "id": "narration_street_citizen",
            "relationship": "Solo Citizen Monologue (आम नागरिक का नज़रिया)",
            "location": "Urban Public Crossroad & Morning Paper Stall",
            "setting": "A bustling public intersection with vehicular traffic in background and morning newspaper stand displaying national headlines.",
            "characters": [
                "🧑 Kabir (Astute Urban Citizen / Desi Narrator - जागरूक नागरिक)"
            ],
            "props": ["unfolded morning newspaper", "metallic ballpoint pen"],
            "audio_sfx": "City Traffic Drone + Crisp Paper Unfold",
            "wardrobes": {
                "KABIR": "Clean everyday henley shirt and denim jeans, looking directly into camera lens."
            }
        },
        {
            "id": "narration_tech_insider",
            "relationship": "Solo Industry Insider (टेक विश्लेषक)",
            "location": "Tech Park Glass Skybridge",
            "setting": "A modern glass-encased skybridge connecting office towers with panoramic highway view and corporate logos.",
            "characters": [
                "👩 Priya (Tech Industry Insider / Analyst - टेक विशेषज्ञ)"
            ],
            "props": ["corporate digital tablet", "smartwatch with flashing notification"],
            "audio_sfx": "Subtle Digital Chime + Low Air-Conditioner Hum",
            "wardrobes": {
                "PRIYA": "Crisp blazer over round-neck tee with minimalist lanyard badge."
            }
        },
        {
            "id": "narration_pragmatic_homemaker",
            "relationship": "Solo Household Economic Anchor (गृहलक्ष्मी का विश्लेषण)",
            "location": "Home Living Room with Ledger Table",
            "setting": "A tidy living room corner with monthly utility receipts, calculator, and brass diya in home temple visible behind.",
            "characters": [
                "👩 Sunita (Pragmatic Middle-Class Homemaker - गृहणी)"
            ],
            "props": ["monthly electricity bill", "plastic desk calculator"],
            "audio_sfx": "Calculator Button Click + Soft Domestic Ambience",
            "wardrobes": {
                "SUNITA": "Traditional cotton handloom saree with glass bangles on wrist."
            }
        },
        {
            "id": "narration_field_reporter",
            "relationship": "Solo Field Reporter (ग्राउंड रिपोर्टर)",
            "location": "Outside Ministry Bhavan Security Gate",
            "setting": "The stone entrance gates of a central government secretariat with metal barricades, security personnel, and moving staff in background.",
            "characters": [
                "🎙️ Rajesh (Independent Ground Journalist - खोजी पत्रकार)"
            ],
            "props": ["lapel mic with transmitter box", "spiral field reporter notebook"],
            "audio_sfx": "Camera Shutter Click + Distant Motorcade Siren",
            "wardrobes": {
                "RAJESH": "Weathered field journalist jacket with press pass lanyard badge."
            }
        },
        {
            "id": "narration_exam_aspirant",
            "relationship": "Solo Youth Aspirant (युवा प्रतियोगी छात्र)",
            "location": "Coaching Hub Library Cubicle",
            "setting": "A compact library study cubicle surrounded by tall stacks of general studies books, sticky notes, and table lamp.",
            "characters": [
                "🧑 Rohan (Civil Services Aspirant - प्रतियोगी छात्र)"
            ],
            "props": ["thick standard reference book", "fluorescent yellow highlighter"],
            "audio_sfx": "Highlighter Glide + Quiet Library Page Turn",
            "wardrobes": {
                "ROHAN": "Casual cotton hoodie with spectacles, tired but determined gaze."
            }
        },
        {
            "id": "narration_rural_elder",
            "relationship": "Solo Grassroots Elder (गांव के बुजुर्ग की चौपाल)",
            "location": "Village Panchayat Chaupal & Well",
            "setting": "A clean bricked village chaupal platform under a peepal tree with earthen water pots and agricultural fields beyond.",
            "characters": [
                "👴 Chacha Ramphal (Village Elder / Farmer - अनुभवी किसान)"
            ],
            "props": ["wooden walking staff", "cotton gamchha on shoulder"],
            "audio_sfx": "Breeze Through Leaves + Distant Tractor Chug",
            "wardrobes": {
                "CHACHA RAMPHAL": "Hand-spun khadi dhoti-kurta with checkered gamchha draped over shoulder."
            }
        }
    ],

    "Debate": [
        {
            "id": "debate_economist_vs_citizen",
            "relationship": "Macro Economist vs Ground Reality Citizen (नीति विशेषज्ञ बनाम आम नागरिक)",
            "location": "Studio Debate Desk with Infographic Split-Screen",
            "setting": "A high-contrast broadcast debate pod with digital statistical charts on one side and inflation receipt graphics on the other.",
            "characters": [
                "📊 Dr. Sen (Macro Policy Economist - नीति अर्थशास्त्री)",
                "🧑 Ramesh (Middle-Class Salaried Citizen - आम नागरिक)"
            ],
            "props": ["GDP printed bar chart report", "actual shopping receipt strip"],
            "audio_sfx": "Debate Gavel Chime + Sharp Whoosh Transition",
            "wardrobes": {
                "DR. SEN": "Formal dark grey blazer with pocket square and wireframe spectacles.",
                "RAMESH": "Simple blue checked cotton shirt with pen in breast pocket."
            }
        },
        {
            "id": "debate_elder_vs_genz",
            "relationship": "Traditional Elder vs Gen-Z Digital Native (परंपरा बनाम आधुनिकता)",
            "location": "Community Park Jogging Track Bench",
            "setting": "A green residential park bench at sunrise with morning walkers in background and birds chirping in eucalyptus trees.",
            "characters": [
                "👴 Shastri Ji (Traditional Heritage Advocate - बुजुर्ग मार्गदर्शक)",
                "👩 Ananya (Tech-First Gen-Z Student - डिजिटल युवा)"
            ],
            "props": ["physical hardbound Sanskrit text", "smartphone streaming short video"],
            "audio_sfx": "Park Bird Song + Fast Smartphone Swipe Sound",
            "wardrobes": {
                "SHASTRI JI": "Traditional saffron-hued cotton kurta with wooden tulsi mala.",
                "ANANYA": "Contemporary athleisure track jacket with wireless earbuds."
            }
        },
        {
            "id": "debate_bureaucrat_vs_whistleblower",
            "relationship": "Government Spokesperson vs Investigative Activist (सरकारी पक्ष बनाम आरटीआई कार्यकर्ता)",
            "location": "Secretariat Media Press Briefing Room",
            "setting": "An institutional briefing room with wooden dais, government emblem backdrop, microphones, and press gallery.",
            "characters": [
                "👔 Officer Mathur (Official Government Spokesperson - सरकारी प्रवक्ता)",
                "🧑 Kabir (RTI & Transparency Activist - आरटीआई कार्यकर्ता)"
            ],
            "props": ["embossed government gazette notification", " RTI reply documents in yellow envelope"],
            "audio_sfx": "Mic Feedback Hum + Document Folder Slap",
            "wardrobes": {
                "OFFICER MATHUR": "Formal dark Nehru jacket over crisp white shirt with official ID lanyard.",
                "KABIR": "Simple cotton kurta with cloth shoulder bag containing RTI dossiers."
            }
        },
        {
            "id": "debate_founder_vs_gig_worker",
            "relationship": "Tech Startup Founder vs Platform Gig Worker (स्टार्टअप फाउंडर बनाम डिलीवरी वर्कर)",
            "location": "Commercial High-Street Curb Outside Coworking Hub",
            "setting": "A bustling urban pavement right in front of a glass tech hub where delivery bikes park beside sleek electric sedans.",
            "characters": [
                "🧑 Vikram (VC-Backed Startup Founder - ऐप फाउंडर)",
                "🧑 Rohan (Platform Delivery Partner - गिग वर्कर)"
            ],
            "props": ["tablet showing algorithm efficiency graph", "smartphone showing deducted payout slip"],
            "audio_sfx": "Bike Idle Rumble + App Notification Ping",
            "wardrobes": {
                "VIKRAM": "Designer branded hoodie, smart sneakers, and titanium smartwatch.",
                "ROHAN": "Branded delivery company nylon windcheater with reflective strips and helmet under arm."
            }
        },
        {
            "id": "debate_builder_vs_environmentalist",
            "relationship": "Infrastructure Developer vs Green Activist (बिल्डर बनाम पर्यावरणविद्)",
            "location": "Overlook Ridge by Wetland Construction Zone",
            "setting": "A hillside overlook displaying expansive wetland on one flank and heavy earth-moving excavators on the opposite bank.",
            "characters": [
                "🏢 Builder Singhal (Real Estate Consortium Head - प्रोजेक्ट बिल्डर)",
                "👩 Dr. Sneha (Environmental Ecologist - पर्यावरण वैज्ञानिक)"
            ],
            "props": ["rolled architectural masterplan blueprint", "digital air/water quality testing meter"],
            "audio_sfx": "Heavy Earth-Mover Roar + Digital Sensor Beep",
            "wardrobes": {
                "BUILDER SINGHAL": "Linen collared shirt, yellow construction hardhat, and designer sunglasses.",
                "DR. SNEHA": "Cotton field kurti, sun hat, and laboratory ID badge clip."
            }
        },
        {
            "id": "debate_prosecutor_vs_defence_counsel",
            "relationship": "Prosecution Advocate vs Defence Lawyer (सरकारी वकील बनाम बचाव पक्ष)",
            "location": "High Court Portico Pillars",
            "setting": "The historic red-brick pillared portico of the High Court with advocates in black robes consulting legal briefs between hearings.",
            "characters": [
                "⚖️ Advocate Verma (Senior Public Prosecutor - लोक अभियोजक)",
                "⚖️ Advocate Roy (Constitutional Defence Counsel - बचाव पक्ष अधिवक्ता)"
            ],
            "props": ["bound Indian Penal Code commentary", "certified High Court bail order petition"],
            "audio_sfx": "Heavy Law Book Thud + Rapid Footsteps on Marble",
            "wardrobes": {
                "ADVOCATE VERMA": "Classic advocate black coat and white stiff neckband with state emblem lapel pin.",
                "ADVOCATE ROY": "Advocate black gown over three-piece dark formal suit and crisp white collar."
            }
        }
    ],

    "Interview": [
        {
            "id": "interview_whistleblower_investigator",
            "relationship": "Investigative Journalist & Secret Whistleblower (खोजी पत्रकार और व्हिसलब्लोअर)",
            "location": "Secluded Archive Corner in Public Library",
            "setting": "A dim, quiet reference library archive aisle flanked by tall metal bookstacks and historical gazettes.",
            "characters": [
                "🎙️ Rajesh (Lead Investigative Anchor - खोजी पत्रकार)",
                "🧑 Whistleblower X (Ex-Department Officer - गोपनीय सूत्र)"
            ],
            "props": ["compact voice recording device", "sealed brown file marked Confidential"],
            "audio_sfx": "Recorder Click + Whispered Tone Echo",
            "wardrobes": {
                "RAJESH": "Semi-formal checked blazer and dark collared shirt with notebook.",
                "WHISTLEBLOWER X": "Subtle trench jacket and pulled-down flat cap obscuring forehead."
            }
        },
        {
            "id": "interview_podcaster_tech_innovator",
            "relationship": "Tech Podcaster & Frontier AI Innovator (पॉडकास्टर और एआई विशेषज्ञ)",
            "location": "Acoustic Foam Sound Studio",
            "setting": "A contemporary studio with studio-grade boom microphones, LED accent lighting, and dual headphone monitors.",
            "characters": [
                "🎙️ Ananya (Tech Podcast Host - पॉडकास्ट होस्ट)",
                "🔬 Dr. Vikram (Chief AI Research Scientist - प्रमुख वैज्ञानिक)"
            ],
            "props": ["boom studio microphone", "semiconductor microchip wafer sample"],
            "audio_sfx": "Studio Acoustic Mic Hit + Sub Bass Whoosh",
            "wardrobes": {
                "ANANYA": "Trendy casual knit sweater with studio monitor headphones around neck.",
                "DR. VIKRAM": "Casual dark collared shirt with university faculty pin."
            }
        },
        {
            "id": "interview_ground_reporter_impacted_citizen",
            "relationship": "Field Reporter & Flood-Impacted Citizen (ग्राउंड रिपोर्टर और प्रभावित नागरिक)",
            "location": "Temporary Flood Relief Embankment Tent",
            "setting": "A muddy river embankment with tarpaulin relief shelters, rescue boats on water edge, and local families gathered.",
            "characters": [
                "🎙️ Neha (National TV Field Correspondent - फील्ड संवाददाता)",
                "🧑 Mohan (Displaced Village Resident - प्रभावित ग्रामीण)"
            ],
            "props": ["handheld news channel microphone with foam logo", "ration token card"],
            "audio_sfx": "Wind in Lapel Mic + Flowing Water Splash",
            "wardrobes": {
                "NEHA": "All-weather waterproof news jacket and sturdy field boots.",
                "MOHAN": "Modest mud-stained cotton kurta with towel wrapped on shoulder."
            }
        },
        {
            "id": "interview_financial_anchor_bullion_merchant",
            "relationship": "Financial News Anchor & Bullion Merchant (बिजनेस एंकर और सर्राफा व्यापारी)",
            "location": "Zaveri Bazaar Gold Trade Vault",
            "setting": "A high-security bullion trading room with velvet-lined transaction counters, digital gold price ticker screen, and jewelers inspecting bars.",
            "characters": [
                "📈 Priya (Market Financial Anchor - बिजनेस एंकर)",
                "🪙 Seth Chunnilal (Senior Bullion Trader - सर्राफा अध्यक्ष)"
            ],
            "props": ["hallmarked 100g gold bar replica", "digital micro-carat balance scale"],
            "audio_sfx": "Gold Metal Clink + Live Ticker Electronic Chime",
            "wardrobes": {
                "PRIYA": "Tailored corporate blazer with press badge.",
                "SETH CHUNNILAL": "Traditional embroidered silk kurta with gold chain and accounting eyeglasses."
            }
        },
        {
            "id": "interview_sports_reporter_athlete",
            "relationship": "Sports Correspondent & Medal-Winning Athlete (स्पोर्ट्स पत्रकार और युवा एथलीट)",
            "location": "National Sports Stadium Synthetic Running Track",
            "setting": "The bright red synthetic track of a national stadium with hurdle racks, stadium bleachers, and afternoon sun overhead.",
            "characters": [
                "🎙️ Karan (Sports Bureau Chief - खेल पत्रकार)",
                "🏃 Suman (National Gold Medal Sprinter - धावक एथलीट)"
            ],
            "props": ["metallic winner medal on ribbon", "spiked running shoes"],
            "audio_sfx": "Stadium PA Announcement + Track Cleats Crunch",
            "wardrobes": {
                "KARAN": "Polo sports jersey with channel media badge and clipboard.",
                "SUMAN": "Official India track jersey with tricolor striping and training sweatband."
            }
        },
        {
            "id": "interview_consumer_host_regulatory_chief",
            "relationship": "Consumer Rights Host & Regulatory Chief (उपभोक्ता मंच होस्ट और नियामक प्रमुख)",
            "location": "Standards & Safety Regulatory Laboratory",
            "setting": "A certified standards laboratory with testing centrifuges, packaged food verification samples, and regulatory stamp files.",
            "characters": [
                "🎙️ Kabir (Consumer Advocate Show Host - उपभोक्ता प्रहरी)",
                "👔 Director Agrawal (Consumer Protection Authority Head - नियामक प्रमुख)"
            ],
            "props": ["tested FMCG product sample with red defect tag", "official regulatory notice file"],
            "audio_sfx": "Lab Centrifuge Whir + Heavy Official Seal Stamp",
            "wardrobes": {
                "KABIR": "Smart-casual corduroy jacket with open collar shirt.",
                "DIRECTOR AGRAWAL": "Formal collared shirt, silk tie, and government appointment lanyard."
            }
        }
    ],

    "Street Reaction": [
        {
            "id": "street_metro_turnstile",
            "relationship": "Daily Urban Commuters (मेट्रो दैनिक यात्री)",
            "location": "Metro Station Smartcard Turnstile Concourse",
            "setting": "A bustling underground metro concourse with crowds tapping transit smartcards at automated fare gates under digital route screens.",
            "characters": [
                "🧑 Rohan (Daily Corporate Commuter - दैनिक यात्री 1)",
                "👩 Priya (College Commuter - दैनिक यात्री 2)"
            ],
            "props": ["metro smartcard", "mobile phone with QR ticket screen"],
            "audio_sfx": "Turnstile Automatic Beep + Echoing Metro PA Chime",
            "wardrobes": {
                "ROHAN": "Backpack, collared shirt, and earphones in collar.",
                "PRIYA": "Casual college denim jacket and crossbody tote bag."
            }
        },
        {
            "id": "street_auto_bus_stand",
            "relationship": "Commuters & Auto Driver (सवारी और ऑटो चालक)",
            "location": "City Bus Shelter & Auto Stand Curb",
            "setting": "A crowded roadside bus shelter during rush hour with yellow-green CNG auto-rickshaws lined along the curb.",
            "characters": [
                "🛺 Manoj (Street-Smart Auto Driver - ऑटो ड्राइवर)",
                "🧑 Ramesh (Frustrated Bus Passenger - दफ्तर जाने वाला यात्री)"
            ],
            "props": ["auto ignition key bunch", "paper bus fare ticket"],
            "audio_sfx": "Auto Engine Two-Stroke Throttle + Bus Air Brake Hiss",
            "wardrobes": {
                "MANOJ": "Khaki uniform driver shirt with city transport badge.",
                "RAMESH": "Formal office shirt with lunch tiffin bag in hand."
            }
        },
        {
            "id": "street_mandi_shoppers",
            "relationship": "Market Shoppers & Vegetable Hawker (मंडी खरीदार और सब्जी विक्रेता)",
            "location": "Weekly Morning Wholesale Sabzi Mandi",
            "setting": "A packed morning vegetable bazaar with pyramids of fresh tomatoes, digital weighing scale beeping, and colorful plastic tarpaulins.",
            "characters": [
                "🥕 Ramu (Vegetable Stall Hawker - सब्जी विक्रेता)",
                "👩 Sunita (Shrewd Bargaining Shopper - खरीदार गृहणी)"
            ],
            "props": ["bundle of fresh coriander", "metal weight counter-balance"],
            "audio_sfx": "Vendor Street Call + Metal Scale Clatter",
            "wardrobes": {
                "RAMU": "Faded plaid shirt with blue waist cloth and cloth towel on head.",
                "SUNITA": "Cotton printed salwar with shopping bag slung over forearm."
            }
        },
        {
            "id": "street_coaching_hub_students",
            "relationship": "Competitive Exam Batchmates (कोचिंग छात्र संगी)",
            "location": "Narrow Lane Outside Major Test Center",
            "setting": "A dense urban coaching alleyway flanked by admission hoardings, stationery shops, and hundreds of students exiting an exam hall.",
            "characters": [
                "🧑 Aarav (First-Attempt Student - छात्र 1)",
                "🧑 Vikram (Repeat Exam Veteran - छात्र 2)"
            ],
            "props": ["printed exam question paper", "transparent clipboard with admit card"],
            "audio_sfx": "Paper Rustle + Crowd Murmur of Students",
            "wardrobes": {
                "AARAV": "Simple crewneck t-shirt with transparent pencil pouch in hand.",
                "VIKRAM": "Casual shirt over white undershirt with backpack."
            }
        },
        {
            "id": "street_temple_ghat_promenade",
            "relationship": "Pilgrims & Riverside Shopkeeper (श्रद्धालु और दुकानदार)",
            "location": "Holy River Ghat Stone Steps",
            "setting": "Broad stone ghat steps leading down to sacred river water with brass temple bells, flower vendor baskets, and evening river breeze.",
            "characters": [
                "🪔 Pandit Ji (Riverside Ritual Store Keeper - घाट दुकानदार)",
                "👴 Shastri Ji (Visiting Senior Devotee - श्रद्धालु)"
            ],
            "props": ["brass puja diya", "clay pot of river water"],
            "audio_sfx": "Resonant Temple Bell Toll + Gentle River Lap",
            "wardrobes": {
                "PANDIT JI": "Traditional saffron dhoti-kurta with sandalwood tilak on forehead.",
                "SHASTRI JI": "White cotton kurta with wool shawl draped across chest."
            }
        },
        {
            "id": "street_cinema_lobby_exit",
            "relationship": "Moviegoers & Pop Culture Fans (सिनेमा दर्शक)",
            "location": "Multiplex Ticket Concourse & Poster Hall",
            "setting": "A brightly lit multiplex lobby with giant movie poster standees, glowing marquee boards, and audiences streaming out of auditorium doors.",
            "characters": [
                "🍿 Kabir (Film Enthusiast Commuter - युवा दर्शक 1)",
                "👩 Ananya (Pop Culture Critic - युवा दर्शक 2)"
            ],
            "props": ["large tub of cinema popcorn", "ticket stub slips"],
            "audio_sfx": "Lobby Surround Sound Bass + Popcorn Crunch",
            "wardrobes": {
                "KABIR": "Casual denim trucker jacket over black graphic t-shirt.",
                "ANANYA": "Stylish high-waist pants and chic cropped jacket."
            }
        }
    ],

    "Satirical Skit": [
        {
            "id": "skit_netaji_and_chaiwala",
            "relationship": "Vain Politician & Sharp-Tongued Vendor (नेताजी और चायवाला)",
            "location": "Campaign Street Corner Tea Tapri",
            "setting": "A lively street tea stall adorned with political campaign flags, party buntings, and plastic chairs under a tree.",
            "characters": [
                "🏛️ Netaji Tiwari (Ward Corporator / Candidate - क्षेत्रीय नेताजी)",
                "☕ Rohan (Wily Street Chaiwala - हाजिरजवाब चायवाला)"
            ],
            "props": ["heavy marigold garland", "long aluminum tea strainer", "unpaid chai bill chit"],
            "audio_sfx": "Car Horn Whoosh + Tapri Brass Kettle Hiss",
            "wardrobes": {
                "NETAJI TIWARI": "Starch-crisp white khadi kurta-pyjama with vibrant saffron-green party scarf and oversized sunglasses.",
                "ROHAN": "Faded striped collared shirt with blue cotton tea vendor apron."
            }
        },
        {
            "id": "skit_bureaucrat_and_citizen",
            "relationship": "Red-Tape Babu & Baffled Citizen (बाबूजी और परेशान नागरिक)",
            "location": "Municipal Birth & Property Clearance Window",
            "setting": "A dusty government administrative desk piled high with tied red-tape files, ceiling fan creaking, and small glass teller hole.",
            "characters": [
                "👔 Babu Mishra (Senior Desk In-Charge - अनुभवी बाबूजी)",
                "🧑 Rajesh (Common Taxpaying Citizen - आम नागरिक)"
            ],
            "props": ["rubber ink stamp", "stamp ink pad", "bundle of 12 photocopied forms"],
            "audio_sfx": "Slow Ceiling Fan Squeak + Loud Ink Stamp Thud",
            "wardrobes": {
                "BABU MISHRA": "Half-sleeve safari shirt with ballpoint pens in pocket and spectacles perched on tip of nose.",
                "RAJESH": "Modest checked shirt holding overflowing plastic folder of certificates."
            }
        },
        {
            "id": "skit_fintech_bro_and_dadi",
            "relationship": "Overhyped FinTech Salesman & Skeptical Dadi (फिनटेक सेल्समैन और समझदार दादी)",
            "location": "Traditional Living Room Divan",
            "setting": "A traditional home drawing room with embroidered bolster cushions, antique clock, and family photos on wood-paneled walls.",
            "characters": [
                "📱 Bunny (Hyperactive FinTech App Marketer - फिनटेक सेल्समैन)",
                "👵 Dadi Ji (Traditional Matriarch - पारंपरिक दादीजी)"
            ],
            "props": ["smartphone with glowing dynamic crypto graph", "vintage steel biscuit tin storing cash"],
            "audio_sfx": "Fast App Chime + Metallic Biscuit Tin Clank",
            "wardrobes": {
                "BUNNY": "Tight blazer over round-neck tech startup tee and ultra-white sneakers.",
                "DADI JI": "Classic white chanderi cotton saree with traditional reading glasses."
            }
        },
        {
            "id": "skit_corporate_hr_and_coder",
            "relationship": "Corporate HR 'Wellness' Officer & Exhausted Coder (एचआर अधिकारी और थका हुआ कोडर)",
            "location": "Corporate Relaxation Beanbag Corner",
            "setting": "A tech company 'Zen Room' decorated with motivational posters, plastic plants, and colorful beanbags right beside a glowing server rack.",
            "characters": [
                "🧘 HR Shweta (Chief Happiness Officer - वेलनेस एचआर)",
                "💻 Vikram (Sleep-Deprived Senior Coder - 80-घंटे काम करने वाला कोडर)"
            ],
            "props": ["brass mindfulness singing bell", "jumbo caffeinated energy drink can"],
            "audio_sfx": "Singing Bowl Resonant Hum + Fast Keyboard Frenzy",
            "wardrobes": {
                "HR SHWETA": "Pastel formal linen suit with corporate silver lanyard.",
                "VIKRAM": "Disheveled hoodie with bedhead hair and dark circles under eyes."
            }
        },
        {
            "id": "skit_coaching_salesman_and_parent",
            "relationship": "Coaching Seminar Pitchman & Frugal Father (कोचिंग काउंसलर और सतर्क पिता)",
            "location": "Air-Conditioned Admission Seminar Desk",
            "setting": "A luxury hotel banquet hall turned coaching admission center with glossy flex banners displaying Rank 1 toppers and stage spotlight.",
            "characters": [
                "🎯 Director Malhotra (Coaching Institute Admission Head - एडमिशन डायरेक्टर)",
                "👴 Sharma Ji (Frugal Government Employee Father - सतर्क अभिभावक)"
            ],
            "props": ["glossy 40-page gold-embossed coaching brochure", "chequebook with worn pen"],
            "audio_sfx": "Smooth Jazz Background + Paper Cheque Tear Sound",
            "wardrobes": {
                "DIRECTOR MALHOTRA": "Silk double-breasted suit with gold cufflinks and slicked-back hair.",
                "SHARMA JI": "Modest safari suit with cloth briefcase clutched tight on lap."
            }
        },
        {
            "id": "skit_traffic_cop_and_excuse_artist",
            "relationship": "Traffic Police Havaldar & Creative Excuse Maker (ट्रैफिक पुलिस और बहानेबाज)",
            "location": "Major Traffic Junction Barricade",
            "setting": "A busy road intersection with yellow barricades, digital speed camera tripod, and auto-rickshaws waiting at red light.",
            "characters": [
                "👮 Havaldar Yadav (City Traffic Enforcement Officer - ट्रैफिक हवलदार)",
                "🧑 Bunty (Smooth-Talking Commuter - बहानेबाज राइडर)"
            ],
            "props": ["handheld digital traffic e-challan POS device", "half-broken scooter helmet"],
            "audio_sfx": "Traffic Whistle Blast + Digital Challan POS Beep",
            "wardrobes": {
                "HAVALDAR YADAV": "Immaculate khaki police uniform with white traffic sleeve bands and leather belt.",
                "BUNTY": "Colorful printed shirt with helmet dangling awkwardly from left elbow."
            }
        }
    ],

    "Lament": [
        {
            "id": "lament_bereaved_relatives",
            "relationship": "Bereaved Kin & Consoling Neighbor (शोकाकुल परिजन और ढांढस बंधाता पड़ोसी)",
            "location": "Courtyard of Tragedy-Hit Residence",
            "setting": "A somber village or town courtyard with neighbors sitting silently on woven cots under overcast skies.",
            "characters": [
                "🧑 Mohan (Grieving Family Member - शोकाकुल परिजन)",
                "👴 Chacha Dinanath (Consoling Elder - ढांढस बंधाता बुजुर्ग)"
            ],
            "props": ["framed photograph with white garland", "untouched brass cup of water"],
            "audio_sfx": "Muffled Sob Echo + Gentle Wind Whistle",
            "wardrobes": {
                "MOHAN": "Plain unironed white cotton kurta with reddened eyes and slumped posture.",
                "CHACHA DINANATH": "Dull grey handloom dhoti-kurta placing comforting hand on shoulder."
            }
        },
        {
            "id": "lament_laid_off_employee_spouse",
            "relationship": "Laid-Off Tech Veteran & Supportive Spouse (नौकरी गंवाने वाला कर्मी और जीवनसाथी)",
            "location": "Midnight Kitchen Dining Table",
            "setting": "A dimly lit kitchen dining table at 1 AM with a single ceiling pendant lamp lighting an opened cardboard severance box.",
            "characters": [
                "🧑 Rohan (Laid-Off IT Professional - हताश कर्मी)",
                "👩 Priya (Supportive Wife - संबल देती पत्नी)"
            ],
            "props": ["printed termination notice letter", "deactivated corporate plastic ID card"],
            "audio_sfx": "Ticking Wall Clock + Soft Exhale of Grief",
            "wardrobes": {
                "ROHAN": "Wrinkled office shirt with loosened collar and hollow expression.",
                "PRIYA": "Simple cotton home night-kurti holding his trembling hand."
            }
        },
        {
            "id": "lament_displaced_farmers",
            "relationship": "Drought-Hit Farmer & Village Peer (सूखा पीड़ित किसान और साथी)",
            "location": "Cracked Dry Reservoir Basin",
            "setting": "The dry cracked mud bed of a dried-up village reservoir under a scorching sun with desiccated crops visible on horizon.",
            "characters": [
                "🌾 Ramphal (Debt-Ridden Farmer - कर्जदार किसान)",
                "🌾 Sukhiram (Fellow Agrarian - सह-किसान)"
            ],
            "props": ["handful of parched dry soil", "bank debt recovery notice slip"],
            "audio_sfx": "Dry Earth Crumble + Scorching Summer Wind",
            "wardrobes": {
                "RAMPHAL": "Weather-beaten cotton dhoti with frayed gamchha covering head.",
                "SUKHIRAM": "Faded collarless village shirt looking out at barren land."
            }
        },
        {
            "id": "lament_retiring_craftsman_son",
            "relationship": "Aging Handloom Master & Apprentice Son (शिल्पकार पिता और पुत्र)",
            "location": "Fading Handloom Workshop Loft",
            "setting": "A dusty traditional handloom workshop with wooden shuttle frames standing idle and bundles of unsold silk yarn.",
            "characters": [
                "🧶 Master Ustad (Veteran Handloom Weaver - बुजुर्ग बुनकर)",
                "🧑 Imran (Young Apprentice Son - विवश पुत्र)"
            ],
            "props": ["wooden loom shuttle", "bundle of woven pure silk border"],
            "audio_sfx": "Creaking Wooden Loom + Melancholic Flute Note",
            "wardrobes": {
                "MASTER USTAD": "Traditional cotton lungi and vest with spectacles tied by thread.",
                "IMRAN": "Everyday casual shirt touching the idle wooden loom frame."
            }
        },
        {
            "id": "lament_old_age_resident_volunteer",
            "relationship": "Elderly Home Resident & Visiting Volunteer (वृद्धाश्रम निवासी और सेवादार)",
            "location": "Care Home Sunlit Garden Veranda",
            "setting": "A quiet elderly care home veranda with potted ferns, cane armchairs, and long shadows stretching in late afternoon.",
            "characters": [
                "👵 Shanti Devi (Abandoned Elderly Mother - वृद्धाश्रम निवासी)",
                "👩 Sneha (Compassionate Youth Volunteer - सामाजिक कार्यकर्ता)"
            ],
            "props": ["faded black-and-white family photograph", "crocheted wool shawl"],
            "audio_sfx": "Rustling Dry Leaves + Distant Temple Bell Toll",
            "wardrobes": {
                "SHANTI DEVI": "Faded white cotton widow saree with trembling hands.",
                "SNEHA": "Modest pastel kurti kneeling gently beside the armchair."
            }
        },
        {
            "id": "lament_healthcare_night_shift",
            "relationship": "Exhausted ICU Doctors (थके हुए चिकित्सक साथी)",
            "location": "Government Hospital Night-Shift Duty Room",
            "setting": "A cramped hospital duty doctors' lounge with half-eaten biscuits, medicine charts, and neon tube flickering overhead.",
            "characters": [
                "🩺 Dr. Alok (ICU Resident Doctor - जूनियर डॉक्टर)",
                "🩺 Dr. Meera (Senior Casualty Surgeon - सीनियर सर्जन)"
            ],
            "props": ["pulled-down surgical N95 mask", "flatline ECG report strip"],
            "audio_sfx": "Medical Monitor Beep Fade + Heavy Exhausted Sigh",
            "wardrobes": {
                "DR. ALOK": "Stained hospital green scrubs with stethoscope hanging limp.",
                "DR. MEERA": "Blue surgical scrubs rubbing temples in silent fatigue."
            }
        }
    ],

    "Argument": [
        {
            "id": "argument_domestic_budget",
            "relationship": "Husband & Wife (दंपति में तकरार)",
            "location": "Middle-Class Kitchen Counter",
            "setting": "A kitchen counter during dinner prep with a smoking fry-pan, grocery bills, and gas subsidy passbook.",
            "characters": [
                "👩 Sunita (Frustrated Homemaker - नाराज पत्नी)",
                "🧑 Rajesh (Defensive Salaried Husband - सफाई देता पति)"
            ],
            "props": ["gas cylinder red booking slip", "empty steel wallet box"],
            "audio_sfx": "Lid Clatter on Steel Pan + Sharp Discontented Sigh",
            "wardrobes": {
                "SUNITA": "Daily-wear cotton printed saree with pallu tucked at waist.",
                "RAJESH": "Home cotton vest and pajama holding his hands out defensively."
            }
        },
        {
            "id": "argument_father_son_career",
            "relationship": "Traditional Father & Startup-Dreaming Son (पिता और बेटे में बहस)",
            "location": "Drawing Room Dining Table",
            "setting": "A family dining room with open textbooks on one side and a startup business plan on a laptop screen on the other.",
            "characters": [
                "👴 Sharma Ji (Conservative Father - सख्त पिता)",
                "🧑 Aarav (Rebellious Tech Graduate Son - जिद्दी बेटा)"
            ],
            "props": ["government service exam form", "angel investment pitch presentation deck"],
            "audio_sfx": "Table Fist Slam + Chair Scrape on Floor",
            "wardrobes": {
                "SHARMA JI": "Cotton kurta with stern furrowed brow and reading glasses in hand.",
                "AARAV": "Denim jacket and headphones around neck, gesturing with conviction."
            }
        },
        {
            "id": "argument_neighbors_parking",
            "relationship": "Apartment Neighbors (सोसाइटी पड़ोसी विवाद)",
            "location": "Apartment Stilt Parking Lot",
            "setting": "A residential building stilt parking lot with cars parked bumper to bumper and chalk-drawn parking slot numbers.",
            "characters": [
                "🧑 Verma Ji (First Floor Resident - कार मालिक पड़ोसी 1)",
                "🧑 Gupta Ji (Ground Floor Shop Owner - स्कूटर मालिक पड़ोसी 2)"
            ],
            "props": ["set of car keys", "yellow society warning parking wheel clamp"],
            "audio_sfx": "Car Remote Lock Beep + Loud Argument Echo in Stilt Area",
            "wardrobes": {
                "VERMA JI": "Casual morning polo shirt and sports sandals.",
                "GUPTA JI": "Traditional daily kurta holding morning milk packet."
            }
        },
        {
            "id": "argument_appraisal_colleagues",
            "relationship": "Competitive Corporate Peers (कॉर्पोरेट प्रतिद्वंद्वी)",
            "location": "Conference Room Glass Enclosure",
            "setting": "A soundproof glass corporate meeting room with whiteboard filled with quarterly KPI metrics and half-erased target tables.",
            "characters": [
                "👩 Priya (High-Performing Lead - प्रोजेक्ट लीड)",
                "🧑 Rohan (Disgruntled Peer - असंतुष्ट सहकर्मी)"
            ],
            "props": ["printed annual performance appraisal sheet", "dry-erase whiteboard marker"],
            "audio_sfx": "Dry-Erase Marker Snap Cap + Chair Swivel Creak",
            "wardrobes": {
                "PRIYA": "Tailored formal shirt with corporate RFID badge.",
                "ROHAN": "Collared shirt with rolled-up sleeves and confrontational body language."
            }
        },
        {
            "id": "argument_landowner_and_contractor",
            "relationship": "Plot Owner & Building Contractor (मकान मालिक और ठेकेदार)",
            "location": "Unfinished Brickwork Building Site",
            "setting": "The raw concrete floor of a house under construction with exposed rebar pillars, cement bags, and measuring tape.",
            "characters": [
                "🧑 Rajesh (Frustrated House Owner - मकान मालिक)",
                "👷 Thekedar Jagdish (Defensive Masonry Contractor - ठेकेदार)"
            ],
            "props": ["steel measuring tape", "sub-standard cracked brick sample"],
            "audio_sfx": "Measuring Tape Snap Retract + Brick Thud on Concrete",
            "wardrobes": {
                "RAJESH": "Casual collared shirt dusty from walking through site.",
                "THEKEDAR JAGDISH": "Faded safari shirt with yellow measuring tape around neck."
            }
        },
        {
            "id": "argument_commuter_and_conductor",
            "relationship": "Passenger & City Bus Conductor (यात्री और बस कंडक्टर)",
            "location": "Overcrowded Public City Bus Aisle",
            "setting": "A packed public state transport bus aisle with passengers swaying to turns and conductor squeezing through seats.",
            "characters": [
                "🧑 Kabir (Agitated Daily Commuter - यात्री)",
                "🎫 Conductor Tiwari (Overworked Bus Conductor - बस कंडक्टर)"
            ],
            "props": ["torn 50-rupee currency note", "metal ticket punch machine"],
            "audio_sfx": "Conductor Bell Whistle + Bus Engine Grunt",
            "wardrobes": {
                "KABIR": "Commuter checked shirt with crowded shoulder pressure.",
                "CONDUCTOR TIWARI": "Khaki bus conductor uniform with leather cash coin pouch."
            }
        }
    ]
}


# -----------------------------------------------------------------------------
# 2. CREATIVE ANGLES (Minimum 6 Setups per Creative Angle)
# -----------------------------------------------------------------------------

CREATIVE_ANGLE_SETUPS: Dict[str, List[Dict[str, Any]]] = {
    "Contrast & Comparison": [
        {
            "id": "contrast_ac_vs_pushcart",
            "location": "Luxury Air-Conditioned Showroom vs Roadside Pushcart",
            "relationship": "Elite Consumer vs Struggling Street Vendor",
            "characters": ["👔 Premium Buyer (अमीर खरीदार)", "🛒 Street Vendor (ठेले वाला)"],
            "setting": "Split visual comparing a plush air-conditioned department store counter against an unshaded roadside pushcart under direct sun.",
            "props": ["gold premium credit card", "battered manual balance scale"],
            "audio_sfx": "AC Chime vs Roadside Traffic Commotion"
        },
        {
            "id": "contrast_high_tech_ev_vs_cycle_rickshaw",
            "location": "EV Fast-Charging Hub vs Cycle Rickshaw Stand",
            "relationship": "Green Tech Early Adopter vs Manual Laborer",
            "characters": ["🚗 EV Luxury Owner (ईवी मालिक)", "🚲 Rickshaw Puller (रिक्शा चालक)"],
            "setting": "A high-tech electric vehicle charging station adjacent to a manual cycle-rickshaw stand during a heatwave.",
            "props": ["digital touchscreen charger plug", "towel wiping sweat from rickshaw handle"],
            "audio_sfx": "Electric Humming Whine vs Rickshaw Bell Ring"
        },
        {
            "id": "contrast_private_vs_district_hospital",
            "location": "Five-Star Corporate Hospital vs District Civil Clinic",
            "relationship": "Medical Tourism Executive vs Rural Patient",
            "characters": ["🏥 Corporate Hospital Rep (निजी अस्पताल)", "🧑 Rural Patient (जिला अस्पताल मरीज)"],
            "setting": "Side-by-side juxtaposition of marble-floored luxury suite lobby and overflowing district hospital corridor with patients on stretchers.",
            "props": ["leather-bound room tariff menu", "torn government hospital OPD slip"],
            "audio_sfx": "Piano Muzak vs Crowded Emergency Siren"
        },
        {
            "id": "contrast_air_conditioned_school_vs_single_teacher",
            "location": "Smart International Classroom vs Village Single-Teacher School",
            "relationship": "Smart School Educator vs Village Shiksha Mitra",
            "characters": ["👩 Smart School Teacher (इंटरनेशनल स्कूल)", "🧑 Village Teacher (प्राथमिक शिक्षक)"],
            "setting": "Interactive smart touchscreen podium in an elite school contrasted with peeling blackboard in a single-room rural primary school.",
            "props": ["stylus digital pen", "broken piece of white chalk"],
            "audio_sfx": "Interactive Digital Chime vs Chalk Scraping on Slate"
        },
        {
            "id": "contrast_executive_boardroom_vs_basement_security",
            "location": "40th-Floor Corporate Boardroom vs Basement Guard Cabin",
            "relationship": "Chief Executive Officer vs Contract Security Guard",
            "characters": ["👔 Managing Director (कंपनी प्रमुख)", "💂 Security Guard (सुरक्षा गार्ड)"],
            "setting": "Panoramic skyline glass boardroom discussing bonus packages contrasted with a windowless basement security desk with a small table fan.",
            "props": ["fountain pen and annual profit report", "steel lunchbox and security logbook"],
            "audio_sfx": "Executive Coffee Stir vs Guard Whistle and Radio Buzz"
        },
        {
            "id": "contrast_space_launch_vs_potholed_road",
            "location": "Space Telemetry Screen vs Waterlogged City Colony",
            "relationship": "Rocket Telemetry Scientist vs Commuter Stranded in Pothole",
            "characters": ["🚀 Space Scientist (अंतरिक्ष वैज्ञानिक)", "🧑 Stranded Commuter (सड़क पर फंसा नागरिक)"],
            "setting": "Ultra-precise mission control countdown displays contrasted with an urban commuter pushing a stalled scooter through waterlogged potholed road.",
            "props": ["orbital calculation monitor", "exhausted kick-start of water-choked scooter"],
            "audio_sfx": "Rocket Countdown Echo vs Splashing Mud Puddle"
        }
    ],

    "The Untold Truth / Hidden Angle": [
        {
            "id": "untold_warehouse_gig_workers",
            "location": "E-Commerce Sorting Mega-Warehouse",
            "relationship": "Algorithm Supervisor & Packaging Associate",
            "characters": ["📦 Package Sorter (वेयरहाउस कर्मचारी)", "⏱️ Floor Supervisor (फ्लोर सुपरवाइजर)"],
            "setting": "Endless industrial conveyor belts with workers scanning parcels under barcode lasers running on strict 10-second quotas.",
            "props": ["handheld laser barcode scanner", "timer stopwatch on monitor"],
            "audio_sfx": "Conveyor Belt Whir + Laser Beep"
        },
        {
            "id": "untold_food_safety_lab",
            "location": "Government Food Quality Testing Lab",
            "relationship": "Food Chemist & Citizen Consumer",
            "characters": ["🧪 Food Testing Chemist (खाद्य विश्लेषक)", "🧑 Consumer (जागरूक उपभोक्ता)"],
            "setting": "Chemical reagents, test tubes with adulterated milk and spice samples turning unexpected blue colors under chemical indicators.",
            "props": ["chemical pipette dropper", "adulterated spice sample flask"],
            "audio_sfx": "Glass Dropper Clink + Chemical Sizzle"
        },
        {
            "id": "untold_railway_track_maintainer",
            "location": "Midnight Railway Line Kilometer Marker",
            "relationship": "Trackman (Gangman) & Station Controller",
            "characters": ["🔨 Gangman Trackman (रेलवे ट्रैकमैन)", "📻 Station Master (स्टेशन मास्टर)"],
            "setting": "Dark isolated railway track bed at 2 AM with a trackman tapping steel fishplates with a heavy hammer under a handheld flashlight.",
            "props": ["heavy track inspection hammer", "red-green handheld safety lamp"],
            "audio_sfx": "Hammer Impact on Rail Steel + Distant Train Whistle"
        },
        {
            "id": "untold_server_data_center",
            "location": "High-Density AI Server Farm Cooling Hall",
            "relationship": "Data Center Infrastructure Engineer & Green Auditor",
            "characters": ["🖥️ Systems Tech (डाटा सेंटर इंजीनियर)", "🌱 Water Auditor (पर्यावरण ऑडिटर)"],
            "setting": "Towering rows of server racks with flashing green LEDs inside an industrial cooling facility consuming millions of liters of groundwater.",
            "props": ["water consumption flow meter", "flashing optical fiber patch cable"],
            "audio_sfx": "Giant Cooling Fan Roar + High-Pitch Server Whine"
        },
        {
            "id": "untold_whistleblower_legal_counsel",
            "location": "Public Park Bench at Dusk",
            "relationship": "Ex-Auditor Whistleblower & Human Rights Lawyer",
            "characters": ["📁 Whistleblower (गोपनीय ऑडिटर)", "⚖️ Counsel (अधिवक्ता)"],
            "setting": "A quiet shadowy park bench at dusk where an ex-financial auditor hands over an encrypted flash drive detailing hidden balance sheet debts.",
            "props": ["metallic encrypted USB thumb drive", "sealed legal agreement"],
            "audio_sfx": "Dusk Cricket Chirp + Low Whispered Tone"
        },
        {
            "id": "untold_sanitation_worker_safety",
            "location": "Urban Drainage Sump Manhole",
            "relationship": "Municipal Sanitation Worker & Union Advocate",
            "characters": ["🦺 Sanitation Worker (सफाई मित्र)", "🧑 Labor Union Rep (यूनियन प्रतिनिधि)"],
            "setting": "Street drainage access point showing the stark lack of mechanized breathing apparatus despite official zero-manual scavenging claims.",
            "props": ["bamboo clearing rod", "safety harness missing respirator"],
            "audio_sfx": "Sludge Splash + Distant Traffic Drone"
        }
    ],

    "Common Citizen Impact": [
        {
            "id": "citizen_petrol_pump_queue",
            "location": "Fuel Dispenser Island Queue",
            "relationship": "Commuter on Scooter & Fuel Pump Attendant",
            "characters": ["🛵 Office Commuter (दैनिक यात्री)", "⛽ Pump Attendant (पेट्रोल पंप कर्मी)"],
            "setting": "Long queue of two-wheelers watching the digital fuel price counter rapidly tick upward beyond their daily budget.",
            "props": ["500 rupee note", "digital dispenser fuel price meter"],
            "audio_sfx": "Dispenser Motor Hum + Fuel Nozzle Clack"
        },
        {
            "id": "citizen_vegetable_bill_shock",
            "location": "Neighborhood Vegetable Cart",
            "relationship": "Middle-Class Homemaker & Vegetable Vendor",
            "characters": ["👩 Homemaker (गृहणी)", "🛒 Sabziwala (सब्जी विक्रेता)"],
            "props": ["cloth shopping bag", "1 kg weight on scale"],
            "setting": "A neighborhood corner vegetable stall where prices of everyday onion and tomato trigger immediate recalculation of weekly meals.",
            "audio_sfx": "Plastic Bag Rustle + Calculator Click"
        },
        {
            "id": "citizen_school_fee_counter",
            "location": "Private School Accounts Office Window",
            "relationship": "Salaried Parent & School Cashier",
            "characters": ["🧑 Salaried Father (मध्यमवर्गीय पिता)", "💼 Accounts Clerk (अकाउंट्स क्लर्क)"],
            "setting": "A crowded school fee counter at the start of academic session showing mandatory annual fee hikes and uniform bundled costs.",
            "props": ["printed fee breakdown structure slip", "cheque slip with trembling pen"],
            "audio_sfx": "Receipt Stamp Thud + Cash Register Clatter"
        },
        {
            "id": "citizen_cng_auto_queue",
            "location": "Nighttime CNG Fuel Station Line",
            "relationship": "Two Auto Drivers Waiting in Line",
            "characters": ["🛺 Auto Driver 1 (ऑटो चालक 1)", "🛺 Auto Driver 2 (ऑटो चालक 2)"],
            "setting": "A half-kilometer long queue of auto-rickshaws waiting at 11 PM for CNG refills, eating dinner out of steel tiffins on car hoods.",
            "props": ["steel tiffin box", "CNG cylinder compliance card"],
            "audio_sfx": "High Pressure Gas Hiss + Exhaust Drone"
        },
        {
            "id": "citizen_bank_pension_queue",
            "location": "Nationalized Bank Senior Citizen Window",
            "relationship": "Retired Pensioner & Bank Teller",
            "characters": ["👴 Retired Pensioner (बुजुर्ग पेंशनभोगी)", "👔 Bank Cashier (बैंक खजांची)"],
            "setting": "A cramped public sector bank branch with elderly citizens clutching passbooks for monthly pension life certificate verification.",
            "props": ["printed bank passbook", "biometric thumb scanner machine"],
            "audio_sfx": "Dot Matrix Passbook Printer Screech + Counter Bell"
        },
        {
            "id": "citizen_generic_pharmacy",
            "location": "Jan Aushadhi Generic Medical Store",
            "relationship": "Chronically Ill Patient & Pharmacy Chemist",
            "characters": ["🧑 Patient (दवा खरीदार)", "💊 Chemist (जेनेरिक मेडिकल संचालक)"],
            "setting": "A neighborhood generic drugstore with price comparison boards showing 80% discount over branded multinational pharma drugs.",
            "props": ["prescription with branded names", "generic substitute strip"],
            "audio_sfx": "Medicine Strip Snip + Paper Bag Slide"
        }
    ],

    "Satire & Irony": [
        {
            "id": "satire_smart_city_waterlog",
            "location": "Smart City Project Gate & Flooded Street",
            "relationship": "City Municipal Councillor & Stranded Resident",
            "characters": ["🏛️ Ward Councillor (स्मार्ट सिटी पार्षद)", "🧑 Resident in Gumboots (जलभराव से परेशान नागरिक)"],
            "setting": "An illuminated 'Smart City Global Milestone' flex banner hanging directly over knee-deep monsoon waterlogging with floating garbage.",
            "props": ["framed award certificate", "broken plastic umbrella"],
            "audio_sfx": "Water Splash + Loud Brass Band Echo"
        },
        {
            "id": "satire_air_purifier_in_toxic_smog",
            "location": "Open-Air Smog Tower Construction Deck",
            "relationship": "Anti-Pollution Campaigner & Local Traffic Cop",
            "characters": ["🌿 Green Tech Vendor (स्मॉग टॉवर वेंडर)", "👮 Traffic Cop with Mask (धुएं में खड़ा ट्रैफिक पुलिस)"],
            "setting": "An ultra-expensive outdoor air-purification device operating in the middle of severe AQI 480 grey smog where visibility is 20 meters.",
            "props": ["AQI meter flashing 499 hazardous", "portable fan blowing grey dust"],
            "audio_sfx": "Mechanical Fan Whir + Persistent Coughing"
        },
        {
            "id": "satire_paperless_office_photocopies",
            "location": "Digital E-Governance Service Center",
            "relationship": "Digital Officer & Helpless Applicant",
            "characters": ["💻 E-Gov Operator (डिजिटल ऑपरेटर)", "🧑 Applicant (परेशान आवेदक)"],
            "setting": "A sign declaring '100% Paperless Digital India Office' while requiring the citizen to provide three physical photocopies of Aadhaar, PAN, and electricity bill.",
            "props": ["bulky photocopy machine spitting paper", "Aadhaar printouts"],
            "audio_sfx": "Photocopy Machine Rhythmic Squeak + Paper Slam"
        },
        {
            "id": "satire_luxury_diet_next_to_ration_line",
            "location": "Keto Diet Clinic Beside Government Fair Price Shop",
            "relationship": "Luxury Fitness Coach & Ration Card Holder",
            "characters": ["🥗 Keto Wellness Coach (कीटो डाइट एक्सपर्ट)", "🌾 Ration Card Beneficiary (राशन कार्ड उपभोक्ता)"],
            "setting": "A glass-front luxury clinic selling 'Zero-Carb Himalayan Berry detox juice' directly next to a line of people waiting for subsidized wheat ration.",
            "props": ["designer detox smoothie jar", "jute sack of subsidized grains"],
            "audio_sfx": "Blender Puree Whir + Weighing Scale Thud"
        },
        {
            "id": "satire_bullet_train_cattle_delay",
            "location": "Semi-High Speed Train Track Barrier",
            "relationship": "Loco Pilot & Village Cowherd",
            "characters": ["🚅 High Speed Train Pilot (वंदे भारत लोको पायलट)", "🐄 Cowherd (चरवाहा)"],
            "setting": "An ultra-aerodynamic high-speed train halted on the tracks because a wandering cow is leisurely chewing grass between the rails.",
            "props": ["modern digital locomotive console", "wooden stick tapping cow flank"],
            "audio_sfx": "Pneumatic Train Horn Blast + Cow Moo"
        },
        {
            "id": "satire_zero_call_drop_signal_hunt",
            "location": "Terrace Water Tank with Mobile Stretched High",
            "relationship": "Telecom Customer & AI Customer Care Voice",
            "characters": ["📱 Frustrated Caller (नेटवर्क ढूंढता नागरिक)", "🤖 Automated Voice (एआई कस्टमर केयर)"],
            "setting": "A citizen balancing on a terrace water tank with their smartphone stretched high toward the sky trying to get a single bar of 5G signal.",
            "props": ["smartphone held at arm's length", "call drop disconnect tone"],
            "audio_sfx": "Call Drop Three Beeps + Robotic Recorded Message"
        }
    ],

    "Future Forecast & What Next": [
        {
            "id": "forecast_ai_jobs_debate",
            "location": "Modern Tech Incubator Whiteboard",
            "relationship": "Senior Software Architect & Fresh CS Graduate",
            "characters": ["💻 Tech Architect (सीनियर आर्किटेक्ट)", "🧑 Fresh Graduate (नया इंजीनियर)"],
            "setting": "A startup lab whiteboard mapping out automated code pipelines, debating whether junior developer roles will exist in 2028.",
            "props": ["interactive AI prompt terminal", "traditional coding textbook"],
            "audio_sfx": "Rapid Keystrokes + Server Notification Ping"
        },
        {
            "id": "forecast_climate_urban_map",
            "location": "City Metropolitan Planning Projection Room",
            "relationship": "Urban Hydrologist & Municipal Commissioner",
            "characters": ["🗺️ Climate Planner (शहरी योजनाकार)", "👔 Commissioner (नगर आयुक्त)"],
            "setting": "A high-resolution topographic projection table showing 2035 sea-level and monsoon flood contours overtaking low-lying coastal suburbs.",
            "props": ["laser pointer on elevation contours", "climate risk dossier"],
            "audio_sfx": "Projection Laser Click + Low Drone of Air Conditioning"
        },
        {
            "id": "forecast_ev_grid_transformation",
            "location": "Smart Power Grid Dispatch Operations Room",
            "relationship": "Power Grid Dispatcher & EV Fleet Manager",
            "characters": ["⚡ Grid Controller (ग्रिड नियंत्रक)", "🚌 EV Bus Operator (ईवी फ्लीट मैनेजर)"],
            "setting": "Massive wall-sized electric grid monitors displaying peak evening load spikes as millions of electric scooters plug into chargers simultaneously.",
            "props": ["megawatt dispatch console", "fast-charging fleet schedule"],
            "audio_sfx": "Substation Electrical Hum + Digital Alert Chime"
        },
        {
            "id": "forecast_space_economy",
            "location": "Commercial Satellite Mission Operations Floor",
            "relationship": "Commercial Space Flight Director & Payload Investor",
            "characters": ["🛰️ Flight Director (मिशन डायरेक्टर)", "📈 Space Venture Capitalist (स्पेस इन्वेस्टर)"],
            "setting": "Telemetry consoles tracking commercial low-Earth orbit satellite constellations launching broadband internet across rural territories.",
            "props": ["telemetry orbital tracker", "satellite model mockup"],
            "audio_sfx": "Telemetry Digital Chirp + Radio Communications Loop"
        },
        {
            "id": "forecast_agritech_drone_farming",
            "location": "Smart Agricultural Farm Field Station",
            "relationship": "Drone Agri-Tech Specialist & Traditional Farmer",
            "characters": ["🚁 Drone Pilot Agronomist (ड्रोन कृषि विशेषज्ञ)", "🌾 Progressive Farmer (प्रगतिशील किसान)"],
            "setting": "An agricultural drone hovering automatically over mustard crop fields, transmitting real-time moisture and fertilizer heatmaps to a tablet.",
            "props": ["drone flight controller joystick", "crop soil sensor probe"],
            "audio_sfx": "Multirotor Drone High-Pitch Buzz + Tablet Notification"
        },
        {
            "id": "forecast_fintech_cashless_society",
            "location": "Hyper-Connected Digital Market Stall",
            "relationship": "Biometric Payment Tech Lead & Street Retailer",
            "characters": ["💳 Digital Payments Pioneer (डिजिटल पेमेंट इंजीनियर)", "🧑 Retail Merchant (दुकानदार)"],
            "setting": "A busy wholesale market where payments occur exclusively through facial recognition scanners and palm-vein readers without mobile devices.",
            "props": ["palm biometric verification sensor", "digital balance audio speaker"],
            "audio_sfx": "Biometric Sensor Tone + Multi-Language Audio Confirmation"
        }
    ],

    "Follow the Money / Economic Audit": [
        {
            "id": "money_corporate_tax_audit",
            "location": "Chartered Accountant's Audit Chamber",
            "relationship": "Senior Auditor & Corporate Finance Head",
            "characters": ["📊 Senior CA (वरिष्ठ चार्टर्ड अकाउंटेंट)", "💼 CFO (कंपनी वित्त प्रमुख)"],
            "setting": "Desks covered in audited balance sheets, transfer-pricing ledgers, and offshore subsidiary transaction flowcharts.",
            "props": ["thick audit file binder", "financial calculator"],
            "audio_sfx": "Rapid Calculator Keystrokes + Heavy File Binder Clack"
        },
        {
            "id": "money_real_estate_black_money",
            "location": "Luxury Villa Sales Gallery Lounge",
            "relationship": "Real Estate Broker & Speculative Buyer",
            "characters": ["🏢 Property Consultant (प्रॉपर्टी ब्रोकर)", "🧑 Investor (रियल एस्टेट निवेशक)"],
            "setting": "A private discussion room in an ultra-luxury development discussing circle rates versus actual cash component ratios.",
            "props": ["architectural 3D villa model", "circle rate government gazette copy"],
            "audio_sfx": "Espresso Cup Clink + Blueprint Paper Unfold"
        },
        {
            "id": "money_tender_procurement_kickback",
            "location": "Public Works Department (PWD) Corridor",
            "relationship": "Infrastructure Contractor & Executive Engineer",
            "characters": ["🏗️ PWD Contractor (सड़क ठेकेदार)", "👔 Executive Engineer (अधिशासी अभियंता)"],
            "setting": "A dim PWD corridor corner reviewing road construction tender bids and percentage commissions on bitumen mixtures.",
            "props": ["sealed tender bid envelope", "bitumen quality inspection report"],
            "audio_sfx": "Paper Envelope Tear + Creaking Corridor Door"
        },
        {
            "id": "money_bullion_gold_smuggling",
            "location": "Customs Air Cargo Clearance Inspection Bay",
            "relationship": "Customs Enforcement Officer & Bullion Importer",
            "characters": ["🛃 Customs Officer (कस्टम अधीक्षक)", "🪙 Bullion Consignment Agent (गोल्ड एजेंट)"],
            "setting": "An airport cargo bay holding industrial machinery parts scanned under X-ray showing concealed solid gold cylinder cores.",
            "props": ["X-ray scanner monitor display", "chemical acid testing streak stone"],
            "audio_sfx": "X-Ray Machine Buzz + Heavy Metallic Gold Bar Clink"
        },
        {
            "id": "money_coaching_empire_revenues",
            "location": "Commercial Coaching Consortium Head Office",
            "relationship": "Coaching Chain CEO & Financial Controller",
            "characters": ["🎓 Coaching Conglomerate CEO (कोचिंग साम्राज्य प्रमुख)", "📈 Financial Auditor (फाइनेंशियल ऑडिटर)"],
            "setting": "A glass executive tower reviewing thousands of crores in non-refundable student hostel fees, test series subscriptions, and faculty buyout costs.",
            "props": ["franchise revenue bar chart", "faculty transfer contract"],
            "audio_sfx": "Executive Pen Tap + Computer Mouse Clicks"
        },
        {
            "id": "money_dynamic_airline_surge",
            "location": "Aviation Ticket Operations Control Console",
            "relationship": "Airlines Revenue Manager & Stranded Passenger",
            "characters": ["✈️ Airline Revenue Strategist (एविएशन मैनेजर)", "🧑 Stranded Traveler (परेशान यात्री)"],
            "setting": "An airline pricing desk showing algorithms quadrupling ticket fares during festival rush while planes sit on tarmac with technical delays.",
            "props": ["surge pricing algorithm monitor", "boarding pass with exorbitant price tag"],
            "audio_sfx": "Keyboard Rapid Clatter + Airport PA Announcement"
        }
    ],

    "Emotional & Human Story": [
        {
            "id": "human_migrant_family_return",
            "location": "Railway Platform Edge at Dawn",
            "relationship": "Returning Migrant Worker & Young Daughter",
            "characters": ["🚆 Migrant Father (प्रवासी पिता)", "👧 Little Daughter (मासूम बेटी)"],
            "setting": "A crowded train platform at 5 AM with rolled-up bedding rolls, steel trunks, and morning mist hanging over the rails.",
            "props": ["tied steel trunk with rope", "plastic water bottle"],
            "audio_sfx": "Train Engine Whistle + Early Morning Platform Footsteps"
        },
        {
            "id": "human_peasant_daughter_education",
            "location": "Mud House Veranda by Kerosene Lamp",
            "relationship": "Farming Father & Scholarship-Winning Daughter",
            "characters": ["🌾 Small Farmer (मेहनती किसान)", "👩 Med-School Aspirant Daughter (मेधावी बेटी)"],
            "setting": "A humble earthen veranda where a farmer proudly places his calloused hands on his daughter's medical college admission merit list.",
            "props": ["illuminated admission letter", "flickering kerosene lantern"],
            "audio_sfx": "Night Crickets + Rustle of Parchment Paper"
        },
        {
            "id": "human_soldier_homecoming",
            "location": "Small Town Bus Stand Welcome Corner",
            "relationship": "Returning Soldier & Aging Mother",
            "characters": ["🎖️ Jawan on Leave (छुट्टी पर आया जवान)", "👵 Mother (प्रतीक्षारत मां)"],
            "setting": "A rural bus stop shaded by neem tree where a soldier carrying military rucksack is embraced by his waiting mother with tears in eyes.",
            "props": ["heavy olive-green military rucksack", "cotton aarti thali"],
            "audio_sfx": "Bus Pulling Away in Dust + Soft Emotional Music Note"
        },
        {
            "id": "human_handloom_weaver_legacy",
            "location": "Varanasi Silk Weaver's Loom Pit",
            "relationship": "Master Silk Weaver & Young Grandson",
            "characters": ["🧶 Master Weaver (बुजुर्ग बुनकर)", "🧑 Grandson (पोता)"],
            "setting": "A traditional pit-loom room where generations of silk zari weaving are passed down despite industrial powerloom competition.",
            "props": ["wooden handloom shuttle", "pure silver zari thread spool"],
            "audio_sfx": "Rhythmic Wooden Shuttle Clack-Clack + Soft Breathing"
        },
        {
            "id": "human_disaster_rescue_worker",
            "location": "Debris Clearing Site After Landslide",
            "relationship": "NDRF Rescuer & Rescued Child",
            "characters": ["🦺 NDRF Rescue Specialist (बचाव कर्मी)", "🧒 Rescued Child (सुरक्षित बच्चा)"],
            "setting": "Rain-soaked hillside debris where an NDRF rescuer carefully wraps a warm foil emergency blanket around a recovered child.",
            "props": ["foil thermal emergency blanket", "rescue helmet with headlight"],
            "audio_sfx": "Heavy Rain on Canvas + Sigh of Relief"
        },
        {
            "id": "human_community_kitchen_dignity",
            "location": "Gurdwara / Temple Community Langar Hall",
            "relationship": "Volunteer Cook & Hungry Laborer",
            "characters": ["🍲 Langar Sewadar (सेवादार)", "🧑 Daily Wage Laborer (मजदूर)"],
            "setting": "A clean tiled langar hall where steaming dal and fresh rotis are served with equal dignity to all sitting in rows on the floor.",
            "props": ["large steel dal ladle", "fresh wheat rotis on cloth"],
            "audio_sfx": "Steel Plates Clink + Reverent Chant in Background"
        }
    ],

    "Actionable Advice / Life Hack": [
        {
            "id": "advice_cyber_fraud_defense",
            "location": "Home Living Room with Smartphone",
            "relationship": "Cyber Crime Consultant & Common User",
            "characters": ["🛡️ Cyber Security Specialist (साइबर सुरक्षा विशेषज्ञ)", "🧑 Common Smartphone User (नागरिक)"],
            "setting": "A clean, direct-to-camera demonstration of exact smartphone settings to block unauthorized APKs and fraudulent bank SMS links.",
            "props": ["smartphone with blocked permission toggle", "fraud APK alert warning on screen"],
            "audio_sfx": "Digital Alert Beep + Touchscreen Click"
        },
        {
            "id": "advice_gold_purity_hallmark",
            "location": "Jewellery Testing Counter with Magnifier",
            "relationship": "BIS Hallmarking Inspector & Jewellery Buyer",
            "characters": ["🔍 BIS Inspector (हॉलमार्क निरीक्षक)", "👩 Gold Buyer (सोना खरीदार)"],
            "setting": "A jeweler's counter showing how to use the BIS Care mobile app to verify 6-digit HUID code before buying any gold ornament.",
            "props": ["jeweler's 10x magnifying loupe", "BIS HUID 6-digit laser code on ring"],
            "audio_sfx": "Metallic Ring Clink + App QR Scan Beep"
        },
        {
            "id": "advice_traffic_e_challan_contest",
            "location": "Traffic Virtual Court Portal Screen",
            "relationship": "Motor Vehicle Legal Advisor & Driver",
            "characters": ["⚖️ Legal Aid Advisor (मोटर वाहन सलाहकार)", "🛵 Scooter Commuter (चालान प्राप्त चालक)"],
            "setting": "A laptop screen showing the step-by-step virtual court dispute process for contesting illegal or camera-glitch traffic challans online.",
            "props": ["laptop showing virtual court website", "photograph of contested traffic camera angle"],
            "audio_sfx": "Mouse Click + Document Download Chime"
        },
        {
            "id": "advice_epfo_pf_withdrawal_fix",
            "location": "Provident Fund Helpdesk Desk",
            "relationship": "Labor Law Consultant & Salaried Employee",
            "characters": ["👔 EPFO Consultant (पीएफ सलाहकार)", "🧑 Salaried Worker (कर्मचारी)"],
            "setting": "A step-by-step walk-through showing how to link bank KYC and correct name mismatches preventing provident fund claim rejections.",
            "props": ["UAN member portal login page", "bank passbook with seal"],
            "audio_sfx": "Keyboard Typing + Success Checkmark Tone"
        },
        {
            "id": "advice_generic_medicine_lookup",
            "location": "Generic Drug Formulary Counter",
            "relationship": "Clinical Pharmacist & Chronic Patient",
            "characters": ["💊 Clinical Pharmacist (फार्मासिस्ट)", "👴 Pensioner (दवा खरीदार)"],
            "setting": "Demonstration using official 1mg/Jan Aushadhi search tool to find identical salt chemical compositions costing a fraction of branded pills.",
            "props": ["salt composition database printout", "twin blister packs of same drug"],
            "audio_sfx": "Paper Rustle + Pill Blister Pop"
        },
        {
            "id": "advice_land_registry_encumbrance_check",
            "location": "Sub-Registrar Digital Record Kiosk",
            "relationship": "Property Title Lawyer & First-Time Plot Buyer",
            "characters": ["📜 Title Verification Lawyer (दस्तावेज वकील)", "🧑 Plot Buyer (प्लॉट खरीदार)"],
            "setting": "Detailed instructions on obtaining a 30-year online non-encumbrance certificate (EC) from revenue portals before paying plot booking token.",
            "props": ["certified non-encumbrance certificate", "survey boundary plot blueprint"],
            "audio_sfx": "Official Document Seal Stamp + Paper Signature Scratch"
        }
    ]
}


# -----------------------------------------------------------------------------
# 3. SCRIPT TOPIC DOMAINS (Minimum 6 Setups per Script Topic Domain)
# -----------------------------------------------------------------------------

DOMAIN_SETUPS: Dict[str, List[Dict[str, Any]]] = {
    "government_sir": [
        {
            "id": "gov_sir_collectorate_desk",
            "location": "District Collectorate Administrative Planning Chamber",
            "relationship": "Senior Administrative Officer & Industrial Investor",
            "setting": "A bustling government administrative planning office and collectorate corridor. Wooden desks stacked with official files, blueprint maps of the Special Investment Region (SIR), ceiling fans, and official wall seals.",
            "characters": [
                "👔 Sharma Ji (Government Administrative Officer - वरिष्ठ अधिकारी)",
                "🧑 Rajesh (Industrial Investor / Local Landowner - उद्यमी / नागरिक)"
            ],
            "props": ["Special Investment Region blueprint map", "blue official document file folder", "ink stamp"],
            "audio_sfx": "Paper File Thud + Official Stamp Press",
            "wardrobes": {
                "SHARMA JI": "Crisp half-sleeve formal collared shirt with ballpoint pens in front pocket and official government ID lanyard.",
                "RAJESH": "Smart-casual collared shirt and trousers, holding a blue official document file folder."
            }
        },
        {
            "id": "gov_sir_land_revenue_patwari",
            "location": "Tehsil Land Revenue Record Office",
            "relationship": "Patwari (Revenue Clerk) & Farmer / Landowner",
            "characters": [
                "📜 Patwari Ramnath (Village Revenue Officer - लेखपाल / पटवारी)",
                "🌾 Kisan Sukhdev (Agricultural Landowner - जमीन मालिक किसान)"
            ],
            "setting": "A bustling tehsil record office with cloth-bound land record bahi-khatas, village cadastral map sheets, and waiting landholders.",
            "props": ["cloth-wrapped land revenue ledger (बस्ता)", "khasra-khatauni certificate"],
            "audio_sfx": "Cloth Bahi-Khata Thud + Inkpot Pen Scratch",
            "wardrobes": {
                "PATWARI RAMNATH": "Traditional cotton shirt with fabric vest and reading glasses on cord.",
                "KISAN SUKHDEV": "White dhoti-kurta with gamchha on shoulder, holding land title papers."
            }
        },
        {
            "id": "gov_sir_municipal_zoning",
            "location": "Municipal Corporation Urban Town Planning Cell",
            "relationship": "Chief Town Planner & Residential Developer",
            "characters": [
                "📐 Engineer Mehta (Town Planning Director - नगर योजनाकार)",
                "🏢 Builder Singhal (Project Developer - प्रोजेक्ट बिल्डर)"
            ],
            "setting": "Large drafting tables with 3D master plans for highway bypasses, zoning clearance stamps, and municipal seal dossiers.",
            "props": ["masterplan zoning map", "clearance application file with red ribbon"],
            "audio_sfx": "Blueprint Roll Snap + Desk Ruler Tap",
            "wardrobes": {
                "ENGINEER MEHTA": "Checked formal shirt with roll-up sleeves and government ID badge.",
                "BUILDER SINGHAL": "Safari suit with gold wristwatch holding clearance folder."
            }
        },
        {
            "id": "gov_sir_secretariat_corridor",
            "location": "State Secretariat (Mantralaya) Corridor",
            "relationship": "Joint Secretary & Public Sector Contractor",
            "characters": [
                "🏛️ Joint Secretary Mathur (IAS Officer - संयुक्त सचिव)",
                "💼 Contractor Verma (Infrastructure Vendor - सरकारी ठेकेदार)"
            ],
            "props": ["confidential cabinet note folder", "official brass security pass"],
            "setting": "A long carpeted secretariat corridor flanked by wooden ministerial chambers, brass nameplates, and peons carrying red-labeled files.",
            "audio_sfx": "Muffled Marble Footsteps + Distant Typewriter Clatter",
            "wardrobes": {
                "JOINT SECRETARY MATHUR": "Dark formal Nehru jacket over spotless white shirt with state emblem lapel pin.",
                "CONTRACTOR VERMA": "Formal collared shirt and tailored trousers clutching project binder."
            }
        },
        {
            "id": "gov_sir_pension_welfare",
            "location": "Social Welfare & Pension Distribution Counter",
            "relationship": "Welfare Inspector & Elderly Widow Pensioner",
            "characters": [
                "📋 Welfare Inspector Sneha (समाज कल्याण अधिकारी)",
                "👵 Shanti Devi (Elderly Pensioner - बुजुर्ग पेंशनभोगी)"
            ],
            "props": ["pension verification passbook", "biometric thumbprint verification device"],
            "setting": "A ground-floor citizen service window with queued elderly citizens verifying monthly welfare transfers under ceiling fan.",
            "audio_sfx": "Biometric Machine Beep + Passbook Leafing Sound",
            "wardrobes": {
                "WELFARE INSPECTOR SNEHA": "Simple printed cotton kurti with government ID lanyard.",
                "SHANTI DEVI": "Faded cotton saree clutching passbook in trembling hands."
            }
        },
        {
            "id": "gov_sir_sub_registrar_deed",
            "location": "Sub-Registrar Deed Registration Office",
            "relationship": "Sub-Registrar Officer & Property Buyer",
            "characters": [
                "🖋️ Sub-Registrar Tripathi (उप-निबंधक अधिकारी)",
                "🧑 Kabir (First-Time Buyer - रजिस्ट्री कराने वाला नागरिक)"
            ],
            "props": ["stamp paper legal deed with red wax seal", "digital webcam for biometric photo"],
            "setting": "A busy deed registry room with green stamp paper files, biometric cameras, signature registers, and deed writers outside windows.",
            "audio_sfx": "Heavy Seal Stamp Thud + Webcam Click",
            "wardrobes": {
                "SUB-REGISTRAR TRIPATHI": "Half-sleeve collared shirt with government ID badge.",
                "KABIR": "Modest formal shirt with plastic envelope of stamp papers."
            }
        }
    ],

    "healthcare": [
        {
            "id": "health_hospital_opd",
            "location": "Government Hospital OPD Corridor & Consultation Room",
            "relationship": "Senior Physician & Common Citizen Patient",
            "characters": [
                "🩺 Dr. Rajesh (Senior Hospital Physician - वरिष्ठ चिकित्सक)",
                "🧑 Ramesh (Patient / Common Citizen - मरीज)"
            ],
            "props": ["medical prescription slip", "medicine strip", "stethoscope"],
            "setting": "Government hospital OPD corridor and consultation room. Stethoscopes, medicinal cabinets, official health posters on green-painted walls, and patient queue in background.",
            "audio_sfx": "Hospital Murmur + Medicine Strip Pop",
            "wardrobes": {
                "DR. RAJESH": "White medical lab coat over light-blue formal shirt with stethoscope around neck.",
                "RAMESH": "Everyday modest cotton shirt and trousers, holding a medical prescription slip."
            }
        },
        {
            "id": "health_casualty_ward",
            "location": "24x7 Emergency Casualty Ward Entrance",
            "relationship": "Casualty Duty Doctor & Panicked Relative",
            "characters": [
                "🩺 Dr. Alok (Emergency Medical Officer - ईएमओ डॉक्टर)",
                "🧑 Vikram (Worried Patient Attendant - तीमारदार)"
            ],
            "props": ["emergency triage clipboard", "oxygen pulse oximeter"],
            "setting": "Fast-moving emergency ward with wheeled stretchers, flashing ambulance red lights visible through swing doors, and vital monitors beeping.",
            "audio_sfx": "Heart Rate Monitor Pulse + Urgent Wheel Stretcher Rattle",
            "wardrobes": {
                "DR. ALOK": "Surgical scrubs with stethoscopes in pocket and plastic ID badge.",
                "VIKRAM": "Disheveled casual t-shirt and jeans pacing with anxious gestures."
            }
        },
        {
            "id": "health_generic_pharmacy",
            "location": "Jan Aushadhi Generic Pharmacy Counter",
            "relationship": "Licensed Chemist & Chronic Illness Pensioner",
            "characters": [
                "💊 Pharmacist Neha (जेनेरिक फार्मासिस्ट)",
                "👴 Sharma Ji (Chronic Patient - नियमित मरीज)"
            ],
            "props": ["Jan Aushadhi generic medicine box", "handwritten doctor prescription"],
            "setting": "A tidy generic medical outlet with shelves filled with low-cost medicines and digital price comparison poster prominently displayed.",
            "audio_sfx": "Pill Bottle Shake + Medicine Blister Pack Snip",
            "wardrobes": {
                "PHARMACIST NEHA": "White pharmacy coat with licensed chemist ID clip.",
                "SHARMA JI": "Khadi kurta holding a cloth medical file pouch."
            }
        },
        {
            "id": "health_pathology_lab",
            "location": "Diagnostic Pathology Blood Testing Lab",
            "relationship": "Lab Technician & Anxious Patient",
            "characters": [
                "🔬 Tech Manoj (Senior Lab Technician - पैथोलॉजिस्ट)",
                "👩 Sunita (Patient Awaiting Report - मरीज)"
            ],
            "props": ["vacutainer blood sample tube", "centrifuge machine", "printed lipid report"],
            "setting": "A busy diagnostic pathology laboratory with centrifuge units, chemical reagents, blood sample racks, and patients waiting for lipid profile reports.",
            "audio_sfx": "Centrifuge Whir + Barcode Scanner Beep",
            "wardrobes": {
                "TECH MANOJ": "Blue laboratory coat, disposable nitrile gloves, and spectacles.",
                "SUNITA": "Comfortable salwar-kameez pressing cotton swab to inner elbow."
            }
        },
        {
            "id": "health_rural_phc",
            "location": "Primary Health Centre (PHC) Immunization Hall",
            "relationship": "ANM Health Worker & Village Mother",
            "characters": [
                "💉 ANM Shanti (Community Health Worker - एएनएम सिस्टर)",
                "👩 Meera (Village Mother - ग्रामीण मां)"
            ],
            "props": ["cold-chain vaccine carrier box", "child immunization immunization card"],
            "setting": "A whitewashed primary health centre veranda with health awareness charts on walls, blue cold-chain vaccine boxes, and village mothers with infants.",
            "audio_sfx": "Baby Soft Whimper + Cold-Chain Box Latch Click",
            "wardrobes": {
                "ANM SHANTI": "Official blue-bordered white cotton staff nurse saree with hospital pin.",
                "MEERA": "Traditional printed daily-wear village saree holding infant wrapped in towel."
            }
        },
        {
            "id": "health_ayush_wellness",
            "location": "Government AYUSH & Traditional Wellness Center",
            "relationship": "Ayurvedic Medical Officer & Patient",
            "characters": [
                "🌿 Vaidya Shastri (Ayurvedic Physician - आयुष चिकित्सक)",
                "🧑 Rohan (Lifestyle Ailment Patient - मरीज)"
            ],
            "props": ["brass mortar and pestle", "herbal formulation jar"],
            "setting": "A serene government traditional medicine clinic with wooden herb drawers, brass mortar and pestle on desk, and potted medicinal plants in courtyard.",
            "audio_sfx": "Mortar Pestle Grinding + Soothing Water Fountain",
            "wardrobes": {
                "VAIDYA SHASTRI": "Traditional light yellow kurta with Ayurvedic physician lapel crest.",
                "ROHAN": "Casual collared polo shirt and trousers."
            }
        }
    ],

    "legal": [
        {
            "id": "legal_high_court_steps",
            "location": "High Court Entrance Steps & Pillared Corridor",
            "relationship": "Senior High Court Advocate & Litigant Client",
            "characters": [
                "⚖️ Advocate Verma (Senior High Court Lawyer - वरिष्ठ अधिवक्ता)",
                "🧑 Kabir (Litigant / Common Citizen - मुवक्किल / नागरिक)"
            ],
            "props": ["tied legal case file", "law book", "petition document"],
            "setting": "High Court entrance steps and pillared corridor. Advocates carrying tied legal case files, official notices on notice boards, and waiting litigants in background.",
            "audio_sfx": "Gavel Impact + Case File Rustle",
            "wardrobes": {
                "ADVOCATE VERMA": "Black legal advocate coat with white neckband over crisp white collared shirt.",
                "KABIR": "Modest formal attire, clutching a tied legal case file folder."
            }
        },
        {
            "id": "legal_district_notary",
            "location": "District Court Notary & Affidavit Shed",
            "relationship": "Court Notary Advocate & Stamp Paper Buyer",
            "characters": [
                "🖋️ Notary Advocate Saxena (नोटरी अधिवक्ता)",
                "🧑 Rajesh (Affidavit Applicant - आवेदक)"
            ],
            "props": ["red notary seal stamp", "notary register ledger", "100-rupee judicial stamp paper"],
            "setting": "A bustling tin-roofed shed outside the district courtroom with typists on manual typewriters and notary stamps flying.",
            "audio_sfx": "Manual Typewriter Clack-Clack + Heavy Notary Seal Thud",
            "wardrobes": {
                "NOTARY ADVOCATE SAXENA": "Advocate coat with spectacles and red stamp pad beside elbow.",
                "RAJESH": "Simple checked shirt holding draft affidavit paper."
            }
        },
        {
            "id": "legal_bar_association_library",
            "location": "High Court Bar Association Law Library",
            "relationship": "Senior Counsel & Junior Research Advocate",
            "characters": [
                "⚖️ Senior Counsel Sen (वरिष्ठ अधिवक्ता)",
                "⚖️ Junior Advocate Priya (रिसर्च एसोसिएट)"
            ],
            "props": ["bound All India Reporter (AIR) volume", "tablet displaying Supreme Court judgments"],
            "setting": "Tall wooden bookshelves lined with thousands of leather-bound legal law reports, reading desks with green glass banker's lamps.",
            "audio_sfx": "Heavy Book Spine Thud + Whispered Legal Discussion",
            "wardrobes": {
                "SENIOR COUNSEL SEN": "Full three-piece dark advocate suit with white neckband.",
                "JUNIOR ADVOCATE PRIYA": "Black advocate coat with white band holding stack of cited judgments."
            }
        },
        {
            "id": "legal_police_station_fir",
            "location": "City Police Station Duty Officer Desk",
            "relationship": "Station House Officer (Inspector) & Complainant",
            "characters": [
                "👮 Inspector Rathore (Station In-Charge - थाना प्रभारी)",
                "🧑 Ramesh (Victim Complainant - शिकायतकर्ता नागरिक)"
            ],
            "props": ["official FIR register book", "police wireless handset"],
            "setting": "A busy city police station duty room with wireless walkie-talkie chatter, case notice boards on blue walls, and heavy wooden FIR register desk.",
            "audio_sfx": "Police Radio Squelch + FIR Register Pen Scratch",
            "wardrobes": {
                "INSPECTOR RATHORE": "Khaki police uniform with three stars on shoulder and leather service belt.",
                "RAMESH": "Casual modest shirt with bruised forehead or anxious demeanor."
            }
        },
        {
            "id": "legal_consumer_forum",
            "location": "District Consumer Disputes Redressal Commission",
            "relationship": "Consumer Forum President & Aggrieved Consumer",
            "characters": [
                "⚖️ Presiding Member Gupta (उपभोक्ता फोरम अध्यक्ष)",
                "👩 Sunita (Complainant Consumer - पीड़ित उपभोक्ता)"
            ],
            "props": ["defective home appliance warranty card", "official consumer complaint dossier"],
            "setting": "A formal hearing courtroom with three bench members, national emblem on wooden wall, and complainant presenting evidence.",
            "audio_sfx": "Gavel Double Strike + Document Page Turn",
            "wardrobes": {
                "PRESIDING MEMBER GUPTA": "Formal suit with national emblem pin.",
                "SUNITA": "Everyday cotton saree holding receipts and complaint file."
            }
        },
        {
            "id": "legal_jail_mulakat_room",
            "location": "Central Prison Mulakat (Visitor) Barrier",
            "relationship": "Defence Attorney & Undertrial Prisoner's Brother",
            "characters": [
                "⚖️ Advocate Roy (Defence Counsel - बचाव पक्ष वकील)",
                "🧑 Vikram (Undertrial's Brother - बंदी का भाई)"
            ],
            "props": ["High Court interim bail petition copy", "iron grill barrier"],
            "setting": "Heavy iron-meshed prison visitor partition with jail wardens standing guard and families talking across acoustic window.",
            "audio_sfx": "Heavy Iron Gate Clang + Guard Whistle",
            "wardrobes": {
                "ADVOCATE ROY": "Advocate coat with white band holding bail order copy.",
                "VIKRAM": "Plain shirt with desperate pleading eyes."
            }
        }
    ],

    "tech_corporate": [
        {
            "id": "tech_glass_partition_office",
            "location": "Modern Glass-Partitioned Corporate IT Office & Reception",
            "relationship": "Senior Software Engineer & Product Manager",
            "characters": [
                "👩 Priya (Senior Software Engineer / Colleague 1 - सीनियर डेवलपर)",
                "🧑 Rohan (Product Manager / Colleague 2 - प्रोडक्ट मैनेजर)"
            ],
            "props": ["corporate RFID access badge", "slim work laptop", "coffee mug"],
            "setting": "A glass-partitioned modern corporate IT office and reception. RFID security turnstiles, ergonomic workstations, and indoor foliage in background.",
            "audio_sfx": "RFID Turnstile Beep + Keyboard Clatter",
            "wardrobes": {
                "PRIYA": "Smart-casual corporate collared shirt with company RFID lanyard badge.",
                "ROHAN": "Collared polo shirt, dark denim jeans, with corporate RFID badge clip."
            }
        },
        {
            "id": "tech_cafeteria_breakout",
            "location": "IT Tech Park Cafeteria Breakout Terrace",
            "relationship": "Tech Lead & Fresher Software Developer",
            "characters": [
                "🧑 Karan (Tech Lead - टीम लीड)",
                "🧑 Aarav (Fresher Engineer - फ्रेशर डेवलपर)"
            ],
            "props": ["reusable ceramic coffee tumbler", "laptop displaying code pull request"],
            "setting": "An open-air cafeteria breakout terrace with wooden benches overlooking tech park fountains, coffee cups, and laptops on tables.",
            "audio_sfx": "Coffee Machine Hiss + Laughter from Nearby Lunch Tables",
            "wardrobes": {
                "KARAN": "Casual tech company branded hoodie with smart smartwatch.",
                "AARAV": "Crisp formal shirt (typical fresher attire) with new lanyard."
            }
        },
        {
            "id": "tech_startup_coworking",
            "location": "Startup Hub Open-Desk Coworking Space",
            "relationship": "Co-Founders (Tech CTO & Business CEO)",
            "characters": [
                "🚀 Vikram (Startup CEO - फाउंडर)",
                "💻 Sneha (Startup CTO - को-फाउंडर)"
            ],
            "props": ["investor pitch deck on tablet", "post-it brainstorm wall board"],
            "setting": "A vibrant open-plan coworking space with colorful acoustic dividers, startup pitch decks on digital screens, and mobile app wireframes on glass walls.",
            "audio_sfx": "Dry-Erase Marker Squeak + Startup Chime Alert",
            "wardrobes": {
                "VIKRAM": "Startup graphic t-shirt under unstructured navy blazer with sneakers.",
                "SNEHA": "Round-neck tee, glasses, and earphones around neck."
            }
        },
        {
            "id": "tech_server_datacenter",
            "location": "Enterprise Cloud Server Room",
            "relationship": "DevOps Engineer & Site Reliability Lead",
            "characters": [
                "🖥️ Manoj (Site Reliability Engineer - सिस्टम इंजीनियर)",
                "👩 Priya (Cloud Architect - क्लाउड आर्किटेक्ट)"
            ],
            "props": ["rugged diagnostic tablet", "color-coded ethernet patch cables"],
            "setting": "Cold-aisle server environment with glowing blue and green LED status lights, server fan roar, and strict biometric security door.",
            "audio_sfx": "Server Cooling Fan Roar + Keypad Door Lock Tone",
            "wardrobes": {
                "MANOJ": "Anti-static wrist strap, hooded jacket (due to AC chill), and security badge.",
                "PRIYA": "Fleece jacket over collared shirt with access keycard."
            }
        },
        {
            "id": "tech_wfh_home_office",
            "location": "Urban Home Studio Office Setup",
            "relationship": "Remote Software Engineer & Spouse",
            "characters": [
                "🧑 Rajesh (Remote Senior Developer - रिमोट वर्कर)",
                "👩 Sunita (Spouse - जीवनसाथी)"
            ],
            "props": ["dual-monitor stand", "wireless headset with boom mic", "delivery tiffin"],
            "setting": "A dual-monitor workstation corner in a flat with ring light, ergonomic chair, and kid's toys visible on living room floor beyond.",
            "audio_sfx": "Video Call Join Ping + Keyboard Mechanical Clicks",
            "wardrobes": {
                "RAJESH": "Collared formal shirt on top with comfortable home track pants below.",
                "SUNITA": "Casual home kurti placing a cup of tea by mousepad."
            }
        },
        {
            "id": "tech_hr_appraisal_room",
            "location": "HR Performance Review Glass Pod",
            "relationship": "HR Business Partner & Disgruntled Developer",
            "characters": [
                "👔 HR Director Mehra (एचआर डायरेक्टर)",
                "💻 Kabir (Senior Software Engineer - सीनियर कोडर)"
            ],
            "props": ["bell curve rating printout", "confidential appraisal envelope"],
            "setting": "A formal frosted-glass room with printed appraisal sheets showing 3.2% annual increment versus 80-hour work week.",
            "audio_sfx": "Paper Envelope Slide + Awkward Air Conditioner Silence",
            "wardrobes": {
                "HR DIRECTOR MEHRA": "Formal corporate power suit with polished leather shoes.",
                "KABIR": "Plain polo shirt sitting back with folded arms and skeptical expression."
            }
        }
    ],

    "economy_market": [
        {
            "id": "econ_zaveri_bullion_counter",
            "location": "Zaveri Bazaar Gold Trade Vault & Counter",
            "relationship": "Bullion Merchant & Gold Investor",
            "characters": [
                "🪙 Seth Chunnilal (Senior Bullion Trader - सर्राफा अध्यक्ष)",
                "📈 Rajesh (Gold Investor / Buyer - सोना खरीदार)"
            ],
            "props": ["digital carat balance scale", "hallmarked 100g gold bar replica", "market rate ticker"],
            "setting": "A high-end bullion showroom and traditional gold trade counter. Velvet display trays, digital carat weighing scale, wall-mounted bullion market tickers, and glass counters.",
            "audio_sfx": "Gold Metal Clink + Live Ticker Electronic Chime",
            "wardrobes": {
                "SETH CHUNNILAL": "Traditional embroidered silk kurta with gold chain and accounting eyeglasses.",
                "RAJESH": "Smart-casual collared shirt and trousers holding a bank chequebook."
            }
        },
        {
            "id": "econ_sabzi_mandi_wholesale",
            "location": "Wholesale Agriculture Produce Market (APMC) Yard",
            "relationship": "Wholesale Commission Agent (Arhatiya) & Farmer",
            "characters": [
                "🌾 Arhatiya Banwari (Wholesale Commission Agent - आढ़ती)",
                "🌾 Kisan Ramu (Produce Supplier - किसान)"
            ],
            "props": ["wooden receipt ledger (बही खाता)", "handheld megaphone for open auction"],
            "setting": "A massive open APMC auction platform with mountain heaps of onions and potatoes, tractor trailers backing up, and rapid bidding calls.",
            "audio_sfx": "Auctioneer Fast Bidding Chant + Tractor Diesel Engine",
            "wardrobes": {
                "ARHATIYA BANWARI": "Cotton kurta with pencil behind ear and thick leather ledger binder.",
                "KISAN RAMU": "Dusty dhoti-kurta with towel wrapped securely around head."
            }
        },
        {
            "id": "econ_dalal_street_brokerage",
            "location": "Stock Brokerage Multi-Monitor Trading Floor",
            "relationship": "Equity Trading Advisor & Retail Investor",
            "characters": [
                "📊 Broker Deepak (Stock Market Advisor - इक्विटी ब्रोकर)",
                "🧑 Kabir (Retail Investor - शेयर निवेशक)"
            ],
            "props": ["six-monitor trading terminal with candlestick charts", "live order book"],
            "setting": "A buzzing equity brokerage desk with red and green candle tickers flickering, multiple TV news feeds, and telephone ringers buzzing.",
            "audio_sfx": "Rapid Telephone Ringing + Multi-Monitor Mouse Clicks",
            "wardrobes": {
                "BROKER DEEPAK": "Half-sleeve formal shirt with sleeves rolled up and headphones on one ear.",
                "KABIR": "Checked casual shirt holding smartphone checking demat app."
            }
        },
        {
            "id": "econ_commercial_bank_teller",
            "location": "Nationalized Commercial Bank Cash Teller Counter",
            "relationship": "Senior Bank Cashier & Small Business Depositor",
            "characters": [
                "💵 Cashier Sharma (Senior Bank Cashier - बैंक खजांची)",
                "🧑 Shopkeeper Gupta (Retail Trader - व्यापारी)"
            ],
            "props": ["bundle of 500-rupee currency notes", "counterfeit note UV scanner detector"],
            "setting": "Heavy bulletproof glass teller cage with digital note counter spinning rapidly and long queue of shopkeepers with cash bags.",
            "audio_sfx": "Electronic Note Counting Machine Flutter + Metal Cash Drawer Slam",
            "wardrobes": {
                "CASHIER SHARMA": "Formal shirt with ink-stained thumb and reading spectacles.",
                "SHOPKEEPER GUPTA": "Linen kurta carrying a sturdy canvas cash zipper bag."
            }
        },
        {
            "id": "econ_kirana_inflation_desk",
            "location": "Neighborhood Kirana Store Checkout",
            "relationship": "Grocery Merchant & Regular Homemaker",
            "characters": [
                "🧑 Grocer Ramesh (किराना दुकानदार)",
                "👩 Sunita (Housewife - नियमित ग्राहक)"
            ],
            "props": ["UPI QR standee", "paper grocery bill with double-digit price hikes"],
            "setting": "A neighborhood provision store front where prices of edible oil, pulses, and wheat flour are tabulated under neon tube.",
            "audio_sfx": "UPI Soundbox Voice Notification + Paper Bag Rustle",
            "wardrobes": {
                "GROCER RAMESH": "Casual collared t-shirt with shop apron and calculation notepad.",
                "SUNITA": "Everyday cotton saree holding shopping bag with frustrated expression."
            }
        },
        {
            "id": "econ_customs_port_cargo",
            "location": "Inland Container Depot Customs Clearance Shed",
            "relationship": "Customs Appraiser & Import-Export Agent",
            "characters": [
                "🛃 Appraiser Verma (सीमा शुल्क मूल्यांकन अधिकारी)",
                "💼 Clearing Agent Mohan (कस्टम क्लीयरिंग एजेंट)"
            ],
            "props": ["bill of entry shipping document", "container cargo seal clamp"],
            "setting": "Industrial port logistics park with stacked shipping containers, giant gantry cranes, and trucks lined for cargo inspection.",
            "audio_sfx": "Gantry Crane Horn + Container Metal Lock Clang",
            "wardrobes": {
                "APPRAISER VERMA": "Customs department uniform with rank stars and clipboard.",
                "CLEARING AGENT MOHAN": "Casual shirt and denim trousers with heavy cargo folder."
            }
        }
    ],

    "education": [
        {
            "id": "edu_coaching_hub_class",
            "location": "High-Density Competitive Coaching Classroom",
            "relationship": "Senior Faculty & Anxious Aspirant",
            "characters": [
                "👨‍🏫 Master Verma (IIT-JEE / UPSC Physics Faculty - प्रमुख शिक्षक)",
                "🧑 Aarav (Competitive Exam Aspirant - गंभीर छात्र)"
            ],
            "props": ["thick physics coaching module", "chalkboard eraser", "classroom microphone"],
            "setting": "A tiered coaching lecture hall packed with 300 students taking furious notes from a blackboard dense with calculus equations.",
            "audio_sfx": "Microphone Lapel Echo + 300 Notebooks Turning Pages",
            "wardrobes": {
                "MASTER VERMA": "Collared formal shirt with chalk dust on trousers and lapel mic clipped to collar.",
                "AARAV": "Casual cotton hoodie with spectacles, hunched over wooden desk."
            }
        },
        {
            "id": "edu_university_canteen",
            "location": "Central University Student Canteen",
            "relationship": "Final-Year University Batchmates",
            "characters": [
                "👩 Ananya (Literature Finalist - छात्रा 1)",
                "🧑 Vikram (Political Science Student - छात्र 2)"
            ],
            "props": ["steel plate of samosas", "university library card", "printed thesis draft"],
            "setting": "A buzzing stone-walled university canteen with student union posters, tea cups on laminate tables, and energetic ideological debate.",
            "audio_sfx": "Canteen Crockery Clatter + Heated Student Debate Murmur",
            "wardrobes": {
                "ANANYA": "Handloom kurti with silver jhumkas and canvas tote bag.",
                "VIKRAM": "Denim jacket over black tee with cloth sling bag."
            }
        },
        {
            "id": "edu_exam_controller_window",
            "location": "State Board / University Exam Controller Office",
            "relationship": "Exam Controller Babu & Paper-Leak Victim Student",
            "characters": [
                "👔 Clerk Mathur (परीक्षा नियंत्रण बाबू)",
                "🧑 Rohan (Protesting Student - पीड़ित छात्र)"
            ],
            "props": ["stamped hall ticket admit card", "paper leak cancellation notification"],
            "setting": "An iron-barred university inquiry window where students gather after sudden examination cancellations and delays.",
            "audio_sfx": "Loud Student Crowd Shouting Outside + Window Grill Rattle",
            "wardrobes": {
                "CLERK MATHUR": "Old safari shirt behind iron mesh window looking exasperated.",
                "ROHAN": "Faded t-shirt holding crumpled admit card against the bars."
            }
        },
        {
            "id": "edu_placement_interview_hall",
            "location": "College Campus Placement Cell Waiting Corridor",
            "relationship": "Campus Placement Officer & Nervous Candidate",
            "characters": [
                "💼 Placement Officer Sneha (प्लेसमेंट अधिकारी)",
                "🧑 Kabir (Engineering Job Seeker - छात्र)"
            ],
            "props": ["leather resume folder", "company shortlist notice board"],
            "setting": "A quiet air-conditioned college placement waiting lobby with students in brand-new ill-fitting suits adjusting ties nervously.",
            "audio_sfx": "Polished Shoes on Tile + Nervous Throat Clearing",
            "wardrobes": {
                "PLACEMENT OFFICER SNEHA": "Formal corporate saree with placement cell clip.",
                "KABIR": "Crisp black formal suit with freshly tied red tie and folder."
            }
        },
        {
            "id": "edu_hostel_room_midnight",
            "location": "Cramped Two-Bed Student Hostel Room",
            "relationship": "Hostel Roommates (रूममेट्स)",
            "characters": [
                "🧑 Bunty (Nocturnal Crammer - छात्र 1)",
                "🧑 Deepak (Exhausted Repeater - छात्र 2)"
            ],
            "props": ["electric heating kettle boiling instant noodles", "stacks of sticky-note books"],
            "setting": "A tiny hostel room with peeling whitewash walls covered in world maps, formula sheets, two iron cots, and single fluorescent tube.",
            "audio_sfx": "Electric Kettle Bubble + Pen Scribble on Rough Pad",
            "wardrobes": {
                "BUNTY": "Cotton track pants and sleeveless undershirt with glasses on.",
                "DEEPAK": "Disheveled t-shirt lying on bed staring up at formula poster."
            }
        },
        {
            "id": "edu_primary_school_balwadi",
            "location": "Rural Primary School Courtyard",
            "relationship": "Primary School Master & Concerned Parent",
            "characters": [
                "👨‍🏫 Master Ji (Primary Headmaster - हेडमास्टर)",
                "🌾 Kisan Ramu (Parent - किसान पिता)"
            ],
            "props": ["midday meal metal plate", "elementary Hindi alphabet textbook"],
            "setting": "A village primary school veranda with children sitting on coir mats chanting Hindi multiplication tables under an open sky.",
            "audio_sfx": "Children Chanting Multiplication Tables in Chorus",
            "wardrobes": {
                "MASTER JI": "Clean khadi kurta-pyjama with wooden pointing stick.",
                "KISAN RAMU": "Simple dhoti-kurta holding his little son's hand."
            }
        }
    ],

    "infrastructure_transit": [
        {
            "id": "infra_airport_boarding_gate",
            "location": "International Airport Departure Terminal & Gate",
            "relationship": "Airline Captain Pilot & Delayed Passenger",
            "characters": [
                "✈️ Captain Rajesh (Senior Flight Commander - मुख्य पायलट)",
                "🧑 Kabir (Frustrated Delayed Passenger - हवाई यात्री)"
            ],
            "props": ["pilot navigation tablet", "boarding pass showing 4-hour delay"],
            "setting": "Modern international airport departure terminal and flight dispatch lounge. Panoramic glass windows overlooking the runway tarmac, flight departure screens, and boarding gate.",
            "audio_sfx": "Airport Chime Announcement + Jet Engine Taxi Whine",
            "wardrobes": {
                "CAPTAIN RAJESH": "Crisp white pilot uniform with four gold epaulet stripes on shoulders and airline peak cap.",
                "KABIR": "Modern travel hoodie and denim jeans with rolling carry-on luggage."
            }
        },
        {
            "id": "infra_railway_dispatch_console",
            "location": "Zonal Railway Locomotive Dispatch & Signaling Console",
            "relationship": "Station Master & Vande Bharat Loco Pilot",
            "characters": [
                "🚆 Station Master Sharma (वरिष्ठ स्टेशन अधीक्षक)",
                "🧑 Loco Pilot Vikram (ट्रेन लोको पायलट)"
            ],
            "props": ["digital track signaling console", "railway green signal flag", "train order book"],
            "setting": "Zonal railway locomotive dispatch room and digital signaling console. Digital track line status consoles, railway dispatch schedule boards, and radio communications.",
            "audio_sfx": "Train Diesel/Electric Horn + Relay Switch Click",
            "wardrobes": {
                "STATION MASTER SHARMA": "Crisp white railway uniform with brass railway insignia buttons.",
                "LOCO PILOT VIKRAM": "Rail pilot navy uniform vest with digital two-way walkie-talkie."
            }
        },
        {
            "id": "infra_metro_control_room",
            "location": "Urban Metro Central Operations Command Center",
            "relationship": "Metro Operations Chief & Track Safety Engineer",
            "characters": [
                "🚇 Controller Neha (मेट्रो ऑपरेशंस कंट्रोलर)",
                "👷 Track Engineer Manoj (ट्रैक सुरक्षा इंजीनियर)"
            ],
            "props": ["multi-screen automated train supervision (ATS) console", "high-visibility hardhat"],
            "setting": "A high-tech darkened operations control room with wall-sized real-time schematic maps of underground and elevated metro lines.",
            "audio_sfx": "Automated Train Arrival Announcement + Electronic Relay Tone",
            "wardrobes": {
                "CONTROLLER NEHA": "Formal collared shirt with metro operations headset.",
                "TRACK ENGINEER MANOJ": "Reflective orange safety vest with heavy site boots."
            }
        },
        {
            "id": "infra_highway_toll_plaza",
            "location": "National Expressway Automated FASTag Toll Barrier",
            "relationship": "Toll Collector & Long-Haul Truck Driver",
            "characters": [
                "🛣️ Toll Operator Rakesh (टोल ऑपरेटर)",
                "🚚 Trucker Balwant Singh (ट्रक ड्राइवर)"
            ],
            "props": ["handheld RFID FASTag scanner", "trip consignment e-way bill"],
            "setting": "A 16-lane expressway toll booth with booming truck diesel exhausts, computerized barrier arms rising and lowering rapidly.",
            "audio_sfx": "Heavy Truck Air Brake Hiss + FASTag Sensor Beep",
            "wardrobes": {
                "TOLL OPERATOR RAKESH": "Fluorescent high-vis jacket inside glass-enclosed booth.",
                "TRUCKER BALWANT SINGH": "Checked flannel shirt with traditional turban and towel on shoulder."
            }
        },
        {
            "id": "infra_flyover_construction_deck",
            "location": "Elevated Expressway Flyover Segment Deck",
            "relationship": "Senior Project Engineer & Heavy Crane Operator",
            "characters": [
                "🏗️ Project Engineer Verma (प्रोजेक्ट इंजीनियर)",
                "👷 Crane Operator Jagdish (क्रेन ऑपरेटर)"
            ],
            "props": ["precast concrete girder diagram", "laser leveling survey tool"],
            "setting": "Eighty feet above ground on an unfinished concrete flyover deck with towering gantry cranes lifting multi-ton concrete segments into place.",
            "audio_sfx": "Heavy Diesel Crane Whir + Steel Cable Creak",
            "wardrobes": {
                "PROJECT ENGINEER VERMA": "White safety helmet, safety harness, and blueprint clipboard.",
                "CRANE OPERATOR JAGDISH": "Yellow hardhat, heavy leather work gloves, and steel-toe boots."
            }
        },
        {
            "id": "infra_inland_port_container",
            "location": "Intermodal Inland Port Logistics Depot",
            "relationship": "Freight Logistics Manager & Freight Train Conductor",
            "characters": [
                "🚢 Logistics Head Singhal (लॉजिस्टिक्स हेड)",
                "🚆 Goods Train Guard Tiwari (मालगाड़ी गार्ड)"
            ],
            "props": ["digital manifest tablet", "tamper-evident container bolt seal"],
            "setting": "An expansive logistics yard with freight trains carrying hundreds of double-stacked containers under giant rail-mounted gantry cranes.",
            "audio_sfx": "Heavy Rail Clatter + Container Thud on Rail Wagon",
            "wardrobes": {
                "LOGISTICS HEAD SINGHAL": "High-vis yellow safety vest over collared shirt.",
                "GOODS TRAIN GUARD TIWARI": "Khaki railway guard uniform with green inspection flag."
            }
        }
    ],

    "environment_climate": [
        {
            "id": "env_aqi_control_tower",
            "location": "City Environmental Monitoring Control Tower & Lab",
            "relationship": "Environmental Scientist & Municipal Field Officer",
            "characters": [
                "🔬 Dr. Sneha (Lead Environmental Scientist - पर्यावरण वैज्ञानिक)",
                "👔 Officer Mathur (Municipal Air Quality Officer - प्रदूषण नियंत्रण अधिकारी)"
            ],
            "props": ["digital particulate PM2.5 air sampler", "real-time AQI heatmap display"],
            "setting": "City environmental monitoring control tower and air analysis lab. Digital AQI hazard index monitors flashing red, air filtration particulate gauges, and city smog horizon view.",
            "audio_sfx": "Air Sampler Pump Whir + Hazard Alarm Pulse",
            "wardrobes": {
                "DR. SNEHA": "White laboratory coat over modest kurti with pollution monitoring badge.",
                "OFFICER MATHUR": "Formal collared shirt and trousers holding city pollution compliance dossier."
            }
        },
        {
            "id": "env_solar_farm_control",
            "location": "Mega Solar Power Plant Substation Cabin",
            "relationship": "Solar Energy Engineer & Local Agrarian Landowner",
            "characters": [
                "☀️ Solar Tech Engineer Rohan (सोलर इंजीनियर)",
                "🌾 Kisan Ramdas (Land Lease Partner - किसान)"
            ],
            "props": ["photovoltaic inverter efficiency monitor", "solar panel cleaning wiper"],
            "setting": "A desert or arid landscape covered in tens of thousands of shimmering blue solar panels reflecting bright sunshine into a high-voltage substation.",
            "audio_sfx": "High-Voltage Inverter Hum + Desert Wind Whistle",
            "wardrobes": {
                "SOLAR TECH ROHAN": "Safety helmet, sunglasses, and high-visibility work shirt.",
                "KISAN RAMDAS": "White cotton dhoti-kurta with sunglasses looking across panels."
            }
        },
        {
            "id": "env_organic_farming_collective",
            "location": "Organic Agriculture Demonstration Farm",
            "relationship": "Agronomist Scientist & Progressive Organic Farmer",
            "characters": [
                "🌱 Agronomist Dr. Rao (कृषि वैज्ञानिक)",
                "🌾 Kisan Sukhwinder (जैविक किसान)"
            ],
            "props": ["vermicompost soil nutrient kit", "heirloom indigenous seed packets"],
            "setting": "Lush multi-cropped farm with drip irrigation tubes, companion flowering plants, and bio-fertilizer compost pits.",
            "audio_sfx": "Drip Irrigation Click + Rustle of Green Crop Leaves",
            "wardrobes": {
                "DR. RAO": "Khadi shirt with field boots and soil testing kit.",
                "KISAN SUKHWINDER": "Turban, cotton kurta, and soil-stained hands showing healthy earth."
            }
        },
        {
            "id": "env_river_flood_embankment",
            "location": "River Embankment Flood Early-Warning Station",
            "relationship": "Irrigation Executive Engineer & Riverside Village Head",
            "characters": [
                "🌊 Irrigation Engineer Verma (सिंचाई अभियंता)",
                "👴 Pradhan Dinanath (ग्राम प्रधान)"
            ],
            "props": ["gauge water level telemetry marker", "flood alert megaphone"],
            "setting": "A stone-reinforced river embankment with muddy floodwaters rushing past calibrated water-level depth markers nearing danger mark.",
            "audio_sfx": "Roaring River Current + Megaphone Static Squelch",
            "wardrobes": {
                "IRRIGATION ENGINEER VERMA": "Waterproof rain jacket with blueprint tube.",
                "PRADHAN DINANATH": "Dhoti-kurta with rain umbrella and worried village elders."
            }
        },
        {
            "id": "env_waste_biomethanation_plant",
            "location": "Municipal Solid Waste Biomethanation Facility",
            "relationship": "Waste Management Director & Sanitation Worker",
            "characters": [
                "♻️ Waste Tech Manager Alok (बायो-वेस्ट मैनेजर)",
                "🦺 Sanitation Operator Ramu (सफाई संचालक)"
            ],
            "props": ["methane gas pressure dial gauge", "organic compost nutrient sack"],
            "setting": "A clean automated municipal composting facility processing hundreds of tons of segregated green organic city kitchen waste.",
            "audio_sfx": "Waste Shredder Drum Rotation + Gas Vent Whoosh",
            "wardrobes": {
                "WASTE TECH MANAGER ALOK": "Safety helmet and clipboard.",
                "SANITATION OPERATOR RAMU": "Heavy rubber boots, protective apron, and respirator mask."
            }
        },
        {
            "id": "env_forestry_nursery",
            "location": "State Forest Department Native Tree Nursery",
            "relationship": "Forest Range Officer & Environmental Youth Volunteer",
            "characters": [
                "🌲 Range Officer Rathore (वन क्षेत्राधिकारी)",
                "👩 Volunteer Priya (पर्यावरण स्वयंसेवक)"
            ],
            "props": ["sapling planting trowel", "geo-tagged afforestation record tablet"],
            "setting": "Thousands of green potted native neem and peepal tree saplings shaded beneath green agro-netting with misty sprinkler lines.",
            "audio_sfx": "Water Sprinkler Swish + Gentle Forest Birds",
            "wardrobes": {
                "RANGE OFFICER RATHORE": "Forest Department khaki uniform with green shoulder strap.",
                "VOLUNTEER PRIYA": "Cotton t-shirt with gardening gloves and canvas hat."
            }
        }
    ],

    "police_safety": [
        {
            "id": "police_traffic_junction",
            "location": "Bustling Urban Traffic Junction with Barricades",
            "relationship": "Traffic Police Inspector & Commuter Driver",
            "characters": [
                "👮 Inspector Yadav (Traffic Enforcement Lead - ट्रैफिक इंस्पेक्टर)",
                "🧑 Bunty (Everyday Commuter - सामान्य नागरिक)"
            ],
            "props": ["digital e-challan POS device", "traffic whistle", "printed driving license"],
            "setting": "Bustling Indian urban traffic junction with barricades. Very fast-paced, high-energy street action to fit the 10-second limit. Barricades, police patrol vehicle, and busy vehicular commotion.",
            "audio_sfx": "Traffic Whistle Blast + Patrol Siren Blip",
            "wardrobes": {
                "INSPECTOR YADAV": "Crisp khaki police uniform with white traffic sleeve bands and service cap.",
                "BUNTY": "Everyday casual printed shirt and trousers."
            }
        },
        {
            "id": "police_thana_reception",
            "location": "City Police Station Citizen Helpdesk (Thana)",
            "relationship": "Duty Sub-Inspector & Citizen Reporting Theft",
            "characters": [
                "👮 Sub-Inspector Shinde (ड्यूटी सब-इंस्पेक्टर)",
                "👩 Sunita (Distressed Citizen - शिकायतकर्ता महिला)"
            ],
            "props": ["stamped receipt copy of complaint", "computer keyboard logging online complaint"],
            "setting": "A tidy modernized police station reception room with glass partition, women's helpdesk sign, and CCTV monitoring screen.",
            "audio_sfx": "Computer Keyboard Typing + Police Walkie-Talkie Chime",
            "wardrobes": {
                "SUB-INSPECTOR SHINDE": "Immaculate khaki uniform with state police shoulder crest.",
                "SUNITA": "Traditional modest kurti holding handwritten complaint paper."
            }
        },
        {
            "id": "police_cyber_crime_cell",
            "location": "District Cyber Crime Investigation Cell",
            "relationship": "Cyber Crime Inspector & Financial Fraud Victim",
            "characters": [
                "💻 Cyber Inspector Verma (साइबर अपराध निरीक्षक)",
                "👴 Sharma Ji (Senior Citizen Pensioner Victim - ठगी का शिकार)"
            ],
            "props": ["fraudulent bank SMS screen", "IP trace forensic terminal"],
            "setting": "A modern forensic office with multi-monitor setups tracking spoofed phone numbers, bank freeze orders, and mule account chains.",
            "audio_sfx": "Keyboard Mechanical Tapping + Monitor Notification Ping",
            "wardrobes": {
                "CYBER INSPECTOR VERMA": "Police uniform with technical division badge.",
                "SHARMA JI": "Simple sweater over kurta holding mobile phone with trembling hands."
            }
        },
        {
            "id": "police_highway_patrol_checkpost",
            "location": "Night Highway Border Inter-State Checkpost",
            "relationship": "Highway Patrol Officer & Commercial Transporter",
            "characters": [
                "🚔 Officer Rathore (हाइवे पेट्रोल अधिकारी)",
                "🚚 Driver Balram (अंतर्राज्यीय ट्रक चालक)"
            ],
            "props": ["reflective breathalyzer test unit", "vehicle registration smartcard"],
            "setting": "A brightly floodlit highway checkpoint at midnight with heavy reflective barricades, flashing blue-red patrol lights, and heavy commercial transport.",
            "audio_sfx": "Breathalyzer Digital Beep + Heavy Truck Idling",
            "wardrobes": {
                "OFFICER RATHORE": "Khaki uniform with high-visibility reflective cross-belt and flashlight.",
                "DRIVER BALRAM": "Cotton kurta-pajama with fabric money belt."
            }
        },
        {
            "id": "police_forensic_crime_scene",
            "location": "Forensic Evidence Collection Van & Cordon",
            "relationship": "Forensic Science Officer & Detective Inspector",
            "characters": [
                "🔬 Forensic Officer Dr. Priya (फोरेंसिक वैज्ञानिक)",
                "🕵️ Detective Inspector Khan (अपराध जांच अधिकारी)"
            ],
            "props": ["evidence marker yellow cones", "tamper-evident plastic evidence bag"],
            "setting": "A cordoned-off scene with yellow police tape, ultraviolet forensic light scanning floor, and numbered evidence markers on ground.",
            "audio_sfx": "Camera Flash Pop + Forensic Kit Latch Click",
            "wardrobes": {
                "FORENSIC OFFICER DR. PRIYA": "White disposable forensic protective suit and gloves.",
                "DETECTIVE INSPECTOR KHAN": "Plainclothes safari suit with leather holster and police ID."
            }
        },
        {
            "id": "police_community_mohalla_panchayat",
            "location": "Neighborhood Community Policing Camp",
            "relationship": "Community Police Officer & Resident Welfare Head",
            "characters": [
                "👮 ACP Mathur (सहायक पुलिस आयुक्त)",
                "🧑 RWA President Gupta (सोसाइटी आरडब्ल्यूए अध्यक्ष)"
            ],
            "props": ["neighborhood CCTV camera placement map", "community contact directory"],
            "setting": "A sunny residential colony park clubroom where colony residents and police officers sit together drinking tea and reviewing night security.",
            "audio_sfx": "Tea Cup Clatter + Respectful Public Applause",
            "wardrobes": {
                "ACP MATHUR": "Khaki officer uniform with peaked cap on table.",
                "RWA PRESIDENT GUPTA": "Smart-casual kurta with colony association badge."
            }
        }
    ],

    "domestic": [
        {
            "id": "domestic_kitchen_budget",
            "location": "A Cozy Indian Middle-Class Household Kitchen & Living Room",
            "relationship": "Husband & Wife (पति-पत्नी)",
            "characters": [
                "👩 Sunita (Wife / Pragmatic Homemaker - समझदार पत्नी)",
                "🧑 Rajesh (Husband / Salaried Employee - नौकरीपेशा पति)"
            ],
            "props": ["handwritten grocery budget list", "gas cylinder receipt", "steel tea cup"],
            "setting": "A cozy Indian middle-class household kitchen and living room. Gas stove, stainless steel spice containers, handwritten grocery list, and tea cups on the counter.",
            "audio_sfx": "Steel Tumbler Clink + Pressure Cooker Whistle",
            "wardrobes": {
                "SUNITA": "Casual traditional printed cotton daily-wear saree or comfortable kurti.",
                "RAJESH": "Casual collared half-sleeve home shirt and cotton trousers."
            }
        },
        {
            "id": "domestic_study_generational",
            "location": "Traditional Indian Household Study Room & Veranda",
            "relationship": "Father & Son (पिता-पुत्र)",
            "characters": [
                "👴 Sharma Ji (Elder Father - पिताजी)",
                "🧑 Aarav (Tech-Minded Son - बेटा)"
            ],
            "props": ["reading spectacles", "morning Hindi newspaper", "college marksheet file"],
            "setting": "A traditional Indian household study room or veranda. Generational contrast atmosphere with reading glasses, newspapers, and study books.",
            "audio_sfx": "Spectacle Case Snap + Newspaper Rustle",
            "wardrobes": {
                "SHARMA JI": "Traditional cotton kurta-pyjama with reading spectacles.",
                "AARAV": "Modern casual hoodie or oversized t-shirt and denim jeans."
            }
        },
        {
            "id": "domestic_festive_living_room",
            "location": "Festive Diwali Decorated Living Room",
            "relationship": "Mother & Daughter (मां-बेटी)",
            "characters": [
                "👩 Mother Shanti (पारिवारिक मां)",
                "👧 Daughter Ananya (कॉलेज छात्रा बेटी)"
            ],
            "props": ["brass thali of terracotta diyas", "powder rangoli stencil"],
            "setting": "A brightly lit home living room decorated with marigold flower garlands, flickering clay diyas, and stainless steel sweet boxes.",
            "audio_sfx": "Diwali Firecracker Pop in Distance + Brass Bell Ring",
            "wardrobes": {
                "MOTHER SHANTI": "Festive silk saree with traditional gold earrings.",
                "DAUGHTER ANANYA": "Bright festive lehenga-kurti with bangles."
            }
        },
        {
            "id": "domestic_balcony_evening_tea",
            "location": "Apartment 5th-Floor Balcony at Sunset",
            "relationship": "Retired Couple (वरिष्ठ दंपत्ति)",
            "characters": [
                "👴 Retired Bank Officer Mohan (सेवानिवृत्त पति)",
                "👵 Suman (सेवानिवृत्त शिक्षिका पत्नी)"
            ],
            "props": ["steaming ginger chai cups in saucers", "potted tulsi plant"],
            "setting": "A modest apartment balcony with potted plants, overlooking evening city lights and birds returning to trees at dusk.",
            "audio_sfx": "Evening Breeze Rustle + Gentle Ceramic Cup Clink",
            "wardrobes": {
                "RETIRED MOHAN": "Soft cotton kurta and reading glasses.",
                "SUMAN": "Comfortable cotton saree with knitted cardigan."
            }
        },
        {
            "id": "domestic_kitchen_gas_cylinder",
            "location": "Kitchen Utility Corner Beside Gas Cylinder",
            "relationship": "Housewife & LPG Gas Delivery Agent",
            "characters": [
                "👩 Homemaker Meera (गृहणी)",
                "🚚 Gas Delivery Agent Ramu (सिलेंडर डिलीवरी मैन)"
            ],
            "props": ["red 14.2kg LPG gas cylinder", "blue consumer passbook and receipt"],
            "setting": "The back utility balcony of an apartment where a new red cylinder is connected with seal broken and soap-water leak check.",
            "audio_sfx": "Heavy Steel Cylinder Clang on Floor + Gas Seal Pop",
            "wardrobes": {
                "HOMEMAKER MEERA": "Everyday home cotton kurti.",
                "GAS DELIVERY AGENT RAMU": "Dusty work shirt, rubber gloves, and brass weight scale."
            }
        },
        {
            "id": "domestic_dining_electricity_bill",
            "location": "Middle-Class Dining Room Table Under Fan",
            "relationship": "Brother & Sister (भाई-बहन)",
            "characters": [
                "🧑 Elder Brother Kabir (बड़ा भाई)",
                "👩 Younger Sister Sneha (छोटी बहन)"
            ],
            "props": ["shockingly high summer electricity bill", "smartphone UPI app"],
            "setting": "A ceiling fan spinning on medium speed over a dining table where siblings analyze soaring summer air conditioner power bills.",
            "audio_sfx": "Ceiling Fan Hum + Smartphone Calculation Tap",
            "wardrobes": {
                "ELDER BROTHER KABIR": "Casual crewneck t-shirt.",
                "YOUNGER SISTER SNEHA": "College casual wear with hair tied in ponytail."
            }
        }
    ]
}


# -----------------------------------------------------------------------------
# 4. CONVENIENT LOOKUP HELPERS
# -----------------------------------------------------------------------------

def get_scene_style_catalog(scene_style: str) -> List[Dict[str, Any]]:
    """Retrieve all available rich setups for a specific Scene Style (min 6)."""
    s_clean = scene_style.split("(")[0].strip().title()
    for key, setups in SCENE_STYLE_SETUPS.items():
        if key.lower() in s_clean.lower() or s_clean.lower() in key.lower():
            return setups
    return SCENE_STYLE_SETUPS.get("Dialogue", [])


def get_creative_angle_catalog(angle: str) -> List[Dict[str, Any]]:
    """Retrieve all available rich setups for a specific Creative Angle (min 6)."""
    a_clean = angle.split("(")[0].strip()
    for key, setups in CREATIVE_ANGLE_SETUPS.items():
        if key.lower() in a_clean.lower() or a_clean.lower() in key.lower():
            return setups
    return CREATIVE_ANGLE_SETUPS.get("Common Citizen Impact", [])


def get_domain_catalog(domain: str) -> List[Dict[str, Any]]:
    """Retrieve all available rich setups for a specific Script Topic Domain (min 6)."""
    d_clean = domain.lower().strip()
    for key, setups in DOMAIN_SETUPS.items():
        if key in d_clean or d_clean in key:
            return setups
    return DOMAIN_SETUPS.get("government_sir", [])
