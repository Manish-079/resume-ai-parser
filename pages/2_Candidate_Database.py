import os
import json
import base64
import html
import re
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
# LUCIDE ICONS
# =========================================================
st.markdown("""
<script src="https://unpkg.com/lucide@latest"></script>
""", unsafe_allow_html=True)

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

if "candidate_ai_matches" not in st.session_state:
    st.session_state.candidate_ai_matches = []

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


def load_resumes(search_query="", min_score=0):
    base_query = """
    SELECT
        id, file_name, analysis_mode, name, email, phone, skills, degree, university,
        graduation_year, date_of_birth, location, address, linkedin,
        github, languages, years_of_experience, relevant_years_experience,
        experience_breakdown, job_title, certifications, match_score, fit_summary, created_at
    FROM resume
    WHERE COALESCE(match_score, 0) >= %s
    """

    params = [min_score]
    cleaned_query = safe_str(search_query)

    if cleaned_query:
        base_query += """
        AND (
            COALESCE(name, '') ILIKE %s
            OR COALESCE(skills, '') ILIKE %s
            OR COALESCE(job_title, '') ILIKE %s
            OR COALESCE(fit_summary, '') ILIKE %s
            OR COALESCE(languages, '') ILIKE %s
            OR COALESCE(certifications, '') ILIKE %s
            OR COALESCE(degree, '') ILIKE %s
            OR COALESCE(university, '') ILIKE %s
            OR COALESCE(location, '') ILIKE %s
            OR COALESCE(relevant_years_experience, '') ILIKE %s
            OR COALESCE(experience_breakdown, '') ILIKE %s
        )
        """
        search_param = f"%{cleaned_query}%"
        params.extend([search_param] * 11)

    base_query += " ORDER BY created_at DESC"

    with connect_db() as conn:
        df = pd.read_sql(base_query, conn, params=params)

    return df

