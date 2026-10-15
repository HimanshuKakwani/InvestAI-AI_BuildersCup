"""Tests verifying that non-financial and irrelevant inputs are properly detected and rejected."""
import io
import pytest
from PIL import Image
from app.engine.orchestrator import AnalysisService
from app.routes.api import create_app

service = AnalysisService()


def test_irrelevant_text_returns_not_financial_advice():
    """Text with cooking or casual chatter must return Not a financial advice."""
    res = service.run_investigation("text", "Here is a recipe for Italian pasta with garlic and olive oil.", region_override="IN")
    assert res.get("is_financial_advice") is False
    assert "Not a financial advice, kindly provide relevant input" in res.get("message", "")
    assert "resolved_stock" not in res
    assert "parameters" not in res


def test_irrelevant_youtube_url_returns_not_financial_advice():
    """Music or non-financial YouTube URLs must be rejected."""
    res = service.run_investigation("youtube_url", "https://www.youtube.com/watch?v=fJ9rUzIMcZQ", region_override="IN")
    assert res.get("is_financial_advice") is False
    assert "Not a financial advice, kindly provide relevant input" in res.get("message", "")
    assert "resolved_stock" not in res


def test_f1_racing_video_rejected_immediately():
    """Formula 1 official racing video must be rejected instantly without treating numbers as tickers."""
    res = service.run_investigation("youtube_url", "https://youtu.be/WtlHPTO0VDM?si=uDMdRGcWyZ54NmLp", region_override="IN")
    assert res.get("is_financial_advice") is False
    assert res.get("message") == "Not a financial advice, kindly provide relevant input"
    assert "15.NS" not in str(res)
    assert "resolved_stock" not in res


def test_irrelevant_image_returns_not_financial_advice():
    """Uploading an arbitrary non-financial image should not audit Reliance or fake stocks."""
    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    bytes_data = buf.getvalue()

    res = service.run_investigation("screenshot", bytes_data, region_override="IN", image_mime="image/png")
    assert res.get("is_financial_advice") is False
    assert "Not a financial advice, kindly provide relevant input" in res.get("message", "")
    assert "resolved_stock" not in res


def test_api_analyze_endpoint_returns_200_for_irrelevant_media():
    """API endpoint returns HTTP 200 with is_financial_advice: False so the UI can render cleanly."""
    app = create_app()
    client = app.test_client()

    # 1. Text payload
    resp = client.post("/api/analyze", json={
        "modality": "text",
        "payload": "Check out this cute cat video and subscribe!",
        "region": "IN"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("is_financial_advice") is False
    assert data.get("message") == "Not a financial advice, kindly provide relevant input"
    assert "resolved_stock" not in data

    # 2. Image upload
    img = Image.new("RGB", (100, 100), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp_img = client.post("/api/analyze", data={
        "screenshot": (buf, "cat.png"),
        "region": "IN"
    }, content_type="multipart/form-data")
    assert resp_img.status_code == 200
    data_img = resp_img.get_json()
    assert data_img.get("is_financial_advice") is False
    assert data_img.get("message") == "Not a financial advice, kindly provide relevant input"


def test_relevant_financial_tip_succeeds_and_audits_stock():
    """Legitimate stock tip must still be audited accurately."""
    tip = "Buy Adani Enterprises target 3800 in 14 days, huge momentum confirmed!"
    res = service.run_investigation("text", tip, region_override="IN")
    assert res.get("is_financial_advice") is not False
    assert res.get("resolved_stock", {}).get("ticker") == "ADANIENT.NS"
    assert res.get("verdict") is not None
    assert len(res.get("parameters", [])) == 9
