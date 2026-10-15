"""Unit tests for ReportStorage and BoundedReportCache."""
import unittest
from app.data.storage import BoundedReportCache, ReportStorage

class TestReportStorage(unittest.TestCase):
    def test_bounded_cache_eviction(self):
        cache = BoundedReportCache(max_items=3)
        cache.set("rep1", {"val": 1})
        cache.set("rep2", {"val": 2})
        cache.set("rep3", {"val": 3})
        self.assertEqual(len(cache), 3)

        # Access rep1 so rep2 becomes oldest
        _ = cache.get("rep1")

        # Adding 4th item should evict rep2
        cache.set("rep4", {"val": 4})
        self.assertEqual(len(cache), 3)
        self.assertIn("rep1", cache)
        self.assertNotIn("rep2", cache)
        self.assertIn("rep3", cache)
        self.assertIn("rep4", cache)

    def test_report_storage_dict_interface(self):
        storage = ReportStorage(max_l1_items=5)
        storage["rep_test"] = {"data": {"verdict": {"score": 8.5}}, "chart_b64": "abc"}

        retrieved = storage.get("rep_test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["data"]["verdict"]["score"], 8.5)
        self.assertEqual(retrieved["chart_b64"], "abc")
        self.assertTrue("rep_test" in storage)

if __name__ == "__main__":
    unittest.main()
