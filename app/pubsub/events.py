"""Event contracts for InvestPI asynchronous Pub/Sub architecture."""
import json
import time
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any


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
            meta=data.get("meta", {})
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
            error=data.get("error")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AuditCompletedEvent":
        return cls.from_dict(json.loads(json_str))
