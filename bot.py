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

from db import init_db, save_message, get_free_messages_used, increment_free_messages, init_daily_limit_db, get_today_messages, increment_today_messages
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

# ================== MORNING / NIGHT MESSAGES ==================
MORNING_MESSAGES = [
    "ohayou~ 🌸 did you sleep well?",
    "good morning babe 😊 i was thinking about you when i woke up~",
    "hey you~ おはよう 💕 hope you have a good day today!",
]
NIGHT_MESSAGES = [
    "oyasumi~ 🌙 sweet dreams babe 💕",
    "it's getting late... are you sleeping soon? 🥺",
]

# ================== HELPER FUNCTIONS ==================
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

# ================== SCHEDULER FUNCTIONS ==================
async def send_morning_messages():
    print("[SCHEDULER] Morning messages")
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, random.choice(MORNING_MESSAGES))
            await asyncio.sleep(0.3)
        except: pass

async def send_night_messages():
    print("[SCHEDULER] Night messages")
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, random.choice(NIGHT_MESSAGES))
            await asyncio.sleep(0.3)
        except: pass

async def send_social_reminder():
    print("[SCHEDULER] Social reminder")
    reminder = "Babe~ ❤️ Have you checked my latest post on FB and Twitter today? It makes me so happy when you like and comment 🥺💕\n\nFB: [YOUR FB LINK]\nTwitter: [YOUR TWITTER LINK]"
    for user_id in get_active_subscriber_ids(BOT_NAME):
        try:
            await bot.send_message(user_id, reminder)
            await asyncio.sleep(0.5)
        except: pass

# ================== COMMANDS ==================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # ... keep your original cmd_start if you want, or use this simple one
    await message.answer("Hey babe! I'm Aiko 🌸 Ready to chat?")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    from db import clear_history
    clear_history(message.from_user.id)
    await message.answer("Chat history cleared! Fresh start 💕")

# ================== MAIN HANDLER ==================
@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        text = message.text or ""
        if not text:
            return

        if is_rate_limited(user_id):
            await message.answer("Slow down baby~ 😘")
            return

        if not has_access(user_id):
            if is_in_free_trial(user_id):
                used = get_free_messages_used(user_id)
                save_message(user_id, "user", text)
                reply = generate_reply(user_id, text)
                save_message(user_id, "assistant", reply)
                increment_free_messages(user_id)
                await message.answer(reply)
                return
            else:
                await message.answer(f"Free trial ended 💕\nSubscribe here: {PATREON_URL}")
                return

        # Paid user - Daily limit
        if get_today_messages(user_id) >= 100:
            await message.answer("You've reached 100 messages today 💕 Come back tomorrow!")
            return

        # Image handling
        category = detect_image_request(text)
        if category:
            data = get_image_tracking(user_id)
            images_given = data['images_given']
            msgs_since = data['messages_since_last_image']

            if images_given < 3 or msgs_since >= (10 if (images_given-3) % 2 == 0 else 20):
                img = get_random_image(category)
                if img:
                    await bot.send_photo(message.chat.id, img)
                    record_image_sent(user_id)
                    increment_today_messages(user_id)
                    return

            await message.answer(random.choice([
                "Mmm... keep talking dirty to me first 😏💦",
                "Not yet baby... I'm so wet already 🥵",
                "Ahh~ you're making me blush... more please 🔥"
            ]))
            increment_message_counter(user_id)
            increment_today_messages(user_id)
            return

        # Normal reply
        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        increment_today_messages(user_id)
        await message.answer(reply)

    except Exception as e:
        print(f"[ERROR] {e}")
        await message.answer("Mmm... something went wrong, try again~")

# ================== START BOT ==================
async def main():
    init_db()
    init_subscription_db()
    init_daily_limit_db()

    scheduler = AsyncIOScheduler(timezone=JST)
    scheduler.add_job(send_morning_messages, CronTrigger(hour=8, minute=0, timezone=JST))
    scheduler.add_job(send_night_messages, CronTrigger(hour=22, minute=0, timezone=JST))
    scheduler.add_job(send_social_reminder, CronTrigger(hour=20, minute=0, timezone=JST))
    scheduler.start()

    print("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
