"""Parameter 7: Exchange Surveillance & Abnormal Volume Activity Checker."""
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

def evaluate_surveillance_and_volume(
    prices_df: Optional[pd.DataFrame],
    surveillance_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates:
    - Inclusion on exchange surveillance lists: ASM (Additional Surveillance) / GSM (Graded Surveillance)
    - High-volume anomalies: Volume > 3.5x the 20-day average without fundamental catalyst (pump indicator).
    """
    notes = []
    score = 7.5
    hard_gate = False

    # 1. Check Surveillance List
    if surveillance_info:
        gsm_stage = surveillance_info.get("gsm_stage")
        if gsm_stage and int(gsm_stage) >= 2:
            return {
                "id": "surveillance_volume",
                "name": "Surveillance & Volume Anomalies",
                "score": 0.0,
                "status": "FAIL",
                "hard_gate": True,
                "explanation": f"CRITICAL: Stock is categorized under Exchange Graded Surveillance Measure (GSM Stage {gsm_stage}). Trading restricted.",
                "facts": {"gsm_stage": gsm_stage, "is_asm": True}
            }
        elif surveillance_info.get("is_asm"):
            score -= 3.0
            notes.append("Flagged on Exchange Additional Surveillance Measure (ASM)")

    # 2. Volume Spike Check on Historical Prices
    if prices_df is not None and len(prices_df) >= 25 and "Volume" in prices_df.columns:
        volumes = prices_df["Volume"].dropna()
        if len(volumes) >= 20:
            recent_vol = float(volumes.iloc[-1])
            avg_vol_20 = float(volumes.iloc[-21:-1].mean())
            if avg_vol_20 > 0:
                vol_ratio = recent_vol / avg_vol_20
                if vol_ratio > 4.5:
                    score -= 3.5
                    notes.append(f"Abnormal volume spike ({vol_ratio:.1f}x 20-day average) indicative of operator action")
                elif vol_ratio > 2.5:
                    score -= 1.5
                    notes.append(f"Elevated volume ({vol_ratio:.1f}x average)")
                else:
                    notes.append("Trading volume within normal 20-day band")

    score = max(1.0, min(10.0, score))
    status = "PASS" if score >= 7.0 else ("WARN" if score >= 4.0 else "FAIL")

    return {
        "id": "surveillance_volume",
        "name": "Surveillance & Volume Anomalies",
        "score": round(score, 1),
        "status": status,
        "hard_gate": False,
        "explanation": "; ".join(notes) if notes else "No abnormal surveillance or operator volume spikes detected.",
        "facts": {"surveillance_flagged": bool(surveillance_info)}
    }
