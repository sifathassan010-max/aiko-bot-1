import sqlite3
from datetime import datetime

DB_NAME = "bot.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    """)

    # Free trial tracking — separate from chat history
    c.execute("""
        CREATE TABLE IF NOT EXISTS free_trials (
            user_id INTEGER PRIMARY KEY,
            messages_used INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, role, content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_history(user_id, limit=15):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT role, content FROM messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))


def clear_history(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_last_message_time(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT timestamp FROM messages
        WHERE user_id = ? AND role = 'user'
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_last_message_role(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT role FROM messages
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_free_messages_used(user_id):
    """How many free trial messages this user has used."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT messages_used FROM free_trials WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def increment_free_messages(user_id):
    """Add 1 to this user's free trial count."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO free_trials (user_id, messages_used)
        VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET messages_used = messages_used + 1
    """, (user_id,))
    conn.commit()
    conn.close()
