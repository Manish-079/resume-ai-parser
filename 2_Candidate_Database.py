import os
import json
import base64
import streamlit as st
import pandas as pd
import psycopg
from openai import OpenAI

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Candidate Database",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# OPENAI
# =========================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    try:
        OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    except Exception:
        OPENAI_API_KEY = ""

client = OpenAI(api_key=OPENAI_API_KEY.strip()) if OPENAI_API_KEY.strip() else None

# =========================================================
# SESSION STATE
# =========================================================
if "candidate_ai_question" not in st.session_state:
    st.session_state.candidate_ai_question = ""

if "candidate_ai_answer" not in st.session_state:
    st.session_state.candidate_ai_answer = ""

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
# HELPERS
# =========================================================
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


def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


def normalize_text_series(series):
    return series.fillna("").astype(str).str.lower()


def build_ai_candidate_context(source_df, max_candidates=60):
    """
    Build a compact, structured context for AI based only on
    existing database records. Keeps it fast and cheaper.
    """
    if source_df.empty:
        return []

    working_df = source_df.copy().head(max_candidates)

    candidate_records = []
    for _, row in working_df.iterrows():
        candidate_records.append({
            "name": safe_str(row.get("name")) or safe_str(row.get("file_name")),
            "analysis_mode": safe_str(row.get("analysis_mode")),
            "job_title": safe_str(row.get("job_title")),
            "years_of_experience": safe_str(row.get("years_of_experience")),
            "skills": safe_str(row.get("skills")),
            "languages": safe_str(row.get("languages")),
            "degree": safe_str(row.get("degree")),
            "university": safe_str(row.get("university")),
            "location": safe_str(row.get("location")),
            "certifications": safe_str(row.get("certifications")),
            "match_score": safe_int(row.get("match_score"), None),
            "fit_summary": safe_str(row.get("fit_summary")),
            "file_name": safe_str(row.get("file_name")),
            "created_at": safe_str(row.get("created_at"))
        })

    return candidate_records


