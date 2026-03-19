import os
import base64
import streamlit as st
import pandas as pd
import psycopg

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Candidate Database",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    --muted: #6D8E96;
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
    color: var(--primary) !important;
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

/* Button style for regular action buttons inside uploader/cards */
[data-testid="stFileUploader"] button,
[data-testid="stDownloadButton"] button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
}

[data-testid="stFileUploader"] button:hover,
[data-testid="stDownloadButton"] button:hover {
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
    color: var(--muted);
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

.mode-box {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 12px 16px;
    margin-bottom: 14px;
    color: var(--text);
}

.small-muted {
    color: var(--muted);
    font-size: 0.95rem;
    font-weight: 500;
    margin-bottom: 0.6rem;
}

/* =========================
INPUTS
========================= */
textarea,
.stTextArea textarea {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    color: var(--text) !important;
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
    color: var(--muted) !important;
    opacity: 1 !important;
}

[data-testid="stTextInput"] input {
    border-radius: 12px !important;
    border: 1px solid var(--border) !important;
    background: #FFFFFF !important;
    color: var(--text) !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(11, 122, 143, 0.12) !important;
}

/* =========================
SELECT BOX
========================= */
div[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    min-height: 50px !important;
    box-shadow: none !important;
}

div[data-baseweb="select"] * {
    color: var(--text) !important;
    opacity: 1 !important;
}

div[data-baseweb="select"] svg {
    fill: var(--primary) !important;
}

/* =========================
FILE UPLOADER
========================= */
[data-testid="stFileUploader"] {
    border: 2px dashed var(--primary) !important;
    border-radius: 20px !important;
    background: #FFFFFF !important;
    padding: 22px !important;
}

[data-testid="stFileUploader"] section {
    background: transparent !important;
    border: none !important;
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
BADGES / SUMMARY
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

/* Keep text-link style for your Use Default / Clear row */
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
    color: var(--primary) !important;
    text-decoration: underline !important;
    background: transparent !important;
}

.divider-pipe {
    color: var(--border);
    margin: 0 2px;
    font-weight: 300;
}
</style>
""", unsafe_allow_html=True)
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
    st.markdown('<div class="small-muted">Candidate database overview and filtering.</div>', unsafe_allow_html=True)

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
st.markdown('<div class="sub-title">Search, filter and review all CVs stored in the database</div>', unsafe_allow_html=True)
st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)

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
# FILTERS
# =========================================================
st.markdown("## Database Explorer")
with st.expander("Filter and Search Candidates", expanded=True):
    f1, f2 = st.columns([2, 1])

    with f1:
        search_query = st.text_input(
            "Search by Name or Skills",
            placeholder="For example: Python, Java, Ruben"
        )

    with f2:
        min_score = st.slider("Minimum Match Score", 0, 100, 0)

# =========================================================
# FILTER LOGIC
# =========================================================
if df.empty:
    filtered_df = df
else:
    df["match_score_num"] = pd.to_numeric(df["match_score"], errors="coerce").fillna(0)
    filtered_df = df[df["match_score_num"] >= min_score]

    if search_query:
        q = search_query.lower()
        filtered_df = filtered_df[
            filtered_df["name"].str.lower().str.contains(q, na=False) |
            filtered_df["skills"].str.lower().str.contains(q, na=False)
        ]

    filtered_df = filtered_df.sort_values(
        by=["match_score_num", "created_at"],
        ascending=[False, False],
        na_position="last"
    )

# =========================================================
# RESULTS
# =========================================================
st.markdown(f"## Candidate Results ({len(filtered_df)})")

if filtered_df.empty:
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