"""Thread-safe Hybrid Case Storage for InvestPI Asynchronous Audits.

Provides two-tier persistence:
- L1: Fast in-memory bounded cache for sub-millisecond local reads and Server-Sent Events (SSE) notification.
- L2: Firebase Firestore persistence across Cloud Run instances and scale-to-zero restarts.
"""
import logging
import threading
import time
from typing import Dict, Any, Optional, List

from app.config import Config

logger = logging.getLogger("InvestPI.PubSub.CaseStore")


class CaseStatus:
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CaseStore:
    """Hybrid in-memory (L1) and Firebase Firestore (L2) case storage."""

    def __init__(self, max_cases: int = 1000):
        self._cases: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._max_cases = max_cases
        self._listeners: Dict[str, List[threading.Event]] = {}
        self._storage = None

    def _get_storage(self):
        """Lazy-load ReportStorage to avoid circular imports and reuse Firestore connection."""
        if self._storage is None:
            try:
                from app.data.storage import ReportStorage
                self._storage = ReportStorage()
            except Exception as e:
                logger.debug(f"Could not initialize ReportStorage for CaseStore: {e}")
                self._storage = False
        return self._storage if self._storage is not False else None

    def _get_firestore_collection(self):
        storage = self._get_storage()
        if storage and storage.is_firestore_connected():
            coll_name = getattr(Config, "FIREBASE_CASES_COLLECTION", "investpi_cases")
            return storage.db.collection(coll_name)
        return None

    def create_case(self, case_id: str, modality: str, region: str = "IN", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = time.time()
        record = {
            "case_id": case_id,
            "status": CaseStatus.QUEUED,
            "modality": modality,
            "region": region,
            "created_at": now,
            "updated_at": now,
            "progress_message": "Queued for forensic ingestion",
            "result": None,
            "error": None,
            "meta": meta or {}
        }
        with self._lock:
            if len(self._cases) >= self._max_cases:
                oldest_key = min(self._cases, key=lambda k: self._cases[k]["created_at"])
                del self._cases[oldest_key]
            self._cases[case_id] = dict(record)

        # L2: Firestore persistence
        try:
            coll = self._get_firestore_collection()
            if coll:
                coll.document(case_id).set(record)
                logger.info(f"Persisted case {case_id} [QUEUED] to Firestore.")
        except Exception as e:
            logger.warning(f"Could not persist case {case_id} to Firestore: {e}")

        return record

    def update_status(self, case_id: str, status: str, message: Optional[str] = None, error: Optional[str] = None):
        now = time.time()
        with self._lock:
            if case_id not in self._cases:
                self._cases[case_id] = {
                    "case_id": case_id,
                    "status": status,
                    "created_at": now,
                    "updated_at": now,
                    "progress_message": message or "",
                    "result": None,
                    "error": error,
                    "meta": {}
                }
            else:
                self._cases[case_id]["status"] = status
                self._cases[case_id]["updated_at"] = now
                if message:
                    self._cases[case_id]["progress_message"] = message
                if error:
                    self._cases[case_id]["error"] = error

        # L2: Firestore persistence
        try:
            coll = self._get_firestore_collection()
            if coll:
                update_fields = {"status": status, "updated_at": now}
                if message:
                    update_fields["progress_message"] = message
                if error:
                    update_fields["error"] = error
                coll.document(case_id).set(update_fields, merge=True)
                logger.info(f"Updated case {case_id} [{status}] in Firestore.")
        except Exception as e:
            logger.warning(f"Could not update case {case_id} in Firestore: {e}")

        self._notify_listeners(case_id)

    def save_result(self, case_id: str, result: Dict[str, Any], is_financial: bool = True):
        now = time.time()
        status = CaseStatus.COMPLETED if is_financial else CaseStatus.REJECTED
        msg = "Forensic audit complete" if is_financial else "Content verified: Non-financial material rejected"

        with self._lock:
            if case_id not in self._cases:
                self._cases[case_id] = {
                    "case_id": case_id,
                    "created_at": now,
                    "updated_at": now,
                    "status": status,
                    "progress_message": msg,
                    "result": result,
                    "error": None,
                    "meta": {}
                }
            else:
                self._cases[case_id]["status"] = status
                self._cases[case_id]["updated_at"] = now
                self._cases[case_id]["progress_message"] = msg
                self._cases[case_id]["result"] = result

        # L2: Firestore persistence
        try:
            coll = self._get_firestore_collection()
            if coll:
                coll.document(case_id).set({
                    "case_id": case_id,
                    "status": status,
                    "updated_at": now,
                    "progress_message": msg,
                    "result": result,
                    "error": None
                }, merge=True)
                logger.info(f"Saved case {case_id} result [{status}] to Firestore.")
        except Exception as e:
            logger.warning(f"Could not save case {case_id} result to Firestore: {e}")

        self._notify_listeners(case_id)

    def mark_failed(self, case_id: str, error_msg: str):
        now = time.time()
        with self._lock:
            if case_id in self._cases:
                self._cases[case_id]["status"] = CaseStatus.FAILED
                self._cases[case_id]["updated_at"] = now
                self._cases[case_id]["progress_message"] = "Investigation failed"
                self._cases[case_id]["error"] = error_msg
            else:
                self._cases[case_id] = {
                    "case_id": case_id,
                    "created_at": now,
                    "updated_at": now,
                    "status": CaseStatus.FAILED,
                    "progress_message": "Investigation failed",
                    "result": None,
                    "error": error_msg,
                    "meta": {}
                }

        try:
            coll = self._get_firestore_collection()
            if coll:
                coll.document(case_id).set({
                    "case_id": case_id,
                    "status": CaseStatus.FAILED,
                    "updated_at": now,
                    "progress_message": "Investigation failed",
                    "error": error_msg
                }, merge=True)
                logger.info(f"Marked case {case_id} FAILED in Firestore.")
        except Exception as e:
            logger.warning(f"Could not mark case {case_id} failed in Firestore: {e}")

        self._notify_listeners(case_id)

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        # 1. Check L1 in-memory cache
        with self._lock:
            case = self._cases.get(case_id)
            if case and case.get("status") in [CaseStatus.COMPLETED, CaseStatus.REJECTED, CaseStatus.FAILED]:
                return dict(case)

        # 2. Check L2 Firestore if missing or still in QUEUED/PROCESSING state
        # (This handles the Cloud Run multi-instance case where Instance B finished the job)
        try:
            coll = self._get_firestore_collection()
            if coll:
                doc = coll.document(case_id).get()
                if doc.exists:
                    doc_data = doc.to_dict()
                    with self._lock:
                        self._cases[case_id] = dict(doc_data)
                    return doc_data
        except Exception as e:
            logger.debug(f"Could not fetch case {case_id} from Firestore: {e}")

        with self._lock:
            c = self._cases.get(case_id)
            return dict(c) if c else None

    def register_listener(self, case_id: str, event: threading.Event):
        with self._lock:
            if case_id not in self._listeners:
                self._listeners[case_id] = []
            self._listeners[case_id].append(event)

    def unregister_listener(self, case_id: str, event: threading.Event):
        with self._lock:
            if case_id in self._listeners and event in self._listeners[case_id]:
                self._listeners[case_id].remove(event)
                if not self._listeners[case_id]:
                    del self._listeners[case_id]

    def _notify_listeners(self, case_id: str):
        with self._lock:
            listeners = list(self._listeners.get(case_id, []))
        for event in listeners:
            event.set()


# Global default instance
case_store = CaseStore()