# =========================================================
# HELPERS
# =========================================================
def safe_str(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
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


def build_ai_candidate_context(source_df, max_candidates=60):
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
            "relevant_years_experience": safe_str(row.get("relevant_years_experience")),
            "experience_breakdown": safe_str(row.get("experience_breakdown")),
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


def extract_json_from_text(text):
    text = safe_str(text)
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


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

Return ONLY valid JSON in this exact format:
{{
  "answer": "short professional answer for recruiter",
  "recommended_candidates": ["Candidate Name 1", "Candidate Name 2", "Candidate Name 3"]
}}

Rules:
- "answer" must be plain readable recruiter text
- "recommended_candidates" must only include names that truly exist in the data
- if no specific candidates should be shown, return an empty list
- use relevant_years_experience and experience_breakdown when they help answer the question
- no markdown
- no code block
- no extra text outside JSON

Candidate database records:
{json.dumps(candidate_context, ensure_ascii=False, indent=2)}

User question:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content.strip()
    parsed = extract_json_from_text(raw)

    if not parsed:
        return {
            "answer": raw,
            "recommended_candidates": []
        }

    return {
        "answer": safe_str(parsed.get("answer")),
        "recommended_candidates": parsed.get("recommended_candidates", [])
        if isinstance(parsed.get("recommended_candidates", []), list) else []
    }


def escape_html_text(value):
    return html.escape(safe_str(value))


def create_initials(name):
    name = safe_str(name)
    if not name:
        return "CV"
    parts = [p for p in name.split() if p]
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def split_tags(value, max_items=8):
    raw = safe_str(value)
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return parts[:max_items]


def format_ai_answer(answer):
    safe_answer = html.escape(safe_str(answer))
    safe_answer = safe_answer.replace("\n", "<br>")
    return safe_answer


def render_tags(tags, variant="default"):
    if not tags:
        return ""
    cls = "tag-chip"
    if variant == "green":
        cls = "tag-chip green"
    elif variant == "gold":
        cls = "tag-chip gold"
    return "".join(
        [f'<span class="{cls}">{html.escape(str(tag))}</span>' for tag in tags]
    )


def score_class(score):
    if score is None:
        return "neutral"
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "average"
    return "low"


def find_matching_candidates(df, candidate_names):
    if df.empty or not candidate_names:
        return pd.DataFrame()

    names_clean = [safe_str(n).lower() for n in candidate_names if safe_str(n)]
    if not names_clean:
        return pd.DataFrame()

    working = df.copy()
    working["_name_clean"] = working["name"].fillna("").astype(str).str.strip().str.lower()

    matched_rows = []

    for target in names_clean:
        exact = working[working["_name_clean"] == target]
        if not exact.empty:
            matched_rows.append(exact.iloc[0])
            continue

        partial = working[working["_name_clean"].str.contains(re.escape(target), na=False)]
        if not partial.empty:
            matched_rows.append(partial.iloc[0])

    if not matched_rows:
        return pd.DataFrame()

    result = pd.DataFrame(matched_rows).drop(columns=["_name_clean"], errors="ignore")
    return result


def prepare_export_dataframe(df):
    if df.empty:
        return df.copy()

    export_df = df.copy()

    def clean_export_value(value):
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join(str(v).strip() for v in value if str(v).strip())
        value = str(value)
        value = value.replace("\r", " ").replace("\n", " ")
        value = re.sub(r"\s+", " ", value).strip()
        return value

    for col in export_df.columns:
        export_df[col] = export_df[col].apply(clean_export_value)

    rename_map = {
        "id": "ID",
        "file_name": "File Name",
        "analysis_mode": "Analysis Mode",
        "name": "Candidate Name",
        "email": "Email",
        "phone": "Phone",
        "skills": "Skills",
        "degree": "Degree",
        "university": "University",
        "graduation_year": "Graduation Year",
        "date_of_birth": "Date of Birth",
        "location": "Location",
        "address": "Address",
        "linkedin": "LinkedIn",
        "github": "GitHub",
        "languages": "Languages",
        "years_of_experience": "Years of Experience",
        "relevant_years_experience": "Relevant Years of Experience",
        "experience_breakdown": "Experience Breakdown",
        "job_title": "Job Title",
        "certifications": "Certifications",
        "match_score": "Match Score",
        "fit_summary": "Fit Summary",
        "created_at": "Imported At"
    }

    export_df = export_df.rename(columns=rename_map)

    preferred_order = [
        "ID",
        "Candidate Name",
        "Job Title",
        "Match Score",
        "Years of Experience",
        "Relevant Years of Experience",
        "Experience Breakdown",
        "Skills",
        "Languages",
        "Certifications",
        "Degree",
        "University",
        "Graduation Year",
        "Location",
        "Email",
        "Phone",
        "LinkedIn",
        "GitHub",
        "Address",
        "Date of Birth",
        "Analysis Mode",
        "File Name",
        "Fit Summary",
        "Imported At"
    ]

    existing_columns = [col for col in preferred_order if col in export_df.columns]
    remaining_columns = [col for col in export_df.columns if col not in existing_columns]
    export_df = export_df[existing_columns + remaining_columns]

    return export_df


def format_experience_breakdown(value):
    raw = safe_str(value)
    if not raw:
        return ""

    try:
        parsed = json.loads(raw)
    except Exception:
        return raw

    if not isinstance(parsed, list):
        return raw

    lines = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        role_name = safe_str(item.get("role_name")) or "Unknown Role"
        estimated_years = safe_str(item.get("estimated_years")) or "N/A"
        relevant_flag = item.get("relevant_to_requested_job_title", False)
        relevant_text = "Yes" if str(relevant_flag).lower() in ["true", "1", "yes"] else "No"
        lines.append(f"• {role_name}: {estimated_years} year(s) | Relevant: {relevant_text}")

    return "\n".join(lines)


def render_candidate_card(row):
    candidate_name = safe_str(row.get("name")) or safe_str(row.get("file_name")) or "Unnamed Candidate"
    score = safe_int(row.get("match_score"), None)
    analysis_mode = safe_str(row.get("analysis_mode")) or "Stored CV"
    job_title = safe_str(row.get("job_title")) or "Role not specified"
    location = safe_str(row.get("location")) or "Location not specified"
    years = safe_str(row.get("years_of_experience"))
    relevant_years = safe_str(row.get("relevant_years_experience"))
    degree = safe_str(row.get("degree"))
    university = safe_str(row.get("university"))
    fit_summary = safe_str(row.get("fit_summary")) or "No summary available."
    created_at = safe_str(row.get("created_at"))
    score_css = score_class(score)

    skills = split_tags(row.get("skills"), max_items=7)
    languages = split_tags(row.get("languages"), max_items=4)
    certifications = split_tags(row.get("certifications"), max_items=4)

    experience_meta_parts = []
    if years:
        experience_meta_parts.append(f"<span>{escape_html_text(years)} years total</span>")
    if relevant_years:
        experience_meta_parts.append(f"<span>{escape_html_text(relevant_years)} years relevant</span>")
    if analysis_mode:
        experience_meta_parts.append(f"<span>{escape_html_text(analysis_mode)}</span>")

    experience_meta_html = ""
    if experience_meta_parts:
        experience_meta_html = "<span class='meta-dot'>•</span>".join(experience_meta_parts)

    candidate_html = f"""
<div class="candidate-card">
<div class="candidate-top">
<div class="avatar-circle">{create_initials(candidate_name)}</div>
<div class="candidate-main">
<div class="candidate-name">{escape_html_text(candidate_name)}</div>
<div class="candidate-role">{escape_html_text(job_title)}</div>
<div class="candidate-meta">
<span>{escape_html_text(location)}</span>
{"<span class='meta-dot'>•</span>" + experience_meta_html if experience_meta_html else ""}
</div>
</div>
</div>
<div class="candidate-summary">
{escape_html_text(fit_summary)}
</div>
<div class="tag-row">
{render_tags(skills, "default")}
</div>
{"<div class='detail-inline'><span class='inline-label'>Languages</span>" + render_tags(languages, "green") + "</div>" if languages else ""}
{"<div class='detail-inline'><span class='inline-label'>Certifications</span>" + render_tags(certifications, "gold") + "</div>" if certifications else ""}
{"<div class='candidate-footer'><span><strong>Education:</strong> " + escape_html_text(degree) + (" | " + escape_html_text(university) if university else "") + "</span></div>" if degree or university else ""}
{"<div class='candidate-footer'><span><strong>Imported:</strong> " + escape_html_text(created_at) + "</span></div>" if created_at else ""}
</div>
"""

    score_html = f"""
<div class="side-score-card {score_css}">
<div class="side-score-label">Match Score</div>
<div class="side-score-value">{f"{score}%" if score is not None else "N/A"}</div>
<div class="side-score-sub">Database fit</div>
</div>
"""

    with st.container():
        left, right = st.columns([5.6, 1.8], vertical_alignment="top")
        with left:
            st.markdown(candidate_html, unsafe_allow_html=True)
        with right:
            st.markdown(score_html, unsafe_allow_html=True)

    with st.expander(f"View Full Candidate Details — {candidate_name}", expanded=False):
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
                    st.markdown(f'<div class="detail-label">{escape_html_text(label)}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="detail-value">{escape_html_text(value)}</div>', unsafe_allow_html=True)

        with info_col2:
            for label, value in [
                ("Job Title", row.get("job_title")),
                ("Years of Experience", row.get("years_of_experience")),
                ("Relevant Years of Experience", row.get("relevant_years_experience")),
                ("Skills", row.get("skills")),
                ("Languages", row.get("languages")),
                ("Certifications", row.get("certifications")),
                ("LinkedIn", row.get("linkedin")),
                ("GitHub", row.get("github")),
                ("File Name", row.get("file_name")),
                ("Analysis Mode", row.get("analysis_mode")),
            ]:
                if safe_str(value):
                    st.markdown(f'<div class="detail-label">{escape_html_text(label)}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="detail-value">{escape_html_text(value)}</div>', unsafe_allow_html=True)

            breakdown_value = format_experience_breakdown(row.get("experience_breakdown"))
            if breakdown_value:
                st.markdown(f'<div class="detail-label">Experience Breakdown</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="detail-value">{escape_html_text(breakdown_value)}</div>', unsafe_allow_html=True)


def clear_ai_state():
    st.session_state["candidate_ai_question"] = ""
    st.session_state["candidate_ai_answer"] = ""
    st.session_state["candidate_ai_matches"] = []


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
    --success: #1f9d6c;
    --success-soft: #eaf8f1;
    --warning: #d09115;
    --warning-soft: #fff7e8;
    --danger: #d85757;
    --danger-soft: #fff0f0;
    --shadow: 0 10px 30px rgba(15, 111, 131, 0.08);
    --shadow-soft: 0 6px 18px rgba(15, 111, 131, 0.06);
    --radius-xl: 24px;
    --radius-lg: 18px;
    --radius-md: 14px;
    --radius-sm: 12px;
}