def ask_ai_about_candidates(question, source_df):
    if not client:
        raise ValueError("OpenAI API key is missing.")

    candidate_context = build_ai_candidate_context(source_df, max_candidates=60)

    if not candidate_context:
        raise ValueError("There are no candidate records available for AI analysis.")

    prompt = f"""
You are a professional recruitment assistant for IT Solutions Worldwide.

You must answer ONLY using the candidate database data below.
Do not invent missing facts.
Do not mention information that is not in the database.
If the answer cannot be determined from the data, say that clearly.

Candidate database records:
{json.dumps(candidate_context, ensure_ascii=False, indent=2)}

User question:
{question}

Instructions:
- Give a concise professional answer
- Prefer bullet points when comparing candidates
- If relevant, mention candidate names and why they fit
- If relevant, rank candidates based only on the stored data
- Keep the tone corporate and clear
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>
:root {
    --primary: #0B7A8F;
    --primary-dark: #075E6E;
    --primary-soft: #EAF6F8;
    --bg: #F4F7F8;
    --card: #FFFFFF;
    --border: #CFE3E8;
    --text: #124B57;
    --text-strong: #163C45;
    --muted: #6D8E96;
    --muted-dark: #4D6C74;
    --success-soft: #EEF9F2;
    --info-soft: #F5FAFB;
}

/* Hide default Streamlit multipage navigation */
[data-testid="stSidebarNav"] {
    display: none !important;
}

/* =========================
GLOBAL
========================= */
html, body, [class*="css"] {
    font-family: "Segoe UI", sans-serif;
}

.stApp {
    background: linear-gradient(180deg, #F8FBFB 0%, #EEF4F5 100%);
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

/* =========================
SIDEBAR
========================= */
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
    color: var(--primary-dark);
    font-size: 1rem;
    font-weight: 800;
    text-transform: uppercase;
    margin-bottom: 1rem;
    letter-spacing: 0.6px;
}

/* =========================
TITLES
========================= */
.main-title {
    font-size: 3rem;
    font-weight: 800;
    color: var(--primary);
    margin-bottom: 0.2rem;
    line-height: 1.05;
}

.sub-title {
    font-size: 1.15rem;
    color: var(--muted-dark);
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

.section-heading {
    font-size: 2.1rem;
    font-weight: 800;
    color: var(--primary-dark);
    margin-top: 1rem;
    margin-bottom: 1rem;
}

/* =========================
TOP NAVIGATION
========================= */
.nav-button-active {
    background: transparent;
    color: var(--primary);
    text-align: center;
    padding: 12px 14px;
    font-weight: 700;
    font-size: 0.95rem;
    border: none;
    box-shadow: none;
}

/* =========================
BUTTONS
========================= */
.stButton > button {
    width: 100%;
    background: transparent !important;
    color: var(--primary-dark) !important;
    border: none !important;
    font-weight: 700;
    font-size: 0.95rem;
    padding: 12px 14px;
    border-radius: 10px;
    box-shadow: none !important;
}

.stButton > button:hover {
    background: var(--primary-soft) !important;
    color: var(--primary-dark) !important;
}

.primary-action button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    box-shadow: 0 6px 14px rgba(11, 122, 143, 0.14) !important;
}

.primary-action button:hover {
    background: var(--primary-dark) !important;
    color: white !important;
}

/* =========================
CARDS / METRICS
========================= */
.metric-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px;
    box-shadow: 0 6px 14px rgba(11, 122, 143, 0.06);
    min-height: 124px;
}

.metric-label {
    color: var(--muted-dark);
    font-size: 0.9rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.metric-value {
    color: var(--primary);
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1;
}

.small-muted {
    color: var(--muted-dark);
    font-size: 0.95rem;
    font-weight: 500;
    margin-bottom: 0.6rem;
}

.filter-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 18px 18px 10px 18px;
    margin-bottom: 18px;
    box-shadow: 0 6px 14px rgba(11, 122, 143, 0.04);
}

.ai-card {
    background: linear-gradient(180deg, #FFFFFF 0%, #F8FCFC 100%);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 18px;
    margin-bottom: 18px;
    box-shadow: 0 6px 14px rgba(11, 122, 143, 0.05);
}

.ai-answer-box {
    background: var(--info-soft);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px;
    color: var(--text-strong);
    line-height: 1.65;
    margin-top: 10px;
}

/* =========================
INPUTS
========================= */
textarea,
.stTextArea textarea {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    color: var(--text-strong) !important;
    padding: 14px !important;
    caret-color: var(--primary) !important;
}

textarea:focus,
.stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(11, 122, 143, 0.12) !important;
    background: #FFFFFF !important;
}

.stTextArea textarea::placeholder {
    color: #7C949B !important;
    opacity: 1 !important;
}

/* Text input */
[data-testid="stTextInput"] input {
    border-radius: 12px !important;
    border: 1px solid var(--border) !important;
    background: #FFFFFF !important;
    color: var(--text-strong) !important;
    -webkit-text-fill-color: var(--text-strong) !important;
    font-weight: 500 !important;
}

[data-testid="stTextInput"] input::placeholder {
    color: #7C949B !important;
    -webkit-text-fill-color: #7C949B !important;
    opacity: 1 !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(11, 122, 143, 0.12) !important;
}

/* =========================
FILTER TEXT VISIBILITY FIX
========================= */

/* General widget labels */
label[data-testid="stWidgetLabel"],
label[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] {
    color: var(--text-strong) !important;
    opacity: 1 !important;
    font-weight: 700 !important;
}

/* Labels used above inputs/selects/sliders */
.stTextInput label,
.stSelectbox label,
.stSlider label,
.stCheckbox label {
    color: var(--text-strong) !important;
    opacity: 1 !important;
    font-weight: 700 !important;
}

/* Search input text */
[data-testid="stTextInput"] input {
    color: var(--text-strong) !important;
    -webkit-text-fill-color: var(--text-strong) !important;
}

/* Dropdown selected text */
div[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    min-height: 50px !important;
    box-shadow: none !important;
}

div[data-baseweb="select"] span,
div[data-baseweb="select"] div,
div[data-baseweb="select"] input,
div[data-baseweb="select"] * {
    color: var(--text-strong) !important;
    -webkit-text-fill-color: var(--text-strong) !important;
    opacity: 1 !important;
    font-weight: 600 !important;
}

div[data-baseweb="select"] svg {
    fill: var(--primary) !important;
}

/* Checkbox labels */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] span {
    color: var(--text-strong) !important;
    opacity: 1 !important;
    font-weight: 600 !important;
}

/* Checkbox square border */
[data-testid="stCheckbox"] div[role="checkbox"] {
    border-color: var(--muted-dark) !important;
}

/* Slider label and value */
[data-testid="stSlider"] label,
[data-testid="stSlider"] p,
[data-testid="stSlider"] span {
    color: var(--text-strong) !important;
    opacity: 1 !important;
    font-weight: 600 !important;
}

/* =========================
DETAILS / SUMMARY
========================= */
.match-badge {
    background: var(--primary-soft);
    border: 2px solid var(--primary);
    color: var(--primary-dark);
    font-weight: 800;
    padding: 10px 16px;
    border-radius: 999px;
    text-align: center;
    display: inline-block;
    white-space: nowrap;
}

.summary-box {
    background: #F7FBFC;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px;
    color: var(--text-strong);
    line-height: 1.6;
}

.detail-label {
    color: var(--muted-dark);
    font-size: 0.85rem;
    font-weight: 800;
    margin-bottom: 2px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.detail-value {
    color: var(--text-strong);
    font-size: 1rem;
    margin-bottom: 12px;
    word-break: break-word;
    line-height: 1.45;
}

/* =========================
SLIDER
========================= */
[data-baseweb="slider"] [role="slider"] {
    background: var(--primary) !important;
    border-color: var(--primary) !important;
}

[data-baseweb="slider"] > div > div > div {
    background: var(--primary-soft) !important;
}

/* =========================
EXPANDER
========================= */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    background: #FFFFFF !important;
    overflow: hidden;
}

[data-testid="stExpander"] summary {
    background: #F7FBFC !important;
    color: var(--primary-dark) !important;
    font-weight: 700;
    border-bottom: 1px solid var(--border);
}

/* =========================
MISC
========================= */
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

# ===============================
# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    root_dir = os.path.dirname(os.path.dirname(__file__))
    image_path_1 = os.path.join(root_dir, "images", "image_18.png")
    image_path_2 = os.path.join(root_dir, "image_18.png")

    final_image_path = None
    if os.path.exists(image_path_1):
        final_image_path = image_path_1
    elif os.path.exists(image_path_2):
        final_image_path = image_path_2

    if final_image_path:
        bin_str = get_base64_of_bin_file(final_image_path)
        st.markdown(
            f"""
            <div style="text-align:center; margin-bottom:30px; padding-top:6px;">
                <img src="data:image/png;base64,{bin_str}" width="320" style="max-width:100%; height:auto;">
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown('<div class="sidebar-section-title">Recruitment Control</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-muted">Search, filter and ask AI about the existing candidate database.</div>', unsafe_allow_html=True)

