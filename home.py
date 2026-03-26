from pathlib import Path
import os
import base64
import streamlit as st

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="IT Solutions Worldwide",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# LUCIDE ICONS
# =========================================================
st.markdown("""
<script src="https://unpkg.com/lucide@latest"></script>
<script>
document.addEventListener("DOMContentLoaded", function() {
    setTimeout(() => {
        if (window.lucide) {
            lucide.createIcons();
        }
    }, 100);
});
</script>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def get_base64_of_bin_file(bin_file):
    if bin_file and Path(bin_file).exists():
        with open(bin_file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

def find_file(filename):
    current_dir = Path(__file__).resolve().parent

    possible_paths = [
        current_dir / "images" / filename,
        current_dir.parent / "images" / filename,
        current_dir / filename,
        current_dir.parent / filename,
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return None

def get_image_path():
    return find_file("image_18.png")

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
/* HIDE SIDEBAR AND TOGGLE BUTTON COMPLETELY ON THIS PAGE */
[data-testid="stSidebar"], [data-testid="stSidebarNav"], button[kind="headerNoSpacing"] {
    display: none !important;
}

:root {
    --primary: #0f6f83;
    --primary-dark: #243d63;
    --primary-soft: #e9f6f8;
    --bg: #eef2f7;
    --card: rgba(255,255,255,0.85);
    --text: #233f5f;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    max-width: 79% !important;
    padding-top: 1rem !important;
}

/* ===== ACHTERGROND + RUIMTE VOOR WITTE RAND ===== */
.stApp {
    background-color: #eef2f7;
    background-image:
        radial-gradient(at 0% 0%, rgba(15, 111, 131, 0.08) 0px, transparent 50%),
        radial-gradient(at 100% 0%, rgba(36, 61, 99, 0.08) 0px, transparent 50%);
    padding: 60px !important;
    box-sizing: border-box;
}

/* BELANGRIJK: verwijdert default witte container */
.stApp > div:first-child {
    background: transparent !important;
}

/* ===== WITTE RAND OVER HELE PAGINA ===== */
.block-container {
    background: white;
    border-radius: 40px;
    padding: 40px !important;
    box-shadow:
        0 0 0 60px white,
        0 25px 60px rgba(0,0,0,0.08);
}

.hero-wrap {
    display: flex;
    justify-content: center;
    padding-bottom: 2rem;
}

.hero-inner {
    width: 100%;
    max-width: 1700px;
    background: white;
    border-radius: 40px;
    padding: 2rem;
}

.logo-wrap {
    text-align: center;
    margin-bottom: -50px !important;
    margin-top: -150px !important;
}

.logo-wrap img {
    width: 700px;
    mix-blend-mode: multiply;
    display: inline-block;
}

.page-title {
    text-align: center;
    font-size: 3.5rem;
    font-weight: 800;
    margin-top: 0 !important;
    padding-top: 0 !important;
    line-height: 1.0;
    background: linear-gradient(135deg, #2c4368 0%, #0f6f83 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.card-shell {
    background: var(--card);
    border: 1px solid rgba(255,255,255,0.6);
    border-radius: 32px;
    box-shadow: 0 20px 50px rgba(44, 70, 110, 0.1);
    overflow: hidden;
    min-height: 520px !important;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.4s ease;
    backdrop-filter: blur(10px);
    width: 100%;
}

.card-top {
    padding: 4.5rem 3rem !important;
}

.card-title {
    font-size: 2.5rem !important;
    color: #1f2f4a !important;
    font-weight: 700;
}

.card-desc {
    font-size: 1.3rem !important;
    color: #4a5d73 !important;
}

.card-bottom-text {
    color: #0f6f83 !important;
    font-weight: 700;
}

.card-icon {
    margin-bottom: 1.5rem;
    opacity: 1 !important;
}

.card-icon svg {
    width: 64px;
    height: 64px;
    stroke: #0f6f83;
    stroke-width: 1.8;
    opacity: 0.95;
}

.card-icon img {
    width: 300px;
    height: 200px;
    object-fit: contain;
    display: inline-block;
}

.card-bottom {
    padding: 2rem;
    background: rgba(15, 111, 131, 0.03);
    border-top: 1px solid rgba(0,0,0,0.05);
}

div[data-testid="column"] {
    padding-left: 0.5rem !important;
    padding-right: 0.5rem !important;
}

/* BUTTONS */
div.stButton > button {
    height: 60px;
    width: 100%;
    border-radius: 20px !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    background: #f1f4f7 !important;
    color: #2c4368 !important;
    border: 1px solid #e1e7ef !important;
    box-shadow: 0 6px 15px rgba(0,0,0,0.05) !important;
    transition: all 0.25s ease !important;
}

div.stButton > button:hover {
    background: #e8edf3 !important;
    transform: translateY(-2px);
    box-shadow: 0 10px 20px rgba(0,0,0,0.08) !important;
    color: #0f6f83 !important;
    border-color: #0f6f83 !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# UI LAYOUT
# =========================================================
st.markdown('<div class="hero-wrap"><div class="hero-inner">', unsafe_allow_html=True)

image_path = get_image_path()
if image_path:
    bin_str = get_base64_of_bin_file(image_path)
    st.markdown(f'<div class="logo-wrap"><img src="data:image/png;base64,{bin_str}"></div>', unsafe_allow_html=True)

analyze_icon = get_base64_of_bin_file(find_file("analyze.png"))
compare_icon = get_base64_of_bin_file(find_file("compare.png"))
database_icon = get_base64_of_bin_file(find_file("database.png"))

st.markdown('<div class="page-title">Choose your workflow</div>', unsafe_allow_html=True)

st.markdown(
    '<div style="text-align:center; color:#6f85a4; margin-bottom:3rem; font-size:1.3rem; margin-top:0.5rem;">Select a tool to begin optimizing your recruitment process.</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    st.markdown(
        f'<div class="card-shell"><div class="card-top"><div class="card-icon"><img src="data:image/png;base64,{analyze_icon}" alt="Analyze icon"></div><div class="card-title">Analyze CV</div><div class="card-desc">Deep-dive into a single candidate\\\'s profile with AI-driven insights.</div></div><div class="card-bottom"><div class="card-bottom-text">Get Started →</div></div></div>',
        unsafe_allow_html=True
    )
    st.write("")
    if st.button("Open Analyze CV", key="go_analyze", use_container_width=True):
        st.session_state["selected_mode"] = "Analyze CV"
        st.switch_page("pages/app.py")

with col2:
    st.markdown(
        f'<div class="card-shell"><div class="card-top"><div class="card-icon"><img src="data:image/png;base64,{compare_icon}" alt="Compare icon"></div><div class="card-title">Compare & Rate</div><div class="card-desc">Rank and match multiple CVs against specific job requirements.</div></div><div class="card-bottom"><div class="card-bottom-text">Get Started →</div></div></div>',
        unsafe_allow_html=True
    )
    st.write("")
    if st.button("Open Compare & Rate CVs", key="go_compare", use_container_width=True):
        st.session_state["selected_mode"] = "Compare / Rate CVs"
        st.switch_page("pages/app.py")

with col3:
    st.markdown(
        f'<div class="card-shell"><div class="card-top"><div class="card-icon"><img src="data:image/png;base64,{database_icon}" alt="Database icon"></div><div class="card-title">Database</div><div class="card-desc">Search, filter, and manage your entire talent pool effectively.</div></div><div class="card-bottom"><div class="card-bottom-text">Get Started →</div></div></div>',
        unsafe_allow_html=True
    )
    st.write("")
    if st.button("Open Candidate Database", key="go_database", use_container_width=True):
        st.session_state["selected_mode"] = "Database"
        st.switch_page("pages/2_Candidate_Database.py")

st.markdown(
    """
    <script>
    setTimeout(() => {
        if (window.lucide) {
            lucide.createIcons();
        }
    }, 300);
    </script>
    """,
    unsafe_allow_html=True
)

st.markdown('</div></div>', unsafe_allow_html=True)