[data-testid="stSidebarNav"] {
    display: none !important;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

html, body, [class*="css"] {
    font-family: "Segoe UI", Arial, sans-serif;
}

.stApp {
    background: radial-gradient(circle at top left, #fafdff 0%, #f5f9fb 30%, #eff5f7 100%);
    color: var(--text);
}

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
    padding-top: 1.25rem;
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

.main-hero {
    background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(244,251,252,0.96) 100%);
    border: 1px solid var(--border);
    border-radius: 26px;
    padding: 1.65rem 1.65rem 1.4rem 1.65rem;
    box-shadow: var(--shadow);
    margin-bottom: 1.1rem;
}

.eyebrow {
    color: var(--primary);
    font-size: 0.86rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
}

.main-title {
    font-size: 3rem;
    font-weight: 800;
    color: var(--primary-dark);
    line-height: 1.02;
    margin-bottom: 0.25rem;
}

.sub-title {
    color: var(--text-soft);
    font-size: 1.08rem;
    font-weight: 500;
    line-height: 1.5;
    max-width: 900px;
    margin-bottom: 0.95rem;
}

.hero-stats {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-top: 0.5rem;
}

.hero-chip {
    background: #ffffff;
    border: 1px solid var(--border);
    color: var(--primary-dark);
    border-radius: 999px;
    padding: 9px 14px;
    font-size: 0.92rem;
    font-weight: 700;
}

.section-heading {
    font-size: 2rem;
    font-weight: 800;
    color: var(--primary-dark);
    margin-top: 1rem;
    margin-bottom: 0.35rem !important;
}

.small-muted {
    color: var(--text-soft);
    font-size: 0.98rem;
    font-weight: 500;
    line-height: 1.55;
    margin-bottom: 0.35rem !important;
}

.panel-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(249,252,253,0.96) 100%);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 1.15rem;
    box-shadow: var(--shadow-soft);
    margin-bottom: 1rem;
}

