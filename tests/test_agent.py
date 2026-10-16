"""Tests for InvestPI AI Forensic Assistant Agent & Guardrails."""
import pytest
from app.routes.api import create_app
from app.agent.forensic_agent import ForensicAssistantAgent, GUARDRAIL_REJECTION_MESSAGE


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_report_context():
    return {
        "report_id": "rep_test_123",
        "resolved_stock": {
            "ticker": "COFORGE.NS",
            "company_name": "Coforge Limited"
        },
        "verdict": {
            "flag": "HIGH RISK / PROBABLE FRAUD",
            "score": 2.2,
            "summary": "Hard gate triggered: Unregistered entity promising guaranteed returns."
        },
        "current_price": 7500.0,
        "claim": {
            "target_price": 9500.0,
            "time_horizon_days": 14,
            "channel_or_author": "StockGuruTrader",
            "exact_quote": "Guaranteed 9500 in 14 days, confirmed breakout!"
        },
        "parameters": [
            {
                "parameter_id": "P1",
                "name": "Price-Move Plausibility",
                "status": "FAIL",
                "score": 0.0,
                "details": "Requires 26.6% move in 14 days, exceeding 3-sigma envelope."
            },
            {
                "parameter_id": "P8",
                "name": "Licensing Verification",
                "status": "FAIL",
                "score": 0.0,
                "details": "Unregistered creator. No SEBI registration found."
            }
        ]
    }


def test_guardrail_blocks_out_of_scope_questions(sample_report_context):
    agent = ForensicAssistantAgent()

    out_of_scope_queries = [
        "What is the capital of France?",
        "Write a Python script to reverse a linked list",
        "Can you bake a chocolate cake for me?",
        "Who won the cricket match yesterday?",
        "Tell me a funny joke",
        "What is the current price of Bitcoin?",
        "How is the weather in Mumbai today?"
    ]

    for query in out_of_scope_queries:
        reply, in_scope = agent.respond(query, report_context=sample_report_context)
        assert in_scope is False, f"Expected query '{query}' to be out of scope"
        assert reply == GUARDRAIL_REJECTION_MESSAGE, f"Expected guardrail message for '{query}', got: {reply}"


def test_in_scope_questions_allowed(sample_report_context):
    agent = ForensicAssistantAgent()

    # Scope classifier unit check across all variations
    in_scope_variations = [
        "Explain the confidence score for Coforge",
        "Why did Parameter 1 fail?",
        "Is the creator SEBI registered?",
        "What is the current market price vs target price?",
        "Why was this flagged as high risk?",
        "Explain the findings on P8"
    ]
    for q in in_scope_variations:
        assert agent.is_question_in_scope(q, sample_report_context) is True

    # Live generation test
    reply, in_scope = agent.respond("Explain the confidence score for Coforge", report_context=sample_report_context)
    assert in_scope is True
    assert reply != GUARDRAIL_REJECTION_MESSAGE
    assert len(reply) > 20


def test_api_chat_endpoint(client, sample_report_context):
    # 1. In-scope chat query
    resp = client.post(
        "/api/chat",
        json={
            "message": "Why is the confidence score so low for Coforge?",
            "context": sample_report_context
        }
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["in_scope"] is True
    assert "COFORGE.NS" in data["ticker"]
    assert "score" in data["reply"].lower()

    # 2. Out-of-scope query triggers guardrail
    resp_blocked = client.post(
        "/api/chat",
        json={
            "message": "Write a python script to solve two sum",
            "context": sample_report_context
        }
    )
    assert resp_blocked.status_code == 200
    blocked_data = resp_blocked.get_json()
    assert blocked_data["in_scope"] is False
    assert blocked_data["reply"] == GUARDRAIL_REJECTION_MESSAGE

    # 3. Missing message validation
    resp_empty = client.post("/api/chat", json={})
    assert resp_empty.status_code == 400
