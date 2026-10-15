"""Tests for MarketSyncService and market-close synchronization endpoints."""
import unittest
from app.data.market_sync import MarketSyncService
from app.routes.api import create_app


class TestMarketSync(unittest.TestCase):
    def setUp(self):
        self.service = MarketSyncService()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_schedule_info_all_markets(self):
        for m in ["IN", "SG", "AU"]:
            info = self.service.get_market_schedule_info(m)
            self.assertIsNotNone(info)
            self.assertEqual(info["market"], m)
            self.assertIn("timezone", info)
            self.assertIn("sync_window_start", info)
            self.assertIn("recommended_cron_utc", info)
            self.assertIn(info["status"], ["BEFORE_MARKET_OPEN", "MARKET_OPEN_TRADING", "SETTLEMENT_PENDING", "SYNC_READY", "WEEKEND_CLOSED"])

    def test_get_all_schedules_structure(self):
        schedules = self.service.get_all_schedules("https://investpi.run.app")
        self.assertIn("markets", schedules)
        self.assertIn("cloud_scheduler_setup", schedules)
        self.assertIn("IN", schedules["markets"])
        self.assertIn("SG", schedules["markets"])
        self.assertIn("AU", schedules["markets"])
        self.assertIn("gcloud scheduler jobs create", schedules["cloud_scheduler_setup"]["IN"])

    def test_schedule_endpoint(self):
        resp = self.client.get("/api/markets/schedule")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("markets", data)
        self.assertIn("cloud_scheduler_setup", data)

    def test_sync_job_timing_validation(self):
        # Without force, outside sync window should be rejected with 400
        resp = self.client.post("/api/jobs/sync-market?market=IN")
        data = resp.get_json()
        if not data.get("schedule", {}).get("can_sync", False):
            self.assertEqual(resp.status_code, 400)
            self.assertIn(data["status"], ["rejected", "skipped"])
        else:
            self.assertEqual(resp.status_code, 200)

    def test_sync_job_force_mode(self):
        # With force=true, sync executes and returns 200
        resp = self.client.post("/api/jobs/sync-market?market=AU&force=true")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["market"], "AU")
        self.assertGreater(data["stocks_total"], 0)


if __name__ == "__main__":
    unittest.main()
