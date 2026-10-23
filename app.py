"""
Fasal Doctor - AI crop disease checker for Pakistani farmers.
DITE Hackathon 2026-27 | Theme: Agriculture

Flow: farmer takes/uploads a leaf photo -> image is shrunk (slow internet friendly)
-> Gemini vision model diagnoses it and returns structured JSON
-> result shown in Urdu / Sindhi / English, with optional audio (Urdu/English).
"""

import io
import os
import sqlite3
from datetime import datetime

import streamlit as st
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Fasal Doctor", page_icon="🌿", layout="centered")

# Tried in order. If one model is unavailable or out of free quota, the next is used.
DEFAULT_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"]
MAX_IMAGE_SIDE = 768          # px, keeps uploads to the API small
DB_PATH = "history.db"


def get_secret(name: str, default: str = "") -> str:
    """Read from environment (.env locally) or Streamlit Cloud secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


API_KEY = get_secret("GEMINI_API_KEY")
MODEL_OVERRIDE = get_secret("GEMINI_MODEL")
MODELS = [MODEL_OVERRIDE] + DEFAULT_MODELS if MODEL_OVERRIDE else DEFAULT_MODELS

# ---------------------------------------------------------------------------
# UI text in three languages
# ---------------------------------------------------------------------------
LANGS = {
    "اردو": "Urdu",
    "سنڌي": "Sindhi",
    "English": "English",
}

T = {
    "Urdu": {
        "title": "فصل ڈاکٹر",
        "subtitle": "بیمار پتے کی تصویر لیں، بیماری اور علاج جانیں",
        "crop": "فصل منتخب کریں",
        "camera": "📷 کیمرے سے تصویر لیں",
        "upload": "🖼️ یا گیلری سے تصویر اپلوڈ کریں",
        "notes": "مزید معلومات (اختیاری) — مثلاً کتنے دن سے ہے؟",
        "check": "🔍 بیماری چیک کریں",
        "wait": "تصویر کا معائنہ ہو رہا ہے…",
        "need_photo": "پہلے پتے کی تصویر لیں یا اپلوڈ کریں۔",
        "healthy": "✅ پودا صحت مند لگتا ہے",
        "disease": "⚠️ بیماری کی نشاندہی",
        "not_plant": "یہ تصویر پودے کے پتے کی نہیں لگتی۔ براہ کرم پتے کی صاف تصویر لیں۔",
        "symptoms": "علامات",
        "cause": "وجہ",
        "organic": "🌱 گھریلو / قدرتی علاج",
        "chemical": "🧪 دوائی (اسپرے)",
        "prevention": "🛡️ آئندہ بچاؤ",
        "confidence": "یقین",
        "urgency": "فوری ضرورت",
        "expert": "👨‍🌾 جلد از جلد قریبی محکمہ زراعت (ایکسٹینشن) افسر سے رابطہ کریں۔",
        "listen": "🔊 سنیں",
        "disclaimer": "یہ AI کی رائے ہے، حتمی تشخیص نہیں۔ اسپرے سے پہلے ہمیشہ مقامی زرعی ماہر سے مشورہ کریں اور دوائی کے لیبل پر دی گئی ہدایات پر عمل کریں۔",
        "history": "پچھلے معائنے",
        "no_key": "API key سیٹ نہیں ہے۔ README دیکھیں۔",
        "error": "ابھی سروس دستیاب نہیں۔ تھوڑی دیر بعد دوبارہ کوشش کریں۔",
        "photo_tip": "بہتر نتیجے کے لیے: دن کی روشنی میں، ایک بیمار پتا قریب سے۔",
    },
    "Sindhi": {
        "title": "فصل ڊاڪٽر",
        "subtitle": "بيمار پن جي تصوير وٺو، بيماري ۽ علاج ڄاڻو",
        "crop": "فصل چونڊيو",
        "camera": "📷 ڪئميرا سان تصوير وٺو",
        "upload": "🖼️ يا گيلري مان تصوير اپلوڊ ڪريو",
        "notes": "وڌيڪ معلومات (اختياري)",
        "check": "🔍 بيماري چيڪ ڪريو",
        "wait": "تصوير جي جانچ ٿي رهي آهي…",
        "need_photo": "پهريان پن جي تصوير وٺو يا اپلوڊ ڪريو.",
        "healthy": "✅ ٻوٽو صحتمند لڳي ٿو",
        "disease": "⚠️ بيماري جي نشاندهي",
        "not_plant": "هي تصوير ٻوٽي جي پن جي ناهي لڳندي. مهرباني ڪري پن جي صاف تصوير وٺو.",
        "symptoms": "علامتون",
        "cause": "سبب",
        "organic": "🌱 قدرتي علاج",
        "chemical": "🧪 دوا (اسپري)",
        "prevention": "🛡️ اڳتي لاءِ بچاءُ",
        "confidence": "يقين",
        "urgency": "تڪڙ",
        "expert": "👨‍🌾 جلد ويجهي زراعت کاتي (ايڪسٽينشن) جي آفيسر سان رابطو ڪريو.",
        "listen": "🔊 ٻڌو (اردو آواز)",
        "disclaimer": "هي AI جي راءِ آهي، آخري تشخيص ناهي. اسپري کان اڳ مقامي زرعي ماهر سان صلاح ڪريو.",
        "history": "پويون جانچون",
        "no_key": "API key سيٽ ناهي. README ڏسو.",
        "error": "هن وقت سروس موجود ناهي. ٿوري دير بعد ٻيهر ڪوشش ڪريو.",
        "photo_tip": "بهتر نتيجي لاءِ: ڏينهن جي روشني ۾، هڪ بيمار پن ويجهو کان.",
    },
    "English": {
        "title": "Fasal Doctor",
        "subtitle": "Take a photo of a sick leaf — get the disease and the treatment",
        "crop": "Select crop",
        "camera": "📷 Take a photo",
        "upload": "🖼️ Or upload from gallery",
        "notes": "Extra details (optional) — e.g. how many days?",
        "check": "🔍 Check disease",
        "wait": "Examining the photo…",
        "need_photo": "Please take or upload a leaf photo first.",
        "healthy": "✅ The plant looks healthy",
        "disease": "⚠️ Disease detected",
        "not_plant": "This doesn't look like a plant leaf. Please take a clear photo of a leaf.",
        "symptoms": "Symptoms",
        "cause": "Cause",
        "organic": "🌱 Natural / low-cost treatment",
        "chemical": "🧪 Chemical treatment (spray)",
        "prevention": "🛡️ Prevention",
        "confidence": "Confidence",
        "urgency": "Urgency",
        "expert": "👨‍🌾 Contact your nearest Agriculture Extension officer soon.",
        "listen": "🔊 Listen",
        "disclaimer": "This is an AI suggestion, not a final diagnosis. Always consult a local agriculture expert before spraying and follow the pesticide label.",
        "history": "Recent checks",
        "no_key": "API key is not set. See the README.",
        "error": "Service is busy right now. Please try again in a minute.",
        "photo_tip": "Tip: daylight, one sick leaf, close up.",
    },
}

CROPS = {
    "Urdu":    ["معلوم نہیں", "کپاس", "گندم", "چاول", "گنا", "آم", "ٹماٹر", "مرچ", "آلو", "پیاز", "کیلا", "دیگر"],
    "Sindhi":  ["خبر ناهي", "ڪپهه", "ڪڻڪ", "چانور", "ڪمند", "انب", "ٽماٽا", "مرچ", "پٽاٽا", "بصر", "ڪيلو", "ٻيو"],
    "English": ["Not sure", "Cotton", "Wheat", "Rice", "Sugarcane", "Mango", "Tomato", "Chilli", "Potato", "Onion", "Banana", "Other"],
}

# ---------------------------------------------------------------------------
# AI: structured output schema + Gemini call
# ---------------------------------------------------------------------------
class Diagnosis(BaseModel):
    is_plant_leaf: bool = Field(description="True only if the image clearly shows a plant leaf/plant part")
    crop_name: str = Field(description="Detected crop name, in the output language")
    is_healthy: bool
    disease_name: str = Field(description="Common local name + English/scientific name in brackets. Empty if healthy")
    confidence: int = Field(description="0-100, how sure the model is")
    urgency: str = Field(description="One of: low, medium, high")
    symptoms: list[str] = Field(description="2-4 short visible symptoms seen in the photo")
    cause: str = Field(description="One short sentence: fungus / bacteria / virus / insect / nutrient deficiency etc.")
    organic_treatment: list[str] = Field(description="2-3 cheap, locally available steps")
    chemical_treatment: list[str] = Field(description="1-3 generic active ingredients commonly used in Pakistan, no brand names, with 'follow label dose'")
    prevention: list[str] = Field(description="2-3 short prevention tips")
    see_expert: bool = Field(description="True if confidence < 60, urgency high, or unclear")
    spoken_summary: str = Field(description="2-3 very simple sentences a farmer can listen to")


def build_prompt(language: str, crop: str, notes: str) -> str:
    return f"""You are an experienced plant pathologist helping small farmers in Sindh and Punjab, Pakistan.
