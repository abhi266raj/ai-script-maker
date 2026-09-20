NEWS TOPIC: {news_topic}
HOOK (0-3s): {hook}
NARRATION / DIALOGUE SUMMARY:
{narration}

TARGET DURATION: {duration_sec}s
NUMBER OF SCENES TO BREAK DOWN: {target_frames}
ESTIMATED SCENE TIMESTAMPS:
{timestamps_text}

RESEARCHED STORY PROPS & LOCATIONS (From Agent 1):
- Physical Props: {props_text}
- Locations & Settings: {locs_text}
- Tangible Character Actions: {actions_text}

UPSTREAM SPOKEN DIALOGUE (Agent 3):
{lines_summary}

{sub_directive}

TASK:
Direct {target_frames} distinct, visually coordinated 9:16 scenes matching the story's narrative flow.
Every scene's visual B-roll MUST feature the exact physical props and actions researched above!
Maintain visual continuity:
- Scene 1 establishes the setting ({locs_text}) and introduces the primary prop ({props_text}).
- Subsequent scenes show close-up/POV interaction with props executing the spoken dialogue.
- Final scene shows the wider crowd or community reaction and comedic/dramatic payoff.

Format strictly as:
SCENE 1:
TIME: [e.g., 0:00 - 0:03]
CHARACTER: [Speaker name]
DIALOGUE: [Exact Hindi dialogue line]
ACTION: [Specific physical actor action, gesture, and prop interaction ONLY - do NOT describe the general location or camera framing here as that is in Scene Description]
TEXT: [Devanagari on-screen text overlay]
SFX: [Sound effect, e.g. Street Ambience + Whoosh]

(Repeat for SCENE 2 to SCENE {target_frames})
