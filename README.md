# 🌿 Fasal Doctor — AI Crop Disease Checker

**DITE Hackathon 2026-27 · Theme: Agriculture**

**Team:** _TEAM NAME_ — _Member 1_, _Member 2_, _Member 3_

## Problem
Small farmers in Sindh and Punjab often lose a large part of their crop because leaf diseases (cotton leaf curl, wheat rust, rice blast, tomato blight…) are spotted late, and an agriculture expert is not always nearby. Most apps that could help are in English only. Fasal Doctor lets a farmer photograph a sick leaf and get the likely disease, a simple explanation, and low-cost treatment steps in **Urdu, Sindhi or English**, with **audio** for farmers who can't read well.

## How AI is used
| | |
|---|---|
| **Model / API** | Google **Gemini 3.5 Flash** vision model (free tier) via the `google-genai` SDK. Auto-fallback to `gemini-3.1-flash-lite` / `gemini-flash-latest` if quota runs out. |
| **Input** | Leaf photo (resized to 768px to save data), crop name, farmer's notes, chosen language |
| **Output** | Structured JSON (enforced with a Pydantic schema): is it a leaf, crop, healthy or not, disease name, confidence %, urgency, visible symptoms, cause, organic + chemical treatment (generic ingredients only), prevention, whether to see an expert, and a short spoken summary |
| **Extra AI** | Google Text-to-Speech (gTTS) reads the summary aloud in Urdu/English |

Safety: low-confidence or high-urgency results tell the farmer to contact an Agriculture Extension officer; no brand names or doses are given; non-leaf photos are rejected.

## Tech stack
Python · Streamlit · Google Gemini API (`google-genai`) · Pydantic · Pillow · gTTS · SQLite (anonymous check history)

## Run locally
```bash
git clone <your-repo-url>
cd fasal-doctor
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then paste your key from https://aistudio.google.com/apikey
streamlit run app.py
```

## Live demo
- **App:** _https://your-app.streamlit.app_
- **Demo video:** _Google Drive link_

## Screenshots
_add 1–2 screenshots here_

## Credits / resources
- Google Gemini API — https://ai.google.dev
- gTTS — https://github.com/pndurette/gTTS
- Streamlit — https://streamlit.io
- Noto Nastaliq Urdu font — Google Fonts

## Limitations & next steps
- Diagnosis comes from a general vision model, so look-alike diseases can be confused; we show confidence and push uncertain cases to experts.
- Next: fine-tune a local model on PlantVillage + Pakistani crop images for offline use, add Punjabi/Saraiki audio, and send outbreak alerts to extension departments by district.
