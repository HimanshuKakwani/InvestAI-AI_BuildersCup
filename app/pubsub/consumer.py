"""Google Cloud Pub/Sub Push Consumer and Forensic Task Worker."""
import base64
import json
import logging
from typing import Dict, Any

from app.pubsub.events import LeadSubmittedEvent, AuditCompletedEvent, StockSyncEvent, MarketSyncEvent
from app.pubsub.store import case_store, CaseStatus
from app.reporting.chart_generator import generate_price_target_chart

logger = logging.getLogger("InvestPI.PubSub.Consumer")


def process_lead_event(event: LeadSubmittedEvent) -> Dict[str, Any]:
    """Execute complete forensic audit workflow for an ingested lead event."""
    from app.routes.api import analysis_service, reports_cache
    from app.pubsub.publisher import publisher

    case_id = event.case_id
    logger.info(f"Processing investigation for case: {case_id} (modality={event.modality}, region={event.region})")

    case_store.update_status(
        case_id,
        CaseStatus.PROCESSING,
        message="Extracting multimodal claims and auditing regulatory databases..."
    )

    try:
        # Determine payload type
        if event.modality in ["screenshot", "file"]:
            # If payload is base64 encoded string, decode it to raw bytes
            raw_bytes = event.payload
            if isinstance(raw_bytes, str):
                try:
                    raw_bytes = base64.b64decode(raw_bytes)
                except Exception as e:
                    logger.error(f"Base64 decode failed for case {case_id}: {e}")
                    raise ValueError(f"Invalid base64 payload: {e}")

            mime_type = event.mime_type or "image/png"
            result = analysis_service.run_investigation(
                "screenshot",
                raw_bytes,
                region_override=event.region,
                image_mime=mime_type
            )
        else:
            result = analysis_service.run_investigation(
                event.modality,
                event.payload,
                region_override=event.region
            )

        # Ensure modality is retained on output
        result["modality"] = event.modality

        # Check if rejected as non-financial material
        if result.get("is_financial_advice") is False:
            logger.info(f"Case {case_id} classified as non-financial advice. Forensic audit skipped.")
            case_store.save_result(case_id, result, is_financial=False)
            publisher.publish_audit_completed(
                AuditCompletedEvent(
                    case_id=case_id,
                    status="REJECTED_IRRELEVANT",
                    result=result
                )
            )
            return result

        # Financial tip: Generate charts, build PDF link, and cache reports in Firestore
        all_reports = result.get("reports", [result])
        for rep in all_reports:
            rep["modality"] = event.modality
            ticker = rep.get("resolved_stock", {}).get("ticker")
            prices_df = analysis_service.loader.get_price_history(ticker)
            chart_b64 = generate_price_target_chart(
                prices_df,
                ticker=ticker,
                target_price=rep.get("claim", {}).get("target_price"),
                current_price=rep.get("current_price")
            )
            rep_id = rep.get("report_id")
            # Persists to L1 memory cache and Firebase Firestore L2
            reports_cache[rep_id] = {"data": rep, "chart_b64": chart_b64}
            rep["pdf_url"] = f"/api/report/{rep_id}.pdf"
            rep["chart_b64"] = chart_b64

        if all_reports and "pdf_url" in all_reports[0]:
            result["pdf_url"] = all_reports[0]["pdf_url"]

        case_store.save_result(case_id, result, is_financial=True)
        logger.info(f"Case {case_id} successfully audited and completed.")

        publisher.publish_audit_completed(
            AuditCompletedEvent(
                case_id=case_id,
                status="COMPLETED",
                result=result
            )
        )
        return result

    except Exception as e:
        logger.error(f"Error auditing case {case_id}: {e}", exc_info=True)
        error_msg = str(e)
        case_store.mark_failed(case_id, error_msg)
        publisher.publish_audit_completed(
            AuditCompletedEvent(
                case_id=case_id,
                status="FAILED",
                error=error_msg
            )
        )
        return {"error": error_msg, "case_id": case_id, "status": "FAILED"}