# =========================================================
# TOP RIGHT NAVIGATION
# =========================================================
nav_spacer, nav_btn1, nav_btn2 = st.columns([6, 2, 2])

with nav_btn1:
    if st.button("CV Parser", use_container_width=True):
        st.switch_page("app.py")

with nav_btn2:
    st.markdown(
        '<div class="nav-button-active">Candidate Database</div>',
        unsafe_allow_html=True
    )

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-title">Candidate Database</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Search, filter, review and analyze all CVs stored in the database</div>', unsafe_allow_html=True)
st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)

# =========================================================
# LOAD DATA
# =========================================================
db_error = None
try:
    df = load_resumes()
except Exception as e:
    df = pd.DataFrame()
    db_error = str(e)
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
# FILTERS
# =========================================================
st.markdown('<div class="section-heading">Candidate Search</div>', unsafe_allow_html=True)

st.markdown('<div class="filter-card">', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns([2.3, 1.2, 1.2, 0.9])

with f1:
    search_query = st.text_input(
        "Search candidates",
        placeholder="Search by name, skills, role, certifications or keyword"
    )

with f2:
    min_score = st.slider("Minimum score", 0, 100, 0)

with f3:
    mode_filter = st.selectbox(
        "Mode",
        ["All", "Analyze CV", "Compare / Rate CVs"]
    )

with f4:
    sort_option = st.selectbox(
        "Sort by",
        ["Newest", "Highest Score", "Name A-Z"]
    )

q1, q2, q3, q4, q5 = st.columns([1, 1, 1, 1, 2.2])

with q1:
    shortlisted_only = st.checkbox("Shortlisted", value=False)

with q2:
    rated_only = st.checkbox("Rated only", value=False)

with q3:
    analysis_only = st.checkbox("Analysis only", value=False)

with q4:
    reset_filters = st.button("Reset")

if reset_filters:
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# FILTER LOGIC
# =========================================================
if df.empty:
    filtered_df = df
else:
    df = df.copy()

    df["match_score_num"] = pd.to_numeric(df["match_score"], errors="coerce")
    df["search_blob"] = (
        normalize_text_series(df["name"]) + " " +
        normalize_text_series(df["skills"]) + " " +
        normalize_text_series(df["job_title"]) + " " +
        normalize_text_series(df["certifications"]) + " " +
        normalize_text_series(df["fit_summary"]) + " " +
        normalize_text_series(df["analysis_mode"]) + " " +
        normalize_text_series(df["file_name"])
    )

    filtered_df = df.copy()

    if min_score > 0:
        filtered_df = filtered_df[filtered_df["match_score_num"].fillna(0) >= min_score]

    if search_query:
        q = search_query.lower().strip()
        filtered_df = filtered_df[filtered_df["search_blob"].str.contains(q, na=False)]

    if mode_filter != "All":
        filtered_df = filtered_df[filtered_df["analysis_mode"].fillna("") == mode_filter]

    if shortlisted_only:
        filtered_df = filtered_df[filtered_df["match_score_num"].fillna(0) >= 75]

    if rated_only:
        filtered_df = filtered_df[filtered_df["match_score_num"].notna()]

    if analysis_only:
        filtered_df = filtered_df[filtered_df["analysis_mode"].fillna("") == "Analyze CV"]

    if sort_option == "Highest Score":
        filtered_df = filtered_df.sort_values(
            by=["match_score_num", "created_at"],
            ascending=[False, False],
            na_position="last"
        )
    elif sort_option == "Name A-Z":
        filtered_df = filtered_df.sort_values(
            by=["name", "created_at"],
            ascending=[True, False],
            na_position="last"
        )
    else:
        filtered_df = filtered_df.sort_values(
            by=["created_at"],
            ascending=[False],
            na_position="last"
        )

# =========================================================
# AI ASSISTANT
# =========================================================
st.markdown('<div class="section-heading">AI Candidate Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-muted">Ask questions about the candidates currently shown in the filtered results. The AI uses only existing database records, so it stays fast and avoids re-parsing CVs.</div>',
    unsafe_allow_html=True
)

st.markdown('<div class="ai-card">', unsafe_allow_html=True)

ai_left, ai_right = st.columns([5, 1])

with ai_left:
    st.text_area(
        "Ask AI about candidates",
        key="candidate_ai_question",
        height=120,
        placeholder="Examples: Give me the top 3 Python candidates. / Who looks strongest for a data analyst role? / Summarize the shortlisted candidates."
    )

with ai_right:
    st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
    ai_run = st.button("Ask AI", use_container_width=True)
    clear_ai = st.button("Clear AI", use_container_width=True)

if clear_ai:
    st.session_state.candidate_ai_question = ""
    st.session_state.candidate_ai_answer = ""
    st.rerun()

if ai_run:
    if not OPENAI_API_KEY.strip():
        st.error("OpenAI API key is missing.")
    elif filtered_df.empty:
        st.warning("There are no filtered candidates available for AI analysis.")
    elif not st.session_state.candidate_ai_question.strip():
        st.warning("Please enter a question for the AI assistant.")
    else:
        try:
            with st.spinner("Analyzing existing candidate data..."):
                answer = ask_ai_about_candidates(
                    st.session_state.candidate_ai_question.strip(),
                    filtered_df
                )
                st.session_state.candidate_ai_answer = answer
        except Exception as e:
            st.error(f"AI error: {e}")

if st.session_state.candidate_ai_answer:
    st.markdown(
        f'<div class="ai-answer-box">{st.session_state.candidate_ai_answer}</div>',
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# RESULTS
# =========================================================
st.markdown(f'<div class="section-heading">Candidate Results ({len(filtered_df)})</div>', unsafe_allow_html=True)

if filtered_df.empty:
    if db_error:
        st.info("No candidates are shown because the database is not available right now.")
    else:
        st.info("No candidates match the selected filters.")
else:
    for _, row in filtered_df.iterrows():
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