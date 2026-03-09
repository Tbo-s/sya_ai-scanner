from fastapi import HTTPException

from controller.arduino import (
    _compute_port_suggestions,
    _infer_board_role,
    _is_safe_grbl_command,
    _normalize_gate_command,
)


def test_allows_basic_gcode():
    assert _is_safe_grbl_command("G0 X10.5 Y-2 F300")


def test_allows_grbl_system_command():
    assert _is_safe_grbl_command("$X")


def test_rejects_empty_command():
    assert not _is_safe_grbl_command("   ")


def test_rejects_unsafe_characters():
    assert not _is_safe_grbl_command("G0 X10; rm -rf /")


def test_infers_leonardo_from_vid_pid():
    assert _infer_board_role(0x2341, 0x8036, "") == "leonardo"


def test_infers_mega_from_vid_pid():
    assert _infer_board_role(0x2341, 0x0010, "") == "mega"


def test_infers_mega_from_description():
    assert _infer_board_role(None, None, "USB-SERIAL CH340") == "mega"


def test_suggests_ports_from_classification():
    suggestions = _compute_port_suggestions(
        [
            {"device": "/dev/ttyACM0", "board_role": "leonardo"},
            {"device": "/dev/ttyACM1", "board_role": "mega"},
        ]
    )
    assert suggestions["leonardo_port"] == "/dev/ttyACM0"
    assert suggestions["grbl_port"] == "/dev/ttyACM1"
    assert suggestions["confidence"] == "high"


def test_normalizes_gate_command():
    assert _normalize_gate_command(" gate_open ") == "GATE_OPEN"


def test_rejects_invalid_gate_command():
    try:
        _normalize_gate_command("OPEN")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Invalid gate command" in str(exc.detail)
    else:
        assert False, "Expected invalid gate command to raise an exception"
