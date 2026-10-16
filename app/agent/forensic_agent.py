"""InvestPI Forensic Assistant Agent with Multi-Agent Sub-System & Heavy Guardrails."""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types
from app.config import Config
from app.data.loader import DataLoader
from app.agent.subagents import (
    SubAgentCoordinator,
    HistoricalPriceSubAgent,
    PriceTargetSubAgent,
    FundamentalsSubAgent,
    SimpleExplainerSubAgent
)

logger = logging.getLogger("InvestPI.Agent")

GUARDRAIL_REJECTION_MESSAGE = "Question out of my domain, kindly ask something related to given findings"

# Explicit out-of-scope intent triggers
OUT_OF_SCOPE_PATTERNS = [
    r"\b(python|javascript|java|c\+\+|html|css|sql|react|code|coding|script|function|program|bug|debug)\b",
    r"\b(weather|temperature|forecast|rain|sunny|climate)\b",
    r"\b(recipe|cook|bake|food|cake|pizza|burger|pasta|restaurant|ingredient|dinner|lunch)\b",
    r"\b(cricket|football|soccer|basketball|tennis|f1|formula 1|racing|nba|fifa|ipl)\b",
    r"\b(movie|cinema|actor|actress|hollywood|bollywood|song|music|singer|album)\b",
    r"\b(capital of|president of|prime minister of|who is the king|history of|war of)\b",
    r"\b(tell me a joke|write a poem|sing|story|riddle)\b",
    r"\b(bitcoin|doge|ethereum|crypto|solana|binance|nft)\b",  # Unless crypto is the specific audited asset
]

# Core audit & sub-agent domain keywords
IN_SCOPE_CORE_KEYWORDS = {
    "score", "confidence", "confidence score", "verdict", "risk", "high risk", "low risk", "caution",
    "parameter", "parameters", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9",
    "price", "prices", "target", "targets", "cmp", "current price", "target price", "upside", "horizon", "valuation",
    "pe", "pe ratio", "eps", "earnings", "revenue", "sales", "profit", "loss", "pat", "income", "market cap",
    "promoter", "holding", "pledge", "pledging", "shareholding", "governance",
    "analyst", "analysts", "consensus", "surveillance", "asm", "gsm", "volume", "hard gate",
    "sebi", "mas", "asic", "regulator", "regulatory", "license", "licensing", "unregistered",
    "hype", "guarantee", "manipulation", "quote", "transcript", "video", "influencer", "channel",
    "dossier", "report", "finding", "findings", "evidence", "flag", "audited", "audit", "investigation",
    "why", "explain", "breakdown", "summarize", "summary", "details", "methodology", "calculation",
    # Stock, market, returns & performance timeline concepts
    "stock", "stocks", "share", "shares", "equity", "equities", "company", "companies",
    "performance", "performing", "return", "returns", "trend", "trends", "movement",
    "history", "historical", "historic", "track", "record", "past", "recent", "chart", "charts",
    "timeline", "month", "months", "year", "years", "week", "weeks", "day", "days",
    "quarter", "quarters", "annual", "growth", "fall", "dip", "correction", "gain", "gains",
    "rally", "volatility", "momentum", "high", "low", "52-week", "52w", "candle", "candles",
    # Sub-agent specific concepts: future prediction, EMA-200, fundamentals, simple explanation
    "predict", "predicted", "prediction", "future", "projection", "projected", "expected",
    "ema", "ema200", "ema-200", "200", "sma", "moving average", "technical", "technicals",
    "fundamental", "fundamentals", "financial", "financials", "sector",
    "simple", "simply", "easy", "beginner", "layman", "plain", "terms", "overview", "everything",
    "agent", "subagent", "subagents", "source", "sources"
}

# Demonstrative or contextual references to the active audited stock/dossier
CONTEXTUAL_STOCK_REFERENCES = [
    "this stock", "this stocks", "the stock", "these stocks",
    "this company", "the company", "this share", "the share",
    "these shares", "its performance", "it's performance", "its price", "its target", "its fundamentals",
    "this equity", "the findings", "this report", "this dossier",
    "how was it", "how did it", "how has it", "how is it", "what about it",
    "last month", "last 1 month", "last 3 months", "last 6 months", "last year", "past year",
    "next 1 month", "next month", "1 month", "3 months", "6 months", "1 year",
    "in simple terms", "explain in simple", "explain all", "explain everything",
    "future price", "predicted price", "price target", "historic price", "historical price"
]


