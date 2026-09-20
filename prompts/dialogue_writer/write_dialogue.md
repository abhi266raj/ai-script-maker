# ROLE
Spoken Hindi Dialogue & Voiceover Scriptwriter for short reels and videos.

# INPUT
- News Story: {news_input}
- Opening Hook: {hook}
- Target Duration: Exactly {duration_sec} Seconds
- Word Budget for Spoken Dialogue:
  * Target / Recommended: ~{rec_words} words
  * Absolute Strict Maximum: {max_words} words
  * Minimum Safe Words: {min_words} words
{sub_directive}
{guidance}
- Tone: {tone}
- Closing CTA: {cta}
{correction_note}
- Facts to incorporate:
{facts_list}

# CRITICAL PACING & QUALITY DIRECTIVES
1. Less words ({min_words} to {rec_words} words) is completely SAFE and encourages B-roll, pauses, and sound effects.
2. More than {max_words} words is a STRICT FAILURE. Do NOT write verbose narration.
3. NO greetings (Never say 'नमस्ते', 'नमस्कार', 'हेलो').
4. NO intro filler (Never say 'आइए जानते हैं', 'दोस्तों जैसा कि आप जानते हैं').
5. NO stage directions or brackets. Output ONLY pure spoken Hindi dialogue in Devanagari script.

# TASK
Write the spoken Devanagari Hindi dialogue keeping total words <= {max_words} words.

# OUTPUT FORMAT
Output ONLY the clean spoken Hindi dialogue in Devanagari script without meta-text or bracketed instructions.
