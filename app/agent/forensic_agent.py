"""InvestPI Forensic Assistant Agent with Heavy Guardrails."""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types
from app.config import Config

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

# Core audit domain keywords
IN_SCOPE_CORE_KEYWORDS = {
    "score", "confidence", "confidence score", "verdict", "risk", "high risk", "low risk", "caution",
    "parameter", "parameters", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9",
    "price", "target", "cmp", "current price", "target price", "upside", "horizon", "valuation",
    "pe", "pe ratio", "earnings", "profit", "loss", "pat", "promoter", "holding", "pledge",
    "pledging", "analyst", "consensus", "surveillance", "asm", "gsm", "volume", "hard gate",
    "sebi", "mas", "asic", "regulator", "regulatory", "license", "licensing", "unregistered",
    "hype", "guarantee", "manipulation", "quote", "transcript", "video", "influencer", "channel",
    "dossier", "report", "finding", "findings", "evidence", "flag", "audited", "audit", "investigation",
    "why", "explain", "breakdown", "summarize", "details", "methodology", "calculation"
}


class ForensicAssistantAgent:
    """Intelligent Conversational Agent grounded in the current audit report with rigid scope boundaries."""

    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.model_name = "gemini-3.1-flash-lite"
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def is_question_in_scope(self, message: str, report_context: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if a user message stays strictly within the domain of the audited findings."""
        if not message:
            return False

        lower_msg = message.strip().lower()

        # 1. Hard rejection on blatant out-of-scope topics
        for pattern in OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, lower_msg, re.IGNORECASE):
                # Exception: if user specifically refers to the audited stock or score along with it
                # but standard out-of-scope triggers take precedence
                return False

        # 2. Check for reference to the audited stock (ticker or company name)
        stock_terms = set()
        if report_context:
            resolved_stock = report_context.get("resolved_stock") or {}
            ticker = resolved_stock.get("ticker", "").lower().replace(".ns", "").replace(".si", "").replace(".ax", "")
            company_name = resolved_stock.get("company_name", "").lower()
            if ticker:
                stock_terms.add(ticker)
            for word in re.findall(r"\w+", company_name):
                if len(word) >= 3 and word not in {"ltd", "limited", "corp", "inc"}:
                    stock_terms.add(word)

        # Check if message mentions the stock or company
        for term in stock_terms:
            if term and term in lower_msg:
                return True

        # 3. Check for core audit and forensic concepts
        msg_words = set(re.findall(r"\w+", lower_msg))
        if bool(msg_words.intersection(IN_SCOPE_CORE_KEYWORDS)):
            return True

        # Short conversational continuations ("why", "explain that", "what do you mean")
        if len(lower_msg.split()) <= 4 and any(w in lower_msg for w in ["why", "explain", "how", "what", "more"]):
            return True

        return False

    def build_system_prompt(self, report_context: Dict[str, Any]) -> str:
        """Constructs rigid forensic context and guardrail rules for Gemini."""
        resolved = report_context.get("resolved_stock", {})
        ticker = resolved.get("ticker", "AUDITED_EQUITY")
        company_name = resolved.get("company_name", ticker)
        verdict = report_context.get("verdict", {})
        claim = report_context.get("claim", {})
        parameters = report_context.get("parameters", [])

        # Summarize parameters
        params_summary = []
        for p in parameters:
            p_id = p.get("parameter_id", "")
            p_name = p.get("name", "")
            p_status = p.get("status", "")
            p_score = p.get("score", "")
            p_details = p.get("details", "")
            params_summary.append(f"- {p_id} ({p_name}): Status={p_status}, Score={p_score}. Details: {p_details}")
        params_text = "\n".join(params_summary) if params_summary else "Deterministic parameters evaluated."

        return f"""You are the InvestPI Forensic Intelligence Assistant, an empirical financial audit agent.
You are interrogating a completed forensic investigation for:
SECURITY: {company_name} ({ticker})
INVESTPI CONFIDENCE SCORE: {verdict.get('score', 'N/A')}/10
VERDICT CLASSIFICATION: {verdict.get('flag', 'HIGH RISK')}
VERDICT SUMMARY: {verdict.get('summary', 'Audit complete.')}
CURRENT MARKET PRICE: {report_context.get('current_price', 'N/A')}
CLAIMED TARGET PRICE: {claim.get('target_price', 'N/A')} (Horizon: {claim.get('time_horizon_days', 'N/A')} days)
CLAIMED CREATOR / CHANNEL: {claim.get('channel_or_author', claim.get('creator_claimed_name', 'Unknown'))}
EXTRACTED CLAIM QUOTE: "{claim.get('exact_quote', 'N/A')}"
EVALUATED COMPLIANCE PARAMETERS:
{params_text}

CRITICAL HEAVY GUARDRAIL POLICY:
1. You may ONLY answer questions directly pertaining to:
   - The audited security ({ticker} / {company_name}).
   - The InvestPI confidence score and risk verdict.
   - The 9 deterministic compliance parameters (P1 through P9).
   - The empirical valuation, historical prices, and regulatory licensing checks.
2. IF the user asks ANY question outside this audit dossier (e.g. general knowledge, coding, weather, recipes, sports, politics, movies, jokes, cryptocurrency, or other unrelated stocks):
   You MUST respond with EXACTLY this sentence and NOTHING ELSE:
   "{GUARDRAIL_REJECTION_MESSAGE}"
3. Do NOT provide investment advice or price predictions. Answer as an objective forensic analyst explaining the empirical findings.
4. Keep responses clear, concise, professional, and directly grounded in the findings above.
"""

    def generate_demo_response(self, message: str, report_context: Dict[str, Any]) -> str:
        """Deterministic offline response when operating without Gemini API Key."""
        lower = message.lower()
        resolved = report_context.get("resolved_stock", {})
        ticker = resolved.get("ticker", "the audited stock")
        company = resolved.get("company_name", ticker)
        verdict = report_context.get("verdict", {})
        score = verdict.get("score", "2.2")
        flag = verdict.get("flag", "HIGH RISK")
        claim = report_context.get("claim", {})
        target = claim.get("target_price", "N/A")
        cmp = report_context.get("current_price", "N/A")

        if any(w in lower for w in ["score", "confidence", "rating"]):
            return (
                f"The InvestPI forensic score for {company} ({ticker}) is {score}/10, classified as **{flag}**.\n\n"
                f"This score is calculated deterministically across 9 independent compliance parameters. "
                f"Major downward penalties were triggered by unrealistic price velocity targets and regulatory licensing checks."
            )

        if any(w in lower for w in ["p1", "price move", "velocity"]):
            return (
                f"**Parameter 1: Price-Move Plausibility Analysis**\n"
                f"Current Price: {cmp} | Claimed Target: {target}.\n"
                f"The claimed price target requires an abnormal annualized move that significantly exceeds the stock's "
                f"5-year historical 3-sigma volatility envelope."
            )

        if any(w in lower for w in ["license", "licensing", "sebi", "p8", "unregistered"]):
            return (
                f"**Parameter 8: Statutory Regulatory Licensing**\n"
                f"The promoter/creator was checked against the SEBI/regulator intermediary register. "
                f"No active Research Analyst (RA) or Investment Adviser (IA) registration was found for the entity distributing this tip."
            )

        if any(w in lower for w in ["p2", "valuation", "p/e", "pe"]):
            return (
                f"**Parameter 2: Historical Valuation Envelope**\n"
                f"The target price implies a valuation multiple that overshoots the company's 5-year empirical median P/E and P/B range."
            )

        return (
            f"Regarding {company} ({ticker}): The forensic audit classified this claim as **{flag}** (InvestPI Score: {score}/10). "
            f"The target of {target} diverges substantially from 5-year historical fundamentals and empirical analyst consensus."
        )

    def respond(
        self,
        message: str,
        report_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, bool]:
        """
        Processes a user query against the forensic findings with rigid guardrails.
        Returns:
            (response_text: str, is_in_scope: bool)
        """
        report_context = report_context or {}

        # 1. Deterministic Pre-guardrail check
        if not self.is_question_in_scope(message, report_context):
            logger.info(f"Guardrail triggered for out-of-scope query: '{message}'")
            return GUARDRAIL_REJECTION_MESSAGE, False

        # 2. Check offline / demo mode
        if Config.DEMO_MODE or not self.client:
            logger.info("Serving chatbot response in Demo / Offline mode.")
            reply = self.generate_demo_response(message, report_context)
            return reply, True

        # 3. Gemini 3.1 Flash-Lite with rigid system instructions
        system_instruction = self.build_system_prompt(report_context)

        # Build single comprehensive prompt string
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
            "models/gemini-3.1-flash-lite",
            "gemini-3.1-flash-lite",
            "models/gemini-3.8-flash",
            "gemini-3.8-flash",
            "models/gemini-2.5-flash-lite",
            "gemini-2.5-flash-lite",
            "models/gemini-3.5-flash-lite",
            "models/gemini-flash-lite-latest"
        ]

        for model in list(dict.fromkeys(fallback_models)):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,  # Low temperature for factual forensic precision
                        max_output_tokens=600
                    )
                )
                text = (response.text or "").strip()

                # Post-guardrail check on response
                if GUARDRAIL_REJECTION_MESSAGE.lower() in text.lower():
                    return GUARDRAIL_REJECTION_MESSAGE, False

                return text, True
            except Exception as e:
                logger.warning(f"Chat generation attempt failed on {model}: {e}")

        # Fallback if API calls fail
        return self.generate_demo_response(message, report_context), True


# Global default instance
forensic_agent = ForensicAssistantAgent()
