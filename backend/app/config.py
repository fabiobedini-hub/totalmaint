"""Settings, read from environment variables (or a .env file next to the backend folder).

Locally everything has sensible defaults: SQLite in ./data and uploads in ./data/uploads.
On the NAS, docker-compose sets DATABASE_URL to PostgreSQL instead.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_DIR = BASE_DIR.parent                       # totalmaint/


def _load_dotenv() -> None:
    for candidate in (PROJECT_DIR / ".env", BASE_DIR / ".env"):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'totalmaint.db').as_posix()}")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", DATA_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _secret_key() -> str:
    """Use SECRET_KEY if set; otherwise create a random one once and keep it in the data folder."""
    if os.getenv("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    key_file = DATA_DIR / "secret.key"
    if not key_file.exists():
        import secrets
        key_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return key_file.read_text(encoding="utf-8").strip()


SECRET_KEY = _secret_key()
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "720"))  # 30 days: convenient on a phone
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))

# Public address of the app, used in iCal links and reminder e-mails
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")

# Optional e-mail reminders. Leave SMTP_HOST empty to disable.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "7"))  # local hour for the daily reminder run

FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", PROJECT_DIR / "frontend"))

# Groups: anyone with this code can sign up and create their own group (household, boat club ...).
# Empty = sign-up is closed; people only get in through an invitation from a group admin.
SIGNUP_CODE = os.getenv("SIGNUP_CODE", "").strip()
INVITE_DAYS = int(os.getenv("INVITE_DAYS", "14"))  # how long an invitation link works
RESET_HOURS = int(os.getenv("RESET_HOURS", "2"))    # how long a "forgot password" link works
