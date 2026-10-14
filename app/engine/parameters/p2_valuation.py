"""Parameter 2: Valuation-Implied Range Calculator."""
from typing import Dict, Any, Optional

def evaluate_valuation_range(
    fundamentals: Optional[Dict[str, Any]],
    current_price: Optional[float],
    target_price: Optional[float]
) -> Dict[str, Any]:
    """
    Evaluates whether the claimed target price falls within or reasonably close to
    the company's 5-year historical P/E valuation envelope.
    """
    if not fundamentals or not target_price or not current_price:
        return {
            "id": "valuation_range",
            "name": "Valuation-Implied Envelope",
            "score": None,
            "status": "N/A",
            "explanation": "Fundamental P/E band or target price not available.",
            "hard_gate": False
        }

    pe_band = fundamentals.get("pe_band_5y")
    trailing_eps = fundamentals.get("trailing_eps") or fundamentals.get("forward_eps")

    if not pe_band or not trailing_eps or trailing_eps <= 0:
        return {
            "id": "valuation_range",
            "name": "Valuation-Implied Envelope",
            "score": None,
            "status": "N/A",
            "explanation": "No positive historical EPS available to construct P/E envelope.",
            "hard_gate": False
        }

    implied_pe = target_price / trailing_eps
    pe_min = pe_band["min"]
    pe_med = pe_band["median"]
    pe_max = pe_band["max"]

    if implied_pe <= pe_max:
        # Target within historical 5-year valuation band
        score = 8.5 if implied_pe <= pe_med else 7.0
        status = "PASS"
        explanation = f"Target implies P/E of {implied_pe:.1f}x, which is within historical 5-Yr band ({pe_min:.1f}x - {pe_max:.1f}x)."
    else:
        # How far above max historical P/E?
        overshoot_ratio = (implied_pe - pe_max) / pe_max
        if overshoot_ratio > 0.8: # >80% higher than peak historical P/E
            score = 1.0
            status = "FAIL"
            explanation = f"Target implies excessive P/E of {implied_pe:.1f}x (5-Yr peak was {pe_max:.1f}x)."
        elif overshoot_ratio > 0.3:
            score = 3.5
            status = "WARN"
            explanation = f"Target implies stretched P/E of {implied_pe:.1f}x above historical peak {pe_max:.1f}x."
        else:
            score = 5.5
            status = "WARN"
            explanation = f"Target implies slightly elevated P/E of {implied_pe:.1f}x near historical peak ({pe_max:.1f}x)."

    return {
        "id": "valuation_range",
        "name": "Valuation-Implied Envelope",
        "score": score,
        "status": status,
        "hard_gate": False,
        "explanation": explanation,
        "facts": {
            "target_implied_pe": round(implied_pe, 1),
            "pe_5y_median": pe_med,
            "pe_5y_max": pe_max
        }
    }
