"""Parameter 9: Manipulative & Hype Language Classifier."""
from typing import Dict, Any, List

def evaluate_language_hype(
    text_content: str,
    lexicon_dict: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    Scans text or extracted transcript for prohibited guaranteed return claims,
    FOMO urgency, and operator pump terms based on the regional market pack lexicon.
    """
    if not text_content:
        return {
            "id": "hype_language",
            "name": "Manipulative & Hype Language",
            "score": 5.0,
            "status": "WARN",
            "explanation": "No text/transcript provided for linguistic inspection.",
            "hard_gate": False
        }

    lower_text = text_content.lower()
    matches = []
    hard_gate = False

    # Check guaranteed return (Triggers Hard Gate!)
    guar_terms = lexicon_dict.get("guaranteed_return", [])
    for term in guar_terms:
        if term.lower() in lower_text:
            matches.append({"term": term, "category": "GUARANTEED_RETURN"})
            hard_gate = True

    # Check other terms
    for cat in ["urgency", "operator", "hype", "paid_group_push"]:
        terms = lexicon_dict.get(cat, [])
        for term in terms:
            if term.lower() in lower_text:
                matches.append({"term": term, "category": cat.upper()})

    if hard_gate:
        return {
            "id": "hype_language",
            "name": "Manipulative & Hype Language",
            "score": 0.0,
            "status": "FAIL",
            "hard_gate": True,
            "explanation": "Prohibited guaranteed profit / zero-risk terms detected. Direct violation of securities marketing codes.",
            "facts": {"matches": matches, "hard_gate_term": matches[0]["term"]}
        }

    match_count = len(matches)
    if match_count == 0:
        score = 9.0
        status = "PASS"
        explanation = "Neutral language observed; no high-risk scam or urgency patterns detected."
    elif match_count <= 2:
        score = 4.5
        status = "WARN"
        explanation = f"Moderate hype/urgency signals detected ({', '.join([m['term'] for m in matches])})."
    else:
        score = 1.5
        status = "FAIL"
        explanation = f"Heavy use of manipulative FOMO/hype terms ({', '.join([m['term'] for m in matches[:3]])})."

    return {
        "id": "hype_language",
        "name": "Manipulative & Hype Language",
        "score": score,
        "status": status,
        "hard_gate": False,
        "explanation": explanation,
        "facts": {"match_count": match_count, "matches": matches}
    }