.panel-heading {
    color: var(--primary-dark);
    font-size: 1.18rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}

.panel-sub {
    color: var(--text-soft);
    font-size: 0.95rem;
    line-height: 1.5;
    margin-bottom: 0.9rem;
}

label, .stWidgetLabel p {
    color: var(--text) !important;
    font-weight: 700 !important;
}

.stTextInput,
.stSelectbox,
.stTextArea {
    display: flex !important;
    flex-direction: column !important;
    justify-content: flex-start !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}

.stTextInput > label,
.stSelectbox > label,
.stTextArea > label {
    margin-bottom: 6px !important;
    min-height: 30px !important;
    display: flex !important;
    align-items: flex-end !important;
}

.stTextInput > div,
.stSelectbox > div,
.stTextArea > div {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

div[data-baseweb="input"] {
    background-color: #ffffff !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    min-height: 56px !important;
    height: 56px !important;
    display: flex !important;
    align-items: center !important;
    box-sizing: border-box !important;
    box-shadow: none !important;
}

.stTextInput > div > div {
    min-height: 56px !important;
    height: 56px !important;
}

.stTextInput div[data-baseweb="input"] {
    min-height: 56px !important;
    height: 56px !important;
    display: flex !important;
    align-items: center !important;
    border-radius: 16px !important;
    box-sizing: border-box !important;
}

.stTextInput input {
    min-height: 56px !important;
    height: 56px !important;
    line-height: 56px !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    padding-left: 14px !important;
    padding-right: 14px !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    background: #ffffff !important;
    color: #183c45 !important;
    border: none !important;
    border-radius: 16px !important;
    box-sizing: border-box !important;
}

.stTextInput input::placeholder {
    color: #7f9aa3 !important;
    opacity: 1 !important;
}

.stTextInput input:focus {
    border: 1px solid var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(15,111,131,0.12) !important;
}

.stTextArea {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding: 0 !important;
}

.stTextArea > div {
    margin-top: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.stTextArea > div > div {
    margin-top: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.stTextArea textarea {
    background: #ffffff !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    color: var(--text) !important;
    box-shadow: none !important;
    margin-top: 0 !important;
    min-height: 120px !important;
    padding: 14px !important;
}

.stTextArea textarea::placeholder {
    color: #7f9aa3 !important;
    opacity: 1 !important;
}

.stTextArea textarea:focus,
textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(15,111,131,0.12) !important;
}

.stTextArea label {
    margin-bottom: 8px !important;
}

.stSelectbox {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}

.stSelectbox > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.stSelectbox div[data-baseweb="select"] {
    min-height: 56px !important;
    height: 56px !important;
    background: #ffffff !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
    padding-left: 8px !important;
    padding-right: 8px !important;
    box-sizing: border-box !important;
}

.stSelectbox div[data-baseweb="select"] > div {
    background: transparent !important;
    color: var(--text) !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    display: flex !important;
    align-items: center !important;
    min-height: 100% !important;
}

.stSelectbox div[data-baseweb="select"] span {
    color: var(--text) !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
}

.stSelectbox svg {
    fill: var(--primary-dark) !important;
}

.stSelectbox [data-baseweb="select"] {
    box-shadow: none !important;
}

.stSelectbox [data-baseweb="select"]:hover {
    border-color: var(--primary) !important;
    background: #ffffff !important;
}

.stSelectbox div[data-baseweb="select"]:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(15,111,131,0.12) !important;
}

.stDownloadButton > button {
    width: 100%;
    background: linear-gradient(180deg, #ffffff 0%, #f8fbfc 100%) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 14px !important;
    font-weight: 800 !important;
    color: var(--primary-dark) !important;
    min-height: 46px;
}

.ai-shell {
    background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(246,251,252,0.98) 100%);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 1rem 1.2rem 1.2rem 1.2rem !important;
    box-shadow: var(--shadow);
    margin-top: 0.2rem !important;
}

.ai-answer-box {
    background: linear-gradient(180deg, #f7fcfd 0%, #eef8fa 100%);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 1rem 1rem;
    color: var(--text);
    line-height: 1.7;
    margin-top: 1rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
}

.ai-mini-note {
    background: #ffffff;
    border: 1px dashed var(--border-strong);
    border-radius: 16px;
    padding: 0.9rem 1rem;
    color: var(--text-soft);
    font-size: 0.93rem;
    line-height: 1.6;
    margin-top: 0.75rem !important;
}

.candidate-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(249,252,253,0.98) 100%);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 1.2rem;
    box-shadow: var(--shadow-soft);
    margin-bottom: 0.55rem;
}

