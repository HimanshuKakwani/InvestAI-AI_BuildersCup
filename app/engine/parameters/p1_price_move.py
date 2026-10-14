"""Parameter 1: Price-Move Plausibility Calculator."""
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

def evaluate_price_move(
    prices_df: Optional[pd.DataFrame],
    claimed_pct: Optional[float],
    horizon_days: Optional[int]
) -> Dict[str, Any]:
    """
    Evaluates whether a claimed % gain is plausible against the 5-year empirical distribution.
    If claimed move > 5-year maximum historical move -> Hard Gate Triggered, Score = 0.
    """
    if prices_df is None or prices_df.empty or claimed_pct is None or horizon_days is None:
        return {
            "id": "price_move_realism",
            "name": "Price-Move Realism",
            "score": None,
            "status": "N/A",
            "explanation": "Insufficient price history or missing time horizon to calculate historical distribution.",
            "hard_gate": False
        }

    horizon = max(int(horizon_days), 1)
    closes = prices_df["Close"].dropna()

    if len(closes) <= horizon:
        return {
            "id": "price_move_realism",
            "name": "Price-Move Realism",
            "score": None,
            "status": "N/A",
            "explanation": "Price series shorter than claimed horizon.",
            "hard_gate": False
        }

    # Calculate rolling forward returns over identical horizon
    rolling_returns = (closes.shift(-horizon) / closes - 1.0) * 100.0
    rolling_returns = rolling_returns.dropna()

    if rolling_returns.empty:
        return {
            "id": "price_move_realism",
            "name": "Price-Move Realism",
            "score": None,
            "status": "N/A",
            "explanation": "No rolling periods available.",
            "hard_gate": False
        }

    target_move = abs(float(claimed_pct))
    max_5y_move = float(rolling_returns.max())
    p95_move = float(np.percentile(rolling_returns, 95))
    median_move = float(rolling_returns.median())

    # Hard Gate Check
    if target_move > max_5y_move:
        return {
            "id": "price_move_realism",
            "name": "Price-Move Realism",
            "score": 0.0,
            "status": "FAIL",
            "hard_gate": True,
            "explanation": f"Claimed move (+{target_move:.1f}%) exceeds the stock's highest {horizon}-day move (+{max_5y_move:.1f}%) in the past 5 years.",
            "facts": {
                "claimed_pct": target_move,
                "horizon_days": horizon,
                "max_5y_move": round(max_5y_move, 1),
                "p95_move": round(p95_move, 1),
                "median_move": round(median_move, 1)
            }
        }

    # Score out of 10 based on percentile rank
    percentile = float((rolling_returns < target_move).mean() * 100.0)
    # Higher move rarity = lower confidence score
    score = float(round(max(0.0, 10.0 * (1.0 - (percentile / 100.0))), 1))

    status = "PASS" if score >= 7.0 else ("WARN" if score >= 4.0 else "FAIL")

    return {
        "id": "price_move_realism",
        "name": "Price-Move Realism",
        "score": score,
        "status": status,
        "hard_gate": False,
        "explanation": f"Claimed move (+{target_move:.1f}% in {horizon}d) is at the {percentile:.0f}th historical percentile. 5-Yr max was +{max_5y_move:.1f}%.",
        "facts": {
            "claimed_pct": target_move,
            "horizon_days": horizon,
            "max_5y_move": round(max_5y_move, 1),
            "percentile": round(percentile, 1)
        }
    }
