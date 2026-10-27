import io
import json
from datetime import datetime, timezone
from PIL import Image

from app.models import Export, Post, CoordinationCandidate, Account
from app.services.media_forensics import pixel_indicators, analyze_video_keyframes
from app.services.coordination import _compute_qut_coortweet_sync
from app.services.osint import extract_iocs_from_text
from app.services.exports import _build_maltego, _build_lea_dossier
from app.services.providers.telegram import parse_telegram_preview_html, clean_channel_name
from app.services.analytics import _automation_indicators


def test_invid_ela_and_sentinel_fft_forensics():
    img = Image.new("RGB", (128, 128), color=(200, 100, 50))
    res = pixel_indicators(img, mime="image/jpeg")

    assert "ela_analysis" in res
    ela = res["ela_analysis"]
    assert ela["reference_quality"] == 95
    assert "mean_error" in ela
    assert "max_error" in ela
    assert "high_error_pixel_ratio" in ela

    assert "fft_spectral_analysis" in res
    fft = res["fft_spectral_analysis"]
    assert "high_frequency_energy_ratio" in fft
    assert "low_frequency_energy_ratio" in fft
    assert "spectral_energy_balance" in fft
    assert fft["high_frequency_energy_ratio"] >= 0.0


def test_qut_cnt_and_coortweet_coordination():
    t0 = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 27, 10, 0, 15, tzinfo=timezone.utc)  # 15s gap

    p1 = Post(id="p1", account_id="acc_a", raw_text="breaking news #alert", timestamp=t0)
    p2 = Post(id="p2", account_id="acc_b", raw_text="breaking news #alert", timestamp=t1)

    sync_metrics = _compute_qut_coortweet_sync([p1, p2], "acc_a", "acc_b")
    assert sync_metrics["coordination_weight"] > 0
    assert sync_metrics["fastest_sync_seconds"] == 15.0
    assert sync_metrics["synchronized_actions_under_60s"] == 1
    assert "QUT CNT" in sync_metrics["algorithm"]


def test_spiderfoot_osint_ioc_extraction():
    sample_text = (
        "Send payments to BTC address 1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2 or "
        "ETH 0x71C7656EC7ab88b098defB751B7401B5f6d8976F. "
        "For Indian donations use UPI scammer@paytm or fraud@okhdfcbank. "
        "Contact mastermind at t.me/dark_ops or phone +919876543210 or email target@evilcorp.org"
    )

    iocs = extract_iocs_from_text(sample_text)
    assert "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" in iocs.get("crypto_btc", [])
    assert "0x71C7656EC7ab88b098defB751B7401B5f6d8976F" in iocs.get("crypto_eth", [])
    assert "scammer@paytm" in iocs.get("upi_ids", [])
    assert "fraud@okhdfcbank" in iocs.get("upi_ids", [])
    assert "dark_ops" in iocs.get("telegram_handles", [])
    assert "9876543210" in iocs.get("phone_numbers", [])
    assert "target@evilcorp.org" in iocs.get("email_addresses", [])


def test_maltego_export_generation():
    post = Post(
        id="post-maltego-01",
        case_id="case-001",
        account_id="user_alpha",
        raw_text="Fraud syndicate using UPI fraud@paytm and BTC 1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        timestamp=datetime.now(timezone.utc)
    )
    candidate = CoordinationCandidate(
        id="cand-01",
        case_id="case-001",
        account_ids=json.dumps(["user_alpha", "user_beta"]),
        review_state="review_candidate",
        features=json.dumps({"qut_coortweet_metrics": {"coordination_weight": 2.45}})
    )

    data = {
        "posts": [post],
        "candidates": [candidate],
        "comments": [],
        "analyses": {},
        "findings": [],
        "access": [],
        "media": []
    }

    export = Export(
        id="exp-01",
        case_id="case-001",
        fmt="maltego",
        scope="all",
        redaction_mode="full",
        created_by="user-01"
    )

    blob = _build_maltego(None, None, export, data)
    csv_text = blob.decode("utf-8")

    assert "maltego.Alias" in csv_text
    assert "user_alpha" in csv_text
    assert "maltego.CryptoAddress" in csv_text
    assert "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" in csv_text
    assert "maltego.Affiliation" in csv_text
    assert "fraud@paytm" in csv_text
    assert "POSSIBLY_COORDINATED_WITH" in csv_text


def test_telegram_public_osint_scraper():
    assert clean_channel_name("@cyber_alerts") == "cyber_alerts"
    assert clean_channel_name("https://t.me/s/intel_feed") == "intel_feed"
    assert clean_channel_name("https://t.me/news_in") == "news_in"

    mock_html = """
    <div class="tgme_widget_message" data-post="intel_feed/101">
      <div class="tgme_widget_message_text">Urgent: transfer funds to UPI cybercell@paytm</div>
      <div class="tgme_widget_message_info">
        <time datetime="2026-10-27T10:00:00+00:00"></time>
        <span class="tgme_widget_message_views">1.2K</span>
      </div>
      <div class="tgme_widget_message_footer"></div>
    </div>
    """
    parsed = parse_telegram_preview_html(mock_html, "intel_feed")
    assert len(parsed) >= 1
    assert parsed[0]["post_id"] == "intel_feed/101"
    assert "cybercell@paytm" in parsed[0]["text"]
    assert parsed[0]["timestamp"] == "2026-10-27T10:00:00+00:00"


def test_lea_section_65b_dossier():
    class DummyCase:
        id = "case-hackathon-2026"
        title = "National Security Disinformation Probe"
        purpose = "Court admissible forensic evidence capture"

    post = Post(
        id="post-lea-01",
        case_id="case-001",
        account_id="operative_x",
        raw_text="Payment link upi: scam@paytm and BTC 1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        timestamp=datetime.now(timezone.utc)
    )

    data = {
        "posts": [post],
        "candidates": [],
        "comments": [],
        "analyses": {},
        "findings": [],
        "access": [],
        "media": [],
        "buckets": {"established": ["verified_account"], "signals_and_hypotheses": ["timing_sync"]}
    }

    export = Export(
        id="exp-lea-01",
        case_id="case-001",
        fmt="lea_dossier",
        scope="all",
        redaction_mode="full",
        created_by="officer-01"
    )

    pdf_bytes = _build_lea_dossier(None, DummyCase(), export, data)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_cyabra_bot_radar():
    acc = Account(id="bot_farm_01", handle="bot_user", platform="twitter")
    posts = [
        Post(id=f"p_{i}", account_id="bot_farm_01", normalized_text="identical propaganda text",
             raw_text="identical propaganda text",
             timestamp=datetime(2026, 10, 20 + (i // 24), i % 24, 0, 0, tzinfo=timezone.utc))
        for i in range(30)
    ]

    rows = _automation_indicators(posts, {"bot_farm_01": acc})
    assert len(rows) == 1
    radar = rows[0]["features"]["cyabra_radar"]
    assert "diurnal_anomaly_score" in radar
    assert "copypasta_ratio" in radar
    assert "astroturfing_risk" in radar
    assert rows[0]["features"]["diurnal_hours_active"] > 10
