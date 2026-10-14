"""Parameter 8: Regulatory Licensing & Alert List Registry Matcher."""
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz

def evaluate_licensing(
    creator_name: Optional[str],
    registry_data: List[Dict[str, Any]],
    alert_lists_data: List[Dict[str, Any]],
    regulator_name: str = "Regulator"
) -> Dict[str, Any]:
    """
    Checks if creator handle/name matches official registers.
    Checks if creator matches any warning/debarred entity list.
    """
    if not creator_name or creator_name.strip() in ["", "unknown", "none"]:
        return {
            "id": "licensing_check",
            "name": f"{regulator_name} Registration",
            "score": 0.0,
            "status": "WARN",
            "hard_gate": False,
            "explanation": f"Source handle/identity unverified or undisclosed; not registered with {regulator_name}.",
            "facts": {"is_registered": False, "on_alert_list": False}
        }

    c_clean = creator_name.lower().strip()

    # 1. Alert Lists Check (Hard Gate if matched!)
    for alert in alert_lists_data:
        entity = alert.get("entity_name", "").lower()
        aliases = [a.lower() for a in alert.get("aliases", [])]
        candidates = [entity] + aliases
        for cand in candidates:
            if cand and (cand in c_clean or c_clean in cand or fuzz.ratio(c_clean, cand) > 85):
                return {
                    "id": "licensing_check",
                    "name": f"{regulator_name} Registration",
                    "score": 0.0,
                    "status": "FAIL",
                    "hard_gate": True,
                    "explanation": f"Source matched on official {regulator_name} Warning/Debarred list ({alert.get('reason', 'Suspicious activity')}).",
                    "facts": {"is_registered": False, "on_alert_list": True}
                }

    # 2. Registry Check
    for reg in registry_data:
        reg_name = reg.get("name", "").lower()
        aliases = [a.lower() for a in reg.get("aliases", [])]
        candidates = [reg_name] + aliases
        for cand in candidates:
            if cand and (cand in c_clean or c_clean in cand or fuzz.ratio(c_clean, cand) > 82):
                return {
                    "id": "licensing_check",
                    "name": f"{regulator_name} Registration",
                    "score": 9.5,
                    "status": "PASS",
                    "hard_gate": False,
                    "explanation": f"Source verified as registered entity with {regulator_name} ({reg.get('entity_type', 'Licensed')}).",
                    "facts": {
                        "is_registered": True,
                        "on_alert_list": False,
                        "reg_number": reg.get("reg_number")
                    }
                }

    # Creator not registered
    return {
        "id": "licensing_check",
        "name": f"{regulator_name} Registration",
        "score": 1.0,
        "status": "WARN",
        "hard_gate": False,
        "explanation": f"Source not found in {regulator_name} licensing directory. Subject to unlicensed advice restrictions.",
        "facts": {"is_registered": False, "on_alert_list": False}
    }
