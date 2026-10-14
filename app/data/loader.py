"""Dataset & Market Pack loader for InvestPI."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import yaml

from app.config import DATA_DIR, MARKETS_DIR

class DataLoader:
    def __init__(self):
        self.markets: Dict[str, Dict[str, Any]] = {}
        self.universe: Dict[str, List[Dict[str, Any]]] = {}
        self._load_markets()
        self._load_universe()

    def _load_markets(self):
        for yml_path in MARKETS_DIR.glob("*.yaml"):
            market_code = yml_path.stem
            with open(yml_path, "r", encoding="utf-8") as f:
                self.markets[market_code] = yaml.safe_load(f)

    def _load_universe(self):
        univ_path = DATA_DIR / "universe.yaml"
        if univ_path.exists():
            with open(univ_path, "r", encoding="utf-8") as f:
                self.universe = yaml.safe_load(f) or {}

    def get_market_config(self, market_code: str) -> Optional[Dict[str, Any]]:
        return self.markets.get(market_code)

    def resolve_ticker(self, query: str, market_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Resolves a raw string, ticker, or company alias to an official ticker dict."""
        q = query.strip().upper()
        # Direct check
        for m_code, stocks in self.universe.items():
            if market_hint and m_code != market_hint:
                continue
            for s in stocks:
                if s["ticker"].upper() == q:
                    return {**s, "market": m_code}
                if q in [a.upper() for a in s.get("aliases", [])]:
                    return {**s, "market": m_code}
                if q in s.get("name", "").upper():
                    return {**s, "market": m_code}
        return None

    def get_price_history(self, ticker: str) -> Optional[pd.DataFrame]:
        p_path = DATA_DIR / "prices" / f"{ticker}.csv"
        if not p_path.exists():
            return None
        df = pd.read_csv(p_path, parse_dates=["Date"], index_col="Date")
        return df

    def get_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        f_path = DATA_DIR / "fundamentals" / f"{ticker}.json"
        if not f_path.exists():
            return None
        with open(f_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_registry(self, rel_path: str) -> List[Dict[str, Any]]:
        reg_file = DATA_DIR / rel_path
        if not reg_file.exists():
            return []
        with open(reg_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_alerts(self, rel_path: str) -> List[Dict[str, Any]]:
        alert_file = DATA_DIR / rel_path
        if not alert_file.exists():
            return []
        with open(alert_file, "r", encoding="utf-8") as f:
            return json.load(f)
