"""Central configuration loaded from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
MARKETS_DIR = ROOT_DIR / "markets"
REPORTS_DIR = ROOT_DIR / "reports_out"


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    # Demo mode is on automatically when no API key is configured.
    DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1" or not os.getenv("GEMINI_API_KEY")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB uploads
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Google Cloud Pub/Sub & Serverless Worker Configuration
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
    PUBSUB_TOPIC_LEADS = os.getenv("PUBSUB_TOPIC_LEADS", "investpi-leads-inbound")
    PUBSUB_TOPIC_AUDITS = os.getenv("PUBSUB_TOPIC_AUDITS", "investpi-audits-completed")
    PUBSUB_PUSH_TOKEN = os.getenv("PUBSUB_PUSH_TOKEN", "")
    PUBSUB_EMULATOR_HOST = os.getenv("PUBSUB_EMULATOR_HOST", "")
