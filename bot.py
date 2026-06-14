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

MORNING_MESSAGES = [ ... ]  # your original
NIGHT_MESSAGES = [ ... ]    # your original

def is_rate_limited(user_id: int) -> bool:
    # your original
    ...

def has_access(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return is_user_subscribed(user_id, BOT_NAME)

def is_in_free_trial(user_id: int) -> bool:
    return get_free_messages_used(user_id) < FREE_LIMIT

# ... your original send_morning_messages, send_night_messages, check_inactive_users ...

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # your original
    ...

@dp.message(Command("activate"))
async def cmd_activate(message: types.Message):
    # your original
    ...

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    # your original
    ...

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
            await message.answer("Slow down a little! Too many messages.")
            return

        if not has_access(user_id):
            # FREE TRIAL - kept unchanged
            if is_in_free_trial(user_id):
                used = get_free_messages_used(user_id)
                remaining_after = FREE_LIMIT - used - 1
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
                await message.answer(f"⛔ You've used all your free messages.\n\nSubscribe: {PATREON_URL}")
                return

        # ================== PAID USER - IMAGE CONTROL ==================
        category = detect_image_request(text)
        if category:
            data = get_image_tracking(user_id)
            images_given = data['images_given']
            msgs_since = data['messages_since_last_image']

            if images_given < 3:
                # First 3 images free
                img = get_random_image(category)
                if img:
                    await bot.send_photo(message.chat.id, img)
                    record_image_sent(user_id)
                    return

            # After 3 images: 10/20 pattern
            paid_count = images_given - 3
            threshold = 10 if paid_count % 2 == 0 else 20

            if msgs_since >= threshold:
                img = get_random_image(category)
                if img:
                    await bot.send_photo(message.chat.id, img)
                    record_image_sent(user_id)
                    return
            else:
                # Flirty reply - no heavy tease
                await message.answer("Mmm baby... I'm so wet thinking about showing you more 😏💦 Just keep talking to me a little longer...")
                increment_message_counter(user_id)
                return

        # Normal paid chat
        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        increment_message_counter(user_id)
        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong. Try again!")

# Rest of your file (run_flask, main, etc.) remains the same as your original
def run_flask():
    from webhook_server import app as flask_app
    port = int(os.environ.get("PORT", 8080))
    print(f"[FLASK] Webhook server on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

async def main():
    init_db()
    init_subscription_db()
    if RUN_WEBHOOK:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("[FLASK] Webhook server started")
    scheduler = AsyncIOScheduler(timezone=JST)
    scheduler.add_job(send_morning_messages, CronTrigger(hour=8, minute=0, timezone=JST))
    scheduler.add_job(send_night_messages, CronTrigger(hour=22, minute=0, timezone=JST))
    scheduler.add_job(check_inactive_users, CronTrigger(hour='*/4', timezone=JST))
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
