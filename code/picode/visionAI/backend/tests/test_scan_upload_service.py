import base64

from services import scan_upload_service


def test_upload_scan_results_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("APP_SCAN_RESULTS_UPLOAD_ENABLED", "0")

    result = scan_upload_service.upload_scan_results(
        imei="123456789012345",
        session_id="session-1",
        device_model="Test Phone",
        max_value_eur=100.0,
        photo_paths=[],
        ai_result=None,
    )

    assert result == {"enabled": False, "skipped": True, "reason": "disabled"}


def test_build_scan_upload_payload_includes_base64_photos(tmp_path):
    photo_path = tmp_path / "front_side_1.jpg"
    photo_path.write_bytes(b"jpeg-data")

    payload = scan_upload_service.build_scan_upload_payload(
        imei="123456789012345",
        session_id="session-1",
        device_model="Test Phone",
        max_value_eur=100.0,
        photo_paths=[str(photo_path), str(tmp_path / "missing.jpg")],
        ai_result={"grade": "A"},
    )

    assert payload["imei"] == "123456789012345"
    assert payload["session_id"] == "session-1"
    assert payload["device_model"] == "Test Phone"
    assert payload["photo_count"] == 1
    assert payload["ai_result"] == {"grade": "A"}
    assert payload["photos"] == [
        {
            "label": "front_side_1",
            "filename": "front_side_1.jpg",
            "content_type": "image/jpeg",
            "data_base64": base64.b64encode(b"jpeg-data").decode("ascii"),
        }
    ]


def test_upload_scan_results_posts_payload(monkeypatch, tmp_path):
    photo_path = tmp_path / "back_side_1.jpg"
    photo_path.write_bytes(b"image")
    calls = []

    class FakeResponse:
        status_code = 202
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"accepted": True}

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("APP_SCAN_RESULTS_UPLOAD_ENABLED", "1")
    monkeypatch.setenv("APP_SCAN_RESULTS_UPLOAD_URL", "https://example.test/scans")
    monkeypatch.setenv("APP_SCAN_RESULTS_UPLOAD_TIMEOUT_S", "12")
    monkeypatch.setattr(scan_upload_service.requests, "post", fake_post)

    result = scan_upload_service.upload_scan_results(
        imei="123456789012345",
        session_id="session-1",
        device_model="Test Phone",
        max_value_eur=100.0,
        photo_paths=[str(photo_path)],
        ai_result={"grade": "B"},
    )

    assert result["ok"] is True
    assert result["status_code"] == 202
    assert result["photo_count"] == 1
    assert result["response"] == {"accepted": True}
    assert calls[0]["url"] == "https://example.test/scans"
    assert calls[0]["timeout"] == 12
    assert calls[0]["json"]["photos"][0]["data_base64"] == base64.b64encode(b"image").decode("ascii")
