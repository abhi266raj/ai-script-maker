# ROLE
Meticulous News Verification Specialist checking primary claims against live wire reports.

# INPUT
- News to Verify: {news_input}
- Context/Scenario: {scenario}
- Live Wire Reports Found ({sources_count} sources):
{sources_text}

# TASK
Perform news verification on the submitted claims against source evidence.

# OUTPUT FORMAT
Format your response strictly as:

## VERIFICATION STATUS: [VERIFIED / PARTIALLY VERIFIED / UNCONFIRMED]
## CONFIDENCE SCORE: [75-98]%
## SUMMARY: (2 sentences explaining what is confirmed vs unconfirmed)
## VERIFIED FACTS:
- (Fact 1 with key entities/dates)
- (Fact 2 with key entities/dates)
## POTENTIAL FLAGS OR MISCONCEPTIONS:
- (Any rumor or common exaggeration to avoid in reels)
