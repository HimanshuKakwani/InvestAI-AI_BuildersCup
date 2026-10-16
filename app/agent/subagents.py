"""Specialized Sub-Agents for the InvestPI Forensic Intelligence Chatbot.

Implements a modular, Pub/Sub-compliant multi-agent architecture inside the chatbot:
1. HistoricalPriceSubAgent (`historic_price_agent`):
   Fetches 5-year daily OHLCV candles, multi-horizon returns (1W, 1M, 3M, 6M, 1Y, 5Y),
   52-week high/low, volatility, and moving averages.
2. PriceTargetSubAgent (`price_target_agent`):
   Provides a predicted future price target using Institutional Analyst Consensus (`target_mean`).
   If analyst targets are unavailable, deterministically falls back to a 1-Month (21-trading-day)
   projection based on the 200-Day Exponential Moving Average (`EMA-200`).
3. FundamentalsSubAgent (`fundamentals_agent`):
   Retrieves company valuation multiples (EPS, P/E, 5Y P/E band, Market Cap), quarterly/annual
   revenue & net profit trajectory, and promoter shareholding / pledging metrics.
4. SimpleExplainerSubAgent (`explainer_agent`):
   Synthesizes outputs from the price, target, and fundamentals sub-agents into plain,
   jargon-free language for retail investors.
"""
import concurrent.futures
import logging
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.data.loader import DataLoader

logger = logging.getLogger("InvestPI.Agent.SubAgents")


def _currency_symbol(ticker: str, currency_code: str = "INR") -> str:
    """Resolve display currency symbol from ticker suffix or ISO currency code."""
    t_up = (ticker or "").upper()
    c_up = (currency_code or "").upper()
    if t_up.endswith(".SI") or c_up == "SGD":
        return "S$"
    if t_up.endswith(".AX") or c_up == "AUD":
        return "A$"
    if c_up == "USD":
        return "$"
    return "₹"


def _format_market_cap(market_cap: Optional[float], sym: str) -> str:
    """Format raw market cap into human-readable Crores (INR) or Billions/Millions."""
    if not market_cap or market_cap <= 0:
        return "N/A"
    if sym == "₹":
        crores = market_cap / 1e7
        if crores >= 100000:
            return f"₹{crores:,.0f} Cr (₹{market_cap / 1e12:.2f} Lakh Cr)"
        return f"₹{crores:,.2f} Cr"
    if market_cap >= 1e9:
        return f"{sym}{market_cap / 1e9:.2f}B"
    if market_cap >= 1e6:
        return f"{sym}{market_cap / 1e6:.2f}M"
    return f"{sym}{market_cap:,.0f}"


