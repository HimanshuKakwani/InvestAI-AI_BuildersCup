"""Seed local datasets from data/ into Firebase Firestore.

Uploads:
  1. data/universe.yaml       -> Firestore collection 'investpi_config' (doc 'universe')
  2. data/registries/*.json   -> Firestore collection 'investpi_registries'
  3. data/alerts/*.json       -> Firestore collection 'investpi_alerts'
  4. data/fundamentals/*.json -> Firestore collection 'investpi_fundamentals'

Usage:
  python scripts/seed_firestore.py
  python scripts/seed_firestore.py --dry-run
"""
import sys
import logging
from pathlib import Path

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import Config
from app.data.storage import ReportStorage
from app.data.seeder import seed_all_datasets

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("InvestPI.SeedFirestore")


def main():
    is_dry_run = "--dry-run" in sys.argv

    print("=" * 65)
    print("🔥 InvestPI Firestore Dataset Seeder")
    print(f"Target Project: {Config.FIREBASE_PROJECT_ID or 'investpi-builderscup-0000'}")
    print(f"Dry Run Mode:   {is_dry_run}")
    print("=" * 65)

    storage = ReportStorage()
    if not storage.is_firestore_connected() and not is_dry_run:
        print("\n❌ Firestore is not connected locally.")
        print("💡 To connect, run this one-time command in your terminal:")
        print("   gcloud auth application-default login\n")
        print("Or set FIREBASE_CREDENTIALS_PATH=firebase-key.json in .env.")
        sys.exit(1)

    print("\nStarting dataset seeding...")
    results = seed_all_datasets(storage.db, dry_run=is_dry_run)

    print("\n" + "=" * 65)
    if is_dry_run:
        print("🔍 Dry Run Complete! Summary:")
    else:
        print("🎉 Seeding Complete! Summary:")
    print(f"  • Curated Stocks in Universe: {results.get('universe_stocks', 0)}")
    print(f"  • Regulatory Registries:      {results.get('registries', 0)}")
    print(f"  • Investor Alert Lists:       {results.get('alerts', 0)}")
    print(f"  • Stock Fundamentals:         {results.get('fundamentals', 0)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
