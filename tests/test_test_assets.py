import pytest
from pathlib import Path
from app.engine.orchestrator import AnalysisService
from app.config import ROOT_DIR

service = AnalysisService()
TEST_DIR = ROOT_DIR / "test_assets"


def test_india_telegram_ocr_asset():
    p = TEST_DIR / "india" / "telegram_adanient_suzlon_tip.png"
    assert p.exists()
    with open(p, "rb") as f:
        bytes_data = f.read()
    
    result = service.run_investigation("screenshot", bytes_data, region_override="IN", image_mime="image/png")
    assert result is not None
    reports = result.get("reports", [result])
    tickers = [r.get("resolved_stock", {}).get("ticker") for r in reports]
    assert any("ADANIENT" in t for t in tickers)
    assert result.get("verdict") is not None


def test_singapore_ocr_asset():
    p = TEST_DIR / "singapore" / "telegram_dbs_singtel_tip.png"
    assert p.exists()
    with open(p, "rb") as f:
        bytes_data = f.read()

    result = service.run_investigation("screenshot", bytes_data, region_override="SG", image_mime="image/png")
    assert result is not None
    reports = result.get("reports", [result])
    tickers = [r.get("resolved_stock", {}).get("ticker") for r in reports]
    assert any("D05" in t or "Z74" in t for t in tickers)


def test_australia_ocr_asset():
    p = TEST_DIR / "australia" / "discord_bhp_pilbara_tip.png"
    assert p.exists()
    with open(p, "rb") as f:
        bytes_data = f.read()

    result = service.run_investigation("screenshot", bytes_data, region_override="AU", image_mime="image/png")
    assert result is not None
    reports = result.get("reports", [result])
    tickers = [r.get("resolved_stock", {}).get("ticker") for r in reports]
    assert any("BHP" in t or "PLS" in t for t in tickers)


def test_video_clip_assets_exist_and_valid():
    for f in [
        TEST_DIR / "india" / "video_reliance_tcs_breakout.mp4",
        TEST_DIR / "singapore" / "video_singapore_airlines.mp4",
        TEST_DIR / "australia" / "video_cba_bank_alert.mp4"
    ]:
        assert f.exists()
        assert f.stat().st_size > 100000  # > 100 KB valid MP4
