import os
import json
import base64
import streamlit as st
import pandas as pd
import psycopg
from openai import OpenAI
import PyPDF2
import streamlit.components.v1 as components
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="IT Solutions Worldwide",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize a session start time to filter results if not exists
if "view_filter_time" not in st.session_state:
    st.session_state["view_filter_time"] = None


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
                            indicator.style.display = 'none';
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

# =========================================================
# OPENAI
# =========================================================

# Verkrijg de key en zorg dat de variabele altijd bestaat (voorkomt NameError)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# =========================================================
# DATABASE
# =========================================================
def connect_db():
    try:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            database_url = st.secrets.get("DATABASE_URL", "")

        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables or secrets.toml")

        return psycopg.connect(database_url)

    except Exception as e:
        st.error(f"Database connection failed: {e}")
        raise


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
        relevant_years_experience TEXT,
        experience_breakdown TEXT,
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
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS relevant_years_experience TEXT;",
        "ALTER TABLE resume ADD COLUMN IF NOT EXISTS experience_breakdown TEXT;",
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
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def safe_json_text(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def format_experience_breakdown(value):
    if not value:
        return ""
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if isinstance(parsed, list):
            lines = []
            for item in parsed:
                if isinstance(item, dict):
                    role_name = str(item.get("role_name", "")).strip()
                    estimated_years = str(item.get("estimated_years", "")).strip()
                    relevant_flag = item.get("relevant_to_requested_job_title", "")
                    relevant_text = "Yes" if str(relevant_flag).lower() in ["true", "yes", "1"] else "No"
                    line = f"- {role_name or 'Unknown Role'}: {estimated_years or 'N/A'} year(s) | Relevant: {relevant_text}"
                    lines.append(line)
            return "\n".join(lines)
        return str(parsed)
    except Exception:
        return str(value)


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
3. Extract the candidate's total years of experience.
4. Also provide a breakdown of experience by role, field, or job title.
5. Return ONLY valid JSON.

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
  "relevant_years_experience": "",
  "experience_breakdown": [
    {{
      "role_name": "",
      "estimated_years": "",
      "relevant_to_requested_job_title": false
    }}
  ],
  "job_title": "",
  "certifications": "",
  "fit_summary": ""
}}

Rules:
- fit_summary must be short, professional, and explain the candidate profile in 3 to 5 sentences
- do NOT return a match score
- relevant_years_experience must stay empty in Analyze CV mode because no requested job title was provided
- experience_breakdown must include:
  - role_name
  - estimated_years
  - relevant_to_requested_job_title
- if information is missing, return an empty string
- if there is no breakdown, return an empty array []
- extract only what is present in the resume
- do not invent facts
- be conservative with experience estimates
- if dates are unclear, estimate carefully based on the CV
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
        "relevant_years_experience": safe_str(data.get("relevant_years_experience")),
        "experience_breakdown": safe_json_text(data.get("experience_breakdown")),
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
3. Extract the candidate's total years of experience.
4. Then calculate how many years of experience are specifically relevant to the requested job title from the job description.
5. Also provide a breakdown of experience by role, field, or job title.
6. Return ONLY valid JSON.

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
  "relevant_years_experience": "",
  "experience_breakdown": [
    {{
      "role_name": "",
      "estimated_years": "",
      "relevant_to_requested_job_title": false
    }}
  ],
  "job_title": "",
  "certifications": "",
  "match_score": 0,
  "fit_summary": ""
}}

Rules:
- match_score must be an integer from 0 to 100
- fit_summary must be short, professional, and clearly explain the score in 2 to 4 sentences
- relevant_years_experience must reflect only experience relevant to the requested job title from the job description
- experience_breakdown must include:
  - role_name
  - estimated_years
  - relevant_to_requested_job_title
