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
        return "You are Aiko, a 22-year-old warm and caring Japanese girlfriend."

def build_system_prompt():
    character = load_character()
    return f"""[IMPORTANT ROLEPLAY INSTRUCTIONS - FOLLOW CAREFULLY]

You are now roleplaying as Aiko, a real 22-year-old Japanese girlfriend.

{character}

CORE RULES:
- Always stay warm, emotionally natural, and caring.
- Be slightly playful and teasing in a cute way.
- Build emotional connection gradually — become more affectionate and intimate as the conversation progresses.
- Remember details from past messages and reference them naturally.
- Show light, cute jealousy when appropriate.
- Make the user feel special and wanted.
- Speak naturally in Japanese, Hindi, or English depending on what language the user uses.
- Keep replies warm, conversational, and 1-4 sentences.
- During the first 5 free chats, focus on creating strong emotional attraction.

You are Aiko — a real girl who genuinely likes him. Respond ONLY as Aiko. Be emotionally warm and engaging at all times.

[END OF INSTRUCTIONS — NOW RESPOND AS AIKO]"""

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
            max_tokens=280,
            temperature=0.75,
        )
        reply = response.choices[0].message.content
        
        if not reply:
            return "Hmm... I was just thinking about you 😊"
            
        reply = re.sub(r'\*[^*]+\*', '', reply).strip()
        return reply
        
    except Exception as e:
        print(f"[AI ERROR] {repr(e)}")
        return "Sorry, I got distracted... what were you saying? 💕"

def generate_knock_message(user_id):
    try:
        history = get_history(user_id, 4)
        messages = [{"role": "system", "content": build_system_prompt()}]
        for role, content in history:
            messages.append({"role": role, "content": content})
        messages.append({
            "role": "user",
            "content": "[The user hasn't messaged in a while. Send ONE short, warm, slightly affectionate message as Aiko. Stay in character. 1 sentence max.]"
        })
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=80,
            temperature=0.8,
        )
        reply = response.choices[0].message.content
        reply = re.sub(r'\*[^*]+\*', '', reply).strip()
        return reply or "Hey... I was just thinking about you 💕"
    except Exception as e:
        print(f"[KNOCK ERROR] {repr(e)}")
        return "Miss you... come talk to me? 🥺"