.candidate-top {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 0.9rem;
}

.avatar-circle {
    width: 58px;
    height: 58px;
    min-width: 58px;
    border-radius: 50%;
    background: linear-gradient(135deg, #0f6f83 0%, #6fa8b5 100%);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1rem;
    box-shadow: 0 8px 20px rgba(15,111,131,0.18);
}

.candidate-main {
    width: 100%;
}

.candidate-name {
    color: var(--primary-dark);
    font-size: 1.45rem;
    font-weight: 800;
    line-height: 1.15;
    margin-bottom: 0.18rem;
}

.candidate-role {
    color: var(--text);
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
}

.candidate-meta {
    color: var(--text-soft);
    font-size: 0.93rem;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    line-height: 1.45;
}

.meta-dot {
    color: var(--muted);
}

.candidate-summary {
    background: var(--primary-soft-2);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 0.95rem 1rem;
    color: var(--text);
    line-height: 1.65;
    margin-bottom: 0.95rem;
    word-break: break-word;
    white-space: normal;
}

.tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 0.7rem;
}

.tag-chip {
    background: #edf5f7;
    color: var(--primary-dark);
    border: 1px solid #d8e7eb;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 0.82rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
}

.tag-chip.green {
    background: var(--success-soft);
    border-color: #ccebdc;
    color: #166f4e;
}

.tag-chip.gold {
    background: var(--warning-soft);
    border-color: #f0dfb1;
    color: #996500;
}

.detail-inline {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 0.35rem;
    margin-bottom: 0.2rem;
}

.inline-label {
    color: var(--text-soft);
    font-weight: 800;
    font-size: 0.84rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-right: 4px;
}

