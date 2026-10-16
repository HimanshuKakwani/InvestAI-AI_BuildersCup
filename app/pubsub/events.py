"""Event contracts for InvestPI asynchronous Pub/Sub architecture."""
import json
import time
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List


@dataclass
class LeadSubmittedEvent:
    """Event emitted when a user or upstream webhook submits a lead for investigation."""
    case_id: str
    modality: str  # "youtube_url", "text", "screenshot", "file"
    payload: str   # URL string, text tip, or base64 data for files/images
    region: str = "IN"
    mime_type: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)
    event_type: str = "lead_submitted"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadSubmittedEvent":
        return cls(
            case_id=data.get("case_id", ""),
            modality=data.get("modality", "text"),
            payload=data.get("payload", ""),
            region=data.get("region", "IN"),
            mime_type=data.get("mime_type"),
            submitted_at=data.get("submitted_at", time.time()),
            meta=data.get("meta", {}),
            event_type=data.get("event_type", "lead_submitted")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "LeadSubmittedEvent":
        return cls.from_dict(json.loads(json_str))


@dataclass
class AuditCompletedEvent:
    """Event emitted when an investigation finishes (or fails / is rejected)."""
    case_id: str
    status: str  # "COMPLETED", "REJECTED_IRRELEVANT", "FAILED"
    completed_at: float = field(default_factory=time.time)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    event_type: str = "audit_completed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditCompletedEvent":
        return cls(
            case_id=data.get("case_id", ""),
            status=data.get("status", "COMPLETED"),
            completed_at=data.get("completed_at", time.time()),
            result=data.get("result"),
            error=data.get("error"),
            event_type=data.get("event_type", "audit_completed")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AuditCompletedEvent":
        return cls.from_dict(json.loads(json_str))


@dataclass
class StockSyncEvent:
    """Event emitted to request asynchronous fetching and Firestore caching of a stock's prices and fundamentals."""
    ticker: str
    market: str = "IN"
    force_refresh: bool = False
    triggered_at: float = field(default_factory=time.time)
    event_type: str = "stock_sync"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StockSyncEvent":
        return cls(
            ticker=data.get("ticker", ""),
            market=data.get("market", "IN"),
            force_refresh=data.get("force_refresh", False),
            triggered_at=data.get("triggered_at", time.time()),
            event_type=data.get("event_type", "stock_sync")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "StockSyncEvent":
        return cls.from_dict(json.loads(json_str))


@dataclass
class MarketSyncEvent:
    """Event emitted to request asynchronous fan-out synchronization across an entire market."""
    market: str
    force_refresh: bool = False
    triggered_at: float = field(default_factory=time.time)
    event_type: str = "market_sync"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketSyncEvent":
        return cls(
            market=data.get("market", "IN"),
            force_refresh=data.get("force_refresh", False),
            triggered_at=data.get("triggered_at", time.time()),
            event_type=data.get("event_type", "market_sync")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "MarketSyncEvent":
        return cls.from_dict(json.loads(json_str))


@dataclass
class SubAgentTaskEvent:
    """Event emitted to execute or pre-warm chatbot sub-agents asynchronously via Pub/Sub."""
    task_id: str
    ticker: str
    case_id: Optional[str] = None
    market: str = "IN"
    query: str = ""
    claimed_target: Optional[float] = None
    agents_requested: List[str] = field(default_factory=lambda: [
        "historic_price_agent",
        "price_target_agent",
        "fundamentals_agent",
        "explainer_agent"
    ])
    triggered_at: float = field(default_factory=time.time)
    event_type: str = "subagent_task"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubAgentTaskEvent":
        return cls(
            task_id=data.get("task_id", ""),
            ticker=data.get("ticker", ""),
            case_id=data.get("case_id"),
            market=data.get("market", "IN"),
            query=data.get("query", ""),
            claimed_target=data.get("claimed_target"),
            agents_requested=data.get("agents_requested") or [
                "historic_price_agent",
                "price_target_agent",
                "fundamentals_agent",
                "explainer_agent"
            ],
            triggered_at=data.get("triggered_at", time.time()),
            event_type=data.get("event_type", "subagent_task")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SubAgentTaskEvent":
        return cls.from_dict(json.loads(json_str))

