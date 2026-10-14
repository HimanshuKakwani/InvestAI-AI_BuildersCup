"""Parameter 3: Earnings Trajectory & Growth Consistency Checker."""
from typing import Dict, Any, Optional

def evaluate_earnings_trajectory(
    fundamentals: Optional[Dict[str, Any]],
    direction: str = "BUY"
) -> Dict[str, Any]:
    """
    Evaluates whether the company's financial results (4-Quarter and 4-Year revenue/net income)
    mathematically support a bullish or breakout claim.
    """
    if not fundamentals:
        return {
            "id": "earnings_trajectory",
            "name": "Earnings Trajectory",
            "score": None,
            "status": "N/A",
            "explanation": "No financial statements available for this entity.",
            "hard_gate": False
        }

    quarterly = fundamentals.get("quarterly", [])
    annual = fundamentals.get("annual", [])

    if len(quarterly) < 2 and len(annual) < 2:
        return {
            "id": "earnings_trajectory",
            "name": "Earnings Trajectory",
            "score": None,
            "status": "N/A",
            "explanation": "Insufficient quarters/years to compute revenue or net income trajectory.",
            "hard_gate": False
        }

    # 1. Quarterly YoY or QoQ Revenue Growth
    rev_growth_q = None
    if len(quarterly) >= 2:
        q_latest = quarterly[-1].get("revenue")
        q_prev = quarterly[-2].get("revenue")
        if q_latest and q_prev and q_prev > 0:
            rev_growth_q = ((q_latest - q_prev) / q_prev) * 100.0

    # 2. Annual Multi-Year Revenue Growth
    rev_growth_y = None
    if len(annual) >= 2:
        y_latest = annual[-1].get("revenue")
        y_earliest = annual[0].get("revenue")
        n_years = len(annual) - 1
        if y_latest and y_earliest and y_earliest > 0 and n_years > 0:
            rev_growth_y = (((y_latest / y_earliest) ** (1.0 / n_years)) - 1.0) * 100.0

    # 3. Net Margin or Profitability check
    latest_ni = quarterly[-1].get("net_income") if quarterly else (annual[-1].get("net_income") if annual else None)

    # Scoring logic
    score = 6.0
    notes = []

    if rev_growth_q is not None:
        notes.append(f"Recent QoQ Revenue: {rev_growth_q:+.1f}%")
        if rev_growth_q > 15.0:
            score += 2.0
        elif rev_growth_q < -10.0:
            score -= 2.5

    if rev_growth_y is not None:
        notes.append(f"Multi-Year CAGR: {rev_growth_y:+.1f}%")
        if rev_growth_y > 12.0:
            score += 2.0
        elif rev_growth_y < 0:
            score -= 2.0

    if latest_ni is not None:
        if latest_ni < 0 and direction == "BUY":
            score -= 2.0
            notes.append("Company is currently loss-making")
        elif latest_ni > 0:
            notes.append("Profitable operations")

    score = max(1.0, min(10.0, score))
    status = "PASS" if score >= 7.0 else ("WARN" if score >= 4.0 else "FAIL")

    return {
        "id": "earnings_trajectory",
        "name": "Earnings Trajectory",
        "score": round(score, 1),
        "status": status,
        "hard_gate": False,
        "explanation": "; ".join(notes) if notes else "Stable earnings baseline.",
        "facts": {
            "rev_growth_qoq": round(rev_growth_q, 1) if rev_growth_q is not None else None,
            "rev_growth_cagr": round(rev_growth_y, 1) if rev_growth_y is not None else None,
            "profitable": latest_ni > 0 if latest_ni is not None else None
        }
    }
