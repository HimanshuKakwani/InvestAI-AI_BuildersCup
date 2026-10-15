"""InvestPI Report Storage Module.

Provides a hybrid storage layer:
- L1: Bounded in-memory LRU cache to eliminate memory leaks and provide sub-millisecond access.
- L2: Firebase Firestore persistence across Cloud Run instances and scale-to-zero restarts.
Falls back gracefully to L1 in-memory storage if Firebase is not configured or unavailable.
"""
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import Config

logger = logging.getLogger("InvestPI.Storage")


class BoundedReportCache:
    """In-memory bounded LRU cache preventing unbounded memory growth."""

    def __init__(self, max_items: int = 150):
        self.max_items = max_items
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def set(self, key: str, value: Dict[str, Any]):
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self.max_items:
            self._store.popitem(last=False)  # Evict oldest entry

    def get(self, key: str, default: Any = None) -> Optional[Dict[str, Any]]:
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return default

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)


class ReportStorage:
    """
    Hybrid Report Storage:
    - Reads from L1 in-memory LRU cache first.
    - If miss, queries Firebase Firestore (L2).
    - Writes to L1 memory and Firestore asynchronously/safely.
    - Implements dict-like interface for transparent backward compatibility.
    """

    def __init__(self, max_l1_items: int = 150):
        self.l1_cache = BoundedReportCache(max_items=max_l1_items)
        self.db = None
        self._firestore_available = False
        self._init_firebase()

    def _init_firebase(self):
        """Initializes Firebase Admin SDK / Firestore client if available."""
        if not getattr(Config, "USE_FIREBASE", True):
            logger.info("Firebase integration disabled for local environment (updates apply to local data/ folder).")
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred_path = getattr(Config, "FIREBASE_CREDENTIALS_PATH", "")
                project_id = getattr(Config, "FIREBASE_PROJECT_ID", "") or None

                if cred_path and Path(cred_path).exists():
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
                else:
                    # Uses Application Default Credentials (e.g. Cloud Run service account)
                    firebase_admin.initialize_app(options={"projectId": project_id} if project_id else None)

            self.db = firestore.client()
            self._firestore_available = True
            logger.info("Firebase Firestore connected successfully for multi-instance report persistence.")
        except Exception as e:
            logger.info(f"Firebase Firestore not initialized ({e}). Using in-memory bounded cache.")
            self.db = None
            self._firestore_available = False

    def is_firestore_connected(self) -> bool:
        """Returns True if Firestore is connected and active."""
        return self._firestore_available and self.db is not None

    def save_report(self, report_id: str, data: Dict[str, Any], chart_b64: Optional[str] = None):
        """Saves a report to L1 memory cache and Firebase Firestore."""
        record = {
            "data": data,
            "chart_b64": chart_b64,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        # 1. Store in L1 in-memory cache
        self.l1_cache.set(report_id, record)

        # 2. Persist to Firestore if available
        if self._firestore_available and self.db:
            try:
                collection_name = getattr(Config, "FIREBASE_COLLECTION", "investpi_reports")
                doc_ref = self.db.collection(collection_name).document(report_id)
                doc_payload = {
                    "report_id": report_id,
                    "ticker": data.get("resolved_stock", {}).get("ticker"),
                    "company_name": data.get("resolved_stock", {}).get("name"),
                    "market": data.get("resolved_stock", {}).get("market", "IN"),
                    "score": data.get("verdict", {}).get("score"),
                    "flag": data.get("verdict", {}).get("flag"),
                    "data": data,
                    "chart_b64": chart_b64,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                doc_ref.set(doc_payload)
                logger.info(f"Saved report {report_id} to Firebase Firestore [{collection_name}].")
            except Exception as e:
                logger.warning(f"Could not persist report {report_id} to Firestore: {e}")

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a report from L1 cache, or queries Firestore if not present in memory."""
        # 1. Check L1 memory
        cached = self.l1_cache.get(report_id)
        if cached:
            return cached

        # 2. Check Firestore L2
        if self._firestore_available and self.db:
            try:
                collection_name = getattr(Config, "FIREBASE_COLLECTION", "investpi_reports")
                doc = self.db.collection(collection_name).document(report_id).get()
                if doc.exists:
                    doc_data = doc.to_dict()
                    record = {
                        "data": doc_data.get("data", {}),
                        "chart_b64": doc_data.get("chart_b64"),
                        "updated_at": doc_data.get("created_at")
                    }
                    # Populate back into L1 cache for fast subsequent requests
                    self.l1_cache.set(report_id, record)
                    logger.info(f"Retrieved report {report_id} from Firebase Firestore and populated L1 cache.")
                    return record
            except Exception as e:
                logger.warning(f"Error querying Firestore for report {report_id}: {e}")

        return None

    def save_fundamental(self, ticker: str, data: Dict[str, Any]):
        """Persists company fundamentals to Firebase Firestore."""
        if self._firestore_available and self.db:
            try:
                payload = dict(data)
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.db.collection("investpi_fundamentals").document(ticker).set(payload)
                logger.info(f"Persisted fundamentals for {ticker} to Firebase Firestore.")
            except Exception as e:
                logger.warning(f"Could not persist fundamentals for {ticker} to Firestore: {e}")

    def get_fundamental(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Retrieves company fundamentals from Firebase Firestore if available."""
        if self._firestore_available and self.db:
            try:
                doc = self.db.collection("investpi_fundamentals").document(ticker).get()
                if doc.exists:
                    logger.info(f"Retrieved fundamentals for {ticker} from Firebase Firestore.")
                    return doc.to_dict()
            except Exception as e:
                logger.warning(f"Error querying Firestore fundamentals for {ticker}: {e}")
        return None

    def get_registry(self, registry_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieves verified registry entries from Firestore."""
        if self._firestore_available and self.db:
            try:
                doc = self.db.collection("investpi_registries").document(registry_id).get()
                if doc.exists:
                    return doc.to_dict().get("records", [])
            except Exception as e:
                logger.warning(f"Error reading registry {registry_id} from Firestore: {e}")
        return None

    def append_registry_entry(self, registry_id: str, entry: Dict[str, Any]):
        """Appends a newly verified entity to Firestore registry."""
        if self._firestore_available and self.db:
            try:
                doc_ref = self.db.collection("investpi_registries").document(registry_id)
                doc = doc_ref.get()
                if doc.exists:
                    existing = doc.to_dict().get("records", [])
                    # Avoid duplicate reg_number
                    rn = entry.get("reg_number")
                    if not any(r.get("reg_number") == rn for r in existing if rn):
                        existing.append(entry)
                        doc_ref.update({
                            "records": existing,
                            "count": len(existing)
                        })
                else:
                    doc_ref.set({
                        "registry_id": registry_id,
                        "count": 1,
                        "records": [entry]
                    })
                logger.info(f"Persisted newly verified registry entry {entry.get('name')} to Firestore.")
            except Exception as e:
                logger.warning(f"Could not append registry entry to Firestore: {e}")



    # Dict-like interface for backward compatibility
    def __getitem__(self, key: str) -> Dict[str, Any]:
        item = self.get_report(key)
        if item is None:
            raise KeyError(key)
        return item

    def __setitem__(self, key: str, value: Dict[str, Any]):
        data = value.get("data", value)
        chart_b64 = value.get("chart_b64")
        self.save_report(key, data, chart_b64)

    def get(self, key: str, default: Any = None) -> Optional[Dict[str, Any]]:
        item = self.get_report(key)
        return item if item is not None else default

    def __contains__(self, key: str) -> bool:
        return self.get_report(key) is not None
