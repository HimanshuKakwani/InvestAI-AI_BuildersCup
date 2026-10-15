"""Core Forensic Analysis Orchestrator."""
import uuid
from typing import Dict, Any, Optional
from app.data.loader import DataLoader
from app.gemini.client import GeminiAuditor
from app.engine.parameters.p1_price_move import evaluate_price_move
from app.engine.parameters.p2_valuation import evaluate_valuation_range
from app.engine.parameters.p3_earnings import evaluate_earnings_trajectory
from app.engine.parameters.p4_analyst import evaluate_analyst_consensus
from app.engine.parameters.p5_promoter import evaluate_promoter_holding
from app.engine.parameters.p6_regulatory import evaluate_regulatory_orders
from app.engine.parameters.p7_surveillance import evaluate_surveillance_and_volume
from app.engine.parameters.p8_licensing import evaluate_licensing
from app.engine.parameters.p9_hype_language import evaluate_language_hype
from app.engine.scoring import calculate_verdict

class AnalysisService:
    def __init__(self):
        self.loader = DataLoader()
        self.gemini = GeminiAuditor()

    def evaluate_single_claim(
        self,
        claim: Dict[str, Any],
        raw_text_for_p9: str,
        region: str,
        market_cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Audits a single extracted claim against empirical market data and regulatory registries."""
        # Ticker Resolution
        raw_ticker = claim.get("ticker") or ""
        resolved = self.loader.resolve_ticker(raw_ticker, market_hint=region)
        ticker = resolved["ticker"] if resolved else raw_ticker
        company_name = resolved["name"] if resolved else claim.get("company_name", ticker)

        # Load empirical data
        prices_df = self.loader.get_price_history(ticker)
        fundamentals = self.loader.get_fundamentals(ticker)

        # 1. Real-time Live Market Price (10-min intraday cache)
        current_price = self.loader.get_live_price(ticker)

        # 2. Fallback to latest close if live price is unavailable
        if current_price is None:
            if prices_df is not None and not prices_df.empty and "Close" in prices_df.columns:
                current_price = float(prices_df["Close"].iloc[-1])
            elif fundamentals and fundamentals.get("current_price"):
                current_price = float(fundamentals["current_price"])


        # Evaluate 9 Parameters
        claimed_pct = claim.get("claimed_percentage_move")
        if claimed_pct is not None:
            try:
                claimed_pct = float(claimed_pct)
            except Exception:
                claimed_pct = None

        if claimed_pct is None and claim.get("target_price") and current_price:
            try:
                t_price = float(claim["target_price"])
                claimed_pct = ((t_price - current_price) / current_price) * 100.0
            except Exception:
                claimed_pct = None

        try:
            target_price = float(claim["target_price"]) if claim.get("target_price") is not None else None
        except Exception:
            target_price = None
        raw_horizon = claim.get("time_horizon_days")
        try:
            horizon = max(int(raw_horizon), 1) if raw_horizon is not None else 14
        except Exception:
            horizon = 14
        direction = claim.get("direction", "BUY")

        # P1: Price-Move Plausibility
        p1 = evaluate_price_move(prices_df, claimed_pct, horizon)
        
        # P2: Valuation Envelope
        p2 = evaluate_valuation_range(fundamentals, current_price, target_price)

        # P3: Earnings Trajectory
        p3 = evaluate_earnings_trajectory(fundamentals, direction=direction)

        # P4: Analyst Consensus Alignment
        p4 = evaluate_analyst_consensus(fundamentals, target_price, current_price)

        # P5: Promoter & Insider Stability
        p5 = evaluate_promoter_holding(fundamentals, direction=direction)

        # Load registries & alerts
        reg_data = self.loader.get_registry(market_cfg.get("license_registry", ""))
        alert_files = market_cfg.get("alert_lists", [])
        alerts_data = []
        for af in alert_files:
            alerts_data.extend(self.loader.get_alerts(af))

        # P6: Litigation & Regulatory Sanctions
        p6 = evaluate_regulatory_orders(
            ticker=ticker,
            company_name=company_name,
            alert_lists_data=alerts_data,
            regulator_name=market_cfg.get("regulator", "Regulator")
        )

        # P7: Surveillance & Volume Anomalies
        surveillance_info = fundamentals.get("surveillance") if fundamentals else None
        p7 = evaluate_surveillance_and_volume(prices_df, surveillance_info=surveillance_info)

        # P8: Licensing & Alerts Verification
        p8 = evaluate_licensing(
            creator_name=claim.get("creator_claimed_name"),
            registry_data=reg_data,
            alert_lists_data=alerts_data,
            regulator_name=market_cfg.get("regulator", "Regulator"),
            claimed_reg_no=claim.get("creator_claimed_reg_no")
        )

        # P9: Manipulative & Hype Language
        p9 = evaluate_language_hype(
            text_content=claim.get("exact_quote", "") + " " + raw_text_for_p9,
            lexicon_dict=market_cfg.get("red_flag_lexicon", {})
        )

        evaluated_params = [p1, p2, p3, p4, p5, p6, p7, p8, p9]

        is_registered = p8.get("facts", {}).get("is_registered", False)
        verdict = calculate_verdict(evaluated_params, is_source_registered=is_registered)

        report_id = f"rep_{uuid.uuid4().hex[:8]}"

        return {
            "report_id": report_id,
            "region": region,
            "market_name": market_cfg.get("name", region),
            "flag_emoji": market_cfg.get("flag_emoji", ""),
            "regulator": market_cfg.get("regulator", ""),
            "reporting_url": market_cfg.get("reporting", {}).get("url"),
            "reporting_name": market_cfg.get("reporting", {}).get("name"),
            "claim": claim,
            "resolved_stock": resolved or {"ticker": ticker, "name": claim.get("company_name", ticker)},
            "current_price": current_price,
            "verdict": verdict,
            "parameters": evaluated_params
        }

    def run_investigation(
        self,
        modality: str,
        payload: Any,
        region_override: Optional[str] = None,
        image_mime: str = "image/png"
    ) -> Dict[str, Any]:
        """
        Orchestrates full audit across the 9 parameters.
        If multiple stocks are recommended in the video/image/tip, audits all of them
        and returns both an aggregated result and a reports list.
        """
        region = region_override or "IN"
        market_cfg = self.loader.get_market_config(region) or self.loader.get_market_config("IN")
        
        # 1. Extraction via Gemini
        raw_text_for_p9 = ""
        if modality == "youtube_url":
            claims_raw = self.gemini.analyze_youtube_claim(str(payload), market_hint=region)
            raw_text_for_p9 = str(payload)
        elif modality == "screenshot":
            claims_raw = self.gemini.analyze_screenshot(payload, mime_type=image_mime, market_hint=region)
            raw_text_for_p9 = claims_raw[0].get("exact_quote", "") if isinstance(claims_raw, list) and claims_raw else getattr(claims_raw, "get", lambda k, d="": "")("exact_quote", "")
        else:
            claims_raw = self.gemini.analyze_text_or_screenshot(str(payload), market_hint=region)
            raw_text_for_p9 = str(payload)

        # Check if classified as irrelevant or non-financial content
        if isinstance(claims_raw, dict) and claims_raw.get("is_financial_advice") is False:
            return {
                "is_financial_advice": False,
                "message": claims_raw.get("message") or "Not a financial advice, kindly provide relevant input",
                "error": claims_raw.get("message") or "Not a financial advice, kindly provide relevant input"
            }

        # Normalize claims into a list of genuine securities claims
        claims_list = []
        if isinstance(claims_raw, list):
            claims_list = [c for c in claims_raw if isinstance(c, dict) and (c.get("ticker") or c.get("company_name")) and c.get("is_financial_advice") is not False]
        elif isinstance(claims_raw, dict):
            if (claims_raw.get("ticker") or claims_raw.get("company_name")) and claims_raw.get("is_financial_advice") is not False:
                claims_list = [claims_raw]

        if not claims_list:
            return {
                "is_financial_advice": False,
                "message": "Not a financial advice, kindly provide relevant input",
                "error": "Not a financial advice, kindly provide relevant input"
            }

        # Audit each claim
        evaluated_reports = []
        for c in claims_list:
            audit = self.evaluate_single_claim(c, raw_text_for_p9, region, market_cfg)
            evaluated_reports.append(audit)

        primary = evaluated_reports[0]
        # Return container without circular self-reference
        return {
            "report_id": primary["report_id"],
            "region": region,
            "market_name": market_cfg.get("name", region),
            "flag_emoji": market_cfg.get("flag_emoji", ""),
            "regulator": market_cfg.get("regulator", ""),
            "reporting_url": market_cfg.get("reporting", {}).get("url"),
            "reporting_name": market_cfg.get("reporting", {}).get("name"),
            "claim": primary["claim"],
            "resolved_stock": primary["resolved_stock"],
            "current_price": primary["current_price"],
            "verdict": primary["verdict"],
            "parameters": primary["parameters"],
            "reports": evaluated_reports,
            "total_stocks_audited": len(evaluated_reports)
        }