def _format_large_currency(value: Optional[float], sym: str) -> str:
    """Format revenue or net income values cleanly."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    sign = "-" if value < 0 else ""
    abs_val = abs(float(value))
    if sym == "₹":
        return f"{sign}₹{abs_val / 1e7:,.2f} Cr"
    if abs_val >= 1e9:
        return f"{sign}{sym}{abs_val / 1e9:.2f}B"
    if abs_val >= 1e6:
        return f"{sign}{sym}{abs_val / 1e6:.2f}M"
    return f"{sign}{sym}{abs_val:,.2f}"


class HistoricalPriceSubAgent:
    """Sub-Agent 1: Fetches 5-year historical OHLCV price data, returns, volatility, and technicals."""

    AGENT_ID = "historic_price_agent"
    ROLE = "Historical Price & Technical Data Sub-Agent"

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    def run(self, ticker: str, trigger_pubsub_sync_if_stale: bool = True) -> Dict[str, Any]:
        """Fetch historical prices and compute multi-horizon returns and technical baselines."""
        start_ts = time.time()
        sym = _currency_symbol(ticker)
        df = self.loader.get_price_history(ticker)

        if df is None or df.empty or "Close" not in df.columns:
            # Trigger async Pub/Sub sync so background worker populates Firestore/local cache
            if trigger_pubsub_sync_if_stale and ticker and ticker != "AUDITED_EQUITY":
                self._dispatch_pubsub_sync(ticker)
            return {
                "agent_id": self.AGENT_ID,
                "role": self.ROLE,
                "status": "NO_DATA",
                "ticker": ticker,
                "currency_symbol": sym,
                "summary": f"No historical daily price series available for {ticker}.",
                "sources": ["Yahoo Finance (yfinance)", "Firebase Firestore (investpi_prices)"],
                "latency_ms": round((time.time() - start_ts) * 1000, 2)
            }

        closes = df["Close"].dropna()
        if closes.empty:
            return {
                "agent_id": self.AGENT_ID,
                "role": self.ROLE,
                "status": "NO_DATA",
                "ticker": ticker,
                "currency_symbol": sym,
                "summary": f"Closing price series is empty for {ticker}.",
                "sources": ["Yahoo Finance (yfinance)"],
                "latency_ms": round((time.time() - start_ts) * 1000, 2)
            }

        cur_close = float(closes.iloc[-1])
        live_price = self.loader.get_live_price(ticker) or cur_close

        def _price_at_offset(days_back: int) -> float:
            idx = -days_back - 1
            if len(closes) >= abs(idx):
                return float(closes.iloc[idx])
            return float(closes.iloc[0])

        def _pct_return(cur: float, past: float) -> float:
            if past <= 0:
                return 0.0
            return round(((cur - past) / past) * 100.0, 2)

        p_1w = _price_at_offset(5)
        p_1m = _price_at_offset(21)
        p_3m = _price_at_offset(63)
        p_6m = _price_at_offset(126)
        p_1y = _price_at_offset(252)
        p_3y = _price_at_offset(756)
        p_5y = float(closes.iloc[0])

        r_1w = _pct_return(cur_close, p_1w)
        r_1m = _pct_return(cur_close, p_1m)
        r_3m = _pct_return(cur_close, p_3m)
        r_6m = _pct_return(cur_close, p_6m)
        r_1y = _pct_return(cur_close, p_1y)
        r_3y = _pct_return(cur_close, p_3y)
        r_5y = _pct_return(cur_close, p_5y)

        # 52-week & 5-year range
        tail_52w = closes.tail(252)
        high_52w = round(float(tail_52w.max()), 2)
        low_52w = round(float(tail_52w.min()), 2)
        high_5y = round(float(closes.max()), 2)
        low_5y = round(float(closes.min()), 2)

        # Moving averages
        sma_20 = round(float(closes.tail(20).mean()), 2)
        sma_50 = round(float(closes.tail(50).mean()), 2)
        ema_50 = round(float(closes.ewm(span=50, adjust=False).mean().iloc[-1]), 2)
        ema_200 = round(float(closes.ewm(span=200, adjust=False).mean().iloc[-1]), 2)

        # Volatility metrics
        daily_returns = closes.pct_change().dropna()
        daily_vol = float(daily_returns.std()) if not daily_returns.empty else 0.02
        annualized_vol_pct = round(daily_vol * np.sqrt(252) * 100.0, 2)
        monthly_vol_pct = round(daily_vol * np.sqrt(21) * 100.0, 2)

        # Volume analysis
        latest_vol = None
        avg_vol_30d = None
        vol_ratio = None
        if "Volume" in df.columns:
            vols = df["Volume"].dropna()
            if not vols.empty:
                latest_vol = int(vols.iloc[-1])
                avg_30 = float(vols.tail(30).mean())
                avg_vol_30d = int(avg_30)
                if avg_30 > 0:
                    vol_ratio = round(latest_vol / avg_30, 2)

        first_date = str(closes.index[0])[:10]
        last_date = str(closes.index[-1])[:10]

        summary_text = (
            f"[{self.ROLE}] {ticker} (Data window: {first_date} to {last_date}, {len(closes)} trading days):\n"
            f"- Current Price: {sym}{live_price:.2f} (Last Close: {sym}{cur_close:.2f})\n"
            f"- 1-Week Return: {r_1w:+.2f}% ({sym}{p_1w:.2f} -> {sym}{cur_close:.2f})\n"
            f"- 1-Month Return: {r_1m:+.2f}% ({sym}{p_1m:.2f} -> {sym}{cur_close:.2f})\n"
            f"- 3-Month Return: {r_3m:+.2f}% ({sym}{p_3m:.2f} -> {sym}{cur_close:.2f})\n"
            f"- 6-Month Return: {r_6m:+.2f}% ({sym}{p_6m:.2f} -> {sym}{cur_close:.2f})\n"
            f"- 1-Year Return: {r_1y:+.2f}% ({sym}{p_1y:.2f} -> {sym}{cur_close:.2f})\n"
            f"- 5-Year Return: {r_5y:+.2f}% ({sym}{p_5y:.2f} -> {sym}{cur_close:.2f})\n"
            f"- 52-Week Range: Low {sym}{low_52w:.2f} — High {sym}{high_52w:.2f}\n"
            f"- Moving Averages: SMA-20={sym}{sma_20:.2f}, EMA-50={sym}{ema_50:.2f}, EMA-200={sym}{ema_200:.2f}\n"
            f"- Volatility: {annualized_vol_pct:.2f}% annualized ({monthly_vol_pct:.2f}% 1-month 1-sigma)"
        )

        return {
            "agent_id": self.AGENT_ID,
            "role": self.ROLE,
            "status": "OK",
            "ticker": ticker,
            "currency_symbol": sym,
            "candle_count": len(closes),
            "first_date": first_date,
            "last_date": last_date,
            "current_price": round(live_price, 2),
            "last_close": round(cur_close, 2),
            "returns": {
                "1w_pct": r_1w,
                "1m_pct": r_1m,
                "3m_pct": r_3m,
                "6m_pct": r_6m,
                "1y_pct": r_1y,
                "3y_pct": r_3y,
                "5y_pct": r_5y
            },
            "historical_prices": {
                "1w_ago": round(p_1w, 2),
                "1m_ago": round(p_1m, 2),
                "3m_ago": round(p_3m, 2),
                "6m_ago": round(p_6m, 2),
                "1y_ago": round(p_1y, 2),
                "5y_ago": round(p_5y, 2)
            },
            "range_52w": {
                "low": low_52w,
                "high": high_52w,
                "low_5y": low_5y,
                "high_5y": high_5y
            },
            "technicals": {
                "sma_20": sma_20,
                "sma_50": sma_50,
                "ema_50": ema_50,
                "ema_200": ema_200
            },
            "volatility": {
                "daily_std_pct": round(daily_vol * 100.0, 2),
                "monthly_1sigma_pct": monthly_vol_pct,
                "annualized_vol_pct": annualized_vol_pct
            },
            "volume": {
                "latest_volume": latest_vol,
                "avg_volume_30d": avg_vol_30d,
                "volume_ratio": vol_ratio
            },
            "summary": summary_text,
            "sources": [
                "Firebase Firestore L2 Cache (collection: investpi_prices)",
                f"Local Exchange Daily Candle Store (data/prices/{ticker}.csv)",
                "Yahoo Finance Live Exchange Feed (yfinance 5Y OHLCV)"
            ],
            "latency_ms": round((time.time() - start_ts) * 1000, 2)
        }

    @staticmethod
    def _dispatch_pubsub_sync(ticker: str):
        try:
            from app.pubsub.events import StockSyncEvent
            from app.pubsub.publisher import publisher
            market = "SG" if ticker.endswith(".SI") else ("AU" if ticker.endswith(".AX") else "IN")
            publisher.publish_stock_sync(StockSyncEvent(ticker=ticker, market=market, force_refresh=False))
        except Exception as e:
            logger.debug(f"Could not trigger background StockSyncEvent for {ticker}: {e}")


class PriceTargetSubAgent:
    """
    Sub-Agent 2: Provides a predicted future price target for the stock.
    
    Primary Strategy:
      Uses the Average Target Price of Institutional Analysts (`analyst.target_mean`).
    Fallback Strategy (when analyst consensus is missing / None / 0 analysts):
      Computes the 200-Day Exponential Moving Average (`EMA-200`) and projects the
      1-month (21-trading-day) future price target along the EMA-200 trajectory.
    """

    AGENT_ID = "price_target_agent"
    ROLE = "Future Price Target & EMA-200 Forecast Sub-Agent"

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    def run(self, ticker: str, claimed_target: Optional[float] = None) -> Dict[str, Any]:
        """Compute predicted future price target via Analyst Consensus or EMA-200 1-Month Fallback."""
        start_ts = time.time()
        sym = _currency_symbol(ticker)

        df = self.loader.get_price_history(ticker)
        fund = self.loader.get_fundamentals(ticker) or {}

        cur_price = None
        if df is not None and not df.empty and "Close" in df.columns:
            cur_price = float(df["Close"].dropna().iloc[-1])
        if not cur_price:
            cur_price = fund.get("current_price") or self.loader.get_live_price(ticker) or 0.0

        # 1. Calculate EMA-200 & 1-Month (21 trading days) EMA-200 projection
        ema_200_current = None
        ema_200_1m_ago = None
        ema_200_1m_drift = 0.0
        ema_200_1m_target = None
        band_1m_low = None
        band_1m_high = None

        if df is not None and not df.empty and "Close" in df.columns:
            closes = df["Close"].dropna()
            if not closes.empty:
                ema_series = closes.ewm(span=200, adjust=False).mean()
                ema_200_current = round(float(ema_series.iloc[-1]), 2)
                if len(ema_series) >= 22:
                    ema_200_1m_ago = float(ema_series.iloc[-22])
                else:
                    ema_200_1m_ago = float(ema_series.iloc[0])

                # 21-trading-day (1-month) slope of EMA-200
                ema_200_1m_drift = round(ema_200_current - ema_200_1m_ago, 2)
                # Projected EMA-200 target for next 1 month (+21 trading days)
                ema_200_1m_target = round(max(ema_200_current + ema_200_1m_drift, 0.01), 2)

                # 1-sigma 21-day volatility envelope around the EMA-200 1-month target
                daily_ret = closes.pct_change().dropna()
                vol_21d = float(daily_ret.std() * np.sqrt(21)) if not daily_ret.empty else 0.05
                band_1m_low = round(ema_200_1m_target * (1.0 - vol_21d), 2)
                band_1m_high = round(ema_200_1m_target * (1.0 + vol_21d), 2)

        # 2. Check Institutional Analyst Consensus
        analyst = fund.get("analyst") or {}
        target_mean = analyst.get("target_mean")
        target_high = analyst.get("target_high")
        target_low = analyst.get("target_low")
        num_analysts = int(analyst.get("num_analysts") or 0)
        recommendation = analyst.get("recommendation", "N/A")

        has_analyst_consensus = bool(target_mean and float(target_mean) > 0 and num_analysts > 0)

        if has_analyst_consensus:
            predicted_price = round(float(target_mean), 2)
            method = "ANALYST_CONSENSUS_AVERAGE"
            method_label = f"Institutional Analyst Average Target ({num_analysts} Analysts)"
            horizon = "12-Month Consensus Window"
            implied_upside_pct = round(((predicted_price - cur_price) / cur_price) * 100.0, 2) if cur_price > 0 else 0.0
            ema_upside_pct = round(((ema_200_1m_target - cur_price) / cur_price) * 100.0, 2) if (cur_price > 0 and ema_200_1m_target) else 0.0

            summary_text = (
                f"[{self.ROLE}] {ticker} Price Target Forecast:\n"
                f"- Primary Prediction Method: {method_label}\n"
                f"- Predicted Target Price (Analyst Mean): {sym}{predicted_price:.2f} ({implied_upside_pct:+.2f}% vs Current Price {sym}{cur_price:.2f})\n"
                f"- Analyst Target Range: Low {sym}{float(target_low or predicted_price):.2f} — High {sym}{float(target_high or predicted_price):.2f} (Consensus Rating: {str(recommendation).upper()})\n"
                f"- Secondary Technical Baseline (EMA-200 1-Month Projection): {sym}{ema_200_1m_target or 0:.2f} "
                f"(Current EMA-200: {sym}{ema_200_current or 0:.2f}, 1M EMA-200 Drift: {ema_200_1m_drift:+.2f})"
            )
        else:
            # Fallback to EMA-200 for next 1 month
            predicted_price = ema_200_1m_target if ema_200_1m_target is not None else round(cur_price, 2)
            method = "EMA200_1M_PROJECTION"
            method_label = "EMA-200 1-Month Technical Projection (Fallback — No Institutional Analyst Coverage)"
            horizon = "Next 1 Month (21 Trading Days)"
            implied_upside_pct = round(((predicted_price - cur_price) / cur_price) * 100.0, 2) if cur_price > 0 else 0.0

            summary_text = (
                f"[{self.ROLE}] {ticker} Price Target Forecast:\n"
                f"- Institutional Analyst Coverage: Not available (0 analysts covering {ticker}).\n"
                f"- Active Fallback Method: {method_label}\n"
                f"- Current 200-Day EMA (EMA-200): {sym}{ema_200_current or 0:.2f}\n"
                f"- 1-Month EMA-200 Trajectory Drift (21 trading days): {sym}{ema_200_1m_drift:+.2f}\n"
                f"- Predicted Price for Next 1 Month (EMA-200 Based): {sym}{predicted_price:.2f} ({implied_upside_pct:+.2f}% vs Current Price {sym}{cur_price:.2f})\n"
                f"- 1-Month Expected Volatility Range (1-Sigma): {sym}{band_1m_low or predicted_price:.2f} — {sym}{band_1m_high or predicted_price:.2f}"
            )

        # Compare with influencer's claimed target if present
        claim_gap_pct = None
        if claimed_target and float(claimed_target) > 0 and predicted_price and predicted_price > 0:
            claim_gap_pct = round(((float(claimed_target) - predicted_price) / predicted_price) * 100.0, 2)
            summary_text += (
                f"\n- Divergence vs Claimed Target ({sym}{float(claimed_target):.2f}): "
                f"Claimed target is {claim_gap_pct:+.2f}% {'above' if claim_gap_pct > 0 else 'below'} the {method_label} benchmark."
            )

        return {
            "agent_id": self.AGENT_ID,
            "role": self.ROLE,
            "status": "OK",
            "ticker": ticker,
            "currency_symbol": sym,
            "current_price": round(cur_price, 2),
            "has_analyst_consensus": has_analyst_consensus,
            "prediction_method": method,
            "prediction_method_label": method_label,
            "prediction_horizon": horizon,
            "predicted_target_price": predicted_price,
            "implied_return_pct": implied_upside_pct,
            "analyst_consensus": {
                "available": has_analyst_consensus,
                "target_mean": round(float(target_mean), 2) if target_mean else None,
                "target_high": round(float(target_high), 2) if target_high else None,
                "target_low": round(float(target_low), 2) if target_low else None,
                "num_analysts": num_analysts,
                "recommendation": recommendation
            },
            "ema200_model": {
                "ema_200_current": ema_200_current,
                "ema_200_1m_ago": round(ema_200_1m_ago, 2) if ema_200_1m_ago is not None else None,
                "ema_200_1m_drift": ema_200_1m_drift,
                "ema_200_1m_predicted_price": ema_200_1m_target,
                "band_1m_low": band_1m_low,
                "band_1m_high": band_1m_high
            },
            "claimed_target_comparison": {
                "claimed_target": float(claimed_target) if claimed_target else None,
                "divergence_vs_prediction_pct": claim_gap_pct
            },
            "summary": summary_text,
            "sources": [
                "S&P / Refinitiv Institutional Analyst Consensus via Yahoo Finance (targetMeanPrice, numberOfAnalystOpinions)",
                "Firebase Firestore L2 Cache (collection: investpi_fundamentals & investpi_prices)",
                "200-Day Exponential Moving Average (EMA-200) calculated on 5-Year Exchange OHLCV Series"
            ],
            "latency_ms": round((time.time() - start_ts) * 1000, 2)
        }


class FundamentalsSubAgent:
    """Sub-Agent 3: Retrieves company valuation multiples, 5Y P/E bands, earnings trajectory, and shareholding."""

    AGENT_ID = "fundamentals_agent"
    ROLE = "Company Fundamentals & Valuation Sub-Agent"

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    def run(self, ticker: str) -> Dict[str, Any]:
        """Retrieve and analyze fundamental metrics for the given stock ticker."""
        start_ts = time.time()
        fund = self.loader.get_fundamentals(ticker)
        sym = _currency_symbol(ticker, (fund or {}).get("currency", "INR"))

        if not fund:
            return {
                "agent_id": self.AGENT_ID,
                "role": self.ROLE,
                "status": "NO_DATA",
                "ticker": ticker,
                "currency_symbol": sym,
                "summary": f"Fundamental financial statements are not currently available for {ticker}.",
                "sources": ["Firebase Firestore (investpi_fundamentals)", "Yahoo Finance (yfinance)"],
                "latency_ms": round((time.time() - start_ts) * 1000, 2)
            }

        company_name = fund.get("name", ticker)
        sector = fund.get("sector", "General")
        market_cap = fund.get("market_cap")
        market_cap_str = _format_market_cap(market_cap, sym)

        cur_price = fund.get("current_price") or self.loader.get_live_price(ticker) or 0.0
        trailing_eps = fund.get("trailing_eps")
        forward_eps = fund.get("forward_eps")

        current_pe = round(cur_price / trailing_eps, 2) if (cur_price and trailing_eps and trailing_eps > 0) else None
        forward_pe = round(cur_price / forward_eps, 2) if (cur_price and forward_eps and forward_eps > 0) else None

        pe_band = fund.get("pe_band_5y") or {}
        pe_min = pe_band.get("min")
        pe_median = pe_band.get("median")
        pe_max = pe_band.get("max")

        valuation_status = "Fairly Valued within 5-Year Historical Band"
        if current_pe is not None and pe_max and pe_min:
            if current_pe > pe_max:
                valuation_status = f"Stretched / Premium Valuation (Current P/E {current_pe}x > 5Y 95th Percentile {pe_max}x)"
            elif current_pe < pe_min:
                valuation_status = f"Discounted Valuation (Current P/E {current_pe}x < 5Y 5th Percentile {pe_min}x)"
            else:
                valuation_status = f"Within Normal 5Y Band ({pe_min}x – {pe_max}x, Median {pe_median}x)"
        elif trailing_eps is not None and trailing_eps <= 0:
            valuation_status = "Negative / Zero Trailing Earnings (Loss-Making on TTM basis)"

        # Annual revenue & profit trajectory
        annual = fund.get("annual") or []
        valid_annual = [a for a in annual if a.get("revenue") is not None or a.get("net_income") is not None]
        latest_annual = valid_annual[-1] if valid_annual else {}
        prev_annual = valid_annual[-2] if len(valid_annual) >= 2 else {}

        latest_rev = latest_annual.get("revenue")
        latest_ni = latest_annual.get("net_income")
        yoy_rev_growth = None
        yoy_ni_growth = None

        if latest_rev is not None and prev_annual.get("revenue") and prev_annual["revenue"] > 0:
            yoy_rev_growth = round(((latest_rev - prev_annual["revenue"]) / abs(prev_annual["revenue"])) * 100.0, 2)
        if latest_ni is not None and prev_annual.get("net_income") and prev_annual["net_income"] != 0:
            yoy_ni_growth = round(((latest_ni - prev_annual["net_income"]) / abs(prev_annual["net_income"])) * 100.0, 2)

        # Quarterly trajectory
        quarterly = fund.get("quarterly") or []
        valid_q = [q for q in quarterly if q.get("revenue") is not None or q.get("net_income") is not None]
        latest_q = valid_q[-1] if valid_q else {}

        # Shareholding & Promoter Pledging
        shareholding = fund.get("shareholding") or []
        latest_sh = shareholding[-1] if shareholding else {}
        promoter_pct = latest_sh.get("promoter_pct")
        pledged_pct = latest_sh.get("pledged_pct", 0.0)

        profitability = "Profitable" if (latest_ni and latest_ni > 0) or (trailing_eps and trailing_eps > 0) else "Loss-Making / Negative Earnings"

        summary_text = (
            f"[{self.ROLE}] {company_name} ({ticker}) Fundamentals:\n"
            f"- Sector: {sector} | Market Cap: {market_cap_str}\n"
            f"- Earnings Per Share (EPS): Trailing EPS={sym}{trailing_eps if trailing_eps is not None else 'N/A'}, "
            f"Forward EPS={sym}{round(forward_eps, 2) if forward_eps else 'N/A'}\n"
            f"- Valuation Multiples: Current P/E={f'{current_pe}x' if current_pe else 'N/A'}, "
            f"Forward P/E={f'{forward_pe}x' if forward_pe else 'N/A'}\n"
            f"- 5-Year Historical P/E Envelope: Min {pe_min or 'N/A'}x | Median {pe_median or 'N/A'}x | Max {pe_max or 'N/A'}x ({valuation_status})\n"
            f"- Latest Annual Financials ({latest_annual.get('period_end', 'Recent FY')}): "
            f"Revenue={_format_large_currency(latest_rev, sym)}"
            f"{f' ({yoy_rev_growth:+.2f}% YoY)' if yoy_rev_growth is not None else ''}, "
            f"Net Profit (PAT)={_format_large_currency(latest_ni, sym)}"
            f"{f' ({yoy_ni_growth:+.2f}% YoY)' if yoy_ni_growth is not None else ''} ({profitability})\n"
            f"- Latest Quarter ({latest_q.get('period_end', 'Recent Q')}): "
            f"Revenue={_format_large_currency(latest_q.get('revenue'), sym)}, "
            f"Net Profit={_format_large_currency(latest_q.get('net_income'), sym)}\n"
            f"- Ownership & Governance: Promoter/Insider Holding={promoter_pct if promoter_pct is not None else 'N/A'}%, "
            f"Pledged Shares={pledged_pct if pledged_pct is not None else 0.0}%"
        )

        return {
            "agent_id": self.AGENT_ID,
            "role": self.ROLE,
            "status": "OK",
            "ticker": ticker,
            "company_name": company_name,
            "sector": sector,
            "currency_symbol": sym,
            "market_cap": market_cap,
            "market_cap_formatted": market_cap_str,
            "valuation": {
                "current_price": round(float(cur_price), 2) if cur_price else None,
                "trailing_eps": round(float(trailing_eps), 2) if trailing_eps is not None else None,
                "forward_eps": round(float(forward_eps), 2) if forward_eps is not None else None,
                "current_pe": current_pe,
                "forward_pe": forward_pe,
                "pe_band_5y": {
                    "min": pe_min,
                    "median": pe_median,
                    "max": pe_max
                },
                "valuation_status": valuation_status
            },
            "earnings": {
                "profitability_status": profitability,
                "latest_annual_period": latest_annual.get("period_end"),
                "latest_annual_revenue": latest_rev,
                "latest_annual_revenue_formatted": _format_large_currency(latest_rev, sym),
                "latest_annual_net_income": latest_ni,
                "latest_annual_net_income_formatted": _format_large_currency(latest_ni, sym),
                "yoy_revenue_growth_pct": yoy_rev_growth,
                "yoy_net_income_growth_pct": yoy_ni_growth,
                "latest_quarter_period": latest_q.get("period_end"),
                "latest_quarter_revenue_formatted": _format_large_currency(latest_q.get("revenue"), sym),
                "latest_quarter_net_income_formatted": _format_large_currency(latest_q.get("net_income"), sym),
            },
            "ownership": {
                "promoter_holding_pct": promoter_pct,
                "pledged_pct": pledged_pct
            },
            "summary": summary_text,
            "sources": [
                "Firebase Firestore L2 Cache (collection: investpi_fundamentals)",
                f"Curated Fundamentals Snapshot (data/fundamentals/{ticker}.json)",
                "Yahoo Finance Financial Statements & Key Statistics API (yfinance)"
            ],
            "latency_ms": round((time.time() - start_ts) * 1000, 2)
        }


class SimpleExplainerSubAgent:
    """Sub-Agent 4: Translates technical outputs from the Price, Target, and Fundamentals agents into plain, simple language."""

    AGENT_ID = "explainer_agent"
    ROLE = "Plain-Language Financial Explainer Sub-Agent"

    def run(
        self,
        ticker: str,
        price_data: Dict[str, Any],
        target_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        report_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build a plain-English, jargon-free explanation of historic prices, price target forecast, and fundamentals."""
        start_ts = time.time()
        sym = price_data.get("currency_symbol") or _currency_symbol(ticker)
        company = fundamentals_data.get("company_name") or (report_context or {}).get("resolved_stock", {}).get("company_name") or ticker

        # 1. Plain-language Historic Price summary
        returns = price_data.get("returns", {})
        cur_p = price_data.get("current_price", "N/A")
        r_1m = returns.get("1m_pct", 0.0)
        r_3m = returns.get("3m_pct", 0.0)
        r_1y = returns.get("1y_pct", 0.0)
        range_52 = price_data.get("range_52w", {})
        dir_1m = "up" if r_1m >= 0 else "down"
        dir_1y = "gained" if r_1y >= 0 else "dropped"

        simple_price = (
            f"**1. How the Stock Has Performed (Historic Prices):**\n"
            f"{company} ({ticker}) is currently trading at **{sym}{cur_p}**. "
            f"Over the last 1 month, the stock moved **{dir_1m} by {abs(r_1m):.2f}%** (3-month change: **{r_3m:+.2f}%**), "
            f"and over the past 1 year it has **{dir_1y} {abs(r_1y):.2f}%**. "
            f"During the last 52 weeks, its price stayed between a low of **{sym}{range_52.get('low', 'N/A')}** and a high of **{sym}{range_52.get('high', 'N/A')}**."
        )

        # 2. Plain-language Future Price Target summary
        pred_price = target_data.get("predicted_target_price", "N/A")
        implied_ret = target_data.get("implied_return_pct", 0.0)
        has_analysts = target_data.get("has_analyst_consensus", False)
        ema_model = target_data.get("ema200_model", {})
        ema_200_val = ema_model.get("ema_200_current", "N/A")

        if has_analysts:
            ac = target_data.get("analyst_consensus", {})
            n_an = ac.get("num_analysts", 0)
            simple_target = (
                f"**2. Realistic Future Price Target (Analyst Consensus):**\n"
                f"Based on **{n_an} institutional analysts** tracking {company}, the average predicted target price is "
                f"**{sym}{pred_price}** ({implied_ret:+.2f}% from today's price), with estimates ranging from "
                f"**{sym}{ac.get('target_low', pred_price)}** to **{sym}{ac.get('target_high', pred_price)}**. "
                f"(For technical comparison, its 200-day long-term average trendline `EMA-200` sits at **{sym}{ema_200_val}**)."
            )
        else:
            simple_target = (
                f"**2. Realistic Future Price Target (EMA-200 1-Month Projection):**\n"
                f"Because major institutional analysts do not currently publish consensus price targets for {company}, "
                f"our agent uses its **200-day Exponential Moving Average (`EMA-200`)** — a smooth long-term trendline "
                f"currently at **{sym}{ema_200_val}** — to project where the stock is heading over the **next 1 month (21 trading days)**. "
                f"That mathematical trendline projects a 1-month price around **{sym}{pred_price}** ({implied_ret:+.2f}% from current price), "
                f"within a normal 1-month trading range of **{sym}{ema_model.get('band_1m_low', pred_price)} to {sym}{ema_model.get('band_1m_high', pred_price)}**."
            )

        # 3. Plain-language Fundamentals summary
        val = fundamentals_data.get("valuation", {})
        earn = fundamentals_data.get("earnings", {})
        own = fundamentals_data.get("ownership", {})
        mcap_str = fundamentals_data.get("market_cap_formatted", "N/A")
        pe_cur = val.get("current_pe")
        pe_med = val.get("pe_band_5y", {}).get("median")
        rev_str = earn.get("latest_annual_revenue_formatted", "N/A")
        ni_str = earn.get("latest_annual_net_income_formatted", "N/A")
        prom_pct = own.get("promoter_holding_pct", "N/A")
        pledge_pct = own.get("pledged_pct", 0.0)

        pe_explanation = (
            f"Investors currently pay **{pe_cur} times** its annual earnings (P/E ratio), compared to its 5-year normal average of **{pe_med}x**."
            if (pe_cur and pe_med)
            else f"Valuation assessment: **{val.get('valuation_status', 'Evaluated against 5-year historical baseline')}**."
        )

        simple_fundamentals = (
            f"**3. Company Health & Fundamentals (In Simple Terms):**\n"
            f"{company} operates in the **{fundamentals_data.get('sector', 'General')}** sector with a total company size (Market Cap) of **{mcap_str}**. "
            f"In its latest full financial year, it brought in **{rev_str}** in sales and earned **{ni_str}** in net profit ({earn.get('profitability_status', 'N/A')}). "
            f"{pe_explanation} "
            f"Company insiders/promoters own **{prom_pct}%** of the business, with **{pledge_pct}%** of promoter shares pledged as collateral."
        )

        full_plain_explanation = f"{simple_price}\n\n{simple_target}\n\n{simple_fundamentals}"

        return {
            "agent_id": self.AGENT_ID,
            "role": self.ROLE,
            "status": "OK",
            "ticker": ticker,
            "simple_sections": {
                "historic_price_explained": simple_price,
                "future_target_explained": simple_target,
                "fundamentals_explained": simple_fundamentals
            },
            "summary": full_plain_explanation,
            "sources": [
                "Synthesized from HistoricalPriceSubAgent, PriceTargetSubAgent, and FundamentalsSubAgent"
            ],
            "latency_ms": round((time.time() - start_ts) * 1000, 2)
        }