Look at the photo and diagnose the plant's health.

Farmer says the crop is: {crop}
Farmer's notes: {notes or "none"}

Rules:
- Write EVERY text field in {language}. Use very simple words a farmer with little schooling understands.
- If the image is not a plant leaf / plant part, set is_plant_leaf=false and leave other lists empty.
- Only describe symptoms you can actually see. Do not invent.
- Be honest about uncertainty: lower the confidence for blurry photos or look-alike diseases.
- Chemical treatment: generic active ingredient names only (e.g. Mancozeb, Imidacloprid), never brand names, never exact mixing doses — say "follow the label".
- Prefer cheap, locally available organic remedies (neem, removing infected leaves, water management).
"""


def prepare_image(raw: bytes) -> bytes:
    """Fix rotation, shrink and recompress so slow connections & API stay fast."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@st.cache_resource
def get_client():
    return genai.Client(api_key=API_KEY)


def diagnose(image_bytes: bytes, language: str, crop: str, notes: str) -> tuple[Diagnosis, str]:
    client = get_client()
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Diagnosis,
        temperature=0.2,
    )
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        build_prompt(language, crop, notes),
    ]
    last_error = None
    for model in MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            result = resp.parsed if resp.parsed else Diagnosis.model_validate_json(resp.text)
            return result, model
        except Exception as e:  # model missing, quota hit, network error -> try next
            last_error = e
            continue
    raise RuntimeError(f"All models failed: {last_error}")


