import os
import json
import base64
import streamlit as st
import pandas as pd
import psycopg
from openai import OpenAI
import PyPDF2

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="IT Solutions Worldwide",
    layout="wide",
    initial_sidebar_state="expanded"
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
OPENAI_API_KEY = "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"

client = OpenAI(api_key=OPENAI_API_KEY.strip()) if OPENAI_API_KEY.strip() else None

# =========================================================
# DATABASE
# =========================================================
DB_HOST = "localhost"
DB_NAME = "resume_parser"
DB_USER = "postgres"
DB_PASSWORD = "root"
DB_PORT = 5432


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
# CSS - LOGO COLORS
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

.stButton > button {
    width: 100%;
    border: none;
    border-radius: 14px;
    background: var(--primary);
    color: white !important;
    font-weight: 700;
    font-size: 0.98rem;
    padding: 0.82rem 1rem;
    box-shadow: 0 10px 20px rgba(15, 107, 116, 0.18);
}

.stButton > button:hover {
    background: var(--primary-dark);
    color: white !important;
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
</style>
""", unsafe_allow_html=True)
# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    image_path = os.path.join(os.path.dirname(__file__), "images", "image_18.png")
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
    clear_clicked = st.button("Clear Database")

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
left_col, right_col = st.columns(2, gap="large")

with left_col:
    if selected_mode == "Compare / Rate CVs":
        st.markdown("## Job Description")

        button_col1, button_col2 = st.columns([1, 1])

        with button_col1:
            if st.button("Use Default Prompt"):
                st.session_state.job_description_input = DEFAULT_JOB_DESCRIPTION

        with button_col2:
            if st.button("Clear Prompt"):
                st.session_state.job_description_input = ""

        jd_input = st.text_area(
            "Job Description",
            height=320,
            label_visibility="collapsed",
            key="job_description_input",
            placeholder=DEFAULT_JOB_DESCRIPTION
        )

        if st.session_state.job_description_input.strip():
            if st.session_state.job_description_input.strip() == DEFAULT_JOB_DESCRIPTION:
                st.markdown('<div class="small-muted">Default prompt loaded</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="small-muted">Custom prompt active</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="small-muted">Using the default template prompt</div>', unsafe_allow_html=True)

    else:
        st.markdown("## CV Analysis Prompt")

        button_col1, button_col2 = st.columns([1, 1])

        with button_col1:
            if st.button("Use Default Analysis Prompt"):
                st.session_state.analysis_prompt_input = DEFAULT_ANALYSIS_PROMPT

        with button_col2:
            if st.button("Clear Analysis Prompt"):
                st.session_state.analysis_prompt_input = ""

        analysis_input = st.text_area(
            "CV Analysis Prompt",
            height=320,
            label_visibility="collapsed",
            key="analysis_prompt_input",
            placeholder=DEFAULT_ANALYSIS_PROMPT
        )

        if st.session_state.analysis_prompt_input.strip():
            if st.session_state.analysis_prompt_input.strip() == DEFAULT_ANALYSIS_PROMPT:
                st.markdown('<div class="small-muted">Default analysis prompt loaded</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="small-muted">Custom analysis prompt active</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="small-muted">Using the default analysis prompt</div>', unsafe_allow_html=True)

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

if clear_clicked:
    try:
        clear_database()
        st.success("Database cleared successfully.")
        st.rerun()
    except Exception as e:
        st.error(f"Error clearing database: {e}")

# =========================================================
# LOAD DATA
# =========================================================
try:
    df = load_resumes()
except Exception as e:
    df = pd.DataFrame()
    st.error(f"Database error: {e}")

# =========================================================
# METRICS
# =========================================================
if not df.empty:
    score_series = pd.to_numeric(df["match_score"], errors="coerce")
    rated_df = df[score_series.notna()].copy()
    rated_df["match_score"] = pd.to_numeric(rated_df["match_score"], errors="coerce")

    total_resumes = len(df)
    top_match = int(rated_df["match_score"].max()) if not rated_df.empty else 0
    avg_score = int(rated_df["match_score"].mean()) if not rated_df.empty else 0
    shortlisted = len(rated_df[rated_df["match_score"] >= 75]) if not rated_df.empty else 0
else:
    total_resumes = 0
    top_match = 0
    avg_score = 0
    shortlisted = 0

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Total Resumes</div>
            <div class="metric-value">{total_resumes}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with m2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Top Match</div>
            <div class="metric-value">{top_match}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with m3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Average Score</div>
            <div class="metric-value">{avg_score}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with m4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Shortlisted</div>
            <div class="metric-value">{shortlisted}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================================================
# CANDIDATE RESULTS
# =========================================================
st.markdown("## Candidate Results")

if df.empty:
    st.info("No resumes have been analyzed yet.")
else:
    df["match_score_num"] = pd.to_numeric(df["match_score"], errors="coerce")
    df = df.sort_values(by=["match_score_num", "created_at"], ascending=[False, False], na_position="last")

    for _, row in df.iterrows():
        candidate_name = safe_str(row.get("name")) or safe_str(row.get("file_name"))
        score = safe_int(row.get("match_score"), None)
        analysis_mode = safe_str(row.get("analysis_mode"))

        st.markdown("---")

        if score is not None:
            top_left, top_right = st.columns([4, 1])

            with top_left:
                st.subheader(candidate_name)
                st.caption(f"Mode: {analysis_mode}")

            with top_right:
                st.markdown(
                    f'<div class="match-badge">{score}% Match</div>',
                    unsafe_allow_html=True
                )
        else:
            st.subheader(candidate_name)
            st.caption(f"Mode: {analysis_mode}")

        summary_title = "AI Summary" if score is not None else "CV Analysis Summary"
        st.markdown(f"**{summary_title}**")
        st.markdown(
            f'<div class="summary-box">{safe_str(row.get("fit_summary"))}</div>',
            unsafe_allow_html=True
        )

        with st.expander(f"View Resume Details - {candidate_name}"):
            info_col1, info_col2 = st.columns(2)

            with info_col1:
                for label, value in [
                    ("Name", row.get("name")),
                    ("Email", row.get("email")),
                    ("Phone", row.get("phone")),
                    ("Location", row.get("location")),
                    ("Address", row.get("address")),
                    ("Date of Birth", row.get("date_of_birth")),
                    ("Degree", row.get("degree")),
                    ("University", row.get("university")),
                    ("Graduation Year", row.get("graduation_year")),
                ]:
                    if safe_str(value):
                        st.markdown(f'<div class="detail-label">{label}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="detail-value">{safe_str(value)}</div>', unsafe_allow_html=True)

            with info_col2:
                for label, value in [
                    ("Job Title", row.get("job_title")),
                    ("Years of Experience", row.get("years_of_experience")),
                    ("Skills", row.get("skills")),
                    ("Languages", row.get("languages")),
                    ("Certifications", row.get("certifications")),
                    ("LinkedIn", row.get("linkedin")),
                    ("GitHub", row.get("github")),
                    ("File Name", row.get("file_name")),
                ]:
                    if safe_str(value):
                        st.markdown(f'<div class="detail-label">{label}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="detail-value">{safe_str(value)}</div>', unsafe_allow_html=True)