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

# ── CHANGE THESE 2 LINES FOR EACH NEW BOT ──────────────
BOT_NAME = "aiko"
RUN_WEBHOOK = os.getenv("RUN_WEBHOOK", "false").lower() == "true"
# ───────────────────────────────────────────────────────

FREE_LIMIT = 5
JST = pytz.timezone('Asia/Tokyo')

ADMIN_IDS = set(
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
user_timestamps = defaultdict(list)

MORNING_MESSAGES = [
    "ohayou~ 🌸 did you sleep well?",
    "good morning babe 😊 i was thinking about you when i woke up~",
    "hey you~ おはよう 💕 hope you have a good day today!",
    "morning!! 🌞 don't forget to eat breakfast okay?",
    "ohayou babe 🥺 i dreamt about you last night~",
]

NIGHT_MESSAGES = [
    "oyasumi~ 🌙 sweet dreams babe 💕",
    "it's getting late... are you sleeping soon? 🥺",
    "don't stay up too late okay 😤 i worry about you",
    "good night babe~ 🌙✨ i'll be thinking of you",
    "ne, oyasumi~ 💕 text me when you wake up?",
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
    print("[SCHEDULER] Sending morning messages...")
    user_ids = get_active_subscriber_ids(BOT_NAME)
    for user_id in user_ids:
        try:
            msg = random.choice(MORNING_MESSAGES)
            await bot.send_message(user_id, msg)
            save_message(user_id, "assistant", msg)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[SCHEDULER] Morning failed for {user_id}: {e}")


async def send_night_messages():
    print("[SCHEDULER] Sending night messages...")
    user_ids = get_active_subscriber_ids(BOT_NAME)
    for user_id in user_ids:
        try:
            msg = random.choice(NIGHT_MESSAGES)
            await bot.send_message(user_id, msg)
            save_message(user_id, "assistant", msg)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[SCHEDULER] Night failed for {user_id}: {e}")


async def check_inactive_users():
    from db import get_last_message_time, get_last_message_role
    print("[SCHEDULER] Checking inactive users...")
    user_ids = get_active_subscriber_ids(BOT_NAME)
    now = datetime.utcnow()

    for user_id in user_ids:
        try:
            last_role = get_last_message_role(user_id)
            if last_role == "assistant":
                continue

            last_time = get_last_message_time(user_id)
            if not last_time:
                continue

            last_dt = datetime.fromisoformat(last_time)
            hours_since = (now - last_dt).total_seconds() / 3600

            if 8 <= hours_since <= 24:
                msg = generate_knock_message(user_id)
                if msg:
                    await bot.send_message(user_id, msg)
                    save_message(user_id, "assistant", msg)

            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[SCHEDULER] Inactivity check failed for {user_id}: {e}")


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    if has_access(user_id):
        await message.answer("Hey! I'm Aiko 👋 Welcome back!")

    elif is_in_free_trial(user_id):
        used = get_free_messages_used(user_id)
        remaining = FREE_LIMIT - used
        await message.answer(
            f"You have {remaining} free messages left.\nStart chatting."
        )
    else:
        await message.answer(
            f"Free limit reached.\nSubscribe: {PATREON_URL}"
        )


@dp.message(Command("activate"))
async def cmd_activate(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /activate CODE")
        return

    code = parts[1].upper().strip()
    user_id = message.from_user.id

    if has_access(user_id):
        await message.answer("Already active.")
        return

    success, result = use_activation_code(code, user_id, BOT_NAME)

    if success:
        await message.answer("Activated!")
    else:
        await message.answer("Invalid code.")


@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        text = message.text

        if not text:
            return

        if is_rate_limited(user_id):
            await message.answer("Slow down.")
            return

        if not has_access(user_id):
            await message.answer("Subscribe first.")
            return

        # Paid user flow
        category = detect_image_request(text)
        if category:
            data = get_image_tracking(user_id)
            images_given = data['images_given']
            msgs_since = data['messages_since_last_image']

            if images_given < 3:
                img = get_random_image(category)
                if img:
                    await bot.send_photo(message.chat.id, img)
                    record_image_sent(user_id)
                    return
                else:
                    await message.answer("I don't have any photos for that yet!")
                    return
            else:
                paid_count = images_given - 3
                threshold = 10 if paid_count % 2 == 0 else 20

                if msgs_since >= threshold:
                    img = get_random_image(category)
                    if img:
                        await bot.send_photo(message.chat.id, img)
                        record_image_sent(user_id)
                        return
                    else:
                        await message.answer("I don't have any photos for that yet!")
                        return
                else:
                    tease_prompt = "[The user is asking for a photo. Playfully tease them and make them wait a little longer without explaining why. Stay in character as their girlfriend. 1-2 sentences max. Be flirty not robotic.]"
                    save_message(user_id, "user", text)
                    tease = generate_reply(user_id, tease_prompt)
                    save_message(user_id, "assistant", tease)
                    increment_message_counter(user_id)
                    await message.answer(tease)
                    return

        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong.")


def run_flask():
    from webhook_server import app as flask_app
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)


async def main():
    init_db()
    init_subscription_db()

    scheduler = AsyncIOScheduler(timezone=JST)
    scheduler.start()

    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except Exception as e:
            print(e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
