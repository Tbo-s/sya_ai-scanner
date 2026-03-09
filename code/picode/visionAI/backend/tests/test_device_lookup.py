from fastapi import HTTPException

from controller.device_lookup import _normalize_imei, _resolve_device


def test_normalize_imei_from_digits():
    assert _normalize_imei("490154203237518") == "490154203237518"


def test_normalize_imei_strips_non_digits():
    assert _normalize_imei("49 0154-203237518") == "490154203237518"


def test_normalize_imei_rejects_invalid_length():
    try:
        _normalize_imei("12345")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        assert False, "Expected invalid IMEI to raise HTTPException"


def test_resolve_device_prefers_exact_match():
    payload = {
        "exact": {"490154203237518": {"model": "Exact Match", "max_value_eur": 200}},
        "tac": {"49015420": {"model": "Tac Match", "max_value_eur": 100}},
        "fallback": {"model": "Unknown", "max_value_eur": 0},
    }
    result = _resolve_device("490154203237518", payload)
    assert result["found"] is True
    assert result["source"] == "exact"
    assert result["model"] == "Exact Match"
    assert result["max_value_eur"] == 200


def test_resolve_device_uses_tac_if_exact_missing():
    payload = {
        "tac": {"49015420": {"model": "Tac Match", "max_value_eur": 120}},
        "fallback": {"model": "Unknown", "max_value_eur": 0},
    }
    result = _resolve_device("490154203237518", payload)
    assert result["found"] is True
    assert result["source"] == "tac"
    assert result["model"] == "Tac Match"
    assert result["max_value_eur"] == 120


def test_resolve_device_fallback_for_unknown_imei():
    payload = {"fallback": {"model": "Unknown", "max_value_eur": 0}}
    result = _resolve_device("490154203237518", payload)
    assert result["found"] is False
    assert result["source"] == "fallback"
    assert result["model"] == "Unknown"
