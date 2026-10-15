"""Market-Close Synchronization Engine for InvestPI.

Manages scheduled end-of-day market data refreshes across jurisdictions:
  - Validates market closing windows against timezone registries (IN, SG, AU).
  - Incrementally appends latest daily closing candles to 5-year price series.
  - Refreshes company valuation snapshots in Firestore.
  - Syncs both pre-defined universe stocks and dynamically discovered stocks.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.data.loader import DataLoader

logger = logging.getLogger("InvestPI.MarketSync")


class MarketSyncService:
    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    def get_market_schedule_info(self, market_code: str) -> Optional[Dict[str, Any]]:
        """Calculates current market status, local time, and sync readiness."""
        m_code = market_code.upper()
        m_cfg = self.loader.markets.get(m_code)
        if not m_cfg:
            return None

        sched = m_cfg.get("schedule", {})
        tz_name = sched.get("timezone", "UTC")

        try:
            tz = ZoneInfo(tz_name)
            local_now = datetime.now(tz)
        except Exception:
            tz = ZoneInfo("UTC")
            local_now = datetime.now(tz)

        weekday_idx = local_now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        is_weekend = weekday_idx >= 5

        current_time_str = local_now.strftime("%H:%M")
        trading_hours = sched.get("trading_hours", "09:00-17:00")
        parts = trading_hours.split("-")
        open_time_str = parts[0] if len(parts) > 0 else "09:00"
        close_time_str = sched.get("market_close_local", "16:00")
        sync_window_start = sched.get("sync_window_start", "16:30")

        # Determine market state
        if is_weekend:
            status = "WEEKEND_CLOSED"
            can_sync = False
        elif current_time_str < open_time_str:
            status = "BEFORE_MARKET_OPEN"
            can_sync = False
        elif open_time_str <= current_time_str < close_time_str:
            status = "MARKET_OPEN_TRADING"
            can_sync = False
        elif close_time_str <= current_time_str < sync_window_start:
            status = "SETTLEMENT_PENDING"
            can_sync = False
        else:
            status = "SYNC_READY"
            can_sync = True

        return {
            "market": m_code,
            "name": m_cfg.get("name"),
            "timezone": tz_name,
            "local_time": local_now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "current_time": current_time_str,
            "weekday": local_now.strftime("%A"),
            "trading_hours": trading_hours,
            "market_close_local": close_time_str,
            "sync_window_start": sync_window_start,
            "recommended_cron_utc": sched.get("recommended_cron_utc", "0 0 * * 1-5"),
            "status": status,
            "is_weekend": is_weekend,
            "can_sync": can_sync
        }

    def get_all_schedules(self, service_url: Optional[str] = None) -> Dict[str, Any]:
        """Returns schedule status for all onboarded markets and Cloud Scheduler commands."""
        base_url = (service_url or "https://<YOUR-CLOUD-RUN-URL>").rstrip("/")
        schedules = {}
        cron_commands = {}

        for m_code in sorted(self.loader.markets.keys()):
            info = self.get_market_schedule_info(m_code)
            if info:
                schedules[m_code] = info
                cron_utc = info["recommended_cron_utc"]
                cron_commands[m_code] = (
                    f"gcloud scheduler jobs create http sync-market-{m_code.lower()} \\\n"
                    f"  --schedule=\"{cron_utc}\" \\\n"
                    f"  --time-zone=\"UTC\" \\\n"
                    f"  --uri=\"{base_url}/api/jobs/sync-market?market={m_code}\" \\\n"
                    f"  --http-method=POST \\\n"
                    f"  --description=\"Automated end-of-day market sync for {info['name']}\""
                )

        return {
            "markets": schedules,
            "cloud_scheduler_setup": cron_commands
        }

    def sync_market(self, market_code: str, force: bool = False) -> Dict[str, Any]:
        """
        Executes end-of-day synchronization for a market.
        - Validates time window (unless force=True).
        - Increments price history with latest candles.
        - Refreshes company fundamentals in Firestore.
        """
        m_code = market_code.upper()
        sched_info = self.get_market_schedule_info(m_code)
        if not sched_info:
            return {
                "status": "error",
                "message": f"Market '{market_code}' is not an onboarded market."
            }

        if not force and not sched_info["can_sync"]:
            reason = (
                f"Market '{m_code}' is currently {sched_info['status']}. "
                f"Local time is {sched_info['current_time']} ({sched_info['timezone']}). "
                f"Settled data sync window opens at {sched_info['sync_window_start']} on trading days. "
                "Pass force=true to override for manual testing."
            )
            return {
                "status": "rejected",
                "message": reason,
                "schedule": sched_info
            }

        # 1. Collect all stocks for this market
        universe_stocks = self.loader.universe.get(m_code, [])
        tickers = [s["ticker"] for s in universe_stocks if "ticker" in s]

        # 2. Add any dynamically discovered stocks
        storage = self.loader._get_storage()
        if storage and storage.is_firestore_connected():
            try:
                docs = storage.db.collection("investpi_fundamentals").where("market", "==", m_code).stream()
                for doc in docs:
                    t = doc.id
                    if t and t not in tickers:
                        tickers.append(t)
            except Exception as e:
                logger.debug(f"Could not load Firestore dynamic stocks for {m_code}: {e}")
        else:
            # Local mode: discover any dynamically added stock JSONs in data/fundamentals/
            from app.config import DATA_DIR
            fund_dir = DATA_DIR / "fundamentals"
            if fund_dir.exists():
                for f in fund_dir.glob("*.json"):
                    stem = f.stem
                    m = "IN" if stem.endswith((".NS", ".BO")) else ("AU" if stem.endswith(".AX") else ("SG" if stem.endswith(".SI") else ""))
                    if m == m_code and stem not in tickers:
                        tickers.append(stem)

        logger.info(f"Starting end-of-day sync for {m_code}: {len(tickers)} stocks...")

        results = []
        synced_count = 0
        error_count = 0

        for ticker in tickers:
            try:
                # A. Append latest daily candle
                df = self.loader.get_price_history(ticker, force_refresh=True)
                candles_count = len(df) if df is not None and not df.empty else 0

                # B. Refresh company fundamentals
                fund = self.loader.get_fundamentals(ticker, force_refresh=True)
                fund_updated = fund is not None

                results.append({
                    "ticker": ticker,
                    "status": "synced",
                    "total_candles": candles_count,
                    "fundamentals_refreshed": fund_updated
                })
                synced_count += 1
            except Exception as e:
                logger.warning(f"Failed to sync {ticker} during market sync: {e}")
                results.append({
                    "ticker": ticker,
                    "status": "error",
                    "error": str(e)
                })
                error_count += 1

        return {
            "status": "success",
            "market": m_code,
            "market_name": sched_info["name"],
            "force_mode": force,
            "stocks_total": len(tickers),
            "stocks_synced": synced_count,
            "stocks_failed": error_count,
            "results": results,
            "schedule": sched_info
        }
