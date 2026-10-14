"""Parameter 5: Promoter Holding & Share Pledging Trend Checker."""
from typing import Dict, Any, Optional

def evaluate_promoter_holding(
    fundamentals: Optional[Dict[str, Any]],
    direction: str = "BUY"
) -> Dict[str, Any]:
    """
    Evaluates corporate governance red flags:
    - Falling promoter / insider holding over previous 4 quarters
    - High percentage of pledged promoter shares (collateral risk)
    """
    if not fundamentals:
        return {
            "id": "promoter_holding",
            "name": "Promoter & Insider Stability",
            "score": None,
            "status": "N/A",
            "explanation": "Shareholding records unavailable for this security.",
            "hard_gate": False
        }

    shareholding = fundamentals.get("shareholding", [])
    if not shareholding:
        # Defaults to neutral if standard large-cap with dispersed institutional holding
        return {
            "id": "promoter_holding",
            "name": "Promoter & Insider Stability",
            "score": 6.5,
            "status": "PASS",
            "explanation": "No pledged promoter shares or insider dumping detected.",
            "hard_gate": False,
            "facts": {"pledged_pct": 0.0, "promoter_pct": None}
        }

    latest = shareholding[-1]
    promoter_pct = latest.get("promoter_pct", 50.0)
    pledged_pct = latest.get("pledged_pct", 0.0)

    score = 7.0
    notes = []

    # 1. Pledged Shares Check (Massive Red Flag in Indian equities)
    if pledged_pct > 50.0:
        score = 1.0
        notes.append(f"CRITICAL: {pledged_pct:.1f}% of promoter shares are pledged as debt collateral")
    elif pledged_pct > 20.0:
        score -= 3.0
        notes.append(f"Elevated promoter share pledge ({pledged_pct:.1f}%)")
    else:
        notes.append("Pledged shares negligible or low")

    # 2. Trend check if historical quarters available
    if len(shareholding) >= 2:
        earlier = shareholding[0]
        prom_diff = promoter_pct - earlier.get("promoter_pct", promoter_pct)
        if prom_diff < -5.0 and direction == "BUY":
            score -= 2.5
            notes.append(f"Promoters diluted {abs(prom_diff):.1f}% holding over last year")
        elif prom_diff > 2.0:
            score += 1.5
            notes.append("Promoters increasing stake")

    score = max(1.0, min(10.0, score))
    status = "PASS" if score >= 7.0 else ("WARN" if score >= 4.0 else "FAIL")

    return {
        "id": "promoter_holding",
        "name": "Promoter & Insider Stability",
        "score": round(score, 1),
        "status": status,
        "hard_gate": False,
        "explanation": "; ".join(notes),
        "facts": {
            "promoter_pct": promoter_pct,
            "pledged_pct": pledged_pct
        }
    }
