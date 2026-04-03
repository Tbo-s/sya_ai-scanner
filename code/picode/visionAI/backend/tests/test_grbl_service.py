import pytest

import services.grbl_service as grbl_service
from services.grbl_service import _parse_sequence, is_safe_grbl_command, manual_z_down, manual_z_up, z_down, z_up


def test_grbl_allows_basic_command():
    assert is_safe_grbl_command("G0 X10.0 Y-5 F300")


def test_grbl_rejects_empty_command():
    assert not is_safe_grbl_command("   ")


def test_grbl_rejects_unsafe_shell_chars():
    assert not is_safe_grbl_command("G0 X10; rm -rf /")


def test_parse_sequence_pipe_separator():
    assert _parse_sequence("$X|$H") == ["$X", "$H"]


def test_parse_sequence_semicolon_separator():
    assert _parse_sequence("$X;$H") == ["$X", "$H"]


def test_parse_sequence_filters_empty_parts():
    assert _parse_sequence(" $X || ; $H ") == ["$X", "$H"]


def test_z_up_uses_absolute_positioning(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_Z_PICKUP", "42.5")
    monkeypatch.setenv("APP_GRBL_FEED_RATE", "1234")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = z_up()

    assert result["action"] == "z_up"
    assert commands == [("G90", True), ("G1 Z42.5 F1234", True)]


def test_z_down_uses_absolute_positioning(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_Z_TRAVEL", "7.0")
    monkeypatch.setenv("APP_GRBL_FEED_RATE", "900")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = z_down()

    assert result["action"] == "z_down"
    assert commands == [("G90", True), ("G1 Z7.0 F900", True)]


def test_manual_z_up_uses_relative_jog_and_slow_feed(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_Z_STEP", "1.25")
    monkeypatch.setenv("APP_GRBL_MANUAL_Z_FEED_RATE", "90")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = manual_z_up()

    assert result["action"] == "manual_z_up"
    assert commands == [("G91", True), ("G1 Z1.25 F90", True), ("G90", True)]


def test_manual_z_down_uses_relative_jog_and_slow_feed(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_Z_STEP", "0.75")
    monkeypatch.setenv("APP_GRBL_MANUAL_Z_FEED_RATE", "60")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = manual_z_down()

    assert result["action"] == "manual_z_down"
    assert commands == [("G91", True), ("G1 Z-0.75 F60", True), ("G90", True)]


def test_manual_xy_move_omits_zero_y_axis(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = grbl_service.manual_xy_move(1.0, 0.0)

    assert result["action"] == "manual_xy_move"
    assert commands == [("G21", True), ("G91", True), ("G0 X1.0", True)]


def test_manual_xy_move_omits_zero_x_axis(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = grbl_service.manual_xy_move(0.0, -2.5)

    assert result["action"] == "manual_xy_move"
    assert commands == [("G21", True), ("G91", True), ("G0 Y-2.5", True)]


def test_manual_xy_move_keeps_both_axes_when_needed(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = grbl_service.manual_xy_move(1.0, -2.0)

    assert result["action"] == "manual_xy_move"
    assert commands == [("G21", True), ("G91", True), ("G0 X1.0 Y-2.0", True)]


def test_manual_xy_move_rejects_zero_delta():
    with pytest.raises(grbl_service.HTTPException) as exc_info:
        grbl_service.manual_xy_move(0.0, 0.0)

    assert exc_info.value.status_code == 400
