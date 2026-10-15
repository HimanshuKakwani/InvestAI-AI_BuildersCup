import pytest
import pandas as pd
from app.engine.parameters.p1_price_move import evaluate_price_move
from app.engine.parameters.p2_valuation import evaluate_valuation_range
from app.engine.parameters.p3_earnings import evaluate_earnings_trajectory
from app.engine.parameters.p4_analyst import evaluate_analyst_consensus
from app.engine.parameters.p5_promoter import evaluate_promoter_holding
from app.engine.parameters.p8_licensing import evaluate_licensing
from app.engine.parameters.p9_hype_language import evaluate_language_hype
from app.engine.scoring import calculate_verdict
from app.data.loader import DataLoader


def test_price_move_hard_gate():
    dates = pd.date_range("2020-01-01", periods=100)
    prices = pd.DataFrame({"Close": [100 + i * 0.1 for i in range(100)]}, index=dates)
    # Claim +200% in 5 days when historical max is < 5%
    res = evaluate_price_move(prices, 200.0, 5)
    assert res["hard_gate"] is True
    assert res["score"] == 0.0
    assert res["status"] == "FAIL"


def test_valuation_envelope_pass_and_overshoot():
    fundamentals = {
        "trailing_eps": 50.0,
        "pe_band_5y": {"min": 20.0, "median": 25.0, "max": 30.0}
    }
    # Target of 1200 implies PE = 24x (within 20x-30x) -> PASS
    res_pass = evaluate_valuation_range(fundamentals, current_price=1000.0, target_price=1200.0)
    assert res_pass["status"] == "PASS"
    assert res_pass["score"] >= 7.0

    # Target of 3000 implies PE = 60x (100% overshoot of max 30x) -> FAIL
    res_fail = evaluate_valuation_range(fundamentals, current_price=1000.0, target_price=3000.0)
    assert res_fail["status"] == "FAIL"
    assert res_fail["score"] <= 2.0


def test_earnings_trajectory_profitable_vs_loss():
    fund_profitable = {
        "quarterly": [
            {"period_end": "2025-09-30", "revenue": 100000.0, "net_income": 12000.0},
            {"period_end": "2025-12-31", "revenue": 120000.0, "net_income": 15000.0}
        ]
    }
    res_prof = evaluate_earnings_trajectory(fund_profitable, direction="BUY")
    assert res_prof["status"] == "PASS"
    assert res_prof["facts"]["profitable"] is True

    fund_loss = {
        "quarterly": [
            {"period_end": "2025-09-30", "revenue": 50000.0, "net_income": -5000.0},
            {"period_end": "2025-12-31", "revenue": 45000.0, "net_income": -8000.0}
        ]
    }
    res_loss = evaluate_earnings_trajectory(fund_loss, direction="BUY")
    assert res_loss["facts"]["profitable"] is False
    assert res_loss["score"] < res_prof["score"]


def test_analyst_consensus_alignment():
    fundamentals = {
        "analyst": {
            "target_mean": 1500.0,
            "target_high": 1700.0,
            "target_low": 1300.0,
            "num_analysts": 15,
            "recommendation": "buy"
        }
    }
    # Conservative target below mean
    res_cons = evaluate_analyst_consensus(fundamentals, target_price=1450.0, current_price=1350.0)
    assert res_cons["status"] == "PASS"
    assert res_cons["score"] >= 8.0

    # Excessive target far above highest analyst
    res_stretch = evaluate_analyst_consensus(fundamentals, target_price=3000.0, current_price=1350.0)
    assert res_stretch["status"] in ["WARN", "FAIL"]
    assert res_stretch["score"] < 5.0


def test_promoter_stability():
    # Normal promoter holding with no pledges
    fund_healthy = {
        "shareholding": [{"promoter_pct": 52.0, "pledged_pct": 0.0}]
    }
    res_h = evaluate_promoter_holding(fund_healthy, direction="BUY")
    assert res_h["status"] == "PASS"

    # Critical pledge risk (>50% shares pledged)
    fund_risky = {
        "shareholding": [{"promoter_pct": 52.0, "pledged_pct": 65.0}]
    }
    res_r = evaluate_promoter_holding(fund_risky, direction="BUY")
    assert res_r["status"] == "FAIL"
    assert res_r["score"] == 1.0


def test_sebi_licensing_verification():
    mock_registry = [
        {"name": "Motilal Oswal Financial Services Limited", "reg_number": "INH000000412", "aliases": ["motilal oswal"]}
    ]
    mock_alerts = [
        {"entity_name": "Debarred Operator Fraudster", "aliases": ["fraudster tipster"]}
    ]

    # Debarred match -> Hard gate
    res_alert = evaluate_licensing("Fraudster Tipster", mock_registry, mock_alerts, regulator_name="SEBI")
    assert res_alert["hard_gate"] is True
    assert res_alert["status"] == "FAIL"

    # Registered match -> PASS
    res_reg = evaluate_licensing("Motilal Oswal", mock_registry, mock_alerts, regulator_name="SEBI")
    assert res_reg["status"] == "PASS"
    assert res_reg["facts"]["is_registered"] is True

    # Unknown creator
    res_unreg = evaluate_licensing("RandomTelegramAdmin_99", mock_registry, mock_alerts, regulator_name="SEBI")
    assert res_unreg["facts"]["is_registered"] is False
    assert "official SEBI Research Analyst directory" in res_unreg["explanation"]


def test_hype_language_guarantee_gate():
    lexicon = {"guaranteed_return": ["sure-shot", "guaranteed"]}
    res = evaluate_language_hype("This is a sure-shot 100% gain tip!", lexicon)
    assert res["hard_gate"] is True
    assert res["score"] == 0.0


def test_verdict_hard_gate_triggers_high_risk():
    params = [
        {"name": "Price Move", "score": 0.0, "hard_gate": True, "explanation": "Exceeded max move"},
        {"name": "Valuation", "score": 8.0, "hard_gate": False, "explanation": "OK"}
    ]
    verdict = calculate_verdict(params, is_source_registered=False)
    assert verdict["flag"] == "HIGH_RISK"
    assert verdict["hard_gate_triggered"] is True


def test_dataloader_live_fetch():
    loader = DataLoader()
    # Test resolving and fetching ADANIENT.NS
    res = loader.resolve_ticker("ADANIENT", market_hint="IN")
    assert res is not None
    assert "ADANIENT.NS" in res["ticker"]

    # Verify price history
    prices = loader.get_price_history(res["ticker"])
    assert prices is not None
    assert not prices.empty
    assert "Close" in prices.columns

    # Verify fundamentals
    funds = loader.get_fundamentals(res["ticker"])
    assert funds is not None
    assert funds.get("pe_band_5y") is not None
    assert funds.get("analyst") is not None
    assert funds.get("shareholding") is not None