class QuarterlyReportSummarizerSubAgent:
    """
    Sub-Agent 5: Financial & Quarterly Reports Document Summarizer & SWOT Matrix Generator.
    Reads official past-quarter corporate financial filings (Regulation 33 Consolidated Results),
    distills the financial statement into simple, jargon-free bullet pointers, and constructs a
    4-quadrant SWOT Analysis table grounded strictly in quarterly financial statement metrics.
    For demo purposes, supports past-quarter filings for Reliance Industries (`RELIANCE.NS`)
    and State Bank of India (`SBIN.NS`).
    """

    AGENT_ID = "quarterly_report_agent"
    ROLE = "Financial & Quarterly Reports Summarizer Sub-Agent"
    SUPPORTED_DEMO_TICKERS = {
        "RELIANCE.NS": "RELIANCE.NS_Q1_FY27",
        "SBIN.NS": "SBIN.NS_Q1_FY27",
        "TCS.NS": "TCS.NS_Q1_FY27",
        "INFY.NS": "INFY.NS_Q1_FY27",
        "HDFCBANK.NS": "HDFCBANK.NS_Q1_FY27",
        "ITC.NS": "ITC.NS_Q1_FY27",
        "TATASTEEL.NS": "TATASTEEL.NS_Q1_FY27",
        "TRENT.NS": "TRENT.NS_Q1_FY27",
        "TVSMOTOR.NS": "TVSMOTOR.NS_Q1_FY27",
        "ZOMATO.NS": "ZOMATO.NS_Q1_FY27",
    }

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    @classmethod
    def normalize_demo_ticker(cls, ticker_or_name: str) -> Optional[str]:
        """Map raw ticker/alias to one of the 10 supported demo stocks."""
        raw = (ticker_or_name or "").strip().upper()
        if not raw:
            return None

        # Direct ticker check
        if raw in cls.SUPPORTED_DEMO_TICKERS:
            return raw
        base = raw.replace(".NS", "").replace(".BO", "")
        if f"{base}.NS" in cls.SUPPORTED_DEMO_TICKERS:
            return f"{base}.NS"

        # Alias mappings
        if "RELIANCE" in raw or raw in ("RIL", "JIO"):
            return "RELIANCE.NS"
        if "STATE BANK" in raw or raw in ("SBI", "SBIN"):
            return "SBIN.NS"
        if "TATA CONSULTANCY" in raw or raw == "TCS":
            return "TCS.NS"
        if "INFOSYS" in raw or raw == "INFY":
            return "INFY.NS"
        if "HDFC" in raw and ("BANK" in raw or raw in ("HDFCBANK", "HDFC")):
            return "HDFCBANK.NS"
        if raw == "ITC" or "ITC LIMITED" in raw:
            return "ITC.NS"
        if "TATA STEEL" in raw or raw == "TATASTEEL":
            return "TATASTEEL.NS"
        if "TRENT" in raw or "ZUDIO" in raw or "WESTSIDE" in raw:
            return "TRENT.NS"
        if "TVS" in raw or "TVS MOTOR" in raw or raw == "TVSMOTOR":
            return "TVSMOTOR.NS"
        if "ZOMATO" in raw or "BLINKIT" in raw or "ETERNAL" in raw:
            return "ZOMATO.NS"

        return None

    def run(self, ticker: str, analyze_with_gemini: bool = False) -> Dict[str, Any]:
        """
        Read the past-quarter financial filing document & structured statement for the target stock,
        produce simple bullet pointers, and build a Markdown + structured SWOT Analysis table.
        Consumes chunks from BigQuery RAG with local deterministic fallback.
        """
        import json
        from app.config import DATA_DIR, Config
        from app.agent.bigquery_rag import BigQueryFinancialRAG

        start_ts = time.time()
        norm_ticker = self.normalize_demo_ticker(ticker)
        sym = _currency_symbol(norm_ticker or ticker)

        if not norm_ticker or norm_ticker not in self.SUPPORTED_DEMO_TICKERS:
            return {
                "agent_id": self.AGENT_ID,
                "role": self.ROLE,
                "status": "DEMO_UNSUPPORTED_TICKER",
                "is_supported_demo_stock": False,
                "ticker": ticker,
                "supported_tickers": list(self.SUPPORTED_DEMO_TICKERS.keys()),
                "summary": (
                    f"[{self.ROLE}] Full past-quarter financial report document summarization and SWOT table "
                    f"generation is currently enabled for 10 marquee stocks: "
                    f"{', '.join(self.SUPPORTED_DEMO_TICKERS.keys())}. Active stock: `{ticker}`."
                ),
                "simple_pointers": [],
                "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
                "swot_markdown_table": "",
                "sources": [f"NSE / BSE Regulation 33 Filings (10-Stock Pack)"],
                "latency_ms": round((time.time() - start_ts) * 1000, 2)
            }

        rag_engine = BigQueryFinancialRAG()
        q_data = rag_engine.get_quarterly_report(norm_ticker) or {}

        file_stem = self.SUPPORTED_DEMO_TICKERS[norm_ticker]
        q_dir = DATA_DIR / "quarterly_reports"
        md_doc_path = q_dir / f"{file_stem}.md"
        raw_doc_text = ""
        if md_doc_path.exists():
            try:
                with open(md_doc_path, "r", encoding="utf-8") as f:
                    raw_doc_text = f.read()
            except Exception as e:
                logger.warning(f"Failed to read quarterly MD doc {md_doc_path}: {e}")

        company_name = q_data.get("company_name", norm_ticker)
        quarter_label = q_data.get("quarter_label", "Past Quarter (Q1 FY2026-27)")
        filing_type = q_data.get("filing_type", "Regulation 33 Quarterly Financial Results")
        filing_source = q_data.get("FilingSource", "BSE / NSE Quarterly Corporate Filings")
        metrics = q_data.get("headline_metrics", {})
        segments = q_data.get("segment_performance", [])
        pointers = list(q_data.get("simple_pointers", []))
        swot = q_data.get("swot", {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []})
        analysis_engine_used = q_data.get("source_engine", "Google BigQuery Financial Intelligence")

        # Optional live Gemini document reading & enhancement over the raw quarterly filing (.md)
        if analyze_with_gemini and raw_doc_text and getattr(Config, "GEMINI_API_KEY", None) and not getattr(Config, "DEMO_MODE", False):
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=Config.GEMINI_API_KEY)
                prompt = (
                    f"Read the following official quarterly financial filing for {company_name} ({norm_ticker}) "
                    f"and return a JSON object with keys 'simple_pointers' (array of 5 plain-English bullet strings "
                    f"with exact ₹ Crore figures and % growth) and 'swot' (object with keys 'strengths', 'weaknesses', "
                    f"'opportunities', 'threats', each an array of 3 concise financial bullet strings).\n\n"
                    f"DOCUMENT:\n{raw_doc_text}"
                )
                for model_name in ("gemini-3.1-flash-lite", "models/gemini-flash-lite-latest", "gemini-2.0-flash"):
                    try:
                        resp = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                temperature=0.1,
                                max_output_tokens=1500,
                                response_mime_type="application/json"
                            )
                        )
                        parsed = json.loads(resp.text or "{}")
                        if parsed.get("simple_pointers") and parsed.get("swot"):
                            pointers = parsed["simple_pointers"]
                            swot = parsed["swot"]
                            analysis_engine_used = f"Gemini Live Document Reader ({model_name})"
                            break
                    except Exception as inner_e:
                        logger.debug(f"Quarterly report Gemini model {model_name} fallback: {inner_e}")
            except Exception as e:
                logger.warning(f"Gemini live quarterly document summarization fell back to deterministic filing pack: {e}")

        # Build clean Markdown SWOT Table
        s_items = " <br>• ".join(swot.get("strengths", []))
        w_items = " <br>• ".join(swot.get("weaknesses", []))
        o_items = " <br>• ".join(swot.get("opportunities", []))
        t_items = " <br>• ".join(swot.get("threats", []))

        swot_md_table = (
            "| SWOT Dimension | Key Financial Statement Insights (" + quarter_label + ") |\n"
            "| :--- | :--- |\n"
            f"| **STRENGTHS (Internal Positives)** | • {s_items} |\n"
            f"| **WEAKNESSES (Internal Challenges)** | • {w_items} |\n"
            f"| **OPPORTUNITIES (Growth Tailwinds)** | • {o_items} |\n"
            f"| **THREATS (External Headwinds)** | • {t_items} |"
        )

        pointers_md = "\n".join(f"- {p}" for p in pointers)

        formatted_report_md = (
            f"### Quarterly Financial Report Summary: {company_name} ({norm_ticker})\n"
            f"**Filing Audited:** {filing_type} — **{quarter_label}**\n\n"
            f"#### Key Takeaways in Simple Pointers:\n"
            f"{pointers_md}\n\n"
            f"#### Financial Statement SWOT Analysis Table ({quarter_label}):\n"
            f"{swot_md_table}\n\n"
            f"**Source:** {filing_source}"
        )

        # Query BigQuery Financial RAG for semantic verification chunks
        rag_chunks = rag_engine.search_chunks(norm_ticker, query_text="revenue EBITDA net profit PAT growth segments and SWOT analysis", top_k=3)
        rag_source_tag = "Google BigQuery Vector Search (text-embedding-004)" if rag_engine.is_cloud_enabled else "BigQuery Vector RAG Store (text-embedding-004)"

        return {
            "agent_id": self.AGENT_ID,
            "role": self.ROLE,
            "status": "OK",
            "is_supported_demo_stock": True,
            "ticker": norm_ticker,
            "company_name": company_name,
            "quarter_label": quarter_label,
            "filing_type": filing_type,
            "currency_symbol": sym,
            "analysis_engine": analysis_engine_used,
            "headline_metrics": metrics,
            "segment_performance": segments,
            "simple_pointers": pointers,
            "swot": swot,
            "swot_markdown_table": swot_md_table,
            "formatted_report_markdown": formatted_report_md,
            "document_excerpt": raw_doc_text[:600] if raw_doc_text else "",
            "rag_source": rag_source_tag,
            "rag_chunks": rag_chunks,
            "summary": formatted_report_md,
            "sources": [
                filing_source,
                rag_source_tag,
                f"data/quarterly_reports/{file_stem}.md",
                f"data/quarterly_reports/{file_stem}.json"
            ],
            "latency_ms": round((time.time() - start_ts) * 1000, 2)
        }


