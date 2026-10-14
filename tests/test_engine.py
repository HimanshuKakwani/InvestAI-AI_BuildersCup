import pytest
from app.engine.parameters.p1_price_move import evaluate_price_move
from app.engine.parameters.p9_hype_language import evaluate_language_hype
from app.engine.scoring import calculate_verdict
import pandas as pd

def test_price_move_hard_gate():
    dates = pd.date_range("2020-01-01", periods=100)
    prices = pd.DataFrame({"Close": [100 + i*0.1 for i in range(100)]}, index=dates)
    # Claim +200% in 5 days when historical max is < 5%
    res = evaluate_price_move(prices, 200.0, 5)
    assert res["hard_gate"] is True
    assert res["score"] == 0.0
    assert res["status"] == "FAIL"

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
