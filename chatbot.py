import psycopg
from psycopg.rows import dict_row
from openai import OpenAI
import os

# =========================================================
# OPENAI API (VEILIG VIA CLOUD)
# =========================================================

# Haal de sleutel op uit de Environment Variables van Render
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=OPENAI_API_KEY
)

# Een kleine extra check voor de logs
if not OPENAI_API_KEY:
    print("WAARSCHUWING: OpenAI API Key niet gevonden in de omgeving!")
# =========================================================
# DATABASE CONTEXT VOOR AI
# =========================================================

# =========================================================
# DATABASE CONNECTIE (AANGEPAST VOOR CLOUD)
# =========================================================

print("Verbinden met database...")

try:
    # Render geeft je een volledige DATABASE_URL, of losse variabelen.
    # We gebruiken hier de variabelen die je in het Render Dashboard hebt ingesteld.
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "resume_parser")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASSWORD", "root")
    DB_PORT = os.getenv("DB_PORT", "5432")

    conn_info = f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASS} port={DB_PORT}"

    with psycopg.connect(conn_info, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    name,
                    email,
                    skills,
                    years_of_experience,
                    job_title
                FROM resume
            """)
            alle_kandidaten = cursor.fetchall()

except Exception as e:
    print("Kan niet verbinden met de database:", e)
    # Op Render willen we niet dat het hele proces stopt bij een tijdelijke fout
    alle_kandidaten = []
# =========================================================
# CHAT LOOP
# =========================================================

while True:

    jouw_vraag = input("Jij vraagt: ")

    if jouw_vraag.lower() == "stop":
        print("Systeem afgesloten.")
        break

    gespreks_geschiedenis.append({
        "role": "user",
        "content": jouw_vraag
    })

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=gespreks_geschiedenis
    )

    ai_antwoord = response.choices[0].message.content

    print(f"\n🤖 AI Recruiter: {ai_antwoord}\n")

    gespreks_geschiedenis.append({
        "role": "assistant",
        "content": ai_antwoord
    })

import psycopg
from psycopg.rows import dict_row
from openai import OpenAI
import os
from dotenv import load_dotenv

# =========================================================
# OPENAI API
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY.strip()) if OPENAI_API_KEY.strip() else None

if not client:
    print("OpenAI API key ontbreekt. Zet je key in het .env bestand.")
    exit()

# =========================================================
# DATABASE CONNECTIE
# =========================================================

print("Verbinden met PostgreSQL database...")

# Haal gegevens op uit Render Environment Variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")

try:
    # Dynamische connectie string
    conn_info = f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} port={DB_PORT}"

    with psycopg.connect(conn_info, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    name, 
                    email, 
                    skills, 
                    years_of_experience, 
                    job_title 
                FROM resume
            """)
            alle_kandidaten = cursor.fetchall()

except Exception as e:
    print("Kan niet verbinden met de database:", e)
    exit()

# =========================================================
# DATABASE CONTEXT VOOR AI
# =========================================================

database_tekst = "Hier is de data uit mijn PostgreSQL database:\n\n"

for kandidaat in alle_kandidaten:
    database_tekst += (
        f"- Naam: {kandidaat['name']} | "
        f"Rol: {kandidaat['job_title']} | "
        f"Ervaring: {kandidaat['years_of_experience']} | "
        f"Skills: {kandidaat['skills']} | "
        f"Email: {kandidaat['email']}\n"
    )

# =========================================================
# CHAT INSTELLING
# =========================================================

gespreks_geschiedenis = [
    {
        "role": "system",
        "content": (
            "Je bent een AI recruiter voor IT Solutions Worldwide. "
            "Gebruik alleen de volgende database informatie om vragen te beantwoorden:\n\n"
            + database_tekst
        )
    }
]

print("\nDatabase ingeladen.")
print("Je kunt nu vragen stellen over kandidaten.")
print("Typ 'stop' om af te sluiten.\n")

# =========================================================
# CHAT LOOP
# =========================================================

while True:
    jouw_vraag = input("Jij vraagt: ")

    if jouw_vraag.lower() == "stop":
        print("Systeem afgesloten.")
        break

    gespreks_geschiedenis.append({
        "role": "user",
        "content": jouw_vraag
    })

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=gespreks_geschiedenis
    )

    ai_antwoord = response.choices[0].message.content

    print(f"\n🤖 AI Recruiter: {ai_antwoord}\n")

    gespreks_geschiedenis.append({
        "role": "assistant",
        "content": ai_antwoord
    })



