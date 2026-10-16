"""Google Cloud Pub/Sub Publisher with in-process fallback."""
import logging
import concurrent.futures
from typing import Optional, Callable
from app.config import Config
from app.pubsub.events import LeadSubmittedEvent, AuditCompletedEvent, StockSyncEvent, MarketSyncEvent

logger = logging.getLogger("InvestPI.PubSub.Publisher")

# Thread pool executor for local fallback when GCP credentials / project are not configured
_fallback_executor = concurrent.futures.ThreadPoolExecutor(max_workers=6, thread_name_prefix="pubsub-fallback")


class PubSubPublisher:
    """Manages publishing events to Google Cloud Pub/Sub topics.
    
    If GCP_PROJECT_ID is unset or Pub/Sub client cannot connect, automatically
    falls back to asynchronous local background worker for seamless offline development.
    """

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or Config.GCP_PROJECT_ID
        self.client = None
        self.is_gcp_active = False
        self._local_handler: Optional[Callable[[LeadSubmittedEvent], None]] = None

        if self.project_id:
            try:
                from google.cloud import pubsub_v1
                self.client = pubsub_v1.PublisherClient()
                self.is_gcp_active = True
                logger.info(f"Initialized Google Cloud Pub/Sub Publisher for project: {self.project_id}")
            except Exception as e:
                logger.warning(
                    f"Could not initialize Google Cloud Pub/Sub client ({e}). "
                    "Operating in Local Background Worker Fallback mode."
                )
                self.is_gcp_active = False
        else:
            logger.info("GCP_PROJECT_ID not set. Running PubSubPublisher in Local Fallback mode.")

    def set_local_handler(self, handler: Callable[[LeadSubmittedEvent], None]):
        """Register local consumer handler for fallback execution."""
        self._local_handler = handler

    def publish_lead(self, event: LeadSubmittedEvent) -> str:
        """Publishes a lead submission event to the inbound Pub/Sub topic."""
        topic_name = Config.PUBSUB_TOPIC_LEADS
        payload_bytes = event.to_json().encode("utf-8")

        if self.is_gcp_active and self.client:
            try:
                topic_path = self.client.topic_path(self.project_id, topic_name)
                future = self.client.publish(
                    topic_path,
                    payload_bytes,
                    case_id=event.case_id,
                    modality=event.modality,
                    region=event.region,
                    event_type=event.event_type
                )
                msg_id = future.result(timeout=10.0)
                logger.info(f"Published LeadSubmittedEvent to GCP topic '{topic_name}': msg_id={msg_id}, case_id={event.case_id}")
                return str(msg_id)
            except Exception as e:
                logger.error(f"Failed to publish to GCP Pub/Sub: {e}. Falling back to local worker.", exc_info=True)

        # Local Fallback Dispatch
        logger.info(f"[Fallback Mode] Dispatching case {event.case_id} to local thread pool")
        if self._local_handler:
            _fallback_executor.submit(self._local_handler, event)
        else:
            from app.pubsub.consumer import process_lead_event
            _fallback_executor.submit(process_lead_event, event)

        return f"local-{event.case_id}"

    def publish_audit_completed(self, event: AuditCompletedEvent) -> str:
        """Publishes an audit completed event to the completed audits topic."""
        topic_name = Config.PUBSUB_TOPIC_AUDITS
        payload_bytes = event.to_json().encode("utf-8")

        if self.is_gcp_active and self.client:
            try:
                topic_path = self.client.topic_path(self.project_id, topic_name)
                future = self.client.publish(
                    topic_path,
                    payload_bytes,
                    case_id=event.case_id,
                    status=event.status,
                    event_type=event.event_type
                )
                msg_id = future.result(timeout=10.0)
                logger.info(f"Published AuditCompletedEvent to GCP topic '{topic_name}': msg_id={msg_id}, case_id={event.case_id}")
                return str(msg_id)
            except Exception as e:
                logger.error(f"Failed to publish completed event to GCP Pub/Sub: {e}")

        logger.info(f"[Fallback Mode] Audit completed event logged for case {event.case_id}")
        return f"local-audit-{event.case_id}"

    def publish_stock_sync(self, event: StockSyncEvent) -> str:
        """Publishes a per-stock price and fundamental sync event to Pub/Sub for parallel Firestore caching."""
        topic_name = getattr(Config, "PUBSUB_TOPIC_SYNC", "investpi-market-sync")
        payload_bytes = event.to_json().encode("utf-8")

        if self.is_gcp_active and self.client:
            try:
                topic_path = self.client.topic_path(self.project_id, topic_name)
                future = self.client.publish(
                    topic_path,
                    payload_bytes,
                    ticker=event.ticker,
                    market=event.market,
                    event_type=event.event_type
                )
                msg_id = future.result(timeout=10.0)
                logger.info(f"Published StockSyncEvent to GCP topic '{topic_name}' for {event.ticker}: msg_id={msg_id}")
                return str(msg_id)
            except Exception as e:
                logger.warning(f"Could not publish StockSyncEvent to GCP Pub/Sub ({e}). Executing via local thread pool.")

        # Local Fallback Dispatch
        from app.pubsub.consumer import process_stock_sync_event
        _fallback_executor.submit(process_stock_sync_event, event)
        return f"local-sync-{event.ticker}"

    def publish_market_sync(self, event: MarketSyncEvent) -> str:
        """Publishes a market sync fan-out event to Pub/Sub."""
        topic_name = getattr(Config, "PUBSUB_TOPIC_SYNC", "investpi-market-sync")
        payload_bytes = event.to_json().encode("utf-8")

        if self.is_gcp_active and self.client:
            try:
                topic_path = self.client.topic_path(self.project_id, topic_name)
                future = self.client.publish(
                    topic_path,
                    payload_bytes,
                    market=event.market,
                    event_type=event.event_type
                )
                msg_id = future.result(timeout=10.0)
                logger.info(f"Published MarketSyncEvent to GCP topic '{topic_name}' for {event.market}: msg_id={msg_id}")
                return str(msg_id)
            except Exception as e:
                logger.warning(f"Could not publish MarketSyncEvent to GCP Pub/Sub ({e}). Executing via local thread pool.")

        # Local Fallback Dispatch
        from app.pubsub.consumer import process_market_sync_event
        _fallback_executor.submit(process_market_sync_event, event)
        return f"local-market-sync-{event.market}"


# Global publisher instance
publisher = PubSubPublisher()