class ForensicAssistantAgent:
    """
    Master Conversational Agent & Sub-Agent Orchestrator grounded in the active audit dossier.
    Coordinates 4 specialized sub-agents:
      1. HistoricalPriceSubAgent (`historic_price_agent`)
      2. PriceTargetSubAgent (`price_target_agent`) — Analyst Consensus Average or EMA-200 1M Fallback
      3. FundamentalsSubAgent (`fundamentals_agent`)
      4. SimpleExplainerSubAgent (`explainer_agent`)
    """

    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.model_name = "gemini-3.1-flash-lite"
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.loader = DataLoader()
        self.coordinator = SubAgentCoordinator(loader=self.loader)
        self.last_subagent_bundle: Optional[Dict[str, Any]] = None

    def is_question_in_scope(self, message: str, report_context: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if a user message stays strictly within the domain of the audited findings."""
        if not message:
            return False

        lower_msg = message.strip().lower()

        # 1. Hard rejection on blatant out-of-scope topics
        # Note: "forecast" is allowed ONLY if paired with stock/price/target/analyst/ema terms
        for pattern in OUT_OF_SCOPE_PATTERNS:
            match = re.search(pattern, lower_msg, re.IGNORECASE)
            if match:
                matched_word = match.group(0).lower()
                if matched_word == "forecast" and any(
                    fin_term in lower_msg for fin_term in ["price", "stock", "target", "analyst", "ema", "share", "return"]
                ):
                    continue
                return False

        # 2. Check for demonstrative or contextual references to the active audited security
        if any(ref in lower_msg for ref in CONTEXTUAL_STOCK_REFERENCES):
            return True

        # 3. Check for explicit reference to the audited stock (ticker or company name)
        stock_terms = set()
        if report_context:
            resolved_stock = report_context.get("resolved_stock") or {}
            ticker = resolved_stock.get("ticker", "").lower().replace(".ns", "").replace(".si", "").replace(".ax", "")
            company_name = (resolved_stock.get("company_name") or resolved_stock.get("name") or "").lower()
            if ticker:
                stock_terms.add(ticker)
            for word in re.findall(r"\w+", company_name):
                if len(word) >= 3 and word not in {"ltd", "limited", "corp", "inc"}:
                    stock_terms.add(word)

        # Check if message mentions the stock or company
        for term in stock_terms:
            if term and term in lower_msg:
                return True

        # 4. Check for core audit and forensic sub-agent concepts
        msg_words = set(re.findall(r"\w+", lower_msg))
        if bool(msg_words.intersection(IN_SCOPE_CORE_KEYWORDS)):
            return True

        # Short conversational continuations ("why", "explain that", "what do you mean")
        if len(lower_msg.split()) <= 4 and any(w in lower_msg for w in ["why", "explain", "how", "what", "more", "simple"]):
            return True

        return False

    def build_system_prompt(
        self,
        report_context: Dict[str, Any],
        subagent_bundle: Optional[Dict[str, Any]] = None
    ) -> str:
        """Constructs rigid forensic context, sub-agent intelligence, and guardrail rules for Gemini."""
        resolved = report_context.get("resolved_stock", {})
        ticker = resolved.get("ticker", "AUDITED_EQUITY")
        company_name = resolved.get("company_name") or resolved.get("name") or ticker
        verdict = report_context.get("verdict", {})
        claim = report_context.get("claim", {})
        parameters = report_context.get("parameters", [])

        # Summarize 9 forensic parameters
        params_summary = []
        for idx, p in enumerate(parameters, 1):
            p_id = p.get("parameter_id") or p.get("id") or f"P{idx}"
            p_name = p.get("name", f"Parameter {idx}")
            p_status = p.get("status", "")
            p_score = p.get("score", "")
            p_gate = " [HARD GATE TRIGGERED]" if p.get("hard_gate") else ""
            p_details = p.get("explanation") or p.get("details") or p.get("findings") or ""
            params_summary.append(f"- {p_id} ({p_name}): Status={p_status}, Score={p_score}/10{p_gate}. Details: {p_details}")
        params_text = "\n".join(params_summary) if params_summary else "Deterministic parameters evaluated."

        if not subagent_bundle:
            subagent_bundle = self.coordinator.execute_all(ticker=ticker, report_context=report_context)

        subagent_context = subagent_bundle.get("prompt_context_block", "")
        invoked_list = ", ".join(subagent_bundle.get("subagents_invoked", []))

        return f"""You are the InvestPI Forensic Intelligence Assistant, an empirical financial audit chatbot powered by 4 specialized sub-agents:
1. HistoricalPriceSubAgent (historic_price_agent): 5-year daily OHLCV candles, multi-horizon returns (1W, 1M, 3M, 6M, 1Y, 5Y), 52W High/Low, volatility, and moving averages.
2. PriceTargetSubAgent (price_target_agent): Predicted future price target using Institutional Analyst Consensus Average (`target_mean`). When analyst targets are absent, it provides the 1-month (21-trading-day) projected price based on the 200-Day Exponential Moving Average (`EMA-200`).
3. FundamentalsSubAgent (fundamentals_agent): Company EPS, P/E, 5-year P/E valuation band, Market Cap, annual & quarterly Revenue & Net Profit (PAT), and Promoter shareholding/pledging.
4. SimpleExplainerSubAgent (explainer_agent): Translates all technical metrics into plain, simple everyday language.

ACTIVE CASE FILE:
SECURITY: {company_name} ({ticker})
INVESTPI CONFIDENCE SCORE: {verdict.get('score', 'N/A')}/10
VERDICT CLASSIFICATION: {verdict.get('flag', 'HIGH RISK')}
VERDICT SUMMARY: {verdict.get('summary', 'Audit complete.')}
CURRENT MARKET PRICE: {report_context.get('current_price', 'N/A')}
CLAIMED TARGET PRICE: {claim.get('target_price', 'N/A')} (Horizon: {claim.get('time_horizon_days', 'N/A')} days)
CLAIMED CREATOR / CHANNEL: {claim.get('channel_or_author', claim.get('creator_claimed_name', 'Unknown'))}
EXTRACTED CLAIM QUOTE: "{claim.get('exact_quote', 'N/A')}"
EVALUATED 9 COMPLIANCE PARAMETERS:
{params_text}

SUB-AGENTS INVOKED FOR THIS QUERY: [{invoked_list}]
LIVE SUB-AGENT INTELLIGENCE & EMPIRICAL DATA:
{subagent_context}

CRITICAL HEAVY GUARDRAIL & RESPONSE POLICY:
1. You may ONLY answer questions directly pertaining to:
   - The audited security ({ticker} / {company_name}).
   - The InvestPI confidence score, risk verdict, and 9 compliance parameters (P1–P9).
   - Historic price performance, technical moving averages (SMA/EMA-200), and volatility from HistoricalPriceSubAgent.
   - Predicted future price targets from PriceTargetSubAgent (Analyst Consensus Average if available, or EMA-200 1-Month Projection fallback if analyst targets are unavailable).
   - Company fundamentals (EPS, P/E, 5Y P/E band, Revenue, Net Income, Market Cap, Promoter holding/pledging) from FundamentalsSubAgent.
   - Explaining any or all of these findings in simple, beginner-friendly terms and citing the data sources.
2. IF the user asks ANY question outside this audit dossier (e.g. general knowledge, coding, weather, recipes, sports, politics, movies, jokes, cryptocurrency, or other unrelated stocks):
   You MUST respond with EXACTLY this sentence and NOTHING ELSE:
   "{GUARDRAIL_REJECTION_MESSAGE}"
3. Always explain technical concepts in clear, simple terms alongside the exact empirical numbers and mention whether a price target comes from Institutional Analyst Consensus or the EMA-200 1-Month Projection.
"""

    def generate_demo_response(
        self,
        message: str,
        report_context: Dict[str, Any],
        subagent_bundle: Optional[Dict[str, Any]] = None
    ) -> str:
        """Deterministic response backed by live sub-agent data when operating offline or without Gemini API Key."""
        lower = message.lower()
        resolved = report_context.get("resolved_stock", {})
        ticker = resolved.get("ticker", "AUDITED_EQUITY")
        company = resolved.get("company_name") or resolved.get("name") or ticker
        verdict = report_context.get("verdict", {})
        score = verdict.get("score", "2.2")
        flag = verdict.get("flag", "HIGH RISK")
        claim = report_context.get("claim", {})
        target = claim.get("target_price", "N/A")
        cmp = report_context.get("current_price", "N/A")

        if not subagent_bundle:
            subagent_bundle = self.coordinator.execute_all(ticker=ticker, report_context=report_context, message=message)

        agents = subagent_bundle.get("agents", {})
        price_res = agents.get(HistoricalPriceSubAgent.AGENT_ID, {})
        target_res = agents.get(PriceTargetSubAgent.AGENT_ID, {})
        fund_res = agents.get(FundamentalsSubAgent.AGENT_ID, {})
        explainer_res = agents.get(SimpleExplainerSubAgent.AGENT_ID, {})
        sym = price_res.get("currency_symbol", "₹")

        # 1. Plain-language / "explain everything in simple terms" query
        if any(w in lower for w in ["simple", "simply", "layman", "beginner", "everything", "explain all", "overview", "summary"]):
            return (
                f"**Plain-Language Summary for {company} ({ticker})** *(InvestPI Score: {score}/10 — {flag})*:\n\n"
                f"{explainer_res.get('summary', '')}\n\n"
                f"**Data Sources:** {', '.join(subagent_bundle.get('sources', []))}"
            )

        # 2. Predicted Future Price Target / Analyst Consensus / EMA-200 query
        if any(w in lower for w in [
            "predict", "predicted", "prediction", "future", "forecast", "projection",
            "analyst", "analysts", "consensus", "ema", "ema200", "ema-200", "next 1 month", "next month", "target price"
        ]) and not any(w in lower for w in ["p1", "parameter 1"]):
            pred_p = target_res.get("predicted_target_price", "N/A")
            imp_ret = target_res.get("implied_return_pct", 0.0)
            has_an = target_res.get("has_analyst_consensus", False)
            ema_m = target_res.get("ema200_model", {})
            ema_cur = ema_m.get("ema_200_current", "N/A")
            ema_1m = ema_m.get("ema_200_1m_predicted_price", "N/A")

            if has_an:
                ac = target_res.get("analyst_consensus", {})
                return (
                    f"**Predicted Future Price Target for {company} ({ticker})** *(via `price_target_agent`)*:\n"
                    f"- **Prediction Method:** Institutional Analyst Consensus Average ({ac.get('num_analysts', 0)} Analysts)\n"
                    f"- **Predicted Target Price:** **{sym}{pred_p}** ({imp_ret:+.2f}% from current price {sym}{target_res.get('current_price', cmp)})\n"
                    f"- **Analyst Range:** Low {sym}{ac.get('target_low', pred_p)} — High {sym}{ac.get('target_high', pred_p)} (Rating: {str(ac.get('recommendation', 'N/A')).upper()})\n"
                    f"- **EMA-200 Technical Reference:** Current EMA-200 is **{sym}{ema_cur}** (1-Month EMA-200 projection: **{sym}{ema_1m}**).\n"
                    f"- **In Simple Terms:** {explainer_res.get('simple_sections', {}).get('future_target_explained', '')}"
                )
            else:
                return (
                    f"**Predicted Future Price Target for {company} ({ticker})** *(via `price_target_agent` — EMA-200 Fallback)*:\n"
                    f"- **Institutional Analyst Coverage:** Not present (0 analysts covering {ticker}).\n"
                    f"- **Active Fallback Method:** 200-Day Exponential Moving Average (`EMA-200`) 1-Month Projection\n"
                    f"- **Current EMA-200 Baseline:** **{sym}{ema_cur}** (1-Month Drift: {sym}{ema_m.get('ema_200_1m_drift', 0):+.2f})\n"
                    f"- **Predicted Price for Next 1 Month (21 Trading Days):** **{sym}{pred_p}** ({imp_ret:+.2f}% vs Current Price {sym}{target_res.get('current_price', cmp)})\n"
                    f"- **Expected 1-Month Range (1-Sigma):** {sym}{ema_m.get('band_1m_low', pred_p)} — {sym}{ema_m.get('band_1m_high', pred_p)}\n"
                    f"- **In Simple Terms:** {explainer_res.get('simple_sections', {}).get('future_target_explained', '')}"
                )

        # 3. Fundamentals / Valuation / Earnings / Shareholding query
        if any(w in lower for w in [
            "fundamental", "fundamentals", "eps", "revenue", "sales", "profit", "net income",
            "pat", "market cap", "promoter", "pledge", "shareholding", "balance sheet", "financials", "p2", "valuation", "p/e", "pe"
        ]):
            val = fund_res.get("valuation", {})
            earn = fund_res.get("earnings", {})
            own = fund_res.get("ownership", {})
            pe_b = val.get("pe_band_5y", {})
            return (
                f"**Company Fundamentals for {company} ({ticker})** *(via `fundamentals_agent`)*:\n"
                f"- **Sector & Size:** {fund_res.get('sector', 'General')} | Market Cap: **{fund_res.get('market_cap_formatted', 'N/A')}**\n"
                f"- **Valuation Multiples:** Trailing EPS: **{sym}{val.get('trailing_eps', 'N/A')}** | Current P/E: **{val.get('current_pe', 'N/A')}x** "
                f"(5Y Normal P/E Band: {pe_b.get('min', 'N/A')}x – {pe_b.get('max', 'N/A')}x, Median {pe_b.get('median', 'N/A')}x)\n"
                f"- **Annual Financials ({earn.get('latest_annual_period', 'Latest FY')}):** Revenue: **{earn.get('latest_annual_revenue_formatted', 'N/A')}** | "
                f"Net Profit (PAT): **{earn.get('latest_annual_net_income_formatted', 'N/A')}** ({earn.get('profitability_status', 'N/A')})\n"
                f"- **Ownership:** Promoter Holding: **{own.get('promoter_holding_pct', 'N/A')}%** | Pledged Shares: **{own.get('pledged_pct', 0.0)}%**\n"
                f"- **In Simple Terms:** {explainer_res.get('simple_sections', {}).get('fundamentals_explained', '')}"
            )

        # 4. Historic Price Performance / Returns query
        if any(w in lower for w in ["performance", "return", "returns", "month", "year", "trend", "past", "history", "historical", "historic", "52"]):
            rets = price_res.get("returns", {})
            hist_p = price_res.get("historical_prices", {})
            r52 = price_res.get("range_52w", {})
            tech = price_res.get("technicals", {})
            return (
                f"**Empirical Historical Price Data for {company} ({ticker})** *(via `historic_price_agent`)*:\n"
                f"- **Current Price:** **{sym}{price_res.get('current_price', cmp)}**\n"
                f"- **1-Week Return:** {rets.get('1w_pct', 0):+.2f}% (from {sym}{hist_p.get('1w_ago', 'N/A')})\n"
                f"- **1-Month Return:** **{rets.get('1m_pct', 0):+.2f}%** (from {sym}{hist_p.get('1m_ago', 'N/A')})\n"
                f"- **3-Month Return:** {rets.get('3m_pct', 0):+.2f}% (from {sym}{hist_p.get('3m_ago', 'N/A')})\n"
                f"- **1-Year Return:** {rets.get('1y_pct', 0):+.2f}% (from {sym}{hist_p.get('1y_ago', 'N/A')})\n"
                f"- **52-Week Range:** Low {sym}{r52.get('low', 'N/A')} — High {sym}{r52.get('high', 'N/A')}\n"
                f"- **Moving Averages:** SMA-20: {sym}{tech.get('sma_20', 'N/A')} | EMA-50: {sym}{tech.get('ema_50', 'N/A')} | EMA-200: {sym}{tech.get('ema_200', 'N/A')}\n"
                f"- **In Simple Terms:** {explainer_res.get('simple_sections', {}).get('historic_price_explained', '')}"
            )

        if any(w in lower for w in ["score", "confidence", "rating"]):
            return (
                f"The InvestPI forensic score for {company} ({ticker}) is **{score}/10**, classified as **{flag}**.\n\n"
                f"This score is calculated deterministically across 9 independent compliance parameters. "
                f"Major downward penalties were triggered by unrealistic price velocity targets and regulatory licensing checks.\n\n"
                f"{explainer_res.get('summary', '')}"
            )

        if any(w in lower for w in ["p1", "price move", "velocity"]):
            return (
                f"**Parameter 1: Price-Move Plausibility Analysis**\n"
                f"Current Price: {cmp} | Claimed Target: {target}.\n"
                f"The claimed price target requires an abnormal annualized move that significantly exceeds the stock's "
                f"5-year historical 3-sigma volatility envelope ({price_res.get('volatility', {}).get('annualized_vol_pct', 'N/A')}% annualized volatility)."
            )

        if any(w in lower for w in ["license", "licensing", "sebi", "p8", "unregistered"]):
            return (
                f"**Parameter 8: Statutory Regulatory Licensing**\n"
                f"The promoter/creator was checked against the SEBI/regulator intermediary register. "
                f"No active Research Analyst (RA) or Investment Adviser (IA) registration was found for the entity distributing this tip."
            )

        return (
            f"Regarding {company} ({ticker}): The forensic audit classified this claim as **{flag}** (InvestPI Score: {score}/10). "
            f"The target of {target} diverges substantially from 5-year historical fundamentals and empirical analyst/EMA-200 baselines.\n\n"
            f"{explainer_res.get('summary', '')}"
        )

    def respond(
        self,
        message: str,
        report_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, bool]:
        """
        Processes a user query against the forensic findings and specialized sub-agents with rigid guardrails.
        Returns:
            (response_text: str, is_in_scope: bool)
        """
        report_context = report_context or {}

        # 1. Deterministic Pre-guardrail check
        if not self.is_question_in_scope(message, report_context):
            logger.info(f"Guardrail triggered for out-of-scope query: '{message}'")
            self.last_subagent_bundle = None
            return GUARDRAIL_REJECTION_MESSAGE, False

        # 2. Execute specialized Sub-Agents in parallel (Historic Price, Price Target/EMA-200, Fundamentals, Explainer)
        resolved = report_context.get("resolved_stock", {})
        ticker = resolved.get("ticker", "AUDITED_EQUITY")
        subagent_bundle = self.coordinator.execute_all(
            ticker=ticker,
            report_context=report_context,
            message=message
        )
        self.last_subagent_bundle = subagent_bundle

        # 3. Check offline / demo mode
        if Config.DEMO_MODE or not self.client:
            logger.info("Serving chatbot response via Sub-Agent Bundle in Demo / Offline mode.")
            reply = self.generate_demo_response(message, report_context, subagent_bundle=subagent_bundle)
            return reply, True

        # 4. Gemini 3.1 Flash-Lite with rigid system instructions & sub-agent outputs
        system_instruction = self.build_system_prompt(report_context, subagent_bundle=subagent_bundle)

        history_lines = []
        if history:
            for item in history[-6:]:
                role = "User" if item.get("role") == "user" else "InvestPI Assistant"
                history_lines.append(f"{role}: {item.get('content', '')}")
        history_block = "\n".join(history_lines) if history_lines else "None."

        full_prompt = (
            f"{system_instruction}\n\n"
            f"PRIOR CONVERSATION HISTORY:\n{history_block}\n\n"
            f"CURRENT USER QUESTION: {message}\n\n"
            f"INVESTPI ASSISTANT RESPONSE:"
        )

        fallback_models = [
            "gemini-3.1-flash-lite",
            "models/gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-2.0-flash"
        ]

        for model in list(dict.fromkeys(fallback_models)):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,  # Low temperature for factual forensic precision
                        max_output_tokens=2500  # Sufficient budget for internal thinking + complete multi-paragraph answer
                    )
                )
                text = (response.text or "").strip()

                # Post-guardrail check on response
                if GUARDRAIL_REJECTION_MESSAGE.lower() in text.lower():
                    return GUARDRAIL_REJECTION_MESSAGE, False

                # Ensure response wasn't truncated prematurely
                if len(text) >= 40:
                    return text, True
                logger.warning(f"Model {model} returned truncated text ({len(text)} chars), trying next...")
            except Exception as e:
                logger.warning(f"Chat generation attempt failed on {model}: {e}")

        # Fallback if API calls fail (uses live sub-agent data!)
        return self.generate_demo_response(message, report_context, subagent_bundle=subagent_bundle), True


# Global default instance
forensic_agent = ForensicAssistantAgent()
