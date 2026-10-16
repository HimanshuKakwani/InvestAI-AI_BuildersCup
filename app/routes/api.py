"""InvestPI Flask Application Factory & Routes."""
import time
import logging
import json
import uuid
import base64
import threading
from flask import Flask, request, jsonify, render_template, send_file, g, Response
from flasgger import Swagger
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config, ROOT_DIR
from app.data.storage import ReportStorage
from app.engine.orchestrator import AnalysisService
from app.reporting.chart_generator import generate_price_target_chart
from app.reporting.pdf_generator import build_pdf_report
from app.pubsub.events import LeadSubmittedEvent
from app.pubsub.store import case_store, CaseStatus
from app.pubsub.publisher import publisher
from app.pubsub.consumer import handle_push_message
from app.agent import forensic_agent

# API logger inheriting from parent InvestPI
logger = logging.getLogger("InvestPI.API")

analysis_service = AnalysisService()
# Hybrid in-memory bounded LRU cache with Firebase Firestore multi-instance persistence
reports_cache = ReportStorage()

def create_app():
    templates_path = str(ROOT_DIR / "templates")
    static_path = str(ROOT_DIR / "static")
    app = Flask(__name__, template_folder=templates_path, static_folder=static_path)
    app.config.from_object(Config)

    # Enable Cloud Run reverse-proxy HTTPS header forwarding
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1
    )


    # Swagger / OpenAPI Configuration
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/"
    }
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "InvestPI Forensic Due-Diligence & Scam Defense Shield API",
            "description": "Deterministic 9-parameter compliance auditing engine for retail investors in JAPAC (SEBI, MAS, ASIC). Audits YouTube URLs, chat screenshots, and text tips against 5-year empirical market data.",
            "version": "1.0.0",
            "contact": {
                "name": "InvestPI Google AI Builder Cup 2026 Team"
            }
        },
        "tags": [
            {"name": "Forensic Engine", "description": "Core analysis and audit verification endpoints"},
            {"name": "System & Data", "description": "Health checks, market packs, and report downloads"}
        ]
    }
    Swagger(app, config=swagger_config, template=swagger_template)

    # Request & Response Logging Middleware
    @app.before_request
    def before_request_logging():
        g.start_time = time.time()
        # Avoid logging raw binary uploads or static assets in full
        if request.path.startswith("/flasgger") or request.path.startswith("/static"):
            return

        client_ip = request.remote_addr
        method = request.method
        path = request.path

        if request.content_type and "multipart/form-data" in request.content_type:
            files_desc = list(request.files.keys())
            form_data = {k: v for k, v in request.form.items()}
            logger.info(f">> INCOMING [{method}] {path} from {client_ip} | Files: {files_desc} | Form: {form_data}")
        elif request.is_json:
            payload_peek = request.get_json(silent=True)
            logger.info(f">> INCOMING [{method}] {path} from {client_ip} | JSON: {payload_peek}")
        else:
            logger.info(f">> INCOMING [{method}] {path} from {client_ip}")

    @app.after_request
    def after_request_logging(response):
        if request.path.startswith("/flasgger") or request.path.startswith("/static"):
            return response

        duration_ms = round((time.time() - getattr(g, "start_time", time.time())) * 1000, 2)
        status = response.status_code

        # Log brief summary of JSON responses
        if response.content_type and "application/json" in response.content_type:
            try:
                resp_json = json.loads(response.get_data(as_text=True))
                # Truncate parameters array or large data if needed
                if isinstance(resp_json, dict) and "parameters" in resp_json:
                    summary = {
                        "report_id": resp_json.get("report_id"),
                        "ticker": resp_json.get("resolved_stock", {}).get("ticker"),
                        "flag": resp_json.get("verdict", {}).get("flag"),
                        "score": resp_json.get("verdict", {}).get("score")
                    }
                    logger.info(f"<< OUTGOING [{request.method}] {request.path} | Status: {status} | Duration: {duration_ms}ms | Summary: {summary}")
                else:
                    logger.info(f"<< OUTGOING [{request.method}] {request.path} | Status: {status} | Duration: {duration_ms}ms | Resp: {resp_json}")
            except Exception:
                logger.info(f"<< OUTGOING [{request.method}] {request.path} | Status: {status} | Duration: {duration_ms}ms")
        else:
            logger.info(f"<< OUTGOING [{request.method}] {request.path} | Status: {status} | Duration: {duration_ms}ms | Type: {response.content_type}")

        # Add standard CORS headers for cross-origin frontend/demo access
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            "error": "Uploaded image exceeds the 10 MB file size limit.",
            "status": 413
        }), 413

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/healthz")
    def healthz():
        """
        System Health Check
        ---
        tags:
          - System & Data
        responses:
          200:
            description: Service health status and runtime demo mode
            schema:
              properties:
                status:
                  type: string
                  example: healthy
                service:
                  type: string
                  example: InvestPI Engine
                demo_mode:
                  type: boolean
                  example: false
                firebase_connected:
                  type: boolean
                  example: false
        """
        return jsonify({
            "status": "healthy",
            "service": "InvestPI Engine",
            "demo_mode": Config.DEMO_MODE,
            "firebase_connected": reports_cache.is_firestore_connected()
        })


    @app.route("/api/markets")
    def get_markets():
        """
        Supported Jurisdictions & Market Packs
        ---
        tags:
          - System & Data
        responses:
          200:
            description: List of supported market packs (IN, SG, AU) with regulator metadata
        """
        return jsonify(analysis_service.loader.markets)

    @app.route("/api/markets/schedule")
    def get_markets_schedule():
        """
        Market Schedule & Cloud Scheduler Registry
        ---
        tags:
          - System & Data
        responses:
          200:
            description: Live schedule status and Cloud Scheduler commands for all onboarded markets.
        """
        from app.data.market_sync import MarketSyncService
        service = MarketSyncService(analysis_service.loader)
        req_host = request.host_url
        return jsonify(service.get_all_schedules(service_url=req_host)), 200

    @app.route("/api/jobs/sync-market", methods=["GET", "POST"])
    def sync_market_job():
        """
        Automated Market-Close Data Synchronization
        ---
        tags:
          - System & Data
        parameters:
          - name: market
            in: query
            type: string
            required: true
            description: Target market code (IN, SG, AU)
            example: IN
          - name: force
            in: query
            type: boolean
            required: false
            description: Force sync even if outside the scheduled market-close window
        responses:
          200:
            description: Synchronization execution summary.
          400:
            description: Missing or invalid market parameter or rejected timing.
          403:
            description: Unauthorized cron secret.
        """
        cron_secret = getattr(Config, "CRON_SECRET", "")
        if cron_secret:
            token = request.headers.get("X-Cron-Secret") or request.args.get("secret")
            if token != cron_secret:
                return jsonify({"status": "unauthorized", "message": "Invalid cron secret"}), 403

        market = request.args.get("market") or (request.get_json(silent=True) or {}).get("market")
        if not market:
            return jsonify({"status": "error", "message": "Missing required 'market' parameter (e.g. IN, SG, AU)"}), 400

        force_param = request.args.get("force", "").lower() in ("1", "true", "yes")
        is_async = request.args.get("async", "").lower() in ("1", "true", "yes") or (request.get_json(silent=True) or {}).get("async") is True

        if is_async:
            from app.pubsub.events import MarketSyncEvent
            from app.pubsub.publisher import publisher
            event = MarketSyncEvent(market=market.upper(), force_refresh=force_param)
            msg_id = publisher.publish_market_sync(event)
            return jsonify({
                "status": "queued",
                "mode": "async_pubsub",
                "market": market.upper(),
                "message": f"End-of-day market sync for {market.upper()} queued via Pub/Sub fan-out.",
                "msg_id": msg_id
            }), 202

        from app.data.market_sync import MarketSyncService
        service = MarketSyncService(analysis_service.loader)
        result = service.sync_market(market, force=force_param)

        status_code = 200 if result.get("status") in ("success", "skipped") else 400
        return jsonify(result), status_code

    @app.route("/api/admin/seed-prices", methods=["GET", "POST"])
    def admin_seed_prices():
        """
        Seed Price CSVs to Firestore
        ---
        tags:
          - System & Data
        responses:
          200:
            description: Successfully seeded all price CSVs to Firestore 'investpi_prices'.
        """
        storage = analysis_service.loader._get_storage()
        if not storage or not storage.is_firestore_connected():
            return jsonify({"status": "error", "message": "Firestore is not connected."}), 503

        from app.config import DATA_DIR
        import pandas as pd
        p_dir = DATA_DIR / "prices"
        seeded = []
        if p_dir.exists():
            for pf in p_dir.glob("*.csv"):
                ticker = pf.stem
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        csv_text = f.read()
                    df = pd.read_csv(pf, index_col="Date")
                    last_dt_str = str(df.index[-1].date() if hasattr(df.index[-1], "date") else str(df.index[-1]).split()[0])
                    storage.save_prices(ticker, csv_text, last_date=last_dt_str, count=len(df))
                    seeded.append(ticker)
                except Exception as e:
                    logger.warning(f"Error seeding price CSV for {ticker}: {e}")

        return jsonify({
            "status": "success",
            "message": f"Successfully seeded {len(seeded)} price CSVs into Firestore 'investpi_prices'.",
            "total_seeded": len(seeded),
            "tickers": seeded
        }), 200


    @app.route("/api/report/<report_id>.pdf")
    def download_pdf(report_id):
        """
        Download PDF Audit Brief
        ---
        tags:
          - System & Data
        parameters:
          - name: report_id
            in: path
            type: string
            required: true
            description: Unique report ID generated during audit
        responses:
          200:
            description: PDF document with 9-parameter score, sources, charts, and flagged problematic findings.
          404:
            description: Report ID not found in current session.
        """
        cached = reports_cache.get(report_id)
        if not cached:
            logger.warning(f"PDF download requested for unknown report_id: {report_id}")
            return jsonify({"error": "Report not found"}), 404

        result_data = cached["data"]
        chart_b64 = cached.get("chart_b64")

        pdf_buffer = build_pdf_report(result_data, chart_b64=chart_b64)
        filename = f"InvestPI_Audit_{result_data.get('resolved_stock', {}).get('ticker', 'STOCK')}_{report_id}.pdf"
        logger.info(f"Serving generated PDF report: {filename} ({len(pdf_buffer.getvalue())} bytes)")
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        """
        Perform Forensic Due-Diligence Audit
        ---
        tags:
          - Forensic Engine
        consumes:
          - application/json
          - multipart/form-data
        parameters:
          - in: body
            name: body
            description: JSON request for YouTube URL or text tips
            required: false
            schema:
              type: object
              properties:
                modality:
                  type: string
                  enum: [youtube_url, text]
                  default: youtube_url
                  example: youtube_url
                payload:
                  type: string
                  description: YouTube link or social media chat text
                  example: https://www.youtube.com/shorts/DivTA2Lz08s
                region:
                  type: string
                  enum: [IN, SG, AU]
                  default: IN
                  example: IN
          - in: formData
            name: screenshot
            type: file
            required: false
            description: Uploaded chat screenshot image for OCR extraction
          - in: formData
            name: region
            type: string
            required: false
            default: IN
            description: Target market jurisdiction
        responses:
          200:
            description: Full forensic scorecard, 9 evaluated parameters, hard gate status, and PDF download link.
          400:
            description: Invalid input or missing payload
          500:
            description: Analysis engine execution error
        """
        try:
            # Check if multipart form upload with a file (screenshot, video, or PDF financial report)
            upload_key = next((k for k in ["screenshot", "file", "pdf"] if k in request.files), None)
            if upload_key:
                file = request.files[upload_key]
                if file.filename == "":
                    return jsonify({"error": "No file selected"}), 400
                
                image_bytes = file.read()
                mime_type = file.mimetype or "image/png"
                fn = (file.filename or "").lower()
                if fn.endswith(".mp4"):
                    mime_type = "video/mp4"
                elif fn.endswith(".mov"):
                    mime_type = "video/quicktime"
                elif fn.endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                elif fn.endswith(".webp"):
                    mime_type = "image/webp"
                elif fn.endswith(".pdf"):
                    mime_type = "application/pdf"

                region = request.form.get("region", "IN")
                result = analysis_service.run_investigation("screenshot", image_bytes, region_override=region, image_mime=mime_type)

                if result.get("is_financial_advice") is False:
                    return jsonify(result), 200

                # Process all audited stock reports
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
                    logger.info(f"[REPORT_READY] Cached report {rep_id} for {ticker} | Chart: {bool(chart_b64)} | PDF: {rep['pdf_url']}")

                result["pdf_url"] = all_reports[0].get("pdf_url")
                return jsonify(result)

            # Standard JSON body
            data = request.get_json(silent=True) or {}
            modality = data.get("modality", "text")
            payload = data.get("payload", "").strip()
            region = data.get("region", "IN")

            if not payload:
                return jsonify({"error": "Payload content (URL or text) is required"}), 400

            result = analysis_service.run_investigation(modality, payload, region_override=region)

            if result.get("is_financial_advice") is False:
                return jsonify(result), 200

            # Process all audited stock reports
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
                logger.info(f"[REPORT_READY] Cached report {rep_id} for {ticker} | Chart: {bool(chart_b64)} | PDF: {rep['pdf_url']}")

            result["pdf_url"] = all_reports[0].get("pdf_url")
            return jsonify(result)
        except Exception as e:
            logger.error(f"Analysis failure: {e}", exc_info=True)
            return jsonify({"error": f"Investigation failed: {str(e)}"}), 500

    @app.route("/api/analyze/async", methods=["POST"])
    def analyze_async():
        """
        Asynchronous Forensic Audit (Pub/Sub Event Ingestion)
        ---
        tags:
          - Forensic Engine
        consumes:
          - application/json
          - multipart/form-data
        parameters:
          - in: body
            name: body
            description: JSON request for YouTube URL or text tips
            required: false
            schema:
              type: object
              properties:
                modality:
                  type: string
                  enum: [youtube_url, text]
                  default: youtube_url
                payload:
                  type: string
                  description: YouTube link or social media chat text
                region:
                  type: string
                  enum: [IN, SG, AU]
                  default: IN
          - in: formData
            name: screenshot
            type: file
            required: false
            description: Uploaded chat screenshot or document
          - in: formData
            name: region
            type: string
            required: false
            default: IN
        responses:
          202:
            description: Investigation queued. Returns case_id and tracking URLs.
            schema:
              properties:
                case_id:
                  type: string
                status:
                  type: string
                  example: QUEUED
                status_url:
                  type: string
                stream_url:
                  type: string
          400:
            description: Missing or invalid payload
        """
        try:
            case_id = str(uuid.uuid4())
            upload_key = next((k for k in ["screenshot", "file", "pdf"] if k in request.files), None)

            if upload_key:
                file = request.files[upload_key]
                if file.filename == "":
                    return jsonify({"error": "No file selected"}), 400

                raw_bytes = file.read()
                mime_type = file.mimetype or "image/png"
                fn = (file.filename or "").lower()
                if fn.endswith(".mp4"):
                    mime_type = "video/mp4"
                elif fn.endswith(".mov"):
                    mime_type = "video/quicktime"
                elif fn.endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                elif fn.endswith(".webp"):
                    mime_type = "image/webp"
                elif fn.endswith(".pdf"):
                    mime_type = "application/pdf"

                region = request.form.get("region", "IN")
                payload_b64 = base64.b64encode(raw_bytes).decode("utf-8")

                case_store.create_case(case_id, modality="screenshot", region=region)
                event = LeadSubmittedEvent(
                    case_id=case_id,
                    modality="screenshot",
                    payload=payload_b64,
                    region=region,
                    mime_type=mime_type
                )
                publisher.publish_lead(event)

                return jsonify({
                    "case_id": case_id,
                    "status": CaseStatus.QUEUED,
                    "message": "File lead ingested successfully. Forensic audit queued.",
                    "status_url": f"/api/cases/{case_id}",
                    "stream_url": f"/api/cases/{case_id}/stream"
                }), 202

            # JSON payload
            data = request.get_json(silent=True) or {}
            modality = data.get("modality", "text")
            payload = data.get("payload", "").strip()
            region = data.get("region", "IN")

            if not payload:
                return jsonify({"error": "Payload content (URL or text) is required"}), 400

            case_store.create_case(case_id, modality=modality, region=region)
            event = LeadSubmittedEvent(
                case_id=case_id,
                modality=modality,
                payload=payload,
                region=region
            )
            publisher.publish_lead(event)

            return jsonify({
                "case_id": case_id,
                "status": CaseStatus.QUEUED,
                "message": "Lead ingested successfully. Forensic audit queued.",
                "status_url": f"/api/cases/{case_id}",
                "stream_url": f"/api/cases/{case_id}/stream"
            }), 202

        except Exception as e:
            logger.error(f"Async ingestion failed: {e}", exc_info=True)
            return jsonify({"error": f"Failed to ingest lead: {str(e)}"}), 500

    @app.route("/api/cases/<case_id>", methods=["GET"])
    def get_case(case_id):
        """
        Poll Case Status and Results
        ---
        tags:
          - Forensic Engine
        parameters:
          - name: case_id
            in: path
            type: string
            required: true
            description: Investigation case ID
        responses:
          200:
            description: Case metadata, progress status, and audit verdict
          404:
            description: Case ID not found
        """
        case = case_store.get_case(case_id)
        if not case:
            return jsonify({"error": "Case not found", "case_id": case_id}), 404
        return jsonify(case), 200

    @app.route("/api/cases/<case_id>/stream", methods=["GET"])
    def stream_case(case_id):
        """
        Real-time Server-Sent Events (SSE) Stream for Investigation Case
        ---
        tags:
          - Forensic Engine
        parameters:
          - name: case_id
            in: path
            type: string
            required: true
            description: Investigation case ID
        responses:
          200:
            description: Server-Sent Events stream delivering live status updates
        """
        def generate():
            event = threading.Event()
            case_store.register_listener(case_id, event)
            try:
                # Initial snapshot
                c = case_store.get_case(case_id)
                if not c:
                    yield f"data: {json.dumps({'error': 'Case not found', 'case_id': case_id})}\n\n"
                    return
                yield f"data: {json.dumps(c)}\n\n"
                if c.get("status") in [CaseStatus.COMPLETED, CaseStatus.REJECTED, CaseStatus.FAILED]:
                    return

                start_time = time.time()
                while time.time() - start_time < 120:  # 2 minute max stream window
                    signaled = event.wait(timeout=2.0)
                    if signaled:
                        event.clear()
                        c = case_store.get_case(case_id)
                        if c:
                            yield f"data: {json.dumps(c)}\n\n"
                            if c.get("status") in [CaseStatus.COMPLETED, CaseStatus.REJECTED, CaseStatus.FAILED]:
                                break
                    else:
                        # SSE keepalive comment
                        yield ": keepalive\n\n"
            finally:
                case_store.unregister_listener(case_id, event)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @app.route("/api/pubsub/push", methods=["POST"])
    def pubsub_push_webhook():
        """
        Google Cloud Pub/Sub Push Subscription Webhook
        ---
        tags:
          - System & Data
        responses:
          200:
            description: Message acknowledged and processed
          400:
            description: Malformed Pub/Sub envelope
          401:
            description: Unauthorized webhook invocation
        """
        if Config.PUBSUB_PUSH_TOKEN:
            token = request.args.get("token") or request.headers.get("X-InvestPI-Token")
            auth_header = request.headers.get("Authorization", "")
            if token != Config.PUBSUB_PUSH_TOKEN and f"Bearer {Config.PUBSUB_PUSH_TOKEN}" != auth_header:
                logger.warning("Unauthorized Pub/Sub push notification attempt")
                return jsonify({"error": "Unauthorized"}), 401

        envelope = request.get_json(silent=True)
        if not envelope:
            return jsonify({"error": "Missing JSON push envelope"}), 400

        try:
            handle_push_message(envelope)
            return jsonify({"status": "acknowledged", "processed": True}), 200
        except Exception as e:
            logger.error(f"Pub/Sub push webhook error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 400

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """
        Forensic Intelligence Assistant Chatbot
        ---
        tags:
          - Forensic Engine
        consumes:
          - application/json
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: Explain the confidence score and why Parameter 1 triggered a warning.
                report_id:
                  type: string
                  example: rep_12345
                context:
                  type: object
                  description: Optional full report object
                history:
                  type: array
                  items:
                    type: object
        responses:
          200:
            description: Agent response with guardrail status
            schema:
              properties:
                reply:
                  type: string
                in_scope:
                  type: boolean
                ticker:
                  type: string
          400:
            description: Missing message parameter
        """
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"error": "Message parameter is required"}), 400

        report_id = data.get("report_id")
        report_context = data.get("context")

        if not report_context and report_id and report_id in reports_cache:
            report_context = reports_cache[report_id].get("data")

        # Fallback if no context provided: look up most recently cached report
        if not report_context and hasattr(reports_cache, "l1_cache") and len(reports_cache.l1_cache._store) > 0:
            latest_key = list(reports_cache.l1_cache._store.keys())[-1]
            report_context = reports_cache.get(latest_key, {}).get("data")

        history = data.get("history", [])

        reply, in_scope = forensic_agent.respond(
            message=message,
            report_context=report_context,
            history=history
        )

        ticker = report_context.get("resolved_stock", {}).get("ticker") if report_context else None
        bundle = forensic_agent.last_subagent_bundle or {}

        return jsonify({
            "reply": reply,
            "in_scope": in_scope,
            "ticker": ticker,
            "subagents_invoked": bundle.get("subagents_invoked", []) if in_scope else [],
            "sources": bundle.get("sources", []) if in_scope else []
        })

    @app.route("/api/agent/subagents/<ticker>", methods=["GET"])
    def run_subagents_sync(ticker):
        """
        Execute Chatbot Sub-Agents Synchronously for a Security
        ---
        tags:
          - Forensic Engine
        parameters:
          - name: ticker
            in: path
            type: string
            required: true
            description: Stock ticker symbol (e.g. RELIANCE.NS, PASHUPATI.NS, DBS.SI)
          - name: query
            in: query
            type: string
            required: false
            description: Optional natural language query to filter relevant sub-agents
          - name: claimed_target
            in: query
            type: number
            required: false
            description: Optional claimed price target for comparison
        responses:
          200:
            description: Complete intelligence bundle from Historic Price, Price Target (Analyst/EMA-200), Fundamentals, and Simple Explainer sub-agents.
        """
        query = request.args.get("query", "")
        claimed_target = request.args.get("claimed_target", type=float)
        resolved = analysis_service.loader.resolve_ticker(ticker) or {"ticker": ticker.upper(), "name": ticker.upper()}
        norm_ticker = resolved.get("ticker", ticker.upper())

        report_ctx = {
            "resolved_stock": resolved,
            "claim": {"target_price": claimed_target}
        }
        bundle = forensic_agent.coordinator.execute_all(
            ticker=norm_ticker,
            report_context=report_ctx,
            message=query
        )
        return jsonify(bundle), 200

    @app.route("/api/agent/subagents/async", methods=["POST"])
    def run_subagents_async():
        """
        Dispatch Chatbot Sub-Agents Asynchronously via Google Cloud Pub/Sub
        ---
        tags:
          - Forensic Engine
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                ticker:
                  type: string
                  example: PASHUPATI.NS
                market:
                  type: string
                  example: IN
                query:
                  type: string
                  example: Predict future price target and explain fundamentals simply
                claimed_target:
                  type: number
                  example: 140.0
        responses:
          202:
            description: Sub-agent task published to Pub/Sub and queued in CaseStore.
        """
        from app.pubsub.events import SubAgentTaskEvent
        body = request.get_json(silent=True) or {}
        raw_ticker = (body.get("ticker") or "").strip()
        if not raw_ticker:
            return jsonify({"error": "Missing required 'ticker' field"}), 400

        market = (body.get("market") or "IN").upper()
        resolved = analysis_service.loader.resolve_ticker(raw_ticker, market_hint=market) or {"ticker": raw_ticker.upper()}
        norm_ticker = resolved.get("ticker", raw_ticker.upper())

        task_id = f"subagent-{uuid.uuid4().hex[:12]}"
        case_store.create_case(task_id, modality="subagent_task", region=market, meta={"ticker": norm_ticker})

        event = SubAgentTaskEvent(
            task_id=task_id,
            ticker=norm_ticker,
            market=market,
            query=body.get("query", ""),
            claimed_target=body.get("claimed_target")
        )
        msg_id = publisher.publish_subagent_task(event)

        return jsonify({
            "task_id": task_id,
            "ticker": norm_ticker,
            "status": CaseStatus.QUEUED,
            "mode": "async_pubsub",
            "msg_id": msg_id,
            "status_url": f"/api/cases/{task_id}",
            "stream_url": f"/api/cases/{task_id}/stream"
        }), 202

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8050, debug=True)