# ---------------------------------------------------------------------------
# Audio (helps farmers who can't read well). gTTS supports Urdu & English.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def speak(text: str, lang_code: str) -> bytes | None:
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang=lang_code).write_to_fp(buf)
        return buf.getvalue()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Small local history (SQLite) — no personal data stored
# ---------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS checks (ts TEXT, crop TEXT, disease TEXT, confidence INT, urgency TEXT)"
    )
    return conn


def save_check(d: Diagnosis):
    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO checks VALUES (?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), d.crop_name,
                 d.disease_name or "Healthy", d.confidence, d.urgency),
            )
    except Exception:
        pass


def recent_checks(limit: int = 5):
    try:
        with db() as conn:
            return conn.execute(
                "SELECT ts, crop, disease, confidence FROM checks ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
lang_label = st.radio("Language / زبان", list(LANGS.keys()), horizontal=True, label_visibility="collapsed")
language = LANGS[lang_label]
t = T[language]
rtl = language in ("Urdu", "Sindhi")

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@400;700&display=swap');
      .block-container {{ max-width: 720px; padding-top: 1.5rem; }}
      .main, .stMarkdown, .stRadio, label, p, li, h1, h2, h3 {{
        direction: {"rtl" if rtl else "ltr"};
        text-align: {"right" if rtl else "left"};
        {"font-family: 'Noto Nastaliq Urdu', serif; line-height: 2.1;" if rtl else ""}
      }}
      .card {{ border-radius: 14px; padding: 1rem 1.2rem; margin: .6rem 0; border: 1px solid rgba(128,128,128,.25); }}
      .ok   {{ background: rgba(34,139,34,.10); border-color: rgba(34,139,34,.4); }}
      .bad  {{ background: rgba(220,90,30,.10); border-color: rgba(220,90,30,.4); }}
      .stButton button {{ width: 100%; font-size: 1.15rem; padding: .7rem; border-radius: 12px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(f"🌿 {t['title']}")
st.write(t["subtitle"])

if not API_KEY:
    st.error(t["no_key"])
    st.stop()

crop = st.selectbox(t["crop"], CROPS[language])
st.caption(t["photo_tip"])

tab_cam, tab_up = st.tabs([t["camera"], t["upload"]])
with tab_cam:
    cam = st.camera_input(t["camera"], label_visibility="collapsed")
with tab_up:
    up = st.file_uploader(t["upload"], type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed")

photo = cam or up
notes = st.text_input(t["notes"])

if photo:
    st.image(photo, width="stretch")

if st.button(t["check"], type="primary"):
    if not photo:
        st.warning(t["need_photo"])
        st.stop()

    with st.spinner(t["wait"]):
        try:
            img_bytes = prepare_image(photo.getvalue())
            result, used_model = diagnose(img_bytes, language, crop, notes)
        except Exception as e:
            st.error(t["error"])
            with st.expander("details"):
                st.code(str(e))
            st.stop()

    if not result.is_plant_leaf:
        st.warning(t["not_plant"])
        st.stop()

    save_check(result)

    if result.is_healthy:
        st.markdown(f"<div class='card ok'><h3>{t['healthy']}</h3><p>{result.crop_name}</p></div>",
                    unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='card bad'><h3>{t['disease']}</h3>"
            f"<h2>{result.disease_name}</h2><p>{result.crop_name}</p></div>",
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)
    c1.metric(t["confidence"], f"{result.confidence}%")
    urgency_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(result.urgency.lower(), "⚪")
    c2.metric(t["urgency"], f"{urgency_icon} {result.urgency}")

    # Audio summary
    audio = speak(result.spoken_summary, "en" if language == "English" else "ur")
    if audio:
        st.write(t["listen"])
        st.audio(audio, format="audio/mp3")

    def bullet_block(title, items):
        if items:
            st.subheader(title)
            st.markdown("\n".join(f"- {i}" for i in items))

    bullet_block(t["symptoms"], result.symptoms)
    if result.cause and not result.is_healthy:
        st.subheader(t["cause"])
        st.write(result.cause)
    if not result.is_healthy:
        bullet_block(t["organic"], result.organic_treatment)
        bullet_block(t["chemical"], result.chemical_treatment)
    bullet_block(t["prevention"], result.prevention)

    if result.see_expert or result.confidence < 60:
        st.info(t["expert"])

    st.caption(t["disclaimer"])
    st.caption(f"AI model: {used_model}")

rows = recent_checks()
if rows:
    with st.expander(t["history"]):
        for ts, c, d, conf in rows:
            st.write(f"{ts} · {c} · {d} · {conf}%")
