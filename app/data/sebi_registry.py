"""
SEBI Research Analyst Registry Live Verification & Search Engine.
Source: https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=14
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from app.config import DATA_DIR

logger = logging.getLogger("InvestPI.SEBI")

SEBI_PORTAL_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do"
SEBI_RA_URL = f"{SEBI_PORTAL_URL}?doRecognisedFpi=yes&intmId=14"
REGISTRY_FILE = DATA_DIR / "registries" / "IN_sebi_ra_ia.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": SEBI_RA_URL
}


def search_sebi_live(
    query_name: Optional[str] = None,
    reg_no: Optional[str] = None,
    timeout: int = 8
) -> List[Dict[str, Any]]:
    """
    Directly queries SEBI's live Intermediary directory for Research Analysts.
    """
    if not query_name and not reg_no:
        return []

    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        r_init = s.get(SEBI_RA_URL, timeout=timeout)
        if r_init.status_code != 200:
            return []

        post_data = {
            "doRecognisedFpi": "yes",
            "intmId": "14",
            "nextValue": "1"
        }
        if query_name:
            post_data["name"] = query_name.strip()
        if reg_no:
            post_data["regNo"] = reg_no.strip()

        r_post = s.post(SEBI_PORTAL_URL, data=post_data, timeout=timeout)
        if r_post.status_code != 200:
            return []

        soup = BeautifulSoup(r_post.text, "html.parser")
        blocks = soup.find_all("div", class_="fixed-table-body")
        results = []
        for b in blocks:
            entry = {}
            for cv in b.find_all("div", class_="card-view"):
                t_el = cv.find("div", class_="title")
                v_el = cv.find("div", class_="value")
                if t_el and v_el:
                    entry[t_el.get_text(strip=True)] = v_el.get_text(strip=True)

            rn = entry.get("Registration No.", "").strip()
            nm = entry.get("Name", "").strip()
            if rn and nm:
                results.append({
                    "reg_number": rn,
                    "name": nm,
                    "entity_type": "Research Analyst",
                    "validity": entry.get("Validity", "").strip(),
                    "address": entry.get("Address", "").strip()
                })
        return results
    except Exception as e:
        logger.warning(f"SEBI live registry search error: {e}")
        return []


def verify_sebi_creator(
    creator_name: Optional[str],
    claimed_reg_no: Optional[str] = None,
    local_registry: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Verifies if a content creator or tip provider is an authorized SEBI-registered Research Analyst.
    Checks:
    1. Local synchronized registry cache
    2. Official SEBI live portal query (fallback / dynamic discovery)
    """
    clean_name = (creator_name or "").strip()
    clean_reg = (claimed_reg_no or "").strip().upper()

    if not clean_name and not clean_reg:
        return {
            "is_registered": False,
            "on_alert_list": False,
            "reason": "Creator identity undisclosed or anonymous"
        }

    # 1. Local / Cloud Registry Check
    candidates = local_registry or []
    if not candidates:
        try:
            from app.data.storage import ReportStorage
            storage = ReportStorage()
            cloud_reg = storage.get_registry("IN_sebi_ra_ia")
            if cloud_reg:
                candidates = cloud_reg
        except Exception:
            pass

    if not candidates and REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                candidates = json.load(f)
        except Exception:
            candidates = []


    c_lower = clean_name.lower()
    for item in candidates:
        rn = item.get("reg_number", "").upper()
        if clean_reg and rn == clean_reg:
            return {
                "is_registered": True,
                "reg_number": rn,
                "name": item.get("name"),
                "entity_type": item.get("entity_type", "Research Analyst"),
                "validity": item.get("validity", "Perpetual"),
                "source": "SEBI Official Registry (Cached)"
            }

        nm = item.get("name", "").lower()
        aliases = [a.lower() for a in item.get("aliases", [])]
        for candidate_str in [nm] + aliases:
            if candidate_str and (candidate_str in c_lower or c_lower in candidate_str or fuzz.ratio(c_lower, candidate_str) > 85):
                return {
                    "is_registered": True,
                    "reg_number": rn,
                    "name": item.get("name"),
                    "entity_type": item.get("entity_type", "Research Analyst"),
                    "validity": item.get("validity", "Perpetual"),
                    "source": "SEBI Official Registry (Cached)"
                }

    # 2. SEBI Live Portal Query Check
    live_matches = []
    if clean_reg:
        live_matches = search_sebi_live(reg_no=clean_reg)
    if not live_matches and clean_name and len(clean_name) >= 3:
        # Avoid querying generic symbols like "@" or single tokens
        search_kw = clean_name.lstrip("@").split()[0]
        if len(search_kw) >= 3:
            live_matches = search_sebi_live(query_name=search_kw)

    for match in live_matches:
        m_name = match.get("name", "").lower()
        rn = match.get("reg_number", "").upper()
        if (clean_reg and rn == clean_reg) or (c_lower in m_name or m_name in c_lower or fuzz.ratio(c_lower, m_name) > 75):
            # Cache the newly verified record
            _cache_new_sebi_entry(match)
            return {
                "is_registered": True,
                "reg_number": rn,
                "name": match.get("name"),
                "entity_type": "Research Analyst",
                "validity": match.get("validity"),
                "source": "SEBI Official Registry (Live Verified)"
            }

    return {
        "is_registered": False,
        "on_alert_list": False,
        "reason": "Not found in official SEBI Research Analyst directory"
    }


def _cache_new_sebi_entry(entry: Dict[str, Any]):
    """Appends verified entry to local cache so future queries are instant."""
    try:
        if not REGISTRY_FILE.exists():
            data = []
        else:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        reg_map = {item.get("reg_number"): item for item in data if item.get("reg_number")}
        rn = entry.get("reg_number")
        if rn and rn not in reg_map:
            name = entry.get("name", "")
            aliases = [name.lower()]
            short_name = name.lower()
            for sfx in [" private limited", " limited", " pvt ltd", " ltd", " llp", " services", " securities"]:
                short_name = short_name.replace(sfx, "")
            short_name = short_name.strip()
            if short_name and short_name not in aliases:
                aliases.append(short_name)

            new_record = {**entry, "aliases": aliases}
            data.append(new_record)
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Persist to Firestore across Cloud Run instances
            try:
                from app.data.storage import ReportStorage
                storage = ReportStorage()
                storage.append_registry_entry("IN_sebi_ra_ia", new_record)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Failed to append SEBI entry to cache: {e}")

