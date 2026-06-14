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

async def send_social_reminder():
    print("[SCHEDULER] Sending social reminder...")
    user_ids = get_active_subscriber_ids(BOT_NAME)
    for user_id in user_ids:
        try:
            reminder = "Babe~ ❤️ Have you checked my latest post on FB and Twitter today? It makes me so happy when you like and comment 🥺💕\n\nFB: [YOUR FB LINK HERE]\nTwitter: [YOUR TWITTER LINK HERE]"
            await bot.send_message(user_id, reminder)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[REMINDER ERROR] {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if has_access(user_id):
        await message.answer("Hey! I'm Aiko 👋 Welcome back!")
    elif is_in_free_trial(user_id):
        used = get_free_messages_used(user_id)
        remaining = FREE_LIMIT - used
        await message.answer(f"Hey! I'm Aiko 👋\n\nYou have {remaining} free messages to try me out!\nAfter that you'll need a subscription 💕\n\nJust start chatting~")
    else:
        await message.answer(f"Hey! I'm Aiko 👋\n\nYou've used all your free messages!\n\n📌 Subscribe here: {PATREON_URL}")

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
            await message.answer("Slow down a little!")
            return

        if not has_access(user_id):
            if is_in_free_trial(user_id):
                used = get_free_messages_used(user_id)
                save_message(user_id, "user", text)
                reply = generate_reply(user_id, text)
                save_message(user_id, "assistant", reply)
                increment_free_messages(user_id)
                await message.answer(reply)

                if used == 1 or used == 2:
                    await message.answer("マスター…💦 もしよかったら…私の唇でチンポにキスしてあげようか？😏")

                text_lower = text.lower()
                if any(word in text_lower for word in ["yes", "sure", "ok", "please", "はい", "して", "いいよ", "してほしい", "したい", "kiss", "dick", "cock", "チンポ", "picture", "photo", "send me"]):
                    img = get_random_image("dick-kiss")
                    if img:
                        await bot.send_photo(message.chat.id, img)
                return
            else:
                await message.answer(f"⛔ You've used all your free messages.\nSubscribe: {PATREON_URL}")
                return

        # PAID USER - Daily Limit
        if get_today_messages(user_id) >= 100:
            await message.answer("You've reached your daily limit of 100 messages 💕\nCome back tomorrow!")
            return

        # Paid user image control
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
                    increment_today_messages(user_id)
                    return

            paid_count = images_given - 3
            threshold = 10 if paid_count % 2 == 0 else 20

            if msgs_since >= threshold:
                img = get_random_image(category)
                if img:
                    await bot.send_photo(message.chat.id, img)
                    record_image_sent(user_id)
                    increment_today_messages(user_id)
                    return

            # Varied delay replies
            delay_replies = [
                "Mmm baby... I'm so turned on right now 😏💦 Just keep talking to me a little longer...",
                "Hehe~ you're so naughty today 🥵 My body is aching for you... chat with me more first 💕",
                "Ahh... I want to show you so bad 😩 keep seducing me~",
                "Not yet baby... I'm getting so wet thinking about
