import asyncio
import time
from collections import defaultdict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from db import init_db, save_message
from ai import generate_reply
from images import detect_image_request, get_random_image


# -----------------------
# BOT SETUP
# -----------------------
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# -----------------------
# RATE LIMITING
# -----------------------
user_timestamps = defaultdict(list)

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    user_timestamps[user_id] = [t for t in user_timestamps[user_id] if now - t < 60]
    if len(user_timestamps[user_id]) >= 10:
        return True
    user_timestamps[user_id].append(now)
    return False


# -----------------------
# /start COMMAND
# -----------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Hey! I'm Aiko 👋 Talk to me about anything!"
    )


# -----------------------
# MESSAGE HANDLER
# -----------------------
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

        # Check if user is asking for an image
        category = detect_image_request(text)
        if category:
            img = get_random_image(category)
            if img:
                await bot.send_photo(message.chat.id, img)
                return
            else:
                await message.answer("I don't have any photos for that yet!")
                return

        # Save user message and get AI reply
        save_message(user_id, "user", text)
        reply = generate_reply(user_id, text)
        save_message(user_id, "assistant", reply)

        await message.answer(reply)

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        await message.answer("Something went wrong. Try again!")


# -----------------------
# MAIN - safe loop, no recursion
# -----------------------
async def main():
    init_db()
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
