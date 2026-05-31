import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN               = os.getenv("BOT_TOKEN")
GROQ_KEY                = os.getenv("GROQ_KEY")
GMAIL_USER              = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD      = os.getenv("GMAIL_APP_PASSWORD")
DATABASE_URL            = os.getenv("DATABASE_URL")
PATREON_WEBHOOK_SECRET  = os.getenv("PATREON_WEBHOOK_SECRET")
PATREON_URL             = os.getenv("PATREON_URL", "patreon.com/yourpage")

MAX_HISTORY = 6   # kept low to avoid Groq token-per-minute limits
