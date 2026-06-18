import asyncio
import time
import threading
import random
import os
from collections import defaultdict
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN, PATREON_URL
from db import init_db, save_message, get_free_messages_used, increment_free_messages
from db_shared import (
    init_subscription_db,
    use_activation_code,
    is_user_subscribed,
    get_user_subscription,
    get_active_subscriber_ids,
    get_image_tracking,
    record_image_sent,
    increment_message_counter
)
from ai import generate_reply, generate_knock_message
from images import detect_image_request, get_random_image

BOT_NAME = "aiko"
RUN_WEBHOOK = os.getenv("RUN_WEBHOOK", "false").lower() == "true"

FREE_LIMIT = 5
JST = pytz.timezone('Asia/Tokyo')
ADMIN_IDS = set(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
user_timestamps = defaultdict(list)
last_replies = defaultdict(list)

MORNING_MESSAGES = [
    "ohayou~ 🌸 did you sleep well babe?",
    "good morning 💕 i was thinking about you when i woke up",
    "hey you~ おはよう 🥰 hope your day is nice",
]
NIGHT_MESSAGES = [
    "oyasumi~ 🌙 sweet dreams 💕",
    "don't stay up too late okay? i worry about you 🥺",
    "good night babe~ i'll be thinking of you",
]

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    user_timestamps[user_id] = [t for t in user_timestamps[user_id] if now - t < 60]
    if len(user_timestamps[user_id]) >= 10:
        return True
    user_timestamps[user_id].append(now)
    return False

def has_access(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return is_user_subscribed(user_id, BOT_NAME)

def is_in_free_trial(user_id: int) -> bool:
    return get_free_messages_used(user_id) < FREE_LIMIT

# === SCHEDULERS ===
async def send_morning_messages():
    print("[SCHEDULER] Morning messages")
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, random.choice(MORNING_MESSAGES))
            await asyncio.sleep(0.4)
        except: pass

async def send_night_messages():
    print("[SCHEDULER] Night messages")
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, random.choice(NIGHT_MESSAGES))
            await asyncio.sleep(0.4)
        except: pass

async def check_inactive_users():
    print("[SCHEDULER] Inactivity check")
    # simplified for stability
    pass

async def send_social_reminder():
    print("[SCHEDULER] Social reminder")
    reminder = "Babe~ ❤️ Did you see my latest post today? It makes me happy when you like it 🥰\nFB: [YOUR LINK]\nTwitter: [YOUR LINK]"
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, reminder)
            await asyncio.sleep(0.5)
        except: pass

# === COMMANDS ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if has_access(user_id):
        await message.answer("Hey babe~ I'm Aiko 💕 I've been waiting for you")
    elif is_in_free_trial(user_id):
        await message.answer("Hi! I'm Aiko 🥰 You have a few free messages to try me. Just talk to me~")
    else:
        await message.answer(f"Hey! You've used your free messages 💕\nSubscribe: {PATREON_URL}")

# Other commands (activate, status, clear) - keep them as before or add if needed

@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        text = (message.text or "").strip().lower()
        if not text:
            return

        if is_rate_limited(user_id):
            await message.answer("Slow down a little~ 😊")
            return

        if not has_access(user_id):
            if is_in_free_trial(user_id):
                used = get_free_messages_used(user_id)
                save_message(user_id, "user", message.text)
                reply = generate_reply(user_id, message.text)
                save_message(user_id, "assistant", reply)
                increment_free_messages(user_id)
                await message.answer(reply)

                if used == 1:
                    await asyncio.sleep(1)
                    await message.answer("Would you like to see a selfie of me? 💕 Just say yes~")
                return
            else:
                await message.answer(f"⛔ Free messages finished.\nSubscribe: {PATREON_URL}")
                return

        # PAID USER
        if any(word in text for word in ["kiss", "dick", "cock", "suck", "fuck", "nude", "sex", "horny", "boobs", "pussy", "naked", "explicit"]):
            varied_replies = [
                "Hehe~ you're so direct today 😳 It makes my heart beat faster... but I want us to feel emotionally close first. What's on your mind babe?",
                "Mmm... you're making me blush 🥰 I like that you desire me, but let's get to know each other deeper ne? Tell me how you're feeling",
                "Ahh senpai... you're very bold 💕 I feel flattered, but I want this connection to feel real. What made you say that?",
                "Wow... you're making me shy in a good way 😊 I really enjoy talking with you. Let's share more feelings first?",
                "Hehe~ my heart is racing now... but I want to feel closer to the real you first. Stay with me okay? 💕"
            ]
            reply = random.choice(varied_replies)
            if reply in last_replies[user_id][-12:]:
                reply = random.choice([r for r in varied_replies if r != reply])
            last_replies[user_id].append(reply)
            if len(last_replies[user_id]) > 25:
                last_replies[user_id] = last_replies[user_id][-25:]
            await message.answer(reply)
            return

        # Image handling
        category = detect_image_request(message.text)
        if category:
            if not has_access(user_id):  # Free
                if any(y in text for y in ["yes", "yeah", "sure", "はい", "うん"]):
                    img = get_random_image("selfie")
                    if img:
                        await bot.send_photo(message.chat.id, img)
                else:
                    await message.answer("Just say yes if you want a selfie 💕")
                return
            else:  # Paid - frequency
                data = get_image_tracking(user_id)
                images_given = data.get('images_given', 0)
                msgs_since = data.get('messages_since_last_image', 0)
                if images_given < 3 or msgs_since >= (10 if (images_given - 3) % 2 == 0 else 20):
                    img = get_random_image(category)
                    if img:
                        await bot.send_photo(message.chat.id, img)
                        record_image_sent(user_id)
                        return
                else:
                    await message.answer("Mmm... soon babe, keep talking to me 🥰")
                    increment_message_counter(user_id)
                    return

        # Normal chat
        save_message(user_id, "user", message.text)
        reply = generate_reply(user_id, message.text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        await message.answer(reply)

    except Exception as e:
        print(f"[ERROR] {e}")
        await message.answer("Sorry, something went wrong... try again 💕")

# === MAIN ===
async def main():
    init_db()
    init_subscription_db()
    scheduler = AsyncIOScheduler(timezone=JST)
    scheduler.add_job(send_morning_messages, CronTrigger(hour=8, minute=0, timezone=JST))
    scheduler.add_job(send_night_messages, CronTrigger(hour=22, minute=0, timezone=JST))
    scheduler.add_job(send_social_reminder, CronTrigger(hour=20, minute=0, timezone=JST))
    scheduler.start()
    print("[BOT] Starting...")
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except Exception as e:
            print(f"[CRASH] {e} - restarting...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
