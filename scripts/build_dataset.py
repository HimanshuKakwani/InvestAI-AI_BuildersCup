"""Build the offline dataset for the stock universe.

Writes, for every ticker in data/universe.yaml:
  data/prices/<TICKER>.csv          Date, Close, Volume  (5 years, daily)
  data/fundamentals/<TICKER>.json   annual/quarterly revenue & profit, EPS, 5-yr P/E band,
                                    analyst consensus target (if available)

Source: Yahoo Finance via yfinance (prototype only; swap for bhavcopy/filings later).

Usage:
    python scripts/build_dataset.py              # all tickers
    python scripts/build_dataset.py RELIANCE.NS  # selected tickers
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRICES = DATA / "prices"
FUND = DATA / "fundamentals"
SOURCE = "Yahoo Finance (yfinance)"


def _clean(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _row(df: pd.DataFrame, *names: str) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            return df.loc[n]
    return None


def _periods(df: pd.DataFrame, n: int) -> list[dict]:
    """Return the most recent n periods (oldest first) of revenue/net income/eps."""
    if df is None or df.empty:
        return []
    rev = _row(df, "Total Revenue", "Operating Revenue")
    ni = _row(df, "Net Income", "Net Income Common Stockholders")
    eps = _row(df, "Diluted EPS", "Basic EPS")
    cols = sorted(df.columns)[-n:]
    out = []
    for c in cols:
        out.append({
            "period_end": pd.Timestamp(c).date().isoformat(),
            "revenue": _clean(rev[c]) if rev is not None else None,
            "net_income": _clean(ni[c]) if ni is not None else None,
            "eps": _clean(eps[c]) if eps is not None else None,
        })
    return out


def _pe_band(closes: pd.Series, annual: list[dict]) -> dict | None:
    """Daily P/E using the latest fiscal-year EPS available at each date."""
    eps_points = [(pd.Timestamp(a["period_end"]), a["eps"]) for a in annual if a.get("eps")]
    if not eps_points:
        return None
    eps_points.sort()
    eps_series = pd.Series({d: e for d, e in eps_points})
    idx = closes.index.tz_localize(None) if closes.index.tz is not None else closes.index
    aligned = eps_series.reindex(eps_series.index.union(idx)).sort_index().ffill().reindex(idx)
    pe = pd.Series(closes.values, index=idx) / aligned
    pe = pe[(aligned > 0) & pe.notna() & (pe > 0) & (pe < 500)]
    if len(pe) < 60:
        return None
    return {
        "min": round(float(pe.quantile(0.02)), 2),
        "median": round(float(pe.median()), 2),
        "max": round(float(pe.quantile(0.98)), 2),
        "method": "price / latest fiscal-year diluted EPS (2nd-98th percentile)",
    }


def build(ticker: str, meta: dict, market: str) -> None:
    t = yf.Ticker(ticker)
    hist = t.history(period="5y", interval="1d", auto_adjust=True)
    if hist.empty:
        print(f"  !! no price data for {ticker}")
        return
    prices = hist[["Close", "Volume"]].copy()
    prices.index = prices.index.tz_localize(None).date
    prices.index.name = "Date"
    prices.to_csv(PRICES / f"{ticker}.csv")

    try:
        annual = _periods(t.income_stmt, 4)
    except Exception as e:  # noqa: BLE001
        print(f"  ! annual statements failed: {e}")
        annual = []
    try:
        quarterly = _periods(t.quarterly_income_stmt, 5)
    except Exception as e:  # noqa: BLE001
        print(f"  ! quarterly statements failed: {e}")
        quarterly = []
    try:
        info = t.info or {}
    except Exception:  # noqa: BLE001
        info = {}

    fundamentals = {
        "ticker": ticker,
        "name": meta.get("name"),
        "market": market,
        "currency": info.get("currency"),
        "sector": info.get("sector"),
        "trailing_eps": _clean(info.get("trailingEps")),
        "forward_eps": _clean(info.get("forwardEps")),
        "market_cap": _clean(info.get("marketCap")),
        "annual": annual,
        "quarterly": quarterly,
        "pe_band_5y": _pe_band(hist["Close"], annual),
        "analyst": {
            "target_mean": _clean(info.get("targetMeanPrice")),
            "target_high": _clean(info.get("targetHighPrice")),
            "target_low": _clean(info.get("targetLowPrice")),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey"),
        },
        "source": SOURCE,
        "as_of": date.today().isoformat(),
    }
    with open(FUND / f"{ticker}.json", "w", encoding="utf-8") as f:
        json.dump(fundamentals, f, indent=2)
    print(f"  ok {ticker}: {len(prices)} days, {len(annual)}Y/{len(quarterly)}Q, "
          f"PE band={'yes' if fundamentals['pe_band_5y'] else 'no'}")


def main(selected: list[str]) -> None:
    PRICES.mkdir(parents=True, exist_ok=True)
    FUND.mkdir(parents=True, exist_ok=True)
    universe = yaml.safe_load((DATA / "universe.yaml").read_text(encoding="utf-8"))
    for market, stocks in universe.items():
        for s in stocks:
            if selected and s["ticker"] not in selected:
                continue
            print(f"[{market}] {s['ticker']}")
            try:
                build(s["ticker"], s, market)
            except Exception as e:  # noqa: BLE001
                print(f"  !! failed: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
