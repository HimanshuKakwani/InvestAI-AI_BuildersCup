"""Parameter 6: Litigation, Regulatory Orders & Enforcement Check."""
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz

def evaluate_regulatory_orders(
    ticker: str,
    company_name: str,
    alert_lists_data: List[Dict[str, Any]],
    regulator_name: str = "Regulator"
) -> Dict[str, Any]:
    """
    Checks if the targeted company or its promoters are under active regulatory ban,
    SEBI orders, MAS notices, or ASIC court enforcement.
    """
    t_clean = ticker.lower().split(".")[0]
    n_clean = company_name.lower().strip()

    for alert in alert_lists_data:
        entity = alert.get("entity_name", "").lower()
        aliases = [a.lower() for a in alert.get("aliases", [])]
        candidates = [entity] + aliases
        for cand in candidates:
            if cand and (cand in t_clean or t_clean in cand or cand in n_clean or fuzz.ratio(n_clean, cand) > 85):
                return {
                    "id": "regulatory_orders",
                    "name": "Legal & Regulatory Sanctions",
                    "score": 0.0,
                    "status": "FAIL",
                    "hard_gate": True,
                    "explanation": f"Active {regulator_name} order or enforcement ban found: {alert.get('reason', 'Market manipulation')}",
                    "facts": {"has_order": True, "details": alert.get("reason")}
                }

    return {
        "id": "regulatory_orders",
        "name": "Legal & Regulatory Sanctions",
        "score": 8.5,
        "status": "PASS",
        "hard_gate": False,
        "explanation": f"No active debarred entity orders, insider trading bans, or {regulator_name} penalties on record.",
        "facts": {"has_order": False}
    }
