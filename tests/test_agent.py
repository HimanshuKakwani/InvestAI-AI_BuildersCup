"""Tests for InvestPI AI Forensic Assistant Agent, Sub-Agents & Guardrails."""
import base64
import pytest
from app.routes.api import create_app
from app.agent.forensic_agent import ForensicAssistantAgent, GUARDRAIL_REJECTION_MESSAGE
from app.agent.subagents import (
    HistoricalPriceSubAgent,
    PriceTargetSubAgent,
    FundamentalsSubAgent,
    SimpleExplainerSubAgent,
    SubAgentCoordinator
)
from app.pubsub.events import SubAgentTaskEvent


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
            "ticker": "RELIANCE.NS",
            "company_name": "Reliance Industries Limited"
        },
        "verdict": {
            "flag": "HIGH RISK / PROBABLE FRAUD",
            "score": 2.2,
            "summary": "Hard gate triggered: Unregistered entity promising guaranteed returns."
        },
        "current_price": 1174.6,
        "claim": {
            "target_price": 2200.0,
            "time_horizon_days": 14,
            "channel_or_author": "StockGuruTrader",
            "exact_quote": "Guaranteed 2200 in 14 days, confirmed breakout!"
        },
        "parameters": [
            {
                "parameter_id": "P1",
                "name": "Price-Move Plausibility",
                "status": "FAIL",
                "score": 0.0,
                "details": "Requires 87% move in 14 days, exceeding 3-sigma envelope."
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

    # Scope classifier unit check across all variations including sub-agent triggers
    in_scope_variations = [
        "Explain the confidence score for Reliance",
        "Why did Parameter 1 fail?",
        "Is the creator SEBI registered?",
        "What is the current market price vs target price?",
        "Why was this flagged as high risk?",
        "Explain the findings on P8",
        "how was this stocks performance in last 1 months",
        "what is the 1 year return of this stock?",
        "tell me about its performance",
        "what is the predicted future price target based on analysts or ema200?",
        "show me the company fundamentals and PE ratio",
        "explain all of these in simple terms"
    ]
    for q in in_scope_variations:
        assert agent.is_question_in_scope(q, sample_report_context) is True

    # Live generation test
    reply, in_scope = agent.respond("Explain the confidence score for Reliance", report_context=sample_report_context)
    assert in_scope is True
    assert reply != GUARDRAIL_REJECTION_MESSAGE
    assert len(reply) > 20


def test_subagents_direct_execution():
    """Verify all 4 specialized sub-agents execute and return empirical metrics & sources."""
    coordinator = SubAgentCoordinator()

    # 1. Historic Price Sub-Agent
    price_res = coordinator.price_agent.run("RELIANCE.NS")
    assert price_res["agent_id"] == "historic_price_agent"
    assert price_res["status"] == "OK"
    assert "1m_pct" in price_res["returns"]
    assert "1y_pct" in price_res["returns"]
    assert "ema_200" in price_res["technicals"]
    assert len(price_res["sources"]) >= 2

    # 2. Price Target Sub-Agent (Case A: Analyst Consensus Present -> RELIANCE.NS)
    target_res_analyst = coordinator.target_agent.run("RELIANCE.NS", claimed_target=2200.0)
    assert target_res_analyst["agent_id"] == "price_target_agent"
    assert target_res_analyst["has_analyst_consensus"] is True
    assert target_res_analyst["prediction_method"] == "ANALYST_CONSENSUS_AVERAGE"
    assert target_res_analyst["predicted_target_price"] > 0
    assert target_res_analyst["ema200_model"]["ema_200_current"] > 0

    # 3. Price Target Sub-Agent (Case B: Analyst Consensus Missing -> Fallback to EMA-200 1-Month Projection)
    target_res_ema = coordinator.target_agent.run("PASHUPATI.NS", claimed_target=150.0)
    assert target_res_ema["agent_id"] == "price_target_agent"
    assert target_res_ema["has_analyst_consensus"] is False
    assert target_res_ema["prediction_method"] == "EMA200_1M_PROJECTION"
    assert target_res_ema["predicted_target_price"] == target_res_ema["ema200_model"]["ema_200_1m_predicted_price"]
    assert target_res_ema["ema200_model"]["ema_200_current"] > 0

    # 4. Fundamentals Sub-Agent
    fund_res = coordinator.fundamentals_agent.run("RELIANCE.NS")
    assert fund_res["agent_id"] == "fundamentals_agent"
    assert fund_res["status"] == "OK"
    assert fund_res["valuation"]["trailing_eps"] is not None
    assert fund_res["earnings"]["profitability_status"] == "Profitable"

    # 5. Simple Explainer Sub-Agent
    exp_res = coordinator.explainer_agent.run(
        ticker="RELIANCE.NS",
        price_data=price_res,
        target_data=target_res_analyst,
        fundamentals_data=fund_res
    )
    assert exp_res["agent_id"] == "explainer_agent"
    assert "Historic Prices" in exp_res["summary"]
    assert "Future Price Target" in exp_res["summary"]
    assert "Fundamentals" in exp_res["summary"]


def test_api_chat_and_subagent_endpoints(client, sample_report_context):
    # 1. In-scope chat query returns subagents_invoked and sources
    resp = client.post(
        "/api/chat",
        json={
            "message": "What is the predicted future price target and explain in simple terms?",
            "context": sample_report_context
        }
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["in_scope"] is True
    assert "RELIANCE.NS" in data["ticker"]
    assert "price_target_agent" in data["subagents_invoked"]
    assert "explainer_agent" in data["subagents_invoked"]
    assert len(data["sources"]) > 0

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
    assert blocked_data["subagents_invoked"] == []

    # 3. Direct synchronous sub-agents API endpoint
    sync_resp = client.get("/api/agent/subagents/PASHUPATI.NS?claimed_target=140")
    assert sync_resp.status_code == 200
    sync_data = sync_resp.get_json()
    assert sync_data["ticker"] == "PASHUPATI.NS"
    assert "historic_price_agent" in sync_data["agents"]
    assert "price_target_agent" in sync_data["agents"]
    assert "fundamentals_agent" in sync_data["agents"]
    assert "explainer_agent" in sync_data["agents"]
    assert sync_data["agents"]["price_target_agent"]["prediction_method"] == "EMA200_1M_PROJECTION"

    # 4. Pub/Sub asynchronous sub-agents API endpoint + Push Webhook
    async_resp = client.post(
        "/api/agent/subagents/async",
        json={"ticker": "RELIANCE.NS", "market": "IN", "query": "Explain everything simply"}
    )
    assert async_resp.status_code == 202
    async_data = async_resp.get_json()
    assert async_data["mode"] == "async_pubsub"
    assert "task_id" in async_data

    # Test Pub/Sub push webhook with SubAgentTaskEvent
    sub_event = SubAgentTaskEvent(
        task_id="subagent-push-001",
        ticker="RELIANCE.NS",
        market="IN",
        query="Predict future price target"
    )
    b64_payload = base64.b64encode(sub_event.to_json().encode("utf-8")).decode("utf-8")
    push_resp = client.post(
        "/api/pubsub/push",
        json={
            "message": {
                "data": b64_payload,
                "messageId": "msg-subagent-1",
                "attributes": {"event_type": "subagent_task"}
            }
        }
    )
    assert push_resp.status_code == 200
    assert push_resp.get_json()["status"] == "acknowledged"
