"""Parameter 4: Institutional Analyst Consensus Alignment."""
from typing import Dict, Any, Optional

def evaluate_analyst_consensus(
    fundamentals: Optional[Dict[str, Any]],
    target_price: Optional[float],
    current_price: Optional[float]
) -> Dict[str, Any]:
    """
    Evaluates whether the claimed price target aligns with publicly tracked
    institutional analyst consensus price targets and ratings.
    """
    if not fundamentals or not target_price or not current_price:
        return {
            "id": "analyst_consensus",
            "name": "Analyst Consensus Alignment",
            "score": None,
            "status": "N/A",
            "explanation": "Missing price target or fundamental consensus data.",
            "hard_gate": False
        }

    analyst_info = fundamentals.get("analyst", {})
    target_mean = analyst_info.get("target_mean")
    target_high = analyst_info.get("target_high")
    num_analysts = analyst_info.get("num_analysts") or 0
    recommendation = analyst_info.get("recommendation", "N/A")

    if not target_mean or num_analysts == 0:
        return {
            "id": "analyst_consensus",
            "name": "Analyst Consensus Alignment",
            "score": 5.0,
            "status": "WARN",
            "explanation": "No formal institutional analyst consensus coverage tracked for this security.",
            "hard_gate": False,
            "facts": {"has_coverage": False}
        }

    # How far is claimed target from institutional consensus mean?
    deviation_from_mean = ((target_price - target_mean) / target_mean) * 100.0

    if target_price <= target_mean:
        score = 8.5
        status = "PASS"
        explanation = f"Target price ({target_price:.1f}) is conservative compared to consensus mean target ({target_mean:.1f}, {num_analysts} analysts)."
    elif target_high and target_price <= target_high:
        score = 7.0
        status = "PASS"
        explanation = f"Target price ({target_price:.1f}) is within consensus high range ({target_high:.1f}) across {num_analysts} covering analysts."
    else:
        # Target exceeds highest Wall St / Dalal St target
        overshoot_pct = ((target_price - (target_high or target_mean)) / (target_high or target_mean)) * 100.0
        if overshoot_pct > 60.0:
            score = 1.5
            status = "FAIL"
            explanation = f"Target exceeds highest institutional analyst target ({target_high or target_mean:.1f}) by {overshoot_pct:.0f}%."
        elif overshoot_pct > 25.0:
            score = 3.5
            status = "WARN"
            explanation = f"Target is significantly above highest analyst consensus target ({target_high or target_mean:.1f}) by {overshoot_pct:.0f}%."
        else:
            score = 5.5
            status = "WARN"
            explanation = f"Target is slightly above highest analyst consensus target ({target_high or target_mean:.1f}) by {overshoot_pct:.0f}%."

    return {
        "id": "analyst_consensus",
        "name": "Analyst Consensus Alignment",
        "score": score,
        "status": status,
        "hard_gate": False,
        "explanation": explanation,
        "facts": {
            "consensus_mean": round(target_mean, 1) if target_mean else None,
            "consensus_high": round(target_high, 1) if target_high else None,
            "num_analysts": num_analysts,
            "recommendation": recommendation,
            "deviation_pct": round(deviation_from_mean, 1)
        }
    }