- if information is missing, return an empty string
- if there is no breakdown, return an empty array []
- extract only what is present in the resume
- do not invent facts
- be conservative with experience estimates
- if dates are unclear, estimate carefully based on the CV
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
        "relevant_years_experience": safe_str(data.get("relevant_years_experience")),
        "experience_breakdown": safe_json_text(data.get("experience_breakdown")),
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
        github, languages, years_of_experience, relevant_years_experience,
        experience_breakdown, job_title, certifications, match_score, fit_summary
    )
    VALUES (
        %(file_name)s, %(analysis_mode)s, %(name)s, %(email)s, %(phone)s, %(skills)s, %(degree)s, %(university)s,
        %(graduation_year)s, %(date_of_birth)s, %(location)s, %(address)s, %(linkedin)s,
        %(github)s, %(languages)s, %(years_of_experience)s, %(relevant_years_experience)s,
        %(experience_breakdown)s, %(job_title)s, %(certifications)s, %(match_score)s, %(fit_summary)s
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
        relevant_years_experience = EXCLUDED.relevant_years_experience,
        experience_breakdown = EXCLUDED.experience_breakdown,
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


def load_resumes():
    select_query = """
    SELECT
        id, file_name, analysis_mode, name, email, phone, skills, degree, university,
        graduation_year, date_of_birth, location, address, linkedin,
        github, languages, years_of_experience, relevant_years_experience,
        experience_breakdown, job_title, certifications, match_score, fit_summary, created_at
    FROM resume
    ORDER BY
        COALESCE(match_score, -1) DESC,
        created_at DESC
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
# CSS
# =========================================================
st.markdown("""
<style>
:root {
    --primary: #0f6f83;
    --primary-dark: #0a5665;
    --primary-soft: #e9f6f8;
    --primary-soft-2: #f4fbfc;
    --bg: #f5f8fa;
    --bg-2: #eef4f6;
    --card: rgba(255,255,255,0.92);
    --card-strong: #ffffff;
    --border: #d8e7eb;
    --border-strong: #c7dce2;
    --text: #183c45;
    --text-soft: #496771;
    --muted: #6f8e97;
    --shadow: 0 10px 30px rgba(15, 111, 131, 0.08);
    --shadow-soft: 0 6px 18px rgba(15, 111, 131, 0.06);
}

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
    font-family: "Segoe UI", Arial, sans-serif;
}

