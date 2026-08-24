import os
from dotenv import load_dotenv

load_dotenv(".env.local")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Telegram Bot API
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Telegram MTProto (Telethon)
TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_SESSION = os.getenv("TG_SESSION", "")

# AI Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
ORCAROUTER_API_KEY = os.getenv("ORCAROUTER_API_KEY", "")
ORCAROUTER_MODEL = os.getenv("ORCAROUTER_MODEL", "openai/gpt-4o")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# Rate limits
SANITY_MIN_RATE = int(os.getenv("SANITY_MIN_RATE", "140000"))
SANITY_MAX_RATE = int(os.getenv("SANITY_MAX_RATE", "165000"))
OUTLIER_THRESHOLD_IQD = int(os.getenv("OUTLIER_THRESHOLD_IQD", "3000"))

# Channel to post market updates (legacy fallback; empty by default —
# publishing goes to registered targets and subscribers)
MARKET_CHANNEL = os.getenv("MARKET_CHANNEL", "")

# Monitored channels
MONITORED_CHANNELS = [
    "pashagoldd", "borsat_alkfah", "Borsa_Erbil", "PMCgroup",
    "nrxidolar", "iraqborsa", "RaprsyWnrx", "borsakurdstan",
    "httpswyTu0W4VrKZkMGZi", "Ranyadollar", "kurddolar",
    "NrxiDraw24", "nrxidraw852", "YarGold_Co",
]

# Timezone for Iraq/Kurdistan (GMT+3)
TIMEZONE_OFFSET = 3
