"""Tests for InvestPI Google Cloud Pub/Sub Architecture & Asynchronous Workflow."""
import json
import base64
import time
import pytest
from app.routes.api import create_app
from app.pubsub.events import LeadSubmittedEvent, AuditCompletedEvent, StockSyncEvent, MarketSyncEvent
from app.pubsub.store import CaseStore, CaseStatus, case_store
from app.pubsub.consumer import handle_push_message


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_event_serialization():
    """Verify LeadSubmittedEvent and AuditCompletedEvent serialize and deserialize cleanly."""
    event = LeadSubmittedEvent(
        case_id="case-12345",
        modality="youtube_url",
        payload="https://youtube.com/watch?v=sample",
        region="IN"
    )
    json_str = event.to_json()
    reconstructed = LeadSubmittedEvent.from_json(json_str)

    assert reconstructed.case_id == "case-12345"
    assert reconstructed.modality == "youtube_url"
    assert reconstructed.payload == "https://youtube.com/watch?v=sample"
    assert reconstructed.region == "IN"

    audit_event = AuditCompletedEvent(
        case_id="case-12345",
        status=CaseStatus.COMPLETED,
        result={"ticker": "PERSISTENT.NS"}
    )
    audit_json = audit_event.to_json()
    reconstructed_audit = AuditCompletedEvent.from_json(audit_json)
    assert reconstructed_audit.status == CaseStatus.COMPLETED
    assert reconstructed_audit.result["ticker"] == "PERSISTENT.NS"


def test_case_store_lifecycle():
    """Test CaseStore state transitions."""
    store = CaseStore()
    store.create_case("case-abc", modality="text", region="IN")

    initial = store.get_case("case-abc")
    assert initial["status"] == CaseStatus.QUEUED

    store.update_status("case-abc", CaseStatus.PROCESSING, "Running audits")
    processing = store.get_case("case-abc")
    assert processing["status"] == CaseStatus.PROCESSING
    assert processing["progress_message"] == "Running audits"

    store.save_result("case-abc", {"score": 85}, is_financial=True)
    completed = store.get_case("case-abc")
    assert completed["status"] == CaseStatus.COMPLETED
    assert completed["result"]["score"] == 85


def test_async_analysis_endpoint_queued(client):
    """POST /api/analyze/async should return 202 Accepted with case tracking URLs."""
    response = client.post(
        "/api/analyze/async",
        json={
            "modality": "text",
            "payload": "Buy Coforge targets 9000 guaranteed multi-bagger return!",
            "region": "IN"
        }
    )
    assert response.status_code == 202
    data = response.get_json()
    assert "case_id" in data
    assert data["status"] == CaseStatus.QUEUED
    assert "/api/cases/" in data["status_url"]
    assert "/stream" in data["stream_url"]

    case_id = data["case_id"]

    # Allow local fallback background worker a brief moment to process
    time.sleep(1.0)
    status_resp = client.get(f"/api/cases/{case_id}")
    assert status_resp.status_code == 200
    case_data = status_resp.get_json()
    assert case_data["case_id"] == case_id
    assert case_data["status"] in [CaseStatus.QUEUED, CaseStatus.PROCESSING, CaseStatus.COMPLETED, CaseStatus.REJECTED]


def test_pubsub_push_webhook_processing(client):
    """POST /api/pubsub/push should decode base64 GCP Pub/Sub push message and process."""
    event = LeadSubmittedEvent(
        case_id="push-test-001",
        modality="text",
        payload="Persistent Systems target 6500 profit surge",
        region="IN"
    )
    raw_json_bytes = event.to_json().encode("utf-8")
    b64_data = base64.b64encode(raw_json_bytes).decode("utf-8")

    envelope = {
        "message": {
            "data": b64_data,
            "messageId": "pubsub-msg-9999",
            "publishTime": "2026-10-16T00:00:00Z"
        },
        "subscription": "projects/investpi-cloud/subscriptions/investpi-leads-sub"
    }

    # Register case beforehand so push worker can update status
    case_store.create_case("push-test-001", modality="text", region="IN")

    resp = client.post("/api/pubsub/push", json=envelope)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "acknowledged"

    # Verify case status transitioned in case_store
    final_case = case_store.get_case("push-test-001")
    assert final_case["status"] in [CaseStatus.COMPLETED, CaseStatus.REJECTED]
    assert final_case["result"] is not None


