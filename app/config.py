"""Central configuration loaded from environment variables."""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass



import logging
import sys

# Configure central InvestPI parent logger with stream to stdout for Google Cloud Logging
def setup_logging():
    parent_logger = logging.getLogger("InvestPI")
    parent_logger.setLevel(logging.INFO)
    if not parent_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
        parent_logger.addHandler(handler)
    parent_logger.propagate = False
    return parent_logger

setup_logging()

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

    # Google Cloud Pub/Sub & Serverless Worker Configuration
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
    PUBSUB_TOPIC_LEADS = os.getenv("PUBSUB_TOPIC_LEADS", "investpi-leads-inbound")
    PUBSUB_TOPIC_AUDITS = os.getenv("PUBSUB_TOPIC_AUDITS", "investpi-audits-completed")
    PUBSUB_TOPIC_SYNC = os.getenv("PUBSUB_TOPIC_SYNC", "investpi-market-sync")
    PUBSUB_PUSH_TOKEN = os.getenv("PUBSUB_PUSH_TOKEN", "")
    PUBSUB_EMULATOR_HOST = os.getenv("PUBSUB_EMULATOR_HOST", "")

    # Environment detection: True when running on Cloud Run / GCP runtime
    IS_CLOUD = bool(os.getenv("K_SERVICE") or os.getenv("K_REVISION") or os.getenv("GAE_SERVICE"))

    # Firebase / Firestore persistence configuration:
    # - Cloud Run: Enabled by default (persists across instances & scale-to-zero)
    # - Local: Disabled by default (all updates apply strictly to local data/ folder)
    USE_FIREBASE = (
        os.getenv("USE_FIREBASE", "1").lower() in ("1", "true", "yes")
        if IS_CLOUD
        else os.getenv("FORCE_FIREBASE_LOCAL", "0").lower() in ("1", "true", "yes")
    )
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_COLLECTION = os.getenv("FIREBASE_COLLECTION", "investpi_reports")
    FIREBASE_CASES_COLLECTION = os.getenv("FIREBASE_CASES_COLLECTION", "investpi_cases")
    CRON_SECRET = os.getenv("CRON_SECRET", "")

