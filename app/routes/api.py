"""InvestPI Flask Application Factory & Routes."""
import time
import logging
import json
from flask import Flask, request, jsonify, render_template, send_file, g
from flasgger import Swagger
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config, ROOT_DIR
from app.data.storage import ReportStorage
from app.engine.orchestrator import AnalysisService
from app.reporting.chart_generator import generate_price_target_chart
from app.reporting.pdf_generator import build_pdf_report

import sys
# Configure detailed API logger
logger = logging.getLogger("InvestPI.API")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.propagate = True

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
            # Check if multipart form upload with a file
            if "screenshot" in request.files:
                file = request.files["screenshot"]
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

            result["pdf_url"] = all_reports[0].get("pdf_url")
            return jsonify(result)
        except Exception as e:
            logger.error(f"Analysis failure: {e}", exc_info=True)
            return jsonify({"error": f"Investigation failed: {str(e)}"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8050, debug=True)

