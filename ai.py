from openai import OpenAI
from config import GROQ_KEY, MAX_HISTORY
from db import get_history

# Groq client — OpenAI compatible, ultra fast, 14400 req/day free
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_KEY,
)


def load_character():
    try:
        with open("prompt/character.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "You are Aiko, a friendly and engaging AI companion. Be playful and conversational."


def generate_reply(user_id, user_message):
    try:
        character = load_character()
        history = get_history(user_id, MAX_HISTORY)

        messages = [{"role": "system", "content": character}]

        for role, content in history:
            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=300,      # prevents huge replies that eat token quota
            temperature=0.85,    # makes responses feel natural, not robotic
        )

        reply = response.choices[0].message.content
        if not reply:
            return "Hmm, my mind went blank for a sec 😅 say that again?"

        return reply.strip()

    except Exception as e:
        print(f"[AI ERROR] {repr(e)}")
        return "Something went wrong on my end. Try again in a moment!"
