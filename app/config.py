"""Central configuration loaded from environment variables."""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass



DATA_DIR = ROOT_DIR / "data"
MARKETS_DIR = ROOT_DIR / "markets"
REPORTS_DIR = ROOT_DIR / "reports_out"


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Demo mode is on automatically when no API key is configured.
    DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1" or not os.getenv("GEMINI_API_KEY")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB uploads
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Firebase / Firestore persistence configuration
    USE_FIREBASE = os.getenv("USE_FIREBASE", "1").lower() in ("1", "true", "yes")
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_COLLECTION = os.getenv("FIREBASE_COLLECTION", "investpi_reports")