def process_stock_sync_event(event: StockSyncEvent) -> Dict[str, Any]:
    """
    Executes asynchronous historical prices and company fundamentals caching for a single stock.
    Saves price series to Firestore 'investpi_prices' and valuation snapshot to 'investpi_fundamentals'.
    """
    from app.routes.api import analysis_service

    ticker = event.ticker
    logger.info(f"[PubSub Sync] Synchronizing prices & fundamentals for {ticker} (market={event.market}, force={event.force_refresh})...")

    try:
        # 1. Increment/fetch 5-year price series (persists to Firestore 'investpi_prices')
        df = analysis_service.loader.get_price_history(ticker, force_refresh=event.force_refresh)
        candles_count = len(df) if df is not None and not df.empty else 0

        # 2. Fetch/update company valuation fundamentals (persists to Firestore 'investpi_fundamentals')
        fund = analysis_service.loader.get_fundamentals(ticker, force_refresh=event.force_refresh)
        has_fund = fund is not None

        logger.info(f"[PubSub Sync] Successfully synced {ticker}: {candles_count} candles, fundamentals={has_fund}")
        return {
            "status": "success",
            "ticker": ticker,
            "market": event.market,
            "candles_count": candles_count,
            "fundamentals_cached": has_fund
        }
    except Exception as e:
        logger.error(f"[PubSub Sync] Error syncing data for {ticker}: {e}", exc_info=True)
        return {
            "status": "error",
            "ticker": ticker,
            "error": str(e)
        }


def process_market_sync_event(event: MarketSyncEvent) -> Dict[str, Any]:
    """
    Executes asynchronous market-wide fan-out sync across all onboarded stocks in a jurisdiction.
    Publishes individual StockSyncEvents to Pub/Sub to parallelize price and fundamentals caching.
    """
    from app.routes.api import analysis_service
    from app.pubsub.publisher import publisher

    m_code = event.market.upper()
    logger.info(f"[PubSub Market Sync] Initiating fan-out sync for market {m_code} (force={event.force_refresh})...")

    # 1. Discover all tickers in curated universe
    universe_stocks = analysis_service.loader.universe.get(m_code, [])
    tickers = [s["ticker"] for s in universe_stocks if "ticker" in s]

    # 2. Add dynamically discovered stocks from Firestore
    storage = analysis_service.loader._get_storage()
    if storage and storage.is_firestore_connected():
        try:
            docs = storage.db.collection("investpi_fundamentals").where("market", "==", m_code).stream()
            for doc in docs:
                t = doc.id
                if t and t not in tickers:
                    tickers.append(t)
        except Exception as e:
            logger.debug(f"Could not load Firestore dynamic stocks for market sync: {e}")

    # 3. Fan-out individual StockSyncEvents via Pub/Sub
    dispatched = []
    for ticker in tickers:
        stock_event = StockSyncEvent(
            ticker=ticker,
            market=m_code,
            force_refresh=event.force_refresh
        )
        msg_id = publisher.publish_stock_sync(stock_event)
        dispatched.append({"ticker": ticker, "msg_id": msg_id})

    logger.info(f"[PubSub Market Sync] Dispatched {len(dispatched)} parallel stock sync jobs for {m_code}.")
    return {
        "status": "dispatched",
        "market": m_code,
        "total_stocks": len(tickers),
        "dispatched_tasks": dispatched
    }


def handle_push_message(push_envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Google Cloud Pub/Sub HTTP Push message format and invoke the appropriate task worker."""
    if not isinstance(push_envelope, dict) or "message" not in push_envelope:
        raise ValueError("Invalid Pub/Sub push envelope format. Missing 'message' field.")

    message_obj = push_envelope["message"]
    data_b64 = message_obj.get("data", "")
    message_id = message_obj.get("messageId", "unknown")

    if not data_b64:
        raise ValueError("Pub/Sub message contains no data payload.")

    decoded_json_str = base64.b64decode(data_b64).decode("utf-8")
    event_dict = json.loads(decoded_json_str)

    # Route based on event type or attributes
    event_type = event_dict.get("event_type", "")
    attrs = message_obj.get("attributes", {})
    if attrs.get("event_type"):
        event_type = attrs["event_type"]

    logger.info(f"Received Pub/Sub Push message: msg_id={message_id}, event_type={event_type or 'lead'}")

    if event_type == "stock_sync" or ("ticker" in event_dict and "modality" not in event_dict):
        stock_event = StockSyncEvent.from_dict(event_dict)
        return process_stock_sync_event(stock_event)
    elif event_type == "market_sync":
        market_event = MarketSyncEvent.from_dict(event_dict)
        return process_market_sync_event(market_event)
    else:
        lead_event = LeadSubmittedEvent.from_dict(event_dict)
        return process_lead_event(lead_event)
