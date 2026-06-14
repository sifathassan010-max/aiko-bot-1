import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import random
import string
from config import DATABASE_URL

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_subscription_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            telegram_id BIGINT,
            bot_name VARCHAR(100) NOT NULL,
            tier VARCHAR(50) NOT NULL,
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP NOT NULL,
            bonus_bot_end_date TIMESTAMP,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE NOT NULL,
            email VARCHAR(255) NOT NULL,
            bot_name VARCHAR(100) NOT NULL,
            tier VARCHAR(50) NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            telegram_id BIGINT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS free_trials (
            user_id BIGINT PRIMARY KEY,
            messages_used INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS image_tracking (
            user_id BIGINT PRIMARY KEY,
            images_given INTEGER DEFAULT 0,
            messages_since_last_image INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Subscription tables ready.")

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def create_activation_code(email, tier, bot_name):
    code = generate_code()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO activation_codes (code, email, tier, bot_name) VALUES (%s, %s, %s, %s)",
        (code, email, tier, bot_name)
    )
    conn.commit()
    conn.close()
    return code

def use_activation_code(code, telegram_id, bot_name):
    """Activate a code for a specific bot and Telegram user."""
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(
        "SELECT * FROM activation_codes WHERE code = %s AND used = FALSE AND bot_name = %s",
        (code, bot_name)
    )
    activation = c.fetchone()
    if not activation:
        conn.close()
        return False, "Invalid or already used code."
    tier = activation['tier']
    email = activation['email']
    now = datetime.utcnow()
    if tier == '6month':
        end_date = now + timedelta(days=180)
        bonus_end = now + timedelta(days=90)
    elif tier == '3month':
        end_date = now + timedelta(days=90)
        bonus_end = now + timedelta(days=30)
    else:
        end_date = now + timedelta(days=30)
        bonus_end = None
    c.execute("""
        INSERT INTO subscriptions
        (email, telegram_id, bot_name, tier, start_date, end_date, bonus_bot_end_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (email, telegram_id, bot_name, tier, now, end_date, bonus_end))
    c.execute(
        "UPDATE activation_codes SET used = TRUE, telegram_id = %s WHERE code = %s",
        (telegram_id, code)
    )
    conn.commit()
    conn.close()
    return True, tier

def is_user_subscribed(telegram_id, bot_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id FROM subscriptions
        WHERE telegram_id = %s AND bot_name = %s
        AND active = TRUE AND end_date > NOW()
    """, (telegram_id, bot_name))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_user_subscription(telegram_id, bot_name):
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("""
        SELECT * FROM subscriptions
        WHERE telegram_id = %s AND bot_name = %s
        AND active = TRUE AND end_date > NOW()
        ORDER BY end_date DESC LIMIT 1
    """, (telegram_id, bot_name))
    row = c.fetchone()
    conn.close()
    return row

def get_active_subscriber_ids(bot_name):
    """Get all active subscriber Telegram IDs for a specific bot."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT telegram_id FROM subscriptions
        WHERE bot_name = %s
        AND active = TRUE
        AND end_date > NOW()
        AND telegram_id IS NOT NULL
    """, (bot_name,))
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_free_messages_used(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT messages_used FROM free_trials WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def increment_free_messages(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO free_trials (user_id, messages_used)
        VALUES (%s, 1)
        ON CONFLICT (user_id) DO UPDATE SET messages_used = free_trials.messages_used + 1
    """, (user_id,))
    conn.commit()
    conn.close()

def get_image_tracking(user_id):
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM image_tracking WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {'images_given': row['images_given'], 'messages_since_last_image': row['messages_since_last_image']}
    return {'images_given': 0, 'messages_since_last_image': 0}

def record_image_sent(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO image_tracking (user_id, images_given, messages_since_last_image)
        VALUES (%s, 1, 0)
        ON CONFLICT (user_id) DO UPDATE SET
            images_given = image_tracking.images_given + 1,
            messages_since_last_image = 0
    """, (user_id,))
    conn.commit()
    conn.close()

def increment_message_counter(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO image_tracking (user_id, images_given, messages_since_last_image)
        VALUES (%s, 0, 1)
        ON CONFLICT (user_id) DO UPDATE SET
            messages_since_last_image = image_tracking.messages_since_last_image + 1
    """, (user_id,))
    conn.commit()
    conn.close()

# ====================== NEW: Daily 100 Messages Limit ======================
def init_daily_limit_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_limits (
            user_id BIGINT,
            date DATE,
            messages_today INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Daily limit table ready.")

def get_today_messages(user_id: int) -> int:
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().date()
    c.execute("SELECT messages_today FROM daily_limits WHERE user_id = %s AND date = %s", (user_id, today))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def increment_today_messages(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().date()
    c.execute("""
        INSERT INTO daily_limits (user_id, date, messages_today)
        VALUES (%s, %s, 1)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET messages_today = daily_limits.messages_today + 1
    """, (user_id, today))
    conn.commit()
    conn.close()
