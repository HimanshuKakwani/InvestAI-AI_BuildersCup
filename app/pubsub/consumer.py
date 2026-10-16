"""Google Cloud Pub/Sub Push Consumer and Forensic Task Worker."""
import base64
import json
import logging
from typing import Dict, Any

from app.pubsub.events import LeadSubmittedEvent, AuditCompletedEvent
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

        # Financial tip: Generate charts, build PDF link, and cache reports
        all_reports = result.get("reports", [result])
        for rep in all_reports:
            ticker = rep.get("resolved_stock", {}).get("ticker")
            prices_df = analysis_service.loader.get_price_history(ticker)
            chart_b64 = generate_price_target_chart(
                prices_df,
                ticker=ticker,
                target_price=rep.get("claim", {}).get("target_price"),
                current_price=rep.get("current_price")
            )
            rep_id = rep.get("report_id")
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


def handle_push_message(push_envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Google Cloud Pub/Sub HTTP Push message format and invoke the forensic worker."""
    if not isinstance(push_envelope, dict) or "message" not in push_envelope:
        raise ValueError("Invalid Pub/Sub push envelope format. Missing 'message' field.")

    message_obj = push_envelope["message"]
    data_b64 = message_obj.get("data", "")
    message_id = message_obj.get("messageId", "unknown")

    if not data_b64:
        raise ValueError("Pub/Sub message contains no data payload.")

    decoded_json_str = base64.b64decode(data_b64).decode("utf-8")
    event_dict = json.loads(decoded_json_str)
    event = LeadSubmittedEvent.from_dict(event_dict)

    logger.info(f"Received Pub/Sub Push message: msg_id={message_id}, case_id={event.case_id}")
    return process_lead_event(event)
