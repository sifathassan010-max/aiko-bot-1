# Paid user flow
category = detect_image_request(text)
if category:
    data = get_image_tracking(user_id)
    images_given = data['images_given']
    msgs_since = data['messages_since_last_image']

    # First 3 images sent immediately on demand
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
        # Pattern: 10 chats → image, 20 chats → image, 10, 20, 10, 20...
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
            # Bot teases and makes user wait in character
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