.candidate-footer {
    color: var(--text-soft);
    font-size: 0.92rem;
    margin-top: 0.7rem;
}

.side-score-card {
    border-radius: 20px;
    padding: 1.05rem 0.85rem;
    text-align: center;
    border: 1px solid var(--border);
    box-shadow: var(--shadow-soft);
    margin-bottom: 0.6rem;
    min-height: 132px;
}

.side-score-card.excellent {
    background: linear-gradient(180deg, #effaf4 0%, #e4f7ed 100%);
    border-color: #cfeadb;
}

.side-score-card.good {
    background: linear-gradient(180deg, #f4fbfd 0%, #ecf7fa 100%);
    border-color: #d6eaef;
}

.side-score-card.average {
    background: linear-gradient(180deg, #fffaf0 0%, #fff5e0 100%);
    border-color: #f2dfb4;
}

.side-score-card.low {
    background: linear-gradient(180deg, #fff5f5 0%, #ffeded 100%);
    border-color: #f0caca;
}

.side-score-card.neutral {
    background: linear-gradient(180deg, #fafcfd 0%, #f4f8f9 100%);
    border-color: var(--border);
}

.side-score-label {
    color: var(--text-soft);
    font-size: 0.85rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.55rem;
}

.side-score-value {
    color: var(--primary-dark);
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 0.35rem;
}

.side-score-sub {
    color: var(--muted);
    font-size: 0.88rem;
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
    font-size: 0.98rem;
    margin-bottom: 12px;
    word-break: break-word;
    line-height: 1.55;
    white-space: pre-wrap;
}

[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    background: rgba(255,255,255,0.95) !important;
    overflow: hidden;
    box-shadow: var(--shadow-soft);
    margin-top: 0.5rem;
}

[data-testid="stExpander"] summary {
    background: #f9fcfd !important;
    color: var(--primary-dark) !important;
    font-weight: 800;
    border-bottom: 1px solid var(--border);
}

[data-testid="stAlert"] {
    border-radius: 16px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow-soft);
}

.soft-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, #d9e8ed 20%, #d9e8ed 80%, transparent 100%);
    margin: 1rem 0 1.2rem 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<script>
window.addEventListener("load", function() {
    if (window.lucide) {
        lucide.createIcons();
    }
});
</script>
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
            <div style="text-align:center; margin-bottom:18px; padding-top:6px;">
                <img src="data:image/png;base64,{bin_str}" width="280" style="max-width:100%; height:auto;">
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        """
        <div class="sidebar-panel">
            <div class="sidebar-section-title">Recruitment Control</div>
            <div class="sidebar-helper">
                Search, review, and analyze existing CV records already stored in the database.
                Use the AI assistant to compare candidates without re-parsing resumes.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================================================
# TOP RIGHT NAVIGATION
# =========================================================
nav_spacer, nav_right = st.columns([6, 4])

with nav_right:
    inner_left, inner_right = st.columns(2)
    with inner_left:
        if st.button("Home", use_container_width=True):
            st.switch_page("home.py")
    with inner_right:
        st.markdown('<div class="top-nav-active">Candidate Database</div>', unsafe_allow_html=True)

# =========================================================
# HERO HEADER
# =========================================================
st.markdown(
    """
    <div class="main-hero">
        <div class="eyebrow">IT Solutions Worldwide</div>
        <div class="main-title">Candidate Database</div>
        <div class="sub-title">
            Review, filter, and analyze all candidate profiles stored in the system.
            This view is optimized for fast recruiter decision-making, database-driven search,
            and AI-assisted comparison using existing records only.
        </div>
        <div class="hero-stats">
            <span class="hero-chip">Database Search</span>
            <span class="hero-chip">AI Candidate Q&amp;A</span>
            <span class="hero-chip">CSV Export</span>
            <span class="hero-chip">Recruiter-Friendly Review</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================================================
# FILTER PANEL
# =========================================================
st.markdown(
    """
    <div class="panel-card">
        <div class="panel-heading">Filter & Search Candidates</div>
        <div class="panel-sub">
            Search by candidate name, skills, or job title. Use the minimum match score to narrow results.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

filter_col1, filter_col2 = st.columns([2.2, 1])

with filter_col1:
    search_input = st.text_input(
        "Search Name, Skills, or Job Title",
        placeholder="e.g. Python, React, Data Analyst, Project Manager"
    )

with filter_col2:
    score_options = list(range(0, 110, 10))
    score_input_raw = st.selectbox(
        "Minimum Match Score %",
        options=score_options,
        index=0
    )
    score_input = safe_int(score_input_raw, 0)

# =========================================================
# LOAD DATA
# =========================================================
db_error = None
try:
    df = load_resumes(search_query=search_input, min_score=score_input)
except Exception as e:
    df = pd.DataFrame()
    db_error = str(e)

# =========================================================
# DOWNLOAD + STATUS
# =========================================================
action_left, action_mid, action_right = st.columns([5, 3, 2])

with action_left:
    if db_error:
        st.error("Database connection is temporarily unavailable. Candidate records could not be loaded.")
    elif df.empty:
        st.info("No candidates match the current filters.")
    else:
        st.success(f"{len(df)} candidate record(s) loaded successfully.")

with action_right:
    if not df.empty:
        export_df = prepare_export_dataframe(df)
        csv = export_df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            label="Download CSV Report",
            data=csv,
            file_name=f"candidate_report_score{score_input}.csv",
            mime="text/csv",
            use_container_width=True
        )

# =========================================================
# AI ASSISTANT
# =========================================================
st.markdown('<div class="section-heading" style="margin-bottom:0.35rem;">AI Candidate Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-muted" style="margin-bottom:0.35rem;">Ask targeted questions about the currently loaded candidate records. The assistant only uses stored database data and does not re-parse CV files.</div>',
    unsafe_allow_html=True
)

st.markdown('<div class="ai-shell">', unsafe_allow_html=True)

ai_left, ai_right = st.columns([5, 1.15])

with ai_left:
    st.text_area(
        "Ask AI about candidates",
        key="candidate_ai_question",
        height=130,
        placeholder="Examples: Give me the top 3 Python candidates. Who is strongest for a data analyst role? Summarize shortlisted candidates by strengths."
    )

with ai_right:
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
    ai_run = st.button("Ask AI", use_container_width=True)
    st.button("Clear", use_container_width=True, on_click=clear_ai_state)

st.markdown(
    """
    <div class="ai-mini-note">
        Suggested use: compare candidates, identify strongest fits by skill area, summarize shortlisted profiles,
        or rank candidates based only on existing stored data.
    </div>
    """,
    unsafe_allow_html=True
)

if ai_run:
    if not OPENAI_API_KEY.strip():
        st.error("OpenAI API key is missing.")
    elif df.empty:
        st.warning("There are no candidate records available for AI analysis.")
    elif not st.session_state.candidate_ai_question.strip():
        st.warning("Please enter a question for the AI assistant.")
    else:
        try:
            with st.spinner("Analyzing stored candidate data..."):
                ai_result = ask_ai_about_candidates(
                    st.session_state.candidate_ai_question.strip(),
                    df
                )
                st.session_state.candidate_ai_answer = ai_result.get("answer", "")
                st.session_state.candidate_ai_matches = ai_result.get("recommended_candidates", [])
        except Exception as e:
            st.error(f"AI error: {e}")

if st.session_state.candidate_ai_answer:
    st.markdown(
        f'<div class="ai-answer-box">{format_ai_answer(st.session_state.candidate_ai_answer)}</div>',
        unsafe_allow_html=True
    )

    ai_matched_df = find_matching_candidates(df, st.session_state.candidate_ai_matches)

    if not ai_matched_df.empty:
        st.markdown(
            '<div class="section-heading" style="font-size:1.45rem; margin-top:1rem;">AI Recommended Candidates</div>',
            unsafe_allow_html=True
        )
        for _, row in ai_matched_df.iterrows():
            render_candidate_card(row)

st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# RESULTS
# =========================================================
st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
st.markdown(f'<div class="section-heading">Candidate Results ({len(df)})</div>', unsafe_allow_html=True)

if df.empty:
    if db_error:
        st.info("No candidates are displayed because the database is not available right now.")
    else:
        st.info("No candidates were found for the current search and score filters.")
else:
    for _, row in df.iterrows():
        render_candidate_card(row)