<<<<<<< HEAD
import os
import re
import json
import PyPDF2
import psycopg  # PostgreSQL driver
from openai import OpenAI
from dotenv import load_dotenv

# 1. Laad .env variabelen & OpenAI
load_dotenv()

# =========================================================
# OPENAI API
# =========================================================

# 🔑 PLAK HIER JE OPENAI API KEY
OPENAI_API_KEY = "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"

client = OpenAI(
    api_key=OPENAI_API_KEY
)

folder_path = "resumes"
CURRENT_JD = "We are looking for a Python Developer with experience in SQL, REST APIs, and AWS. The candidate should have at least 3 years of experience."

skills_list = [
    "Python", "SQL", "Power BI", "Excel", "Machine Learning",
    "REST APIs", "Git", "AWS", "Azure"
]


# =========================================================
# 2. HELPERS (Voorkomt 'dict' errors)
# =========================================================

def safe_str(value):
    """Zet elk type data (dict, list, None) om naar een schone string voor SQL."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value).strip()


# =========================================================
# 3. DATABASE FUNCTIES
# =========================================================

def connect_database():
    try:
        conn_info = "dbname=resume_parser user=postgres password=root host=localhost port=5432"
        connection = psycopg.connect(conn_info)
        return connection
    except Exception as err:
        print(f"❌ Fout bij verbinden met PostgreSQL: {err}")
        exit(1)


def save_to_database(conn, data):
    query = """
    INSERT INTO resume (
        file_name, name, email, phone, skills, degree, university,
        graduation_year, date_of_birth, location, address,
        linkedin, github, languages, years_of_experience,
        job_title, certifications, match_score, fit_summary
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(query, data)
        conn.commit()


def is_file_in_database(conn, filename):
    query = "SELECT COUNT(*) FROM resume WHERE file_name = %s"
    with conn.cursor() as cursor:
        cursor.execute(query, (filename,))
        result = cursor.fetchone()
        return result[0] > 0


# =========================================================
# 4. EXTRACTIE FUNCTIES
# =========================================================

def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return text


def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return emails[0] if emails else "Not found"


def extract_phone(text):
    phones = re.findall(r"\+?\d[\d\s\-()]{7,}\d", text)
    return phones[0].strip() if phones else "Not found"


def extract_linkedin(text):
    match = re.search(r"https?://(?:www\.)?linkedin\.com/[^\s)]+", text, re.IGNORECASE)
    return match.group(0) if match else "Not found"


def extract_github(text):
    match = re.search(r"https?://(?:www\.)?github\.com/[^\s)]+", text, re.IGNORECASE)
    return match.group(0) if match else "Not found"


def extract_graduation_year(text):
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    return years[0] if years else "Not found"


def extract_skills(text, skills):
    found_skills = []
    text_lower = text.lower()
    for skill in skills:
        if skill.lower() in text_lower and skill not in found_skills:
            found_skills.append(skill)
    return ", ".join(found_skills) if found_skills else "Not found"


# =========================================================
# 5. AI FUNCTIES
# =========================================================

def match_candidate_to_job(resume_text, job_description):
    try:
        prompt = f"Compare Resume to JD. Return JSON: {{'match_percentage': int, 'fit_summary': 'string'}}\nJD: {job_description}\nResume: {resume_text}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "HR Expert"}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"match_percentage": 0, "fit_summary": "Failed"}


def ai_extract_resume_data(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract resume details in JSON."},
                {"role": "user", "content": f"Resume text:\n{text[:6000]}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {}


# =========================================================
# 6. MAIN
# =========================================================

def main():
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    conn = connect_database()

    for filename in pdf_files:
        if is_file_in_database(conn, filename):
            print(f"⏩ Overgeslagen: '{filename}'")
            continue

        print(f"📄 Verwerken: {filename}...")
        file_path = os.path.join(folder_path, filename)
        text = extract_text_from_pdf(file_path)

        if not text.strip(): continue

        ai_data = ai_extract_resume_data(text)
        match_results = match_candidate_to_job(text, CURRENT_JD)

        # Voorbereiden voor database (GEBRUIK SAFE_STR VOOR ALLE VELDEN)
        resume_row = (
            filename,
            safe_str(ai_data.get("name") or filename.rsplit(".", 1)[0]),
            safe_str(extract_email(text)),
            safe_str(extract_phone(text)),
            safe_str(extract_skills(text, skills_list)),
            safe_str(ai_data.get("degree", "Not found")),
            safe_str(ai_data.get("university", "Not found")),
            safe_str(extract_graduation_year(text)),
            safe_str(ai_data.get("date_of_birth", "Not found")),
            safe_str(ai_data.get("location", "Not found")),
            safe_str(ai_data.get("address", "Not found")),
            safe_str(extract_linkedin(text)),
            safe_str(extract_github(text)),
            safe_str(ai_data.get("languages", "Not found")),
            safe_str(ai_data.get("years_of_experience", "Not found")),
            safe_str(ai_data.get("job_title", "Not found")),
            safe_str(ai_data.get("certifications", "Not found")),
            int(match_results.get("match_percentage", 0)),
            safe_str(match_results.get("fit_summary", "No summary"))
        )

        try:
            save_to_database(conn, resume_row)
            print(f"✅ Success! {filename} opgeslagen.")
        except Exception as e:
            print(f"❌ DB Error bij {filename}: {e}")

    conn.close()


if __name__ == "__main__":
    main()
=======
import os
import re
import json
import PyPDF2
import psycopg  # PostgreSQL driver
from openai import OpenAI
from dotenv import load_dotenv

# 1. Laad .env variabelen & OpenAI
load_dotenv()

# =========================================================
# OPENAI API
# =========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY ontbreekt in je .env bestand.")
    exit(1)

client = OpenAI(
    api_key=OPENAI_API_KEY
)

folder_path = "resumes"
CURRENT_JD = "We are looking for a Python Developer with experience in SQL, REST APIs, and AWS. The candidate should have at least 3 years of experience."

skills_list = [
    "Python", "SQL", "Power BI", "Excel", "Machine Learning",
    "REST APIs", "Git", "AWS", "Azure"
]

# =========================================================
# 2. HELPERS (Voorkomt 'dict' errors)
# =========================================================

def safe_str(value):
    """Zet elk type data (dict, list, None) om naar een schone string voor SQL."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value).strip()


# =========================================================
# 3. DATABASE FUNCTIES
# =========================================================

def connect_database():
    try:
        # Haal gegevens op uit Render Environment Variables
        host = os.getenv("DB_HOST")
        dbname = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        port = os.getenv("DB_PORT", "5432")

        # Dynamische connectie string
        conn_info = f"host={host} dbname={dbname} user={user} password={password} port={port}"

        connection = psycopg.connect(conn_info)
        return connection
    except Exception as err:
        print(f"❌ Fout bij verbinden met PostgreSQL: {err}")
        exit(1)

def save_to_database(conn, data):
    query = """
    INSERT INTO resume (
        file_name, name, email, phone, skills, degree, university,
        graduation_year, date_of_birth, location, address,
        linkedin, github, languages, years_of_experience,
        job_title, certifications, match_score, fit_summary
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(query, data)
        conn.commit()


def is_file_in_database(conn, filename):
    query = "SELECT COUNT(*) FROM resume WHERE file_name = %s"
    with conn.cursor() as cursor:
        cursor.execute(query, (filename,))
        result = cursor.fetchone()
        return result[0] > 0


# =========================================================
# 4. EXTRACTIE FUNCTIES
# =========================================================

def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return text


def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return emails[0] if emails else "Not found"


def extract_phone(text):
    phones = re.findall(r"\+?\d[\d\s\-()]{7,}\d", text)
    return phones[0].strip() if phones else "Not found"


def extract_linkedin(text):
    match = re.search(r"https?://(?:www\.)?linkedin\.com/[^\s)]+", text, re.IGNORECASE)
    return match.group(0) if match else "Not found"


def extract_github(text):
    match = re.search(r"https?://(?:www\.)?github\.com/[^\s)]+", text, re.IGNORECASE)
    return match.group(0) if match else "Not found"


def extract_graduation_year(text):
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    return years[0] if years else "Not found"


def extract_skills(text, skills):
    found_skills = []
    text_lower = text.lower()
    for skill in skills:
        if skill.lower() in text_lower and skill not in found_skills:
            found_skills.append(skill)
    return ", ".join(found_skills) if found_skills else "Not found"


# =========================================================
# 5. AI FUNCTIES
# =========================================================

def match_candidate_to_job(resume_text, job_description):
    try:
        prompt = f"Compare Resume to JD. Return JSON: {{'match_percentage': int, 'fit_summary': 'string'}}\nJD: {job_description}\nResume: {resume_text}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "HR Expert"}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"match_percentage": 0, "fit_summary": "Failed"}


def ai_extract_resume_data(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract resume details in JSON."},
                {"role": "user", "content": f"Resume text:\n{text[:6000]}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {}


# =========================================================
# 6. MAIN
# =========================================================

def main():
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    conn = connect_database()

    for filename in pdf_files:
        if is_file_in_database(conn, filename):
            print(f"⏩ Overgeslagen: '{filename}'")
            continue

        print(f"📄 Verwerken: {filename}...")
        file_path = os.path.join(folder_path, filename)
        text = extract_text_from_pdf(file_path)

        if not text.strip(): continue

        ai_data = ai_extract_resume_data(text)
        match_results = match_candidate_to_job(text, CURRENT_JD)

        # Voorbereiden voor database (GEBRUIK SAFE_STR VOOR ALLE VELDEN)
        resume_row = (
            filename,
            safe_str(ai_data.get("name") or filename.rsplit(".", 1)[0]),
            safe_str(extract_email(text)),
            safe_str(extract_phone(text)),
            safe_str(extract_skills(text, skills_list)),
            safe_str(ai_data.get("degree", "Not found")),
            safe_str(ai_data.get("university", "Not found")),
            safe_str(extract_graduation_year(text)),
            safe_str(ai_data.get("date_of_birth", "Not found")),
            safe_str(ai_data.get("location", "Not found")),
            safe_str(ai_data.get("address", "Not found")),
            safe_str(extract_linkedin(text)),
            safe_str(extract_github(text)),
            safe_str(ai_data.get("languages", "Not found")),
            safe_str(ai_data.get("years_of_experience", "Not found")),
            safe_str(ai_data.get("job_title", "Not found")),
            safe_str(ai_data.get("certifications", "Not found")),
            int(match_results.get("match_percentage", 0)),
            safe_str(match_results.get("fit_summary", "No summary"))
        )

        try:
            save_to_database(conn, resume_row)
            print(f"✅ Success! {filename} opgeslagen.")
        except Exception as e:
            print(f"❌ DB Error bij {filename}: {e}")

    conn.close()


if __name__ == "__main__":
    main()

>>>>>>> 516125e (Update secrets voor cloud)
