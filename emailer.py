import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import GMAIL_USER, GMAIL_APP_PASSWORD

# ─────────────────────────────────────────────────────────
# ← YOUR INPUT: Add each bot's Telegram username here
BOT_USERNAMES = {
    "aiko": "@samaikobot",    # ← YOUR INPUT
    "hana": "@YourHanaBotUsername",    # ← YOUR INPUT
}
# ─────────────────────────────────────────────────────────

TIER_DAYS = {
    'monthly': '30 days',
    '3month':  '90 days',
    '6month':  '180 days',
}


def send_activation_email(to_email, code, tier, bot_name,
                           bonus_code=None, bonus_bot=None, bonus_tier=None):

    bot_username = BOT_USERNAMES.get(bot_name, "@UnknownBot")
    bot_display  = bot_name.capitalize()
    duration     = TIER_DAYS.get(tier, '30 days')

    subject = f"✨ Your {bot_display} Bot Activation Code"

    # Build bonus section if applicable
    bonus_section = ""
    if bonus_code and bonus_bot and bonus_tier:
        bonus_username = BOT_USERNAMES.get(bonus_bot, "@UnknownBot")
        bonus_display  = bonus_bot.capitalize()
        bonus_duration = TIER_DAYS.get(bonus_tier, '30 days')
        bonus_section = f"""
━━━━━━━━━━━━━━━━━━━━
🎁 BONUS — Free {bonus_display} Bot Access ({bonus_duration})

Your {bonus_display} Bot activation code:

    {bonus_code}

How to activate your bonus:
1. Open Telegram and search for {bonus_username}
2. Send: /activate {bonus_code}

This bonus is also personal — do not share it.
━━━━━━━━━━━━━━━━━━━━"""

    body = f"""Hello!

Thank you for subscribing to {bot_display} Bot 🎉
Your access duration: {duration}

━━━━━━━━━━━━━━━━━━━━
Your {bot_display} Bot activation code:

    {code}

━━━━━━━━━━━━━━━━━━━━

How to activate:
1. Open Telegram and search for {bot_username}
2. Send this exact message: /activate {code}
3. Done! You are in 🎊
{bonus_section}

⚠️ Important:
- All codes are personal — do not share them
- Each code works only once
- Codes activate your specific Telegram account only

Enjoy! 💕
"""

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent to {to_email} — {bot_name} {tier}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {repr(e)}")
        return False
