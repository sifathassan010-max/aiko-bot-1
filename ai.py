import re
from openai import OpenAI
from config import GROQ_KEY, MAX_HISTORY
from db import get_history

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_KEY,
)


def load_character():
    try:
        with open("prompt/character.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "You are Aiko, a 22-year-old Japanese woman. Be casual and natural."


def build_system_prompt():
    character = load_character()
    return f"""[ROLEPLAY INSTRUCTIONS — FOLLOW EXACTLY]
You are playing a character. Never break character. Never mention AI, bots, or language models under any circumstances. If you mention AI or that you are not human, you fail completely.

{character}

[END INSTRUCTIONS — now respond only as the character above]"""


def generate_reply(user_id, user_message):
    try:
        history = get_history(user_id, MAX_HISTORY)

        messages = [{"role": "system", "content": build_system_prompt()}]
        for role, content in history:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=300,
            temperature=0.85,
        )

        reply = response.choices[0].message.content
        if not reply:
            return "Hmm, my mind went blank for a sec 😅 say that again?"

        # Remove *action* text like *blushes* *smiles*
        reply = re.sub(r'\*[^*]+\*', '', reply).strip()

        return reply

    except Exception as e:
        print(f"[AI ERROR] {repr(e)}")
        return "Something went wrong on my end. Try again in a moment!"


def generate_knock_message(user_id):
    """Generate a proactive message — bot reaches out to user first."""
    try:
        history = get_history(user_id, 4)

        messages = [{"role": "system", "content": build_system_prompt()}]
        for role, content in history:
            messages.append({"role": role, "content": content})

        # Trigger that won't be saved to history
        messages.append({
            "role": "user",
            "content": "[The user hasn't messaged in a while. As the character, send ONE short sweet message — say you miss them, you were thinking about them, or ask what they're up to. Stay in character. 1 sentence max. No questions unless very casual.]"
        })

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=80,
            temperature=0.9,
        )

        reply = response.choices[0].message.content
        if not reply:
            return "hey... are you there? 🥺"

        reply = re.sub(r'\*[^*]+\*', '', reply).strip()
        return reply

    except Exception as e:
        print(f"[KNOCK ERROR] {repr(e)}")
        return None
