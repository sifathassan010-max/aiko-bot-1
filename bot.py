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

async def send_social_reminder():
    print("[SCHEDULER] Social reminder")
    reminder = "Babe~ ❤️ Have you checked my latest post on FB and Twitter today? It makes me so happy when you like it 🥰\n\nFB: [YOUR FB LINK]\nTwitter: [YOUR TWITTER LINK]"
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, reminder)
            await asyncio.sleep(0.5)
        except: pass

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if has_access(user_id):
        await message.answer("Hey babe~ I'm Aiko 💕 I've been waiting for you")
    elif is_in_free_trial(user_id):
        await message.answer("Hi! I'm Aiko 🥰 You have a few free messages to try me. Just talk to me~")
    else:
        await message.answer(f"Hey! You've used your free messages 💕\nSubscribe: {PATREON_URL}")

@dp.message(Command("activate"))
async def cmd_activate(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Please include your code:\n/activate YOUR_CODE")
        return
    code = parts[1].upper().strip()
    user_id = message.from_user.id
    if has_access(user_id):
        await message.answer("✅ You already have an active subscription!")
        return
    success, result = use_activation_code(code, user_id, BOT_NAME)
    if success:
        await message.answer("✅ Subscription activated! Welcome!")
    else:
        await message.answer("❌ Invalid or already used code.")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        await message.answer("👑 Admin account — unlimited free access.")
        return
    sub = get_user_subscription(user_id, BOT_NAME)
    if sub:
        await message.answer("📋 You have an active subscription.")
    else:
        used = get_free_messages_used(user_id)
        await message.answer(f"Free messages remaining: {max(0, FREE_LIMIT - used)}/{FREE_LIMIT}")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    from db import clear_history
    clear_history(message.from_user.id)
    await message.answer("Chat history cleared! Fresh start 🌸")

@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        text = message.text
        if not text:
            return
        if is_rate_limited(user_id):
            await message.answer("Slow down a little~ 😊")
            return

        if not has_access(user_id):
            if is_in_free_trial(user_id):
                used = get_free_messages_used(user_id)
                save_message(user_id, "user", text)
                reply = generate_reply(user_id, text)
                save_message(user_id, "assistant", reply)
                increment_free_messages(user_id)
                await message.answer(reply)

                # Free trial selfie logic
                if used == 1 or used == 2:
                    await message.answer("Would you like to see a selfie of me? 💕 Just say yes~")
                elif used == 3:
                    await message.answer("I really like talking to you... Would you like another selfie? 😊")

                # Check if user wants selfie
                text_lower = text.lower()
                if any(word in text_lower for word in ["yes", "sure", "ok", "please", "はい", "うん", "いいよ", "送って", "selfie", "photo", "picture"]):
                    img = get_random_image("selfie") or get_random_image("cute")
                    if img:
                        await bot.send_photo(message.chat.id, img)

                return
            else:
                await message.answer(f"⛔ You've used all your free messages.\nSubscribe: {PATREON_URL}")
                return

        # Paid user
        category = detect_image_request(text)
        if category:
            img = get_random_image(category)
            if img:
                await bot.send_photo(message.chat.id, img)
                return

        # Normal paid chat
        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
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