def test_pubsub_non_financial_content_rejection(client):
    """Non-financial content sent via Pub/Sub should be cleanly flagged as REJECTED."""
    event = LeadSubmittedEvent(
        case_id="push-test-non-financial",
        modality="text",
        payload="Check out the latest Italian pizza recipe with fresh mozzarella!",
        region="IN"
    )
    raw_json_bytes = event.to_json().encode("utf-8")
    b64_data = base64.b64encode(raw_json_bytes).decode("utf-8")

    envelope = {
        "message": {
            "data": b64_data,
            "messageId": "pubsub-msg-1000",
            "publishTime": "2026-10-16T00:00:00Z"
        },
        "subscription": "projects/investpi-cloud/subscriptions/investpi-leads-sub"
    }

    case_store.create_case("push-test-non-financial", modality="text", region="IN")

    resp = client.post("/api/pubsub/push", json=envelope)
    assert resp.status_code == 200

    case_data = case_store.get_case("push-test-non-financial")
    assert case_data["status"] == CaseStatus.REJECTED
    assert case_data["result"]["is_financial_advice"] is False


def test_sse_stream_endpoint(client):
    """GET /api/cases/<case_id>/stream should stream Server-Sent Events."""
    case_store.create_case("sse-test-001", modality="text", region="IN")
    case_store.save_result("sse-test-001", {"score": 90}, is_financial=True)

    resp = client.get("/api/cases/sse-test-001/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("Content-Type", "")
    content = resp.get_data(as_text=True)
    assert "data: " in content
    assert "sse-test-001" in content
    assert "COMPLETED" in content


def test_stock_sync_event_serialization():
    """Verify StockSyncEvent and MarketSyncEvent contracts serialize and deserialize cleanly."""
    sync_event = StockSyncEvent(ticker="RELIANCE.NS", market="IN", force_refresh=True)
    json_str = sync_event.to_json()
    reconstructed = StockSyncEvent.from_json(json_str)
    assert reconstructed.ticker == "RELIANCE.NS"
    assert reconstructed.market == "IN"
    assert reconstructed.force_refresh is True
    assert reconstructed.event_type == "stock_sync"

    mkt_event = MarketSyncEvent(market="SG", force_refresh=False)
    mkt_json = mkt_event.to_json()
    reconstructed_mkt = MarketSyncEvent.from_json(mkt_json)
    assert reconstructed_mkt.market == "SG"
    assert reconstructed_mkt.event_type == "market_sync"


def test_async_market_sync_endpoint(client):
    """POST /api/jobs/sync-market?market=IN&async=true should queue fan-out via Pub/Sub and return 202."""
    resp = client.post("/api/jobs/sync-market?market=IN&async=true")
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "queued"
    assert data["mode"] == "async_pubsub"
    assert data["market"] == "IN"
    assert "msg_id" in data


def test_pubsub_stock_sync_push_handling(client):
    """POST /api/pubsub/push with a stock_sync event should execute cache refresh for the stock."""
    event = StockSyncEvent(ticker="SUZLON.NS", market="IN", force_refresh=False)
    raw_json_bytes = event.to_json().encode("utf-8")
    b64_data = base64.b64encode(raw_json_bytes).decode("utf-8")

    envelope = {
        "message": {
            "data": b64_data,
            "messageId": "pubsub-sync-001",
            "attributes": {"event_type": "stock_sync"}
        }
    }
    resp = client.post("/api/pubsub/push", json=envelope)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "acknowledged"
