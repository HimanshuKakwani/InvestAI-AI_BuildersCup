"""Firestore Dataset Seeder for InvestPI.

Seeds the datasets in data/ into Firestore collections:
  - data/universe.yaml       -> investpi_config (doc: universe)
  - data/registries/*.json   -> investpi_registries
  - data/alerts/*.json       -> investpi_alerts
  - data/fundamentals/*.json -> investpi_fundamentals
"""
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict
import yaml

from app.config import ROOT_DIR

logger = logging.getLogger("InvestPI.Seeder")
DATA_DIR = ROOT_DIR / "data"


def seed_all_datasets(db, dry_run: bool = False) -> Dict[str, Any]:
    """Uploads universe, registries, alerts, and fundamentals to Firestore."""
    if db is None and not dry_run:
        logger.warning("Cannot seed Firestore: db client is None.")
        return {"error": "Firestore client is not available."}

    summary = {
        "universe_stocks": 0,
        "registries": 0,
        "alerts": 0,
        "fundamentals": 0,
        "dry_run": dry_run
    }

    try:
        # 1. Universe
        univ_path = DATA_DIR / "universe.yaml"
        if univ_path.exists():
            with open(univ_path, "r", encoding="utf-8") as f:
                univ_data = yaml.safe_load(f) or {}
            total_stocks = sum(len(stocks) for stocks in univ_data.values())
            summary["universe_stocks"] = total_stocks
            if not dry_run:
                db.collection("investpi_config").document("universe").set({
                    "markets": univ_data,
                    "total_stocks": total_stocks,
                    "version": "1.0"
                })
            logger.info(f"Seeded universe configuration ({total_stocks} stocks).")

        # 2. Regulatory Registries
        reg_dir = DATA_DIR / "registries"
        if reg_dir.exists():
            for rf in reg_dir.glob("*.json"):
                with open(rf, "r", encoding="utf-8") as f:
                    reg_data = json.load(f)
                doc_id = rf.stem
                if not dry_run:
                    db.collection("investpi_registries").document(doc_id).set({
                        "registry_id": doc_id,
                        "count": len(reg_data),
                        "records": reg_data
                    })
                summary["registries"] += 1
            logger.info(f"Seeded {summary['registries']} regulatory registries.")

        # 3. Investor Alerts
        alerts_dir = DATA_DIR / "alerts"
        if alerts_dir.exists():
            for af in alerts_dir.glob("*.json"):
                with open(af, "r", encoding="utf-8") as f:
                    alert_data = json.load(f)
                doc_id = af.stem
                if not dry_run:
                    db.collection("investpi_alerts").document(doc_id).set({
                        "alert_id": doc_id,
                        "count": len(alert_data),
                        "records": alert_data
                    })
                summary["alerts"] += 1
            logger.info(f"Seeded {summary['alerts']} investor alert lists.")

        # 4. Stock Fundamentals (Batch writes)
        fund_dir = DATA_DIR / "fundamentals"
        if fund_dir.exists():
            fund_files = list(fund_dir.glob("*.json"))
            if not dry_run:
                batch = db.batch()
                batch_count = 0
                for ff in fund_files:
                    ticker = ff.stem
                    with open(ff, "r", encoding="utf-8") as f:
                        fund_data = json.load(f)
                    doc_ref = db.collection("investpi_fundamentals").document(ticker)
                    batch.set(doc_ref, fund_data)
                    batch_count += 1
                    if batch_count >= 400:
                        batch.commit()
                        batch = db.batch()
                        batch_count = 0
                if batch_count > 0:
                    batch.commit()
            summary["fundamentals"] = len(fund_files)
            logger.info(f"Seeded {len(fund_files)} stock fundamentals.")

    except Exception as e:
        logger.error(f"Error during Firestore dataset seeding: {e}", exc_info=True)
        summary["error"] = str(e)

    return summary


def seed_all_datasets_if_needed(db) -> bool:
    """Checks if Firestore is already seeded. If not, runs automatic seeding."""
    if db is None:
        return False

    force_seed = os.getenv("FORCE_SEED_FIRESTORE", "0").lower() in ("1", "true", "yes")

    try:
        if not force_seed:
            # Check if universe doc already exists
            doc = db.collection("investpi_config").document("universe").get()
            if doc.exists:
                logger.info("Firestore datasets already seeded in 'investpi_config/universe'. Skipping startup seed.")
                return False

        logger.info("Auto-seeding Firestore datasets on startup...")
        results = seed_all_datasets(db)
        logger.info(f"Firestore auto-seeding completed: {results}")
        return True
    except Exception as e:
        logger.warning(f"Could not complete auto-seed check: {e}")
        return False
