import hashlib
import hmac
import os
from flask import Flask, request, jsonify
from config import PATREON_WEBHOOK_SECRET
from db_shared import init_subscription_db, create_activation_code
from emailer import send_activation_email

app = Flask(__name__)

# ─────────────────────────────────────────────────────────
# ← YOUR INPUT: Bot names exactly as in Patreon tier titles
BOT_NAMES = ["aiko", "hana"]

# Bonus system: when someone buys left side, they also get right side free
# Format: (bot_name, tier) : (bonus_bot_name, bonus_tier)
BONUS_BOTS = {
    ("aiko", "3month"): ("hana", "monthly"),   # Aiko 3mo → Hana 1mo free
    ("aiko", "6month"): ("hana", "3month"),    # Aiko 6mo → Hana 3mo free
}
# ─────────────────────────────────────────────────────────


def verify_signature(payload_bytes, signature):
    if not PATREON_WEBHOOK_SECRET:
        return True
    expected = hmac.new(
        PATREON_WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_bytes,
        digestmod=hashlib.md5
    ).hexdigest()
    return hmac.compare_digest(expected, signature or '')


def detect_bot_and_tier(tier_title):
    title = (tier_title or '').lower()

    bot_name = BOT_NAMES[0]
    for name in BOT_NAMES:
        if name in title:
            bot_name = name
            break

    if '6' in title or 'six' in title:
        tier = '6month'
    elif '3' in title or 'three' in title:
        tier = '3month'
    else:
        tier = 'monthly'

    return bot_name, tier


@app.route('/webhook/patreon', methods=['POST'])
def patreon_webhook():
    try:
        signature = request.headers.get('X-Patreon-Signature')
        if not verify_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 401

        event = request.headers.get('X-Patreon-Event', '')
        data = request.get_json(force=True)

        if event not in ['members:pledge:create', 'members:create']:
            return jsonify({'status': 'ignored'}), 200

        email = None
        tier_title = None

        for item in data.get('included', []):
            if item.get('type') == 'user':
                email = item.get('attributes', {}).get('email')
            if item.get('type') == 'tier':
                tier_title = item.get('attributes', {}).get('title')

        if not email:
            return jsonify({'error': 'No email found'}), 400

        bot_name, tier = detect_bot_and_tier(tier_title)

        # Generate main activation code
        main_code = create_activation_code(email, tier, bot_name)

        # Check if this purchase includes a bonus bot
        bonus_code = None
        bonus_bot = None
        bonus_tier = None
        bonus_key = (bot_name, tier)

        if bonus_key in BONUS_BOTS:
            bonus_bot, bonus_tier = BONUS_BOTS[bonus_key]
            bonus_code = create_activation_code(email, bonus_tier, bonus_bot)

        # Send email with main code + bonus code if applicable
        send_activation_email(email, main_code, tier, bot_name, bonus_code, bonus_bot, bonus_tier)

        print(f"[WEBHOOK] ✅ {email} — {bot_name} {tier}" +
              (f" + bonus: {bonus_bot} {bonus_tier}" if bonus_bot else ""))

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        print(f"[WEBHOOK ERROR] {repr(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'running'}), 200