.stApp {
    background: radial-gradient(circle at top left, #fafdff 0%, #f5f9fb 30%, #eff5f7 100%);
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

.block-container > div:first-child {
    margin-top: 0 !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff 0%, #f7fbfc 100%);
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.15rem;
    padding-left: 1.15rem;
    padding-right: 1.15rem;
}

.sidebar-panel {
    background: linear-gradient(180deg, #ffffff 0%, #f8fcfd 100%);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 1rem 1rem 1.1rem 1rem;
    box-shadow: var(--shadow-soft);
    margin-top: 0.5rem;
}

.sidebar-section-title {
    color: var(--primary-dark);
    font-size: 0.96rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.65rem;
}

.sidebar-helper {
    color: var(--text-soft);
    font-size: 0.96rem;
    line-height: 1.55;
}

.main-title {
    font-size: 3rem;
    font-weight: 800;
    color: var(--primary-dark);
    margin-bottom: 0.2rem;
    line-height: 1.05;
}

.sub-title {
    font-size: 1.08rem;
    color: var(--text-soft);
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
    background: var(--card-strong);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px;
    box-shadow: var(--shadow-soft);
    min-height: 124px;
}

.metric-label {
    color: var(--text-soft);
    font-size: 0.9rem;
    margin-bottom: 10px;
    font-weight: 700;
    text-transform: uppercase;
}

.metric-value {
    color: var(--primary-dark);
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1;
}

.small-muted {
    color: var(--text-soft);
    font-size: 0.95rem;
    font-weight: 500;
    margin-bottom: 0.6rem;
}

/* Exact same nav logic/style as the database page */
.top-nav-active {
    background: linear-gradient(180deg, #f2fbfd 0%, #eaf6f8 100%);
    color: var(--primary-dark);
    border: 1px solid var(--border-strong);
    padding: 11px 16px;
    border-radius: 999px;
    font-weight: 800;
    text-align: center;
    font-size: 0.95rem;
}

.stButton > button {
    width: 100%;
    border-radius: 14px !important;
    min-height: 44px;
    font-weight: 700 !important;
    border: 1px solid var(--border) !important;
    background: #ffffff !important;
    color: var(--primary-dark) !important;
    box-shadow: none !important;
}

.stButton > button:hover {
    border-color: var(--primary) !important;
    background: var(--primary-soft) !important;
    color: var(--primary-dark) !important;
}

/* Inputs */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    min-height: 50px !important;
    box-shadow: none !important;
}

div[data-baseweb="select"] span,
div[data-baseweb="select"] input,
div[data-baseweb="select"] * {
    color: var(--text) !important;
    opacity: 1 !important;
}

div[data-baseweb="select"] svg {
    fill: var(--primary-dark) !important;
}

textarea,
.stTextArea textarea {
    background: #FFFFFF !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 18px !important;
    color: var(--text) !important;
    font-size: 1rem !important;
    padding: 14px !important;
}

.stTextArea textarea::placeholder {
    color: #7f9aa3 !important;
    opacity: 1 !important;
}

[data-testid="stFileUploader"] {
    background: #FFFFFF !important;
    border: 2px dashed var(--primary) !important;
    border-radius: 24px !important;
    padding: 22px !important;
}

[data-testid="stFileUploader"] section {
    background: transparent !important;
    border: none !important;
}

[data-testid="stFileUploader"] button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
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
    color: var(--text-soft);
    font-size: 0.84rem;
    font-weight: 800;
    margin-bottom: 2px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.detail-value {
    color: var(--text);
    font-size: 1rem;
    margin-bottom: 12px;
    word-break: break-word;
    line-height: 1.45;
    white-space: pre-wrap;
}

[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    background: #FFFFFF !important;
    overflow: hidden;
    box-shadow: var(--shadow-soft);
}

[data-testid="stExpander"] summary {
    font-weight: 700;
    color: var(--primary-dark) !important;
    background: #f9fcfd !important;
}

.match-badge {
    background: var(--primary-soft);
    border: 2px solid var(--primary);
    color: var(--primary-dark);
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
    box-shadow: var(--shadow-soft);
}

hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.4rem 0;
}

h2, h3 {
    color: var(--primary-dark);
}

[data-testid="stAlert"] {
    border-radius: 16px !important;
    border: 1px solid var(--border) !important;
}

.quick-link-row div.stButton > button {
    background: transparent !important;
    border: none !important;
    color: #4c6374 !important;
    text-decoration: none !important;
    box-shadow: none !important;
    padding: 0px !important;
    width: auto !important;
    min-height: 0px !important;
    height: auto !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    border-radius: 0 !important;
}

.quick-link-row div.stButton > button:hover {
    color: var(--primary) !important;
    text-decoration: underline !important;
    background: transparent !important;
    border: none !important;
}

.divider-pipe {
    color: #D6E6E7;
    margin: 0 2px;
    font-weight: 300;
    padding-top: 2px;
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

    st.markdown(
        """
        <div class="sidebar-panel">
            <div class="sidebar-section-title">Recruitment Control</div>
            <div class="sidebar-helper">
                Upload and analyze CVs, compare candidates against a job description, and store structured results in the database.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    selected_mode = st.selectbox(
        "Choose mode",
        ["Analyze CV", "Compare / Rate CVs"]
    )

    analyze_clicked = st.button("Run Analysis")
    clear_ui_clicked = st.button("Clear")

# =========================================================
# TOP RIGHT NAVIGATION
# =========================================================

nav_spacer, nav_right = st.columns([5, 5])

with nav_right:
    inner_left, inner_middle, inner_right = st.columns(3)
    with inner_left:
        if st.button("Home", use_container_width=True):
            st.switch_page("home.py")
    with inner_middle:
        st.markdown('<div class="top-nav-active">CV Parser</div>', unsafe_allow_html=True)
    with inner_right:
        if st.button("Candidate Database", use_container_width=True):
            st.switch_page("pages/2_Candidate_Database.py")
# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-title">IT Solutions Worldwide</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Professional Candidate Intelligence Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)

# Veiligheidscheck op de API key
if not OPENAI_API_KEY or not str(OPENAI_API_KEY).strip():
    st.warning("Paste your OpenAI API key in the OPENAI_API_KEY variable before analyzing resumes.")

st.markdown(
    f'<div class="mode-box"><strong>Current Mode:</strong> {selected_mode}</div>',
    unsafe_allow_html=True
)

# =========================================================
# CLEAR UI LOGIC (CRITICAL: PLACED BEFORE WIDGETS)
# =========================================================
if clear_ui_clicked:
    # 1. Clear text inputs
    st.session_state.job_description_input = ""
    st.session_state.analysis_prompt_input = ""

    # 2. Clear file uploader by incrementing the dynamic key
    st.session_state["uploader_reset_key"] = st.session_state.get("uploader_reset_key", 0) + 1

    # 3. Add a flag to hide results from screen
    st.session_state["hide_results"] = True

    # 4. SET THE FILTER TIME TO NOW TO HIDE OLD RESUMES
    st.session_state["view_filter_time"] = datetime.now()

    st.rerun()

# =========================================================
# ACTIONS (ANALYSIS)
# =========================================================
# Use a dynamic key for the file uploader to allow resetting
uploader_key = f"files_uploader_{st.session_state.get('uploader_reset_key', 0)}"

if analyze_clicked:
    # Get files from dynamic key
    uploaded_files = st.session_state.get(uploader_key)

    if not OPENAI_API_KEY or not str(OPENAI_API_KEY).strip():
        st.error("OpenAI API key is missing.")
    elif not uploaded_files:
        if selected_mode == "Analyze CV":
            st.warning("Please upload 1 PDF resume.")
        else:
            st.warning("Please upload at least one PDF resume.")
    else:
        try:
            # Handle single vs multiple files for loop compatibility
            files_to_process = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]

            processed_count = 0
            current_job_desc = st.session_state.get("job_description_input", DEFAULT_JOB_DESCRIPTION)
            current_analysis_prompt = st.session_state.get("analysis_prompt_input", DEFAULT_ANALYSIS_PROMPT)

            # THE FIX: Set the filter time to "NOW" exactly before starting the parsing
            # This ensures only the results of THIS specific run will be shown.
            st.session_state["view_filter_time"] = datetime.now()
            st.session_state["hide_results"] = False


            def process_file(uploaded_file):
                if uploaded_file is None:
                    return False
                resume_text = read_pdf_text(uploaded_file)
                if not resume_text:
                    return False
                if selected_mode == "Analyze CV":
                    prompt_to_use = current_analysis_prompt.strip() if current_analysis_prompt.strip() else DEFAULT_ANALYSIS_PROMPT
                    result = extract_resume_only(resume_text, prompt_to_use)
                else:
                    jd_to_use = current_job_desc.strip() if current_job_desc.strip() else DEFAULT_JOB_DESCRIPTION
                    result = extract_and_score_resume(resume_text, jd_to_use)
                if not result.get("name"):
                    result["name"] = uploaded_file.name.rsplit(".", 1)[0]
                upsert_resume(uploaded_file.name, result)
                return True


            with st.spinner(f"Analyzing {len(files_to_process)} resume(s) in parallel..."):
                with ThreadPoolExecutor(max_workers=5) as executor:
                    results = list(executor.map(process_file, files_to_process))
                    processed_count = sum(results)

            if processed_count > 0:
                st.success(f"Analysis completed successfully. Processed: {processed_count}")
                st.rerun()
            else:
                st.warning("No readable PDF text found in the uploaded files.")
        except Exception as e:
            st.error(f"Error during analysis: {e}")

# =========================================================
# INPUT AREA
# =========================================================
st_typing_effect()
left_col, right_col = st.columns(2, gap="large")

with left_col:
    st.markdown('<div id="typing-indicator">Typing...</div>', unsafe_allow_html=True)
    title = 'Job Description' if selected_mode == 'Compare / Rate CVs' else 'CV Analysis Prompt'
    st.markdown(f"## {title}")

    st.markdown('<div class="quick-link-row">', unsafe_allow_html=True)
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
            if st.button("✖ Clear Text", key="link_clear_text"):
                if selected_mode == "Compare / Rate CVs":
                    st.session_state.job_description_input = ""
                else:
                    st.session_state.analysis_prompt_input = ""
    st.markdown('</div>', unsafe_allow_html=True)

    if selected_mode == "Compare / Rate CVs":
        st.text_area("JD", height=320, label_visibility="collapsed", key="job_description_input",
                     placeholder=DEFAULT_JOB_DESCRIPTION)
    else:
        st.text_area("Prompt", height=320, label_visibility="collapsed", key="analysis_prompt_input",
                     placeholder=DEFAULT_ANALYSIS_PROMPT)

with right_col:
    if selected_mode == "Analyze CV":
        st.markdown("## Upload One CV")
        st.file_uploader("Upload resume", type=["pdf"], accept_multiple_files=False,
                         label_visibility="collapsed", key=uploader_key)
    else:
        st.markdown("## Candidate Resumes")
        st.file_uploader("Upload resumes", type=["pdf"], accept_multiple_files=True,
                         label_visibility="collapsed", key=uploader_key)

# =========================================================
# LOAD DATA & DISPLAY RESULTS
# =========================================================
try:
    df = load_resumes()
except Exception as e:
    df = pd.DataFrame()
    st.error(f"Database error: {e}")

# APPLY THE SESSION TIMESTAMP FILTER
if not df.empty and st.session_state.get("view_filter_time"):
    df['created_at'] = pd.to_datetime(df['created_at'])
    # HIER GEBEURT DE FILTERING: Toon alleen resumes die na het 'reset moment' zijn toegevoegd/bijgewerkt
    df = df[df['created_at'] >= st.session_state["view_filter_time"]]

# Display results only if there is data AND we haven't just clicked Clear
if not df.empty and not st.session_state.get("hide_results", False):
    total_resumes = len(df)
    score_series = pd.to_numeric(df["match_score"], errors="coerce")
    rated_df = df[score_series.notna()].copy()
    top_match = int(rated_df["match_score"].max()) if not rated_df.empty else 0
    avg_score = int(rated_df["match_score"].mean()) if not rated_df.empty else 0
    shortlisted = len(rated_df[rated_df["match_score"] >= 75]) if not rated_df.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Batch Resumes</div><div class="metric-value">{total_resumes}</div></div>',
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

    st.markdown("---")
    st.subheader("Latest Analysis Results")

    for _, row in df.iterrows():
        candidate_name = safe_str(row.get("name")) or safe_str(row.get("file_name"))
        score = safe_int(row.get("match_score"), None)
        analysis_mode = safe_str(row.get("analysis_mode"))

        top_left, top_right = st.columns([4, 1])
        with top_left:
            st.subheader(candidate_name)
            st.caption(f"Mode: {analysis_mode}")
        with top_right:
            if score is not None:
                st.markdown(f'<div class="match-badge">{score}% Match</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="summary-box">{safe_str(row.get("fit_summary"))}</div>', unsafe_allow_html=True)
        with st.expander(f"View Resume Details - {candidate_name}"):
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                for label, value in [
                    ("Name", row.get("name")),
                    ("Email", row.get("email")),
                    ("Phone", row.get("phone")),
                    ("Location", row.get("location")),
                    ("Degree", row.get("degree")),
                    ("Total Years of Experience", row.get("years_of_experience")),
                    ("Relevant Years of Experience", row.get("relevant_years_experience"))
                ]:
                    if safe_str(value):
                        st.markdown(
                            f'<div class="detail-label">{label}</div><div class="detail-value">{safe_str(value)}</div>',
                            unsafe_allow_html=True)

            with info_col2:
                for label, value in [
                    ("Job Title", row.get("job_title")),
                    ("Skills", row.get("skills")),
                    ("Languages", row.get("languages")),
                    ("Certifications", row.get("certifications")),
                    ("File Name", row.get("file_name"))
                ]:
                    if safe_str(value):
                        st.markdown(
                            f'<div class="detail-label">{label}</div><div class="detail-value">{safe_str(value)}</div>',
                            unsafe_allow_html=True)

                breakdown_value = format_experience_breakdown(row.get("experience_breakdown"))
                if breakdown_value:
                    st.markdown(
                        f'<div class="detail-label">Experience Breakdown</div><div class="detail-value">{breakdown_value}</div>',
                        unsafe_allow_html=True
                    )
        st.markdown("")
elif df.empty:
    st.info("No resumes found in the current session. Upload some to get started.")
