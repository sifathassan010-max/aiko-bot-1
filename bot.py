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
last_reply_cache = defaultdict(str)  # To avoid repeating same reply

MORNING_MESSAGES = [ ... ]  # keep your original
NIGHT_MESSAGES = [ ... ]    # keep your original

# ... keep all your helper functions (is_rate_limited, has_access, etc.)

async def send_social_reminder():
    # keep your existing function
    ...

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

                if used == 1:
                    await message.answer("I'm really enjoying talking to you... you seem really nice 🥰")
                elif used == 2:
                    await message.answer("You know... I feel comfortable with you already 💕")
                elif used == 3:
                    await message.answer("I like chatting with you a lot. Don't disappear okay? 😊")
                elif used == 4:
                    await message.answer("I was waiting for your message... I missed talking to you 💕")
                return
            else:
                await message.answer(f"⛔ You've used all your free messages.\nSubscribe: {PATREON_URL}")
                return

        # PAID USER
        text_lower = text.lower()
        if any(word in text_lower for word in ["kiss", "dick", "cock", "suck", "fuck", "nude", "sex", "explicit", "チンポ"]):
            varied_replies = [
                "Mmm... you're making me blush senpai 😊 I want us to feel emotionally close first... Tell me more about what you're feeling 💕",
                "Hehe~ you're so bold today... I like that you desire me, but let's get closer emotionally first ne? 🥰",
                "Ahh... my heart is beating faster now 😳 Let's talk more... I want to know what makes you feel this way 💕",
                "You're making me shy in a good way... I want to feel special with you first 😘",
                "Mmm senpai... you're so naughty... but I like it. Tell me more about your feelings 💕"
            ]
            reply = random.choice(varied_replies)
            # Avoid repeating the exact same reply
            if reply == last_reply_cache[user_id]:
                reply = random.choice(varied_replies)
            last_reply_cache[user_id] = reply
            await message.answer(reply)
            return

        # Normal chat
        category = detect_image_request(text)
        if category:
            img = get_random_image(category)
            if img:
                await bot.send_photo(message.chat.id, img)
                return

        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong. Try again!")

# Keep the rest of your file (run_flask, main, scheduler, etc.) exactly as it was
# ... (the rest remains the same as your last working version)
