"""InvestPI Deterministic Scoring Matrix & Flag Decision Engine."""
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("InvestPI.Scoring")

def calculate_verdict(
    evaluated_params: List[Dict[str, Any]],
    is_source_registered: bool = False
) -> Dict[str, Any]:
    """
    Executes the Hard Gate checks, Data Sufficiency audit, and assigns the final
    Red / Caution / Green / Not Enough Data flag.
    """
    hard_gates_triggered = []
    valid_scores = []
    positive_count = 0

    for p in evaluated_params:
        if p.get("hard_gate"):
            hard_gates_triggered.append(f"{p['name']}: {p['explanation']}")
        
        score = p.get("score")
        if score is not None:
            valid_scores.append(score)
            if score >= 7.0:
                positive_count += 1

    # 1. Hard Gate Evaluation -> Instant 🔴 High Risk
    if hard_gates_triggered:
        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 1.0
        final_score = min(avg_score, 3.0)
        logger.warning(f"[HARD_GATE_TRIGGERED] Instant 🔴 High Risk activated! Gates: {hard_gates_triggered} | Capped Score: {final_score}")
        return {
            "flag": "HIGH_RISK",
            "flag_color": "RED",
            "flag_label": "High Risk",
            "flag_badge": "🔴",
            "score": final_score,
            "hard_gate_triggered": True,
            "hard_gate_reasons": hard_gates_triggered,
            "evaluated_count": len(valid_scores),
            "positive_ratio": round(positive_count / len(valid_scores), 2) if valid_scores else 0.0
        }

    # 2. Data Sufficiency Check -> ⚪ Not Enough Data
    # If fewer than 4 parameters could be evaluated with valid data
    if len(valid_scores) < 4:
        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0.0
        logger.info(f"[DATA_SUFFICIENCY] Fewer than 4 parameters evaluable ({len(valid_scores)} evaluated). Flag -> ⚪ NOT_ENOUGH_DATA.")
        return {
            "flag": "NOT_ENOUGH_DATA",
            "flag_color": "GRAY",
            "flag_label": "Not Enough Data",
            "flag_badge": "⚪",
            "score": avg_score,
            "hard_gate_triggered": False,
            "hard_gate_reasons": [],
            "evaluated_count": len(valid_scores),
            "positive_ratio": 0.0,
            "notice": "Fewer than required parameters evaluable for this equity; displaying neutral N/A status."
        }

    # 3. Calculate Ratio of Positive Parameters (Score >= 7.0)
    pos_ratio = positive_count / len(valid_scores)
    avg_score = round(sum(valid_scores) / len(valid_scores), 1)

    if pos_ratio < 0.40:
        flag = "HIGH_RISK"
        flag_color = "RED"
        flag_label = "High Risk"
        flag_badge = "🔴"
    elif pos_ratio <= 0.70:
        flag = "CAUTION"
        flag_color = "ORANGE"
        flag_label = "Caution"
        flag_badge = "🟠"
    else:
        # > 70% positive ratio: Source Cap rule applies!
        if is_source_registered:
            flag = "CONSISTENT"
            flag_color = "GREEN"
            flag_label = "Consistent with Public Data"
            flag_badge = "🟢"
        else:
            # Capped at Caution if source is unregistered!
            flag = "CAUTION"
            flag_color = "ORANGE"
            flag_label = "Caution (Unregistered Source)"
            flag_badge = "🟠"
            logger.info(f"[SOURCE_CAP_APPLIED] Score qualified for 🟢 CONSISTENT ({round(pos_ratio*100)}% positive), but source is unregistered. Capped at 🟠 CAUTION.")

    logger.info(f"[VERDICT_DECIDED] Result: {flag_badge} {flag} | Score: {avg_score}/10 | PosRatio: {round(pos_ratio*100)}% ({positive_count}/{len(valid_scores)})")

    return {
        "flag": flag,
        "flag_color": flag_color,
        "flag_label": flag_label,
        "flag_badge": flag_badge,
        "score": avg_score,
        "hard_gate_triggered": False,
        "hard_gate_reasons": [],
        "evaluated_count": len(valid_scores),
        "positive_ratio": round(pos_ratio, 2)
    }
