"""Dataset & Market Pack loader for InvestPI with live financial data integration."""
from datetime import datetime, timezone
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import yaml

from app.config import DATA_DIR, MARKETS_DIR

logger = logging.getLogger("InvestPI.DataLoader")


class DataLoader:
    def __init__(self):
        self.markets: Dict[str, Dict[str, Any]] = {}
        self.universe: Dict[str, List[Dict[str, Any]]] = {}
        self._prices_cache: Dict[str, pd.DataFrame] = {}
        self._fundamentals_cache: Dict[str, Dict[str, Any]] = {}
        self._resolution_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        self._live_price_cache: Dict[str, Any] = {}
        self._storage = None
        self._load_markets()
        self._load_universe()

    def _get_storage(self):
        if self._storage is None:
            try:
                from app.data.storage import ReportStorage
                self._storage = ReportStorage()
            except Exception:
                self._storage = False
        return self._storage if self._storage else None


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
        """
        Resolves a raw string, ticker, or company alias to an official ticker dict.
        Checks curated universe first; dynamically verifies with live exchange if unknown.
        """
        q = query.strip().upper()
        if not q or q.isdigit() or len(q) < 2:
            return None

        cache_key = f"{q}_{market_hint or ''}"
        if cache_key in self._resolution_cache:
            return self._resolution_cache[cache_key]

        # 1. Curated universe check
        for m_code, stocks in self.universe.items():
            if market_hint and m_code != market_hint:
                continue
            for s in stocks:
                if s["ticker"].upper() == q:
                    res = {**s, "market": m_code}
                    self._resolution_cache[cache_key] = res
                    return res
                if q in [a.upper() for a in s.get("aliases", [])]:
                    res = {**s, "market": m_code}
                    self._resolution_cache[cache_key] = res
                    return res
                if q in s.get("name", "").upper():
                    res = {**s, "market": m_code}
                    self._resolution_cache[cache_key] = res
                    return res

        # 2. Dynamic live ticker resolution fallback
        candidates = [q]
        if "." not in q:
            suffix = ".NS" if (market_hint == "IN" or not market_hint) else (".AX" if market_hint == "AU" else ".SI")
            candidates.append(f"{q}{suffix}")

        for cand in candidates:
            try:
                import yfinance as yf
                t = yf.Ticker(cand)
                # Check if valid ticker by fetching fast price or info
                info = t.info or {}
                name = info.get("longName") or info.get("shortName")
                if name:
                    m = "IN" if cand.endswith((".NS", ".BO")) else ("AU" if cand.endswith(".AX") else ("SG" if cand.endswith(".SI") else (market_hint or "IN")))
                    res = {
                        "ticker": cand,
                        "name": name,
                        "market": m,
                        "aliases": [q.lower()]
                    }
                    self._resolution_cache[cache_key] = res
                    return res
            except Exception:
                continue

        self._resolution_cache[cache_key] = None
        return None


    def _map_yf_ticker(self, ticker: str) -> str:
        TICKER_YFINANCE_MAP = {
            "ZOMATO.NS": "ETERNAL.NS",
            "ZOMATO.BO": "ETERNAL.BO",
            "ZOMATO": "ETERNAL.NS",
        }
        return TICKER_YFINANCE_MAP.get(ticker.upper(), ticker)

    def get_live_price(self, ticker: str) -> Optional[float]:
        """
        Returns real-time or near-real-time current market price (CMP).
        Uses a fast 10-minute (600s) intraday cache to prevent provider rate-limiting.
        """
        now = time.time()
        cached = self._live_price_cache.get(ticker)
        if cached:
            val, ts = cached
            if (now - ts) < 600:
                return val

        try:
            import yfinance as yf
            yf_ticker = self._map_yf_ticker(ticker)
            t = yf.Ticker(yf_ticker)

            price = None
            fast_info = getattr(t, "fast_info", None)
            if fast_info:
                try:
                    price = getattr(fast_info, "last_price", None) or getattr(fast_info, "previous_close", None)
                except Exception:
                    pass

            if not price:
                info = getattr(t, "info", {}) or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice")

            if price and float(price) > 0:
                float_p = round(float(price), 2)
                self._live_price_cache[ticker] = (float_p, now)
                return float_p
        except Exception as e:
            logger.debug(f"Could not fetch live tick price for {ticker}: {e}")

        # Fallback to last close in existing price history
        hist = self.get_price_history(ticker)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            fallback_val = round(float(hist["Close"].iloc[-1]), 2)
            self._live_price_cache[ticker] = (fallback_val, now)
            return fallback_val

        return None

    def get_price_history(self, ticker: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Returns 5-year daily OHLCV price history DataFrame.
        Reads from memory/cached CSV and incrementally appends only missing latest days.
        """
        df = None
        if not force_refresh and ticker in self._prices_cache:
            df = self._prices_cache[ticker]

        p_path = DATA_DIR / "prices" / f"{ticker}.csv"
        if df is None and p_path.exists():
            try:
                df = pd.read_csv(p_path, parse_dates=["Date"], index_col="Date")
            except Exception as e:
                logger.warning(f"Error reading cached prices for {ticker}: {e}")

        # If existing historical data exists, incrementally append missing days
        if df is not None and not df.empty and "Close" in df.columns:
            try:
                # Robustly extract the last date from index (handles DatetimeIndex, mixed DST timezones, and strings)
                last_idx_val = df.index[-1]
                if hasattr(last_idx_val, "date"):
                    last_dt = last_idx_val.date()
                else:
                    date_part = str(last_idx_val).split()[0]
                    last_dt = pd.to_datetime(date_part).date()

                # Fetch recent days to check for new settled trading candles (adapts to cover all missing days)
                try:
                    import yfinance as yf
                    yf_ticker = self._map_yf_ticker(ticker)
                    t = yf.Ticker(yf_ticker)

                    # Dynamically adapt fetch window so all missing dates are captured
                    today = pd.Timestamp.now().date()
                    gap_days = max((today - last_dt).days, 1)
                    if gap_days <= 5:
                        fetch_period = "5d"
                    elif gap_days <= 25:
                        fetch_period = "1mo"
                    else:
                        fetch_period = "3mo"

                    delta_df = t.history(period=fetch_period)
                    if delta_df is not None and not delta_df.empty:
                        # Drop incomplete/unsettled rows with NaN or non-positive Close/Open/High/Low
                        delta_df = delta_df.dropna(subset=["Close", "Open", "High", "Low"])
                        delta_df = delta_df[(delta_df["Close"] > 0) & (delta_df["Volume"] > 0)]

                        if not delta_df.empty:
                            if not isinstance(delta_df.index, pd.DatetimeIndex):
                                delta_df.index = pd.to_datetime(delta_df.index)

                            new_rows = delta_df[delta_df.index.date > last_dt]
                            if not new_rows.empty:
                                # Ensure timezone format matches existing CSV
                                last_str = str(df.index[-1])
                                file_has_tz = ("+" in last_str or "-" in last_str[10:])
                                if not file_has_tz and getattr(new_rows.index, "tz", None) is not None:
                                    new_rows.index = new_rows.index.tz_localize(None)

                                # Append ONLY new rows to CSV without modifying or rewriting previous rows
                                p_path.parent.mkdir(parents=True, exist_ok=True)
                                if p_path.exists():
                                    with open(p_path, "rb+") as f:
                                        f.seek(0, 2)
                                        size = f.tell()
                                        if size > 0:
                                            f.seek(size - 1)
                                            if f.read(1) not in (b"\n", b"\r"):
                                                f.write(b"\n")
                                new_rows.to_csv(p_path, mode="a", header=False)

                                # Update in-memory cache
                                df = pd.concat([df, new_rows])
                                df = df[~df.index.duplicated(keep="last")]
                                logger.info(f"Appended {len(new_rows)} settled daily candle(s) for {ticker}.")
                except Exception as e_delta:
                    logger.debug(f"Could not append delta prices for {ticker}: {e_delta}")

                self._prices_cache[ticker] = df
                return df
            except Exception as e_parse:
                logger.debug(f"Price history check issue for {ticker}: {e_parse}")
                self._prices_cache[ticker] = df
                return df

        # Full 5-year fetch if no existing history exists
        try:
            import yfinance as yf
            yf_ticker = self._map_yf_ticker(ticker)
            logger.info(f"Fetching full 5-year price history for {ticker} (yf: {yf_ticker})...")
            t = yf.Ticker(yf_ticker)
            df = t.history(period="5y")
            if df is not None and not df.empty and "Close" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                try:
                    p_path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(p_path)
                except Exception:
                    pass
                self._prices_cache[ticker] = df
                return df
        except Exception as e:
            logger.warning(f"Failed to fetch live prices for {ticker}: {e}")

        # Fallback to existing cached file even if older
        if p_path.exists():
            try:
                df = pd.read_csv(p_path, parse_dates=["Date"], index_col="Date")
                if not df.empty:
                    self._prices_cache[ticker] = df
                    return df
            except Exception:
                pass

        return None



    def get_fundamentals(self, ticker: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Returns fundamental financial metrics, valuation envelope, analyst consensus,
        and shareholding trends. Fetches live on-demand if cache is missing or stale.
        """
        if not force_refresh and ticker in self._fundamentals_cache:
            return self._fundamentals_cache[ticker]

        fallback_cloud_data = None

        # 1. Check Firebase Firestore L2 cache (shared across all Cloud Run instances)
        storage = self._get_storage()
        if storage and storage.is_firestore_connected():
            cloud_data = storage.get_fundamental(ticker)
            if cloud_data and cloud_data.get("trailing_eps") is not None:
                fallback_cloud_data = cloud_data
                if not force_refresh:
                    # Check TTL freshness (TTL = 24 hours / 86400 seconds)
                    is_fresh = True
                    updated_str = cloud_data.get("updated_at")
                    if updated_str:
                        try:
                            up_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                            if (datetime.now(timezone.utc) - up_dt).total_seconds() > 86400:
                                is_fresh = False
                        except Exception:
                            pass
                    elif cloud_data.get("as_of"):
                        try:
                            as_of_date = pd.to_datetime(cloud_data["as_of"]).date()
                            if (pd.Timestamp.now().date() - as_of_date).days >= 1:
                                is_fresh = False
                        except Exception:
                            pass

                    if is_fresh:
                        self._fundamentals_cache[ticker] = cloud_data
                        return cloud_data
                    else:
                        logger.info(f"Firestore fundamentals for {ticker} are older than 24h. Triggering live refresh...")

        f_path = DATA_DIR / "fundamentals" / f"{ticker}.json"
        now = time.time()

        # 2. Check local file cache freshness and completeness (<24h)
        if f_path.exists() and not force_refresh:
            mtime = f_path.stat().st_mtime
            if (now - mtime) < 86400:
                try:
                    with open(f_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Verify has critical fields
                    if data.get("pe_band_5y") and data.get("analyst") and (data.get("trailing_eps") is not None):
                        self._fundamentals_cache[ticker] = data
                        return data
                except Exception as e:
                    logger.warning(f"Error reading cached fundamentals for {ticker}: {e}")


        # Dynamic live fetch via yfinance
        try:
            import yfinance as yf
            yf_ticker = self._map_yf_ticker(ticker)
            logger.info(f"Fetching live fundamental data for {ticker} (yf: {yf_ticker})...")
            t = yf.Ticker(yf_ticker)
            info = t.info or {}

            trailing_eps = info.get("trailingEps")
            if trailing_eps is None:
                trailing_eps = info.get("forwardEps")
            trailing_pe = info.get("trailingPE")
            forward_eps = info.get("forwardEps")
            market_cap = info.get("marketCap")
            curr_price = info.get("currentPrice") or info.get("regularMarketPrice")

            # 1. 5-Year Historical P/E Band Envelope
            pe_band = None
            hist_df = self.get_price_history(ticker)
            if hist_df is not None and not hist_df.empty and trailing_eps and trailing_eps > 0:
                pe_series = (hist_df["Close"] / trailing_eps).dropna()
                # Exclude extreme anomalies
                pe_series = pe_series[(pe_series > 0) & (pe_series < 1000)]
                if not pe_series.empty:
                    pe_band = {
                        "min": round(float(np.percentile(pe_series, 5)), 2),
                        "median": round(float(pe_series.median()), 2),
                        "max": round(float(np.percentile(pe_series, 95)), 2),
                        "method": "5-year daily close / trailing diluted EPS (5th-95th percentile)"
                    }
            if not pe_band and trailing_pe and trailing_pe > 0:
                pe_band = {
                    "min": round(float(trailing_pe * 0.7), 2),
                    "median": round(float(trailing_pe), 2),
                    "max": round(float(trailing_pe * 1.4), 2),
                    "method": "Estimated from current live P/E baseline"
                }

            # 2. Quarterly & Annual Income Trajectory
            quarterly_list = []
            try:
                qs = t.quarterly_income_stmt
                if qs is not None and not qs.empty:
                    for col in reversed(list(qs.columns)[:8]):
                        date_str = str(col)[:10]
                        rev, ni = None, None
                        for r in ["Total Revenue", "Operating Revenue", "Revenue"]:
                            if r in qs.index and pd.notna(qs.loc[r, col]):
                                rev = float(qs.loc[r, col])
                                break
                        for r in ["Net Income", "Net Income Common Stockholders", "Normalized Income"]:
                            if r in qs.index and pd.notna(qs.loc[r, col]):
                                ni = float(qs.loc[r, col])
                                break
                        quarterly_list.append({
                            "period_end": date_str,
                            "revenue": rev,
                            "net_income": ni
                        })
            except Exception as e_q:
                logger.debug(f"Quarterly financials error for {ticker}: {e_q}")

            annual_list = []
            try:
                ans = t.income_stmt
                if ans is not None and not ans.empty:
                    for col in reversed(list(ans.columns)[:5]):
                        date_str = str(col)[:10]
                        rev, ni = None, None
                        for r in ["Total Revenue", "Operating Revenue", "Revenue"]:
                            if r in ans.index and pd.notna(ans.loc[r, col]):
                                rev = float(ans.loc[r, col])
                                break
                        for r in ["Net Income", "Net Income Common Stockholders", "Normalized Income"]:
                            if r in ans.index and pd.notna(ans.loc[r, col]):
                                ni = float(ans.loc[r, col])
                                break
                        annual_list.append({
                            "period_end": date_str,
                            "revenue": rev,
                            "net_income": ni
                        })
            except Exception as e_a:
                logger.debug(f"Annual financials error for {ticker}: {e_a}")

            # 3. Institutional Analyst Consensus
            target_mean = info.get("targetMeanPrice")
            target_high = info.get("targetHighPrice")
            target_low = info.get("targetLowPrice")
            num_analysts = info.get("numberOfAnalystOpinions") or 0
            rec = info.get("recommendationKey", "N/A")

            analyst_info = {
                "target_mean": float(target_mean) if target_mean else None,
                "target_high": float(target_high) if target_high else None,
                "target_low": float(target_low) if target_low else None,
                "num_analysts": int(num_analysts),
                "recommendation": str(rec)
            }

            # 4. Promoter & Insider Stability
            promoter_pct = round(float((info.get("heldPercentInsiders") or 0.5) * 100.0), 2)
            shareholding = [{
                "quarter": "Recent",
                "promoter_pct": promoter_pct,
                "pledged_pct": 0.0
            }]

            data = {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "market": "IN" if ticker.endswith((".NS", ".BO")) else ("AU" if ticker.endswith(".AX") else ("SG" if ticker.endswith(".SI") else "GLOBAL")),
                "currency": info.get("currency", "INR"),
                "sector": info.get("sector", "General"),
                "trailing_eps": trailing_eps,
                "forward_eps": forward_eps,
                "market_cap": market_cap,
                "current_price": curr_price,
                "annual": annual_list,
                "quarterly": quarterly_list,
                "pe_band_5y": pe_band,
                "analyst": analyst_info,
                "shareholding": shareholding,
                "source": "Yahoo Finance (yfinance live)",
                "as_of": str(pd.Timestamp.now().date())
            }

            # 1. Persist to Firebase Firestore if connected (shared across instances)
            storage = self._get_storage()
            if storage and storage.is_firestore_connected():
                storage.save_fundamental(ticker, data)

            # 2. Cache to local JSON file as fallback
            try:
                f_path.parent.mkdir(parents=True, exist_ok=True)
                with open(f_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

            self._fundamentals_cache[ticker] = data
            return data


        except Exception as e:
            logger.warning(f"Failed to fetch live fundamentals for {ticker}: {e}")

        # Fallback to existing cached file
        if f_path.exists():
            try:
                with open(f_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._fundamentals_cache[ticker] = data
                    return data
            except Exception:
                pass

        if fallback_cloud_data:
            self._fundamentals_cache[ticker] = fallback_cloud_data
            return fallback_cloud_data

        return None



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
