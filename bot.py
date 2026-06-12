# Paid user flow
category = detect_image_request(text)

if category:
    data = get_image_tracking(user_id)

    # Safe fallback values
    images_given = data.get('images_given', 0)
    msgs_since = data.get('messages_since_last_image', 0)

    # First 3 images instantly
    if images_given < 3:
        img = get_random_image(category)

        if img:
            await bot.send_photo(message.chat.id, img)

            # increments image count + resets message counter
            record_image_sent(user_id)

            return
        else:
            await message.answer("I don't have any photos for that yet!")
            return

    else:
        # Alternating schedule:
        # 10 chats -> image
        # 20 chats -> image
        # 10 chats -> image
        # 20 chats -> image

        paid_count = images_given - 3

        if paid_count % 2 == 0:
            threshold = 10
        else:
            threshold = 20

        if msgs_since >= threshold:
            img = get_random_image(category)

            if img:
                await bot.send_photo(message.chat.id, img)

                # reset counter + increment image count
                record_image_sent(user_id)

                return
            else:
                await message.answer("I don't have any photos for that yet!")
                return

        else:
            # playful teasing response
            tease_prompt = (
                "[The user is asking for a photo. "
                "Playfully tease them and make them wait a little longer "
                "without explaining why. "
                "Stay in character as their girlfriend. "
                "1-2 sentences max. "
                "Be flirty not robotic.]"
            )

            save_message(user_id, "user", text)

            tease = generate_reply(user_id, tease_prompt)

            save_message(user_id, "assistant", tease)

            increment_message_counter(user_id)

            await message.answer(tease)

            return

# Normal text flow
save_message(user_id, "user", text)

reply = generate_reply(user_id, text)

save_message(user_id, "assistant", reply)

increment_message_counter(user_id)

await message.answer(reply)
