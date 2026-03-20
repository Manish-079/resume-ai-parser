import os
import json
import base64
import streamlit as st  # <--- Make sure 'as' is here
import pandas as pd
import psycopg
from openai import OpenAI
import PyPDF2
import streamlit.components.v1 as components

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="IT Solutions Worldwide",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# TYPING INDICATOR FUNCTION
# =========================================================
def st_typing_effect():
    """Injects JS to show a typing indicator and highlight the box active state."""
    components.html(
        """
        <script>
        const attachTypingListener = () => {
            const inputs = window.parent.document.querySelectorAll('textarea');
            const indicator = window.parent.document.getElementById('typing-indicator');

            inputs.forEach(input => {
                if (input.dataset.typingAttached) return;

                input.addEventListener('input', () => {
                    if (indicator) {
                        indicator.style.display = 'block';
                        clearTimeout(window.typingTimer);
                        window.typingTimer = setTimeout(() => {
                            indicator.style.display =  'none';
                        }, 1000);
                    }
                });
                input.dataset.typingAttached = "true";
            });
        };

        attachTypingListener();
        const observer = new MutationObserver(attachTypingListener);
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        </script>
        """,
        height=0,
    )


# =========================================================
# DEFAULTS
# =========================================================
DEFAULT_JOB_DESCRIPTION = "Give me the best candidates"
DEFAULT_ANALYSIS_PROMPT = "Analyze this CV and extract the most important candidate information."

if "job_description_input" not in st.session_state:
    st.session_state.job_description_input = ""

if "analysis_prompt_input" not in st.session_state:
    st.session_state.analysis_prompt_input = ""

# NEW: Toggle for resetting visibility without deleting DB
if "show_current_results" not in st.session_state:
    st.session_state.show_current_results = True

# =========================================================
# OPENAI (VEILIG VIA STREAMLIT SECRETS)
# Check eerst Render Environment Variables, daarna Streamlit Secrets
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    try:
        OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    except Exception:
        OPENAI_API_KEY = ""

client = OpenAI(api_key=OPENAI_API_KEY.strip()) if OPENAI_API_KEY.strip() else None

# =========================================================
# DATABASE
# =========================================================

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")


def connect_db():
    return psycopg.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )


