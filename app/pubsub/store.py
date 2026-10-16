"""Thread-safe Case Storage for InvestPI Asynchronous Audits."""
import threading
import time
from typing import Dict, Any, Optional, List


class CaseStatus:
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CaseStore:
    """Thread-safe in-memory store for investigation cases.
    
    Can be replaced or backed by Firestore / Cloud Spanner / Redis in production.
    """

    def __init__(self, max_cases: int = 1000):
        self._cases: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._max_cases = max_cases
        # Event listeners for Server-Sent Events (SSE)
        self._listeners: Dict[str, List[threading.Event]] = {}

    def create_case(self, case_id: str, modality: str, region: str = "IN", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            # Prevent unbounded memory growth by evicting oldest cases if needed
            if len(self._cases) >= self._max_cases:
                oldest_key = min(self._cases, key=lambda k: self._cases[k]["created_at"])
                del self._cases[oldest_key]

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
            self._cases[case_id] = record
            return record

    def update_status(self, case_id: str, status: str, message: Optional[str] = None, error: Optional[str] = None):
        with self._lock:
            if case_id in self._cases:
                self._cases[case_id]["status"] = status
                self._cases[case_id]["updated_at"] = time.time()
                if message:
                    self._cases[case_id]["progress_message"] = message
                if error:
                    self._cases[case_id]["error"] = error
        self._notify_listeners(case_id)

    def save_result(self, case_id: str, result: Dict[str, Any], is_financial: bool = True):
        with self._lock:
            if case_id in self._cases:
                self._cases[case_id]["status"] = CaseStatus.COMPLETED if is_financial else CaseStatus.REJECTED
                self._cases[case_id]["updated_at"] = time.time()
                self._cases[case_id]["progress_message"] = "Forensic audit complete" if is_financial else "Content verified: Non-financial material rejected"
                self._cases[case_id]["result"] = result
        self._notify_listeners(case_id)

    def mark_failed(self, case_id: str, error_msg: str):
        with self._lock:
            if case_id in self._cases:
                self._cases[case_id]["status"] = CaseStatus.FAILED
                self._cases[case_id]["updated_at"] = time.time()
                self._cases[case_id]["progress_message"] = "Investigation failed"
                self._cases[case_id]["error"] = error_msg
        self._notify_listeners(case_id)

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            case = self._cases.get(case_id)
            return dict(case) if case else None

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
