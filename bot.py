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

# Import carefully to avoid circular import
from db import init_db, save_message, get_free_messages_used, increment_free_messages
from db import init_daily_limit_db, get_today_messages, increment_today_messages   # Added

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

MORNING_MESSAGES = [ ... ]  # your original list (keep as is)
NIGHT_MESSAGES = [ ... ]    # your original list (keep as is)

def is_rate_limited(user_id: int) -> bool:
    # your original function
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

# Keep all your scheduler functions (send_morning_messages, send_night_messages, check_inactive_users) as they were

async def send_social_reminder():
    print("[SCHEDULER] Sending social reminder...")
    user_ids = get_active_subscriber_ids(BOT_NAME)
    for user_id in user_ids:
        try:
            reminder = "Babe~ ❤️ Have you checked my latest post on FB and Twitter today? It makes me so happy when you like and comment 🥺💕\n\nFB: [YOUR FB LINK]\nTwitter: [YOUR TWITTER LINK]"
            await bot.send_message(user_id, reminder)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[REMINDER ERROR] {e}")

@dp.message(Command("start"))
# ... keep all your command handlers as they are ...

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
            # Free trial part - keep exactly as you had
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

        # PAID USER - Daily Limit Check
        if get_today_messages(user_id) >= 100:
            await message.answer("You've reached your daily limit of 100 messages 💕\nCome back tomorrow!")
            return

        # Your existing image control and chat logic...
        category = detect_image_request(text)
        if category:
            # ... keep your current image control code exactly as it is ...

        # Normal paid chat
        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        increment_today_messages(user_id)        # <-- Added for daily limit
        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong. Try again!")

# Rest of the file (run_flask, main, etc.) remains the same
def run_flask():
    from webhook_server import app as flask_app
    port = int(os.environ.get("PORT", 8080))
    print(f"[FLASK] Webhook server on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

async def main():
    init_db()
    init_subscription_db()
    init_daily_limit_db()               # <-- Added
    if RUN_WEBHOOK:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("[FLASK] Webhook server started")
    scheduler = AsyncIOScheduler(timezone=JST)
    scheduler.add_job(send_morning_messages, CronTrigger(hour=8, minute=0, timezone=JST))
    scheduler.add_job(send_night_messages, CronTrigger(hour=22, minute=0, timezone=JST))
    scheduler.add_job(check_inactive_users, CronTrigger(hour='*/4', timezone=JST))
    scheduler.add_job(send_social_reminder, CronTrigger(hour=20, minute=0, timezone=JST))
    scheduler.start()
    print("[SCHEDULER] Started")
    print("Starting bot...")
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except Exception as e:
            print(f"[CRASH] {e} — restarting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
