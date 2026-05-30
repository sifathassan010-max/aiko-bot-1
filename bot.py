import asyncio
import time
import threading
import os
from collections import defaultdict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, PATREON_URL
from db import init_db, save_message
from db_shared import (
    init_subscription_db,
    use_activation_code,
    is_user_subscribed,
    get_user_subscription
)
from ai import generate_reply
from images import detect_image_request, get_random_image

# ─────────────────────────────────────────────────────────
# ← YOUR INPUT:
# BOT_NAME: set to this bot's name in lowercase
#   Aiko repo  → "aiko"
#   Hana repo  → "hana"
#
# RUN_WEBHOOK: controls whether this bot runs the payment
#   webhook server. Set to True ONLY in Aiko's repo.
#   Hana's repo set to False.
#   You can also set RUN_WEBHOOK env variable in Railway
#   instead of changing this line.
BOT_NAME    = "aiko"
RUN_WEBHOOK = os.getenv("RUN_WEBHOOK", "false").lower() == "true"
# ─────────────────────────────────────────────────────────

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

user_timestamps = defaultdict(list)


def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    user_timestamps[user_id] = [t for t in user_timestamps[user_id] if now - t < 60]
    if len(user_timestamps[user_id]) >= 10:
        return True
    user_timestamps[user_id].append(now)
    return False


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if is_user_subscribed(user_id, BOT_NAME):
        await message.answer("Hey! I'm Aiko 👋 Welcome back!")
    else:
        await message.answer(
            "Hey! I'm Aiko 👋\n\n"
            "To chat with me, you need an active subscription.\n\n"
            f"📌 Subscribe here: {PATREON_URL}\n\n"
            "Already subscribed? Activate your access:\n"
            "/activate YOUR_CODE"
        )


@dp.message(Command("activate"))
async def cmd_activate(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Please include your code:\n"
            "/activate YOUR_CODE\n\n"
            "Example: /activate ABC123XYZ0"
        )
        return

    code = parts[1].upper().strip()
    user_id = message.from_user.id

    if is_user_subscribed(user_id, BOT_NAME):
        await message.answer("✅ You already have an active subscription!")
        return

    success, result = use_activation_code(code, user_id, BOT_NAME)

    if success:
        tier = result
        responses = {
            'monthly': (
                "✅ Activated! Welcome 🎉\n\n"
                "You have 30 days of full access.\n"
                "Start chatting — just say hi!"
            ),
            '3month': (
                "✅ Activated! Welcome 🎉\n\n"
                "You have 90 days of full access.\n"
                "🎁 Check your email for your\n"
                "1 month free bonus bot access!\n\n"
                "Start chatting — just say hi!"
            ),
            '6month': (
                "✅ Activated! Welcome 🎉\n\n"
                "You have 180 days of full access.\n"
                "🎁 Check your email for your\n"
                "3 months free bonus bot access!\n\n"
                "Start chatting — just say hi!"
            )
        }
        await message.answer(responses.get(tier, "✅ Subscription activated! Welcome!"))
    else:
        await message.answer(
            "❌ Invalid or already used code.\n\n"
            "Check your email and try again."
        )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    sub = get_user_subscription(user_id, BOT_NAME)

    if not sub:
        await message.answer(
            "You don't have an active subscription.\n\n"
            f"Subscribe at: {PATREON_URL}"
        )
        return

    tier_names = {'monthly': 'Monthly', '3month': '3 Month', '6month': '6 Month'}
    tier_display = tier_names.get(sub['tier'], sub['tier'])
    end_date = sub['end_date'].strftime('%B %d, %Y')
    msg = f"📋 Subscription Status\n\nPlan: {tier_display}\nExpires: {end_date}"

    if sub['bonus_bot_end_date']:
        bonus = sub['bonus_bot_end_date'].strftime('%B %d, %Y')
        msg += f"\n🎁 Bonus bot access until: {bonus}"

    await message.answer(msg)


@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        text = message.text

        if not text:
            return

        if not is_user_subscribed(user_id, BOT_NAME):
            await message.answer(
                "⛔ No active subscription.\n\n"
                f"Subscribe at: {PATREON_URL}\n\n"
                "Already subscribed? Use /activate YOUR_CODE"
            )
            return

        if is_rate_limited(user_id):
            await message.answer("Slow down a little! Too many messages.")
            return

        category = detect_image_request(text)
        if category:
            img = get_random_image(category)
            if img:
                await bot.send_photo(message.chat.id, img)
                return
            else:
                await message.answer("I don't have any photos for that yet!")
                return

        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)
        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong. Try again!")


def run_flask():
    from webhook_server import app as flask_app
    port = int(os.environ.get("PORT", 8080))
    print(f"[FLASK] Webhook server on port {port}")
    flask_app.run(host="0.0.0.0", port=port)


async def main():
    init_db()
    init_subscription_db()

    # Only Aiko's Railway service runs the webhook server
    if RUN_WEBHOOK:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("[FLASK] Webhook server started")

    print("Starting bot...")
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Bot is running.")
            await dp.start_polling(bot)
        except Exception as e:
            print(f"[CRASH] {e} — restarting in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
