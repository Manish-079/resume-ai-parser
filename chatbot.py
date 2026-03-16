import psycopg
from psycopg.rows import dict_row
from openai import OpenAI
import os

# =========================================================
# OPENAI API
# =========================================================

client = OpenAI(
    api_key="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"
)

# =========================================================
# DATABASE CONNECTIE
# =========================================================

print("Verbinden met PostgreSQL database...")

try:

    conn_info = "host=localhost dbname=resume_parser user=postgres password=root port=5432"

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

if not alle_kandidaten:
    print("Database is leeg. Analyseer eerst CV's.")
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