def init_db():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS resume (
        id SERIAL PRIMARY KEY,
        file_name TEXT UNIQUE,
        analysis_mode TEXT,
        name TEXT,
        email TEXT,
        phone TEXT,
        skills TEXT,
        degree TEXT,
        university TEXT,
        graduation_year TEXT,
        date_of_birth TEXT,
        location TEXT,
        address TEXT,
        linkedin TEXT,
        github TEXT,
        languages TEXT,
        years_of_experience TEXT,
        job_title TEXT,
        certifications TEXT,
        match_score INTEGER NULL,
        fit_summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    alter_queries = [
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS analysis_mode TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS name TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS email TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS phone TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS skills TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS degree TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS university TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS graduation_year TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS date_of_birth TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS location TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS address TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS linkedin TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS github TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS languages TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS years_of_experience TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS job_title TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS certifications TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS match_score INTEGER NULL;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS fit_summary TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
    ]

    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(create_table_query)
            for query in alter_queries:
                cursor.execute(query)
        conn.commit()


# =========================================================
# HELPERS
# =========================================================
def read_pdf_text(uploaded_file):
    try:
        uploaded_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception:
        return ""


def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


def safe_str(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value).strip()


def safe_int(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        return int(float(value))
    except Exception:
        return default


# =========================================================
# OPENAI FUNCTIONS
# =========================================================
def extract_resume_only(resume_text, analysis_prompt):
    if not client:
        raise ValueError("OpenAI API key is missing. Paste your API key in OPENAI_API_KEY.")

    prompt = f"""
You are an AI recruitment assistant for IT Solutions Worldwide.

Task:
1. Extract resume information from the candidate CV.
2. Analyze the candidate professionally.
3. Return ONLY valid JSON.

Return JSON in this exact structure:
{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": "",
  "degree": "",
  "university": "",
  "graduation_year": "",
  "date_of_birth": "",
  "location": "",
  "address": "",
  "linkedin": "",
  "github": "",
  "languages": "",
  "years_of_experience": "",
  "job_title": "",
  "certifications": "",
  "fit_summary": ""
}}

Rules:
- fit_summary must be short, professional, and explain the candidate profile in 3 to 5 sentences
- do NOT return a match score
- if information is missing, return an empty string
- extract only what is present in the resume
- do not invent facts
- skills, languages, and certifications should be returned as comma-separated strings

Analysis focus:
{analysis_prompt}

Resume:
{resume_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    data = json.loads(response.choices[0].message.content)

    normalized = {
        "analysis_mode": "Analyze CV",
        "name": safe_str(data.get("name")),
        "email": safe_str(data.get("email")),
        "phone": safe_str(data.get("phone")),
        "skills": safe_str(data.get("skills")),
        "degree": safe_str(data.get("degree")),
        "university": safe_str(data.get("university")),
        "graduation_year": safe_str(data.get("graduation_year")),
        "date_of_birth": safe_str(data.get("date_of_birth")),
        "location": safe_str(data.get("location")),
        "address": safe_str(data.get("address")),
        "linkedin": safe_str(data.get("linkedin")),
        "github": safe_str(data.get("github")),
        "languages": safe_str(data.get("languages")),
        "years_of_experience": safe_str(data.get("years_of_experience")),
        "job_title": safe_str(data.get("job_title")),
        "certifications": safe_str(data.get("certifications")),
        "match_score": None,
        "fit_summary": safe_str(data.get("fit_summary")),
    }

    return normalized


def extract_and_score_resume(resume_text, job_desc):
    if not client:
        raise ValueError("OpenAI API key is missing. Paste your API key in OPENAI_API_KEY.")

    prompt = f"""
You are an AI recruitment assistant for IT Solutions Worldwide.

Task:
1. Extract resume information from the candidate CV.
2. Compare the resume against the job description.
3. Return ONLY valid JSON.

Return JSON in this exact structure:
{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": "",
  "degree": "",
  "university": "",
  "graduation_year": "",
  "date_of_birth": "",
  "location": "",
  "address": "",
  "linkedin": "",
  "github": "",
  "languages": "",
  "years_of_experience": "",
  "job_title": "",
  "certifications": "",
  "match_score": 0,
  "fit_summary": ""
}}

Rules:
- match_score must be an integer from 0 to 100
- fit_summary must be short, professional, and clearly explain the score in 2 to 4 sentences
- if information is missing, return an empty string
- extract only what is present in the resume
- do not invent facts
- skills, languages, and certifications should be returned as comma-separated strings

Job Description:
{job_desc}

Resume:
{resume_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    data = json.loads(response.choices[0].message.content)

    normalized = {
        "analysis_mode": "Compare / Rate CVs",
        "name": safe_str(data.get("name")),
        "email": safe_str(data.get("email")),
        "phone": safe_str(data.get("phone")),
        "skills": safe_str(data.get("skills")),
        "degree": safe_str(data.get("degree")),
        "university": safe_str(data.get("university")),
        "graduation_year": safe_str(data.get("graduation_year")),
        "date_of_birth": safe_str(data.get("date_of_birth")),
        "location": safe_str(data.get("location")),
        "address": safe_str(data.get("address")),
        "linkedin": safe_str(data.get("linkedin")),
        "github": safe_str(data.get("github")),
        "languages": safe_str(data.get("languages")),
        "years_of_experience": safe_str(data.get("years_of_experience")),
        "job_title": safe_str(data.get("job_title")),
        "certifications": safe_str(data.get("certifications")),
        "match_score": max(0, min(100, safe_int(data.get("match_score"), 0))),
        "fit_summary": safe_str(data.get("fit_summary")),
    }

    return normalized


# =========================================================
# DATABASE ACTIONS
# =========================================================
def upsert_resume(file_name, result):
    insert_query = """
    INSERT INTO resume (
        file_name, analysis_mode, name, email, phone, skills, degree, university,
        graduation_year, date_of_birth, location, address, linkedin,
        github, languages, years_of_experience, job_title,
        certifications, match_score, fit_summary
    )
    VALUES (
        %(file_name)s, %(analysis_mode)s, %(name)s, %(email)s, %(phone)s, %(skills)s, %(degree)s, %(university)s,
        %(graduation_year)s, %(date_of_birth)s, %(location)s, %(address)s, %(linkedin)s,
        %(github)s, %(languages)s, %(years_of_experience)s, %(job_title)s,
        %(certifications)s, %(match_score)s, %(fit_summary)s
    )
    ON CONFLICT (file_name)
    DO UPDATE SET
        analysis_mode = EXCLUDED.analysis_mode,
        name = EXCLUDED.name,
        email = EXCLUDED.email,
        phone = EXCLUDED.phone,
        skills = EXCLUDED.skills,
        degree = EXCLUDED.degree,
        university = EXCLUDED.university,
        graduation_year = EXCLUDED.graduation_year,
        date_of_birth = EXCLUDED.date_of_birth,
        location = EXCLUDED.location,
        address = EXCLUDED.address,
        linkedin = EXCLUDED.linkedin,
        github = EXCLUDED.github,
        languages = EXCLUDED.languages,
        years_of_experience = EXCLUDED.years_of_experience,
        job_title = EXCLUDED.job_title,
        certifications = EXCLUDED.certifications,
        match_score = EXCLUDED.match_score,
        fit_summary = EXCLUDED.fit_summary,
        created_at = CURRENT_TIMESTAMP
    """
    payload = {"file_name": file_name, **result}
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(insert_query, payload)
        conn.commit()


def clear_database():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE resume RESTART IDENTITY;")
        conn.commit()


def load_resumes():
    select_query = """
    SELECT
        id, file_name, analysis_mode, name, email, phone, skills, degree, university,
        graduation_year, date_of_birth, location, address, linkedin,
        github, languages, years_of_experience, job_title,
        certifications, match_score, fit_summary, created_at
    FROM resume
    ORDER BY created_at DESC
    """
    with connect_db() as conn:
        df = pd.read_sql(select_query, conn)
    return df


# =========================================================
# INITIALIZE DATABASE
# =========================================================
try:
    init_db()
except Exception as e:
    st.error(f"Database initialization error: {e}")

# =========================================================
# CSS - LOGO COLORS + ANIMATION
# =========================================================
st.markdown("""
<style>
:root {
    --primary: #0F6B74;
    --primary-dark: #0B545B;
    --primary-soft: #E6F4F4;
    --bg: #F4F7F7;
    --card: #FFFFFF;
    --border: #D6E6E7;
    --text: #0B545B;
    --muted: #6A8E91;
    --soft-gray: #EEF3F3;
}

/* Fix for visibility of labels in Database Page/Expander */
label[data-testid="stWidgetLabel"] p {
    color: #444444 !important; /* Dark Grey */
    font-weight: 700 !important;
}

/* Hide default Streamlit multipage navigation */
[data-testid="stSidebarNav"] {
    display: none !important;
}

#typing-indicator {
    display: none;
    color: var(--primary);
    font-size: 0.85rem;
    font-weight: bold;
    margin-bottom: 5px;
    animation: blink 1s infinite;
}

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

textarea {
    caret-color: var(--primary) !important;
    transition: all 0.3s ease-in-out !important;
}

textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 10px rgba(15, 107, 116, 0.2) !important;
    background-color: #FAFCFC !important;
}

html, body, [class*="css"] {
    font-family: "Segoe UI", sans-serif;
}

.stApp {
    background: linear-gradient(180deg, #F7FAFA 0%, #EEF4F4 100%);
    color: var(--text);
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100%;
}

[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.1rem;
    padding-left: 1.1rem;
    padding-right: 1.1rem;
}

.sidebar-section-title {
    color: var(--primary);
    font-size: 1rem;
    font-weight: 800;
    text-transform: uppercase;
    margin-top: 0.8rem;
    margin-bottom: 1rem;
    letter-spacing: 0.6px;
}

.main-title {
    font-size: 3rem;
    font-weight: 800;
    color: var(--primary);
    margin-bottom: 0.2rem;
    line-height: 1.05;
}

.sub-title {
    font-size: 1.15rem;
    color: var(--muted);
    margin-bottom: 1rem;
    font-weight: 500;
}

.section-line {
    height: 4px;
    width: 120px;
    background: var(--primary);
    border-radius: 999px;
    margin-bottom: 1.8rem;
}

.metric-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px;
    box-shadow: 0 8px 20px rgba(15, 107, 116, 0.08);
    min-height: 124px;
}

.metric-label {
    color: var(--muted);
    font-size: 0.9rem;
    margin-bottom: 10px;
    font-weight: 700;
    text-transform: uppercase;
}

.metric-value {
    color: var(--primary);
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1;
}

.small-muted {
    color: var(--muted);
    font-size: 0.95rem;
    font-weight: 500;
    margin-bottom: 0.6rem;
}

/* Updated top navigation button styling */
.nav-button-active {
    background: #0F6B74;
    color: white;
    text-align: center;
    padding: 12px 14px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 0.95rem;
    border: 1px solid #0F6B74;
    box-shadow: 0 8px 18px rgba(15, 107, 116, 0.18);
}

.stButton > button {
    width: 100%;
    border: 1px solid var(--primary) !important;
    border-radius: 12px;
    background: #FFFFFF !important;
    color: var(--primary) !important;
    font-weight: 700;
    font-size: 0.95rem;
    padding: 0.82rem 1rem;
    box-shadow: 0 8px 18px rgba(15, 107, 116, 0.10);
}

.stButton > button:hover {
    background: var(--primary-soft) !important;
    color: var(--primary-dark) !important;
    border: 1px solid var(--primary) !important;
}

div[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    min-height: 50px !important;
    box-shadow: none !important;
}

div[data-baseweb="select"] span {
    color: #0B545B !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}

div[data-baseweb="select"] input {
    color: #0B545B !important;
    -webkit-text-fill-color: #0B545B !important;
    opacity: 1 !important;
}

div[data-baseweb="select"] svg {
    fill: #0F6B74 !important;
}

div[data-baseweb="select"] * {
    color: #0B545B !important;
    opacity: 1 !important;
}

textarea,
.stTextArea textarea {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    color: var(--text) !important;
    font-size: 1rem !important;
    padding: 14px !important;
}

.stTextArea textarea::placeholder {
    color: var(--muted) !important;
    opacity: 1 !important;
}

/* =========================
FILE UPLOADER
========================= */
[data-testid="stFileUploader"] {
    border: 3px dashed #3E6F79 !important;
    border-radius: 28px !important;
    background: rgba(255, 255, 255, 0.58) !important;
    padding: 22px !important;
}

[data-testid="stFileUploader"] section {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

[data-testid="stFileUploader"] section > div {
    background: transparent !important;
    border: none !important;
}

[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
    background: transparent !important;
    border: none !important;
    min-height: 170px !important;
    padding: 14px 18px !important;
}

[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] > div {
    background: transparent !important;
    border: none !important;
}

[data-testid="stFileUploader"] label,
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] p {
    color: #D9DDE2 !important;
    opacity: 1 !important;
}

[data-testid="stFileUploader"] small {
    color: #E6E9ED !important;
    font-size: 1rem !important;
}

[data-testid="stFileUploader"] svg {
    fill: #A8AFC0 !important;
    color: #A8AFC0 !important;
    width: 54px !important;
    height: 54px !important;
}

[data-testid="stFileUploader"] button {
    background: #3E6F79 !important;
    color: white !important;
    border: none !important;
    border-radius: 18px !important;
    font-weight: 800 !important;
    font-size: 1rem !important;
    padding: 0.9rem 1.8rem !important;
    min-height: 56px !important;
    box-shadow: none !important;
}

[data-testid="stFileUploader"] button:hover {
    background: #325C64 !important;
    color: white !important;
}

.summary-box {
    background: #F7FBFB;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px;
    color: var(--text);
    line-height: 1.6;
}

.detail-label {
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 800;
    margin-bottom: 2px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.detail-value {
    color: var(--text);
    font-size: 1rem;
    margin-bottom: 12px;
    word-break: break-word;
    line-height: 1.45;
}

[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    background: #FFFFFF !important;
    overflow: hidden;
}

[data-testid="stExpander"] summary {
    font-weight: 700;
    color: var(--primary) !important;
}

.match-badge {
    background: var(--primary-soft);
    border: 2px solid var(--primary);
    color: var(--primary);
    font-weight: 800;
    font-size: 1.05rem;
    padding: 12px 20px;
    border-radius: 999px;
    text-align: center;
    display: inline-block;
    white-space: nowrap;
}

.mode-box {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 12px 16px;
    margin-bottom: 14px;
    color: var(--text);
}

hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.4rem 0;
}

h2, h3 {
    color: var(--primary);
}

[data-testid="stAlert"] {
    border-radius: 16px !important;
    border: 1px solid var(--border) !important;
}

/* Styling for the Use Default | Clear links */
div[data-testid="stHorizontalBlock"] div.stButton > button {
    background: transparent !important;
    border: none !important;
    color: #4c6374 !important;
    text-decoration: none !important;
    box-shadow: none !important;
    padding: 0px !important;
    width: auto !important;
    min-height: 0px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
}

div[data-testid="stHorizontalBlock"] div.stButton > button:hover {
    color: #0F6B74 !important;
    text-decoration: underline !important;
    background: transparent !important;
}

.divider-pipe {
    color: #D6E6E7;
    margin: 0 2px;
    font-weight: 300;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    image_path = os.path.join(os.path.dirname(__file__), "images", "image_18.png")
    if not os.path.exists(image_path):
        image_path = os.path.join(os.path.dirname(__file__), "image_18.png")

    if os.path.exists(image_path):
        bin_str = get_base64_of_bin_file(image_path)
        st.markdown(
            f"""
            <div style="text-align:center; margin-bottom:30px; padding-top:6px;">
                <img src="data:image/png;base64,{bin_str}" width="320" style="max-width:100%; height:auto;">
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown('<div class="sidebar-section-title">Recruitment Control</div>', unsafe_allow_html=True)

    selected_mode = st.selectbox(
        "Choose mode",
        ["Analyze CV", "Compare / Rate CVs"]
    )

    analyze_clicked = st.button("Run Analysis")
    # UPDATED BUTTON: "Clear View" resets state without deleting database
    if st.button("Clear View"):
        st.session_state.job_description_input = ""
        st.session_state.analysis_prompt_input = ""
        st.session_state.show_current_results = False
        st.rerun()

# =========================================================
# TOP RIGHT NAVIGATION
# =========================================================
nav_spacer, nav_btn1, nav_btn2 = st.columns([6, 2, 2])

with nav_btn1:
    st.button("CV Parser", use_container_width=True, disabled=True)

with nav_btn2:
    if st.button("Candidate Database", use_container_width=True):
        st.switch_page("pages/2_Candidate_Database.py")

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-title">IT Solutions Worldwide</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Professional Candidate Intelligence Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)

if not OPENAI_API_KEY.strip():
    st.warning("Paste your OpenAI API key in the OPENAI_API_KEY variable before analyzing resumes.")

st.markdown(
    f'<div class="mode-box"><strong>Current Mode:</strong> {selected_mode}</div>',
    unsafe_allow_html=True
)

# =========================================================
# INPUT AREA
# =========================================================
st_typing_effect()
left_col, right_col = st.columns(2, gap="large")

with left_col:
    st.markdown('<div id="typing-indicator">Typing...</div>', unsafe_allow_html=True)

    title = 'Job Description' if selected_mode == 'Compare / Rate CVs' else 'CV Analysis Prompt'
    st.markdown(f"## {title}")

    btn_row_col1, _ = st.columns([1, 1])
    with btn_row_col1:
        l1, l2, l3 = st.columns([0.45, 0.05, 0.3])
        with l1:
            if st.button("🗳 Use Default", key="link_use_default"):
                if selected_mode == "Compare / Rate CVs":
                    st.session_state.job_description_input = DEFAULT_JOB_DESCRIPTION
                else:
                    st.session_state.analysis_prompt_input = DEFAULT_ANALYSIS_PROMPT
        with l2:
            st.markdown('<div class="divider-pipe">|</div>', unsafe_allow_html=True)
        with l3:
            if st.button("✖ Clear", key="link_clear_text"):
                if selected_mode == "Compare / Rate CVs":
                    st.session_state.job_description_input = ""
                else:
                    st.session_state.analysis_prompt_input = ""

    if selected_mode == "Analyze CV":
        st.markdown(
            '<div class="small-muted">Define what the AI should analyze in the CV (skills, experience, education, etc.). No rating will be given.</div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="small-muted">Define the requirements for the job role to compare candidates against.</div>',
            unsafe_allow_html=True)

    if selected_mode == "Compare / Rate CVs":
        st.text_area("JD", height=320, label_visibility="collapsed", key="job_description_input",
                     placeholder=DEFAULT_JOB_DESCRIPTION)
    else:
        st.text_area("Prompt", height=320, label_visibility="collapsed", key="analysis_prompt_input",
                     placeholder=DEFAULT_ANALYSIS_PROMPT)

with right_col:
    if selected_mode == "Analyze CV":
        st.markdown("## Upload One CV")
        st.markdown(
            '<div class="small-muted">Upload 1 PDF resume for profile analysis only. No rating will be given.</div>',
            unsafe_allow_html=True
        )
        uploaded_file_single = st.file_uploader(
            "Upload resume",
            type=["pdf"],
            accept_multiple_files=False,
            label_visibility="collapsed"
        )
        uploaded_files = [uploaded_file_single] if uploaded_file_single else []
    else:
        st.markdown("## Candidate Resumes")
        st.markdown(
            '<div class="small-muted">Upload multiple PDF resumes to compare and rate candidates against the job description.</div>',
            unsafe_allow_html=True
        )
        uploaded_files = st.file_uploader(
            "Upload resumes",
            type=["pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )

# =========================================================
# ACTIONS
# =========================================================
if analyze_clicked:
    st.session_state.show_current_results = True
    if not OPENAI_API_KEY.strip():
        st.error("OpenAI API key is missing.")
    elif not uploaded_files:
        if selected_mode == "Analyze CV":
            st.warning("Please upload 1 PDF resume.")
        else:
            st.warning("Please upload at least one PDF resume.")
    elif selected_mode == "Analyze CV" and len(uploaded_files) != 1:
        st.warning("Analyze CV mode only allows 1 PDF upload.")
    else:
        try:
            processed_count = 0
            skipped_count = 0

            with st.spinner("Analyzing resumes..."):
                for uploaded_file in uploaded_files:
                    if uploaded_file is None:
                        skipped_count += 1
                        continue

                    resume_text = read_pdf_text(uploaded_file)

                    if not resume_text:
                        skipped_count += 1
                        continue

                    if selected_mode == "Analyze CV":
                        analysis_prompt = (
                            st.session_state.analysis_prompt_input.strip()
                            if st.session_state.analysis_prompt_input.strip()
                            else DEFAULT_ANALYSIS_PROMPT
                        )
                        result = extract_resume_only(resume_text, analysis_prompt)
                    else:
                        job_desc = (
                            st.session_state.job_description_input.strip()
                            if st.session_state.job_description_input.strip()
                            else DEFAULT_JOB_DESCRIPTION
                        )
                        result = extract_and_score_resume(resume_text, job_desc)

                    if not result["name"]:
                        result["name"] = uploaded_file.name.rsplit(".", 1)[0]

                    upsert_resume(uploaded_file.name, result)
                    processed_count += 1

            if processed_count > 0:
                st.success(f"Analysis completed successfully. Processed: {processed_count}, Skipped: {skipped_count}")
                st.rerun()
            else:
                st.warning("No readable PDF text found in the uploaded files.")

        except Exception as e:
            st.error(f"Error during analysis: {e}")

# =========================================================
# LOAD DATA (CRITICAL FIX FOR NameError)
# =========================================================
try:
    df = load_resumes()
except Exception as e:
    df = pd.DataFrame()
    st.error(f"Database error: {e}")

# =========================================================
# METRICS AND RESULTS DISPLAY (HIDDEN IF VIEW CLEARED)
# =========================================================
if st.session_state.show_current_results and not df.empty:
    score_series = pd.to_numeric(df["match_score"], errors="coerce")
    rated_df = df[score_series.notna()].copy()
    rated_df["match_score"] = pd.to_numeric(rated_df["match_score"], errors="coerce")

    total_resumes = len(df)
    top_match = int(rated_df["match_score"].max()) if not rated_df.empty else 0
    avg_score = int(rated_df["match_score"].mean()) if not rated_df.empty else 0
    shortlisted = len(rated_df[rated_df["match_score"] >= 75]) if not rated_df.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Resumes</div><div class="metric-value">{total_resumes}</div></div>',
            unsafe_allow_html=True)
    with m2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Top Match</div><div class="metric-value">{top_match}%</div></div>',
            unsafe_allow_html=True)
    with m3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Average Score</div><div class="metric-value">{avg_score}%</div></div>',
            unsafe_allow_html=True)
    with m4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Shortlisted</div><div class="metric-value">{shortlisted}</div></div>',
            unsafe_allow_html=True)