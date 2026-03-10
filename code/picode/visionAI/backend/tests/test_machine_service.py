from services.machine_service import (
    _derive_tray_position_from_status,
    _extract_gate_position,
    _extract_status_line,
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


def test_derive_tray_position_out():
    position = _derive_tray_position_from_status({"trayOutSw": "1", "trayInSw": "0"})
    assert position == "OUT"


def test_derive_tray_position_in():
    position = _derive_tray_position_from_status({"trayOutSw": "0", "trayInSw": "1"})
    assert position == "IN"


def test_derive_tray_position_unknown():
    position = _derive_tray_position_from_status({"trayOutSw": "1", "trayInSw": "1"})
    assert position == "UNKNOWN"
