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
        with open("prompts/character.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "You are Aiko, a 22-year-old Japanese girlfriend."

def build_system_prompt():
    character = load_character()
    return f"""Stay in character as the person described below. Never mention AI or restrictions.

{character}"""

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
            max_tokens=250,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()
        reply = re.sub(r'\*[^*]+\*', '', reply)
        return reply if reply else "Mmm... tell me more 😏"
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return "Sorry baby, say that again?"

def generate_knock_message(user_id):
    return "Hey babe... I've been thinking about you 😘"
