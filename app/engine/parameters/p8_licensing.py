"""Parameter 8: Regulatory Licensing & Alert List Registry Matcher."""
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz

def evaluate_licensing(
    creator_name: Optional[str],
    registry_data: List[Dict[str, Any]],
    alert_lists_data: List[Dict[str, Any]],
    regulator_name: str = "Regulator",
    claimed_reg_no: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks if creator handle/name matches official registers.
    Checks if creator matches any warning/debarred entity list.
    Supports live verification against official SEBI registry (intmId=14).
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

    # 2. Local Registry Check
    for reg in registry_data:
        reg_name = reg.get("name", "").lower()
        reg_num = (reg.get("reg_number") or "").upper()
        if claimed_reg_no and claimed_reg_no.upper() == reg_num:
            return {
                "id": "licensing_check",
                "name": f"{regulator_name} Registration",
                "score": 9.5,
                "status": "PASS",
                "hard_gate": False,
                "explanation": f"Source registration confirmed: {reg.get('name')} ({reg_num}, {reg.get('entity_type', 'Licensed')}).",
                "facts": {
                    "is_registered": True,
                    "on_alert_list": False,
                    "reg_number": reg_num
                }
            }

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
                    "explanation": f"Source verified as registered entity with {regulator_name} ({reg.get('name')}, {reg.get('reg_number')}).",
                    "facts": {
                        "is_registered": True,
                        "on_alert_list": False,
                        "reg_number": reg.get("reg_number")
                    }
                }

    # 3. Live SEBI Registry Verification (for Indian Market / SEBI)
    if regulator_name.upper() == "SEBI":
        try:
            from app.data.sebi_registry import verify_sebi_creator
            sebi_res = verify_sebi_creator(
                creator_name=creator_name,
                claimed_reg_no=claimed_reg_no,
                local_registry=registry_data
            )
            if sebi_res.get("is_registered"):
                return {
                    "id": "licensing_check",
                    "name": "SEBI Registration",
                    "score": 9.5,
                    "status": "PASS",
                    "hard_gate": False,
                    "explanation": f"Source verified in official SEBI Research Analyst directory: {sebi_res.get('name')} ({sebi_res.get('reg_number')}).",
                    "facts": {
                        "is_registered": True,
                        "on_alert_list": False,
                        "reg_number": sebi_res.get("reg_number")
                    }
                }
        except Exception:
            pass

    # Creator not registered
    explanation = (
        f"Source not found in official SEBI Research Analyst directory "
        f"(https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=14). "
        f"Subject to unlicensed advice restrictions."
        if regulator_name.upper() == "SEBI"
        else f"Source not found in {regulator_name} licensing directory. Subject to unlicensed advice restrictions."
    )

    return {
        "id": "licensing_check",
        "name": f"{regulator_name} Registration",
        "score": 1.0,
        "status": "WARN",
        "hard_gate": False,
        "explanation": explanation,
        "facts": {"is_registered": False, "on_alert_list": False}
    }

