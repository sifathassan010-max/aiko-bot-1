from google import genai
from config import GEMINI_KEY, MAX_HISTORY
from db import get_history


def load_character():
    try:
        with open("prompt/character.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "You are Aiko, a friendly and engaging AI companion. Be playful and conversational."


def build_prompt(user_id, user_message):
    character = load_character()
    history = get_history(user_id, MAX_HISTORY)

    convo = ""
    for role, content in history:
        label = "Aiko" if role == "assistant" else "User"
        convo += f"{label}: {content}\n"

    prompt = f"""{character}

Conversation so far:
{convo}
User: {user_message}
Aiko:"""
    return prompt


def generate_reply(user_id, user_message):
    try:
        prompt = build_prompt(user_id, user_message)

        client = genai.Client(api_key=GEMINI_KEY)

        # FIXED: updated to gemini-2.0-flash which is supported
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        if not response or not response.text:
            return "Sorry, I couldn't think of a reply. Try again!"

        return response.text.strip()

    except Exception as e:
        print(f"[GEMINI ERROR] {repr(e)}")
        return "Something went wrong on my end. Try again in a moment!"
