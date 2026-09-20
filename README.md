# 🎬 Hindi Short Reel Script Studio (Apple Foundation Models)

An autonomous AI agent studio designed for short-form content creators (Instagram Reels, YouTube Shorts, TikTok). It takes a **news story** and a **scenario**, and produces high-retention reel scripts in **fluent Hindi** with strict **4-step verification** and output in **multiples of 10**.

Powered on-device by macOS **Apple Foundation Models (`fm`)** and rendered via an interactive **Streamlit web application**.

---

## 🚀 The 4-Step Verification & Pipeline

```
               [ User Input: News Story + Scenario / Angle ]
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ Step 1: News Verification (Antigravity & Live)   │
             │ - Audits factual claims against live wire feeds  │
             │ - Identifies confirmed facts & flagged rumors    │
             │ - Generates a 0-100% Factual Confidence Score    │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ Step 2: Word Count Verification                  │
             │ - Strictly checks Hindi spoken word count        │
             │ - Optimal range: 60-78 words (for 30s reels)     │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ Step 3: Timeline & Duration Fit Check            │
             │ - Estimates speech delivery time (2.3 words/sec) │
             │ - Pacing check: Hook (0-3s), Core, CTA (24-30s)  │
             │ - Flags if script fits or exceeds timeline       │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ Step 4: Clarity, Scene Breakdown & Audio Cues   │
             │ - Visual B-Roll camera directions per scene      │
             │ - On-screen Hindi text overlays                  │
             │ - SFX / Music cues + Viral Hook + Hindi CTA      │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
           ┌──────────────────────────────────────────────────────┐
           │ Output in Multiples of 10 (10, 20, or 30 Scripts)    │
           │ Rendered in Web UI with Tabs, Cards & Teleprompter   │
           └──────────────────────────────────────────────────────┘
```

---

## 🌟 10 Distinct Reel Angles Generated in Each Batch

1. **वायरल ब्रेकिंग अलर्ट (Breaking News Urgency)**: Fast, breathless breaking alert.
2. **क्या आप जानते हैं? (Shocking Curiosity)**: Scroll-stopping surprising fact.
3. **आम इंसान पर असर (Everyday Impact)**: How it impacts the viewer's pocket & daily life.
4. **सच्चाई बनाम अफ़वाह (Fact vs Myth / Reality Check)**: Debunking viral fake claims.
5. **सिनेमाई सस्पेंस (Cinematic Storytelling)**: Dramatic, suspenseful opening.
6. **30-सेकंड क्विक एक्सप्लेनर (Rapid 3-Point Explainer)**: Crisp 3-bullet takeaway.
7. **भविष्य का विज़न (Futuristic / What's Next?)**: Forward-looking perspective.
8. **विवाद और दो पहलू (Public Debate & Both Sides)**: Balanced look at controversies.
9. **पर्दे के पीछे का सच (Behind The Scenes / Deep Insight)**: The untold angle.
10. **जनता की राय (Audience Engagement Poll)**: Inspires comment-section debates.

---

## 💻 How to Run

### 1. Launch the Streamlit Web Studio
```bash
./run.sh
```
*(Or `source .venv/bin/activate && streamlit run app.py`)*

Open **`http://localhost:8501`** in your browser.

### 2. Run via Terminal (CLI Mode)
```bash
source .venv/bin/activate
python main.py "ISRO announces next lunar mission with international robotics" --scenario "Viral tech enthusiast tone" --batch 10 --duration 30
```

---

## 📂 Project Structure

- **[app.py](file:///Users/abhiraj/Documents/news/agent/app.py)**: Streamlit creator web dashboard with batch gallery, verification pills, teleprompter mode, and markdown export.
- **[workflow.py](file:///Users/abhiraj/Documents/news/agent/workflow.py)**: 4-step verification orchestrator.
- **[agents/news_verifier.py](file:///Users/abhiraj/Documents/news/agent/agents/news_verifier.py)**: Step 1 news verification agent using Antigravity / live search.
- **[agents/reel_writer.py](file:///Users/abhiraj/Documents/news/agent/agents/reel_writer.py)**: Hindi reel script generator across 10 viral angles.
- **[core/metrics.py](file:///Users/abhiraj/Documents/news/agent/core/metrics.py)**: Step 2 word count and Step 3 timeline duration algorithms.
- **[core/fm_engine.py](file:///Users/abhiraj/Documents/news/agent/core/fm_engine.py)**: macOS Apple Foundation Models (`/usr/bin/fm`) integration.
- **[core/models.py](file:///Users/abhiraj/Documents/news/agent/core/models.py)**: Data schemas for scripts, scenes, and verification reports.