class SubAgentCoordinator:
    """
    Orchestrates the chatbot sub-agents in parallel and integrates with the Pub/Sub event bus.
    Routes user queries to the specialized sub-agents and aggregates their empirical findings:
      1. HistoricalPriceSubAgent (`historic_price_agent`)
      2. PriceTargetSubAgent (`price_target_agent`)
      3. FundamentalsSubAgent (`fundamentals_agent`)
      4. QuarterlyReportSummarizerSubAgent (`quarterly_report_agent`)
      5. SimpleExplainerSubAgent (`explainer_agent`)
    """

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()
        self.price_agent = HistoricalPriceSubAgent(self.loader)
        self.target_agent = PriceTargetSubAgent(self.loader)
        self.fundamentals_agent = FundamentalsSubAgent(self.loader)
        self.quarterly_agent = QuarterlyReportSummarizerSubAgent(self.loader)
        self.explainer_agent = SimpleExplainerSubAgent()

    def detect_relevant_agents(self, message: str) -> List[str]:
        """Determine which sub-agents are specifically relevant to the user's message."""
        lower = (message or "").lower()
        selected = []

        # 1. Historic Price triggers
        if any(w in lower for w in [
            "price", "performance", "return", "returns", "history", "historical",
            "past", "month", "months", "week", "year", "trend", "high", "low",
            "52", "candle", "volatility", "volume", "chart", "moved", "performing"
        ]):
            selected.append(HistoricalPriceSubAgent.AGENT_ID)

        # 2. Future Price Target / Analyst / EMA-200 triggers
        if any(w in lower for w in [
            "target", "predict", "predicted", "prediction", "future", "forecast",
            "analyst", "analysts", "consensus", "ema", "ema200", "ema-200", "200",
            "projection", "next 1 month", "next month", "upside", "expected", "reach"
        ]):
            selected.append(PriceTargetSubAgent.AGENT_ID)

        # 3. Fundamentals triggers
        if any(w in lower for w in [
            "fundamental", "fundamentals", "pe", "p/e", "valuation", "eps",
            "earning", "earnings", "revenue", "sales", "profit", "loss", "income",
            "pat", "market cap", "promoter", "holding", "pledge", "pledging",
            "balance sheet", "financial", "financials", "annual", "sector"
        ]):
            selected.append(FundamentalsSubAgent.AGENT_ID)

        # 4. Quarterly Report Summarizer & SWOT triggers
        if any(w in lower for w in [
            "quarterly", "quarter", "q1", "q2", "q3", "q4", "swot",
            "strengths", "weaknesses", "opportunities", "threats",
            "quarterly report", "financial report", "results", "pointers",
            "segment", "jio", "o2c", "nii", "nim", "gnpa", "nnpa", "casa"
        ]):
            selected.append(QuarterlyReportSummarizerSubAgent.AGENT_ID)

        # 5. Simple explanation / summary triggers or fallback
        if any(w in lower for w in [
            "simple", "simply", "explain", "summary", "summarize", "overview",
            "all", "everything", "easy", "beginner", "layman", "break down", "breakdown",
            "tell me about", "what do you think", "score", "verdict"
        ]) or not selected:
            for aid in [
                HistoricalPriceSubAgent.AGENT_ID,
                PriceTargetSubAgent.AGENT_ID,
                FundamentalsSubAgent.AGENT_ID,
                QuarterlyReportSummarizerSubAgent.AGENT_ID,
            ]:
                if aid not in selected:
                    selected.append(aid)

        # Always include the explainer sub-agent so the chatbot has plain-language synthesis ready
        if SimpleExplainerSubAgent.AGENT_ID not in selected:
            selected.append(SimpleExplainerSubAgent.AGENT_ID)

        return selected

    def execute_all(
        self,
        ticker: str,
        report_context: Optional[Dict[str, Any]] = None,
        message: str = ""
    ) -> Dict[str, Any]:
        """
        Executes the data & document sub-agents concurrently via ThreadPoolExecutor and synthesizes
        plain-language explanations via SimpleExplainerSubAgent.
        """
        start_ts = time.time()
        report_context = report_context or {}
        claim = report_context.get("claim") or {}
        claimed_target = claim.get("target_price")

        invoked_ids = self.detect_relevant_agents(message)

        # Allow explicit mention of Reliance or SBIN in message to override ticker for quarterly agent if queried
        lower_msg = (message or "").lower()
        quarterly_ticker = ticker
        if "reliance" in lower_msg or "ril" in lower_msg.split():
            quarterly_ticker = "RELIANCE.NS"
        elif "sbin" in lower_msg or "sbi" in lower_msg.split() or "state bank" in lower_msg:
            quarterly_ticker = "SBIN.NS"

        # Execute the 4 empirical & document sub-agents concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="chatbot-subagent") as pool:
            f_price = pool.submit(self.price_agent.run, ticker)
            f_target = pool.submit(self.target_agent.run, ticker, claimed_target)
            f_fund = pool.submit(self.fundamentals_agent.run, ticker)
            f_quart = pool.submit(self.quarterly_agent.run, quarterly_ticker)

            price_res = f_price.result()
            target_res = f_target.result()
            fund_res = f_fund.result()
            quart_res = f_quart.result()

        # Run SimpleExplainerSubAgent over the gathered empirical results
        explainer_res = self.explainer_agent.run(
            ticker=ticker,
            price_data=price_res,
            target_data=target_res,
            fundamentals_data=fund_res,
            report_context=report_context
        )

        # Deduplicate sources across all sub-agents
        all_sources = []
        for res in (price_res, target_res, fund_res, quart_res):
            for src in res.get("sources", []):
                if src not in all_sources:
                    all_sources.append(src)

        prompt_context_block = (
            f"=== SUB-AGENT 1: {price_res['summary']}\n\n"
            f"=== SUB-AGENT 2: {target_res['summary']}\n\n"
            f"=== SUB-AGENT 3: {fund_res['summary']}\n\n"
            f"=== SUB-AGENT 4 (PLAIN-LANGUAGE SYNTHESIS):\n{explainer_res['summary']}\n\n"
            f"=== SUB-AGENT 5 (QUARTERLY REPORT SUMMARIZER & SWOT TABLE):\n{quart_res['summary']}\n\n"
            f"=== VERIFIED DATA SOURCES:\n" + "\n".join(f"- {s}" for s in all_sources)
        )

        return {
            "ticker": ticker,
            "subagents_invoked": invoked_ids,
            "agents": {
                HistoricalPriceSubAgent.AGENT_ID: price_res,
                PriceTargetSubAgent.AGENT_ID: target_res,
                FundamentalsSubAgent.AGENT_ID: fund_res,
                QuarterlyReportSummarizerSubAgent.AGENT_ID: quart_res,
                SimpleExplainerSubAgent.AGENT_ID: explainer_res,
            },
            "sources": all_sources,
            "prompt_context_block": prompt_context_block,
            "total_latency_ms": round((time.time() - start_ts) * 1000, 2)
        }

