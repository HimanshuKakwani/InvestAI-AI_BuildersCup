"""
Syncs official SEBI Research Analysts from SEBI Portal
URL: https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=14
"""
import sys
import json
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT_DIR / "data" / "registries" / "IN_sebi_ra_ia.json"

SEBI_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do"
INTERMEDIARY_URL = f"{SEBI_URL}?doRecognisedFpi=yes&intmId=14"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": INTERMEDIARY_URL
}

def sync_sebi_analysts(max_pages: int = 5):
    print(f"Connecting to SEBI Intermediaries Registry ({INTERMEDIARY_URL})...")
    s = requests.Session()
    s.headers.update(HEADERS)
    
    try:
        r_get = s.get(INTERMEDIARY_URL, timeout=15)
        if r_get.status_code != 200:
            print(f"Failed to load initial page: HTTP {r_get.status_code}")
            return
    except Exception as e:
        print(f"Connection error: {e}")
        return

    # Load existing registry to merge
    existing = []
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    reg_map = {item.get("reg_number"): item for item in existing if item.get("reg_number")}
    print(f"Existing local records: {len(reg_map)}")

    new_count = 0
    # Page 1 is in r_get
    current_html = r_get.text
    for page_idx in range(1, max_pages + 1):
        soup = BeautifulSoup(current_html, "html.parser")
        blocks = soup.find_all("div", class_="fixed-table-body")
        print(f"Page {page_idx}: Found {len(blocks)} entries")
        
        if not blocks:
            break

        for b in blocks:
            entry = {}
            for cv in b.find_all("div", class_="card-view"):
                t_el = cv.find("div", class_="title")
                v_el = cv.find("div", class_="value")
                if t_el and v_el:
                    entry[t_el.get_text(strip=True)] = v_el.get_text(strip=True)

            reg_no = entry.get("Registration No.", "").strip()
            name = entry.get("Name", "").strip()
            if not reg_no or not name:
                continue

            # Generate smart aliases
            aliases = [name.lower()]
            short_name = name.lower()
            for suffix in [" private limited", " limited", " pvt ltd", " ltd", " llp", " services", " financial", " securities"]:
                short_name = short_name.replace(suffix, "")
            short_name = short_name.strip()
            if short_name and short_name not in aliases:
                aliases.append(short_name)

            record = {
                "reg_number": reg_no,
                "name": name,
                "entity_type": "Research Analyst",
                "validity": entry.get("Validity", "").strip(),
                "address": entry.get("Address", "").strip(),
                "aliases": aliases
            }

            if reg_no not in reg_map:
                new_count += 1
            reg_map[reg_no] = record

        # Next page request
        if page_idx < max_pages:
            try:
                time.sleep(0.5)
                r_post = s.post(
                    SEBI_URL,
                    data={"doRecognisedFpi": "yes", "intmId": "14", "nextValue": str(page_idx + 1)},
                    timeout=15
                )
                if r_post.status_code == 200:
                    current_html = r_post.text
                else:
                    break
            except Exception as e:
                print(f"Error fetching page {page_idx + 1}: {e}")
                break

    # Save merged records
    final_list = list(reg_map.values())
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2)

    print(f"Sync complete! Added {new_count} new records. Total registered analysts: {len(final_list)}")

if __name__ == "__main__":
    pages = 4
    if len(sys.argv) > 1:
        pages = int(sys.argv[1])
    sync_sebi_analysts(max_pages=pages)
