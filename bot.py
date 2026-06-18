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

MORNING_MESSAGES = [ ... ]  # same as before
NIGHT_MESSAGES = [ ... ]    # same as before

# ... (rate limit, has_access, is_in_free_trial functions remain same)

async def send_morning_messages():
    # same as before
    pass

async def send_night_messages():
    # same as before
    pass

async def check_inactive_users():
    # same as before
    pass

async def send_social_reminder():
    # same as before
    pass

@dp.message(Command("start"))
# ... same as before

@dp.message(Command("activate"))
# ... same as before

@dp.message(Command("status"))
# ... same as before

@dp.message(Command("clear"))
# ... same as before

@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        text = (message.text or "").strip()
        if not text:
            return

        if is_rate_limited(user_id):
            await message.answer("Slow down a little babe~ 😊")
            return

        # FREE TRIAL LOGIC
        if not has_access(user_id):
            if is_in_free_trial(user_id):
                used = get_free_messages_used(user_id)
                save_message(user_id, "user", text)
                reply = generate_reply(user_id, text)
                save_message(user_id, "assistant", reply)
                increment_free_messages(user_id)
                await message.answer(reply)

                # Free trial selfie offer logic
                if used == 1:
                    await asyncio.sleep(1)
                    await message.answer("Would you like to see a selfie of me? 💕 Just say yes if you want~")
                elif used == 3:
                    await asyncio.sleep(1)
                    await message.answer("Do you want me to send you a cute selfie? 🥰 Say yes~")

                return
            else:
                await message.answer(f"⛔ You've used all your free messages.\nSubscribe: {PATREON_URL}")
                return

        # PAID USER
        text_lower = text.lower()

        # SFW Diversion for explicit requests
        if any(word in text_lower for word in ["kiss", "dick", "cock", "suck", "fuck", "nude", "sex", "horny", "boobs", "pussy", "explicit", "チンポ", "エッチ", "naked"]):
            varied_replies = [
                "Hehe~ you're so bold today 😳 I feel flattered... but I want us to feel close emotionally first. What's on your mind babe? 💕",
                "Mmm senpai... you're making me blush 🥰 I like that you desire me, but let's get closer in our hearts first ne?",
                "Ahh... my heart is beating faster 💕 You're very direct... I want to know the real you more. Tell me what you're feeling?",
                "Wow you're making me shy in a good way 😊 I really enjoy talking with you. Let's share our feelings deeper first 💕",
                "Hehe~ I can feel your desire... it makes me happy, but I want our connection to grow stronger emotionally first. Stay with me okay? 🥺"
            ]
            reply = random.choice(varied_replies)
            if reply in last_replies[user_id][-15:]:
                reply = random.choice([r for r in varied_replies if r != reply])
            last_replies[user_id].append(reply)
            if len(last_replies[user_id]) > 25:
                last_replies[user_id] = last_replies[user_id][-25:]
            await message.answer(reply)
            return

        # === IMAGE HANDLING (works for both free & paid, but frequency control only for paid) ===
        category = detect_image_request(text)
        if category:
            # For free users - simple yes context check
            if not has_access(user_id):
                if any(yes in text_lower for yes in ["yes", "yeah", "sure", "はい", "うん", "send", "selfie"]):
                    img = get_random_image("selfie")  # or category
                    if img:
                        await bot.send_photo(message.chat.id, img)
                        return
                else:
                    await message.answer("Just say yes if you want a selfie 💕")
                    return
            else:
                # Paid user image frequency control (3 immediate + 10/20 cooldown)
                data = get_image_tracking(user_id)
                images_given = data['images_given']
                msgs_since = data['messages_since_last_image']

                if images_given < 3 or msgs_since >= (10 if (images_given - 3) % 2 == 0 else 20):
                    img = get_random_image(category)
                    if img:
                        await bot.send_photo(message.chat.id, img)
                        record_image_sent(user_id)
                        return
                else:
                    await message.answer("Mmm... soon babe, keep talking to me a little more 🥰")
                    increment_message_counter(user_id)
                    return

        # Normal chat for paid users
        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong. Try again!")

# Scheduler and main() functions remain the same as previous version
# ... (copy the rest from the previous full code I gave you: run_flask, main(), scheduler jobs, etc.)

if __name__ == "__main__":
    asyncio.run(main())
