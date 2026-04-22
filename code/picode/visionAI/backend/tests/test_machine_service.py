from services import machine_service
from services.machine_service import (
    _derive_tray_position_from_status,
    _extract_gate_position,
    _extract_status_line,
    _get_status_values,
    _parse_status_values,
)


def test_extract_gate_position_from_lines():
    assert _extract_gate_position(["foo", "GATE_POS=UP"]) == "UP"


def test_extract_status_line_finds_latest_status():
    lines = [
        "Leonardo ready",
        "gateState=1, gatePos=UP, trayState=0, gateOpenSw=1, gateCloseSw=0, trayOutSw=0, trayInSw=1",
        "noise",
    ]
    status = _extract_status_line(lines)
    assert status is not None
    assert status.startswith("gateState=")


def test_parse_status_values():
    status_line = "gateState=0, gatePos=DOWN, trayState=2, gateOpenSw=0, gateCloseSw=1, trayOutSw=1, trayInSw=0"
    values = _parse_status_values(status_line)
    assert values["gatePos"] == "DOWN"
    assert values["trayOutSw"] == "1"


def test_parse_status_values_keeps_distance_mm():
    status_line = (
        "gateState=0, gatePos=DOWN, trayState=0, trayPos=IN, wrist1=90, wrist2=90, "
        "vac1=0, vac2=0, valve1=0, valve2=0, distanceMm=123, "
        "gateOpenSw=0, gateCloseSw=1, trayOutSw=0, trayInSw=1"
    )

    status = _extract_status_line([status_line])
    values = _parse_status_values(status or "")

    assert status == status_line
    assert values["distanceMm"] == "123"
    assert values["trayInSw"] == "1"


def test_get_status_values_retries_until_parseable(monkeypatch):
    responses = [
        ["Leonardo ready", "DISTANCE_SENSOR_READY"],
        [
            "gateState=0, gatePos=DOWN, trayState=0, trayPos=IN, "
            "wrist1=90, wrist2=90, vac1=0, vac2=0, valve1=0, valve2=0, "
            "distanceMm=123, gateOpenSw=0, gateCloseSw=1, trayOutSw=0, trayInSw=1"
        ],
    ]

    def fake_send_with_response(command):
        assert command == "STATUS"
        return responses.pop(0)

    monkeypatch.setenv("APP_LEONARDO_STATUS_RETRIES", "2")
    monkeypatch.setenv("APP_LEONARDO_STATUS_RETRY_DELAY_S", "0")
    monkeypatch.setattr(machine_service, "_send_with_response", fake_send_with_response)

    values, lines = _get_status_values()

    assert values["distanceMm"] == "123"
    assert values["trayInSw"] == "1"
    assert lines[0] == "Leonardo ready"


def test_derive_tray_position_out():
    position = _derive_tray_position_from_status({"trayOutSw": "1", "trayInSw": "0"})
    assert position == "OUT"


def test_derive_tray_position_in():
    position = _derive_tray_position_from_status({"trayOutSw": "0", "trayInSw": "1"})
    assert position == "IN"


def test_derive_tray_position_unknown():
    position = _derive_tray_position_from_status({"trayOutSw": "1", "trayInSw": "1"})
    assert position == "UNKNOWN"
