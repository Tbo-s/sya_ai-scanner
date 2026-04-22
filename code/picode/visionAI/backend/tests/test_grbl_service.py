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


def test_parse_grbl_status_line_extracts_coordinates_and_limits():
    grbl_service._set_arm_unhomed()
    status = grbl_service._parse_grbl_status_line("<Idle|MPos:1.000,2.000,3.000|WPos:0.500,1.500,0.000|Pn:XY>")

    assert status is not None
    assert status["state"] == "Idle"
    assert status["machine_position"] == {"x": 1.0, "y": 2.0, "z": 3.0}
    assert status["work_position"] == {"x": 0.5, "y": 1.5, "z": 0.0}
    assert status["limits"] == {"x": True, "y": True}
    assert status["limit_axes"] == ["x", "y"]


def test_parse_grbl_status_line_supports_active_absent_limit_pins(monkeypatch):
    monkeypatch.setenv("APP_GRBL_LIMIT_PIN_MODE", "active_absent")

    status = grbl_service._parse_grbl_status_line("<Idle|MPos:1.000,2.000,3.000|Pn:XY>")
    assert status is not None
    assert status["limits"] == {"x": False, "y": False}

    status = grbl_service._parse_grbl_status_line("<Idle|MPos:1.000,2.000,3.000>")
    assert status is not None
    assert status["limits"] == {"x": False, "y": False}


def test_limit_stop_axes_use_configured_zero_direction(monkeypatch):
    monkeypatch.setenv("APP_GRBL_X_LIMIT_TOWARD_ZERO_SIGN", "1")
    monkeypatch.setenv("APP_GRBL_Y_LIMIT_TOWARD_ZERO_SIGN", "-1")

    assert grbl_service._limit_stop_axes_for_xy_delta(1.0, -1.0) == {"x", "y"}
    assert grbl_service._limit_stop_axes_for_xy_delta(-1.0, 1.0) == set()


def test_z_up_uses_absolute_positioning(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_Z_PICKUP", "42.5")
    monkeypatch.setenv("APP_GRBL_FEED_RATE", "1234")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = z_up()

    assert result["action"] == "z_up"
    assert commands == [("G90", True), ("G1 Z42.5 F1234", True)]
    assert wait_flags == [False]


def test_z_down_uses_absolute_positioning(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_Z_TRAVEL", "7.0")
    monkeypatch.setenv("APP_GRBL_FEED_RATE", "900")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = z_down()

    assert result["action"] == "z_down"
    assert commands == [("G90", True), ("G1 Z7.0 F900", True)]
    assert wait_flags == [False]


def test_manual_z_up_uses_relative_jog_and_slow_feed(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_Z_STEP", "1.25")
    monkeypatch.setenv("APP_GRBL_MANUAL_Z_FEED_RATE", "90")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = manual_z_up()

    assert result["action"] == "manual_z_up"
    assert commands == [("G91", True), ("G1 Z1.25 F90", True), ("G90", True)]
    assert wait_flags == [True]


def test_manual_z_down_uses_relative_jog_and_slow_feed(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_Z_STEP", "0.75")
    monkeypatch.setenv("APP_GRBL_MANUAL_Z_FEED_RATE", "60")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = manual_z_down()

    assert result["action"] == "manual_z_down"
    assert commands == [("G91", True), ("G1 Z-0.75 F60", True), ("G90", True)]
    assert wait_flags == [True]


def test_manual_xy_move_omits_zero_y_axis(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_XY_FEED_RATE", "120")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = grbl_service.manual_xy_move(1.0, 0.0)

    assert result["action"] == "manual_xy_move"
    assert commands == [("G21", True), ("G91", True), ("G1 X1.0 F120", True)]
    assert wait_flags == [True]


def test_manual_xy_move_omits_zero_x_axis(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_XY_FEED_RATE", "120")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = grbl_service.manual_xy_move(0.0, -2.5)

    assert result["action"] == "manual_xy_move"
    assert commands == [("G21", True), ("G91", True), ("G1 Y-2.5 F120", True)]
    assert wait_flags == [True]


def test_manual_xy_move_keeps_both_axes_when_needed(monkeypatch):
    commands = []
    wait_flags = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        wait_flags.append(wait_for_idle)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_XY_FEED_RATE", "120")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    result = grbl_service.manual_xy_move(1.0, -2.0)

    assert result["action"] == "manual_xy_move"
    assert commands == [("G21", True), ("G91", True), ("G1 X1.0 Y-2.0 F120", True)]
    assert wait_flags == [True]


def test_manual_xy_move_rejects_zero_delta():
    with pytest.raises(grbl_service.HTTPException) as exc_info:
        grbl_service.manual_xy_move(0.0, 0.0)

    assert exc_info.value.status_code == 400


def test_manual_xy_move_clamps_to_soft_limit_after_homing(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MANUAL_XY_FEED_RATE", "120")
    monkeypatch.setenv("APP_GRBL_MAX_X", "4.0")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    grbl_service._set_arm_homed_zero()
    with grbl_service._ARM_POSITION_LOCK:
        grbl_service._ARM_XY_POSITION["x"] = 3.5

    result = grbl_service.manual_xy_move(1.0, 0.0)

    assert result["bounded_by_soft_limit"] is True
    assert result["applied_delta"] == {"x": 0.5, "y": 0.0}
    assert result["position"]["x"] == 4.0
    assert commands == [("G21", True), ("G91", True), ("G1 X0.5 F120", True)]


def test_manual_xy_move_skips_when_soft_limit_already_reached(monkeypatch):
    commands = []

    def fake_run_grbl_commands(sequence, wait_for_idle=False, settle_delay_s=0.0, **kwargs):
        commands.extend(sequence)
        return [{"command": command, "wait_for_ok": wait_for_ok} for command, wait_for_ok in sequence]

    monkeypatch.setenv("APP_GRBL_MAX_X", "4.0")
    monkeypatch.setattr(grbl_service, "_run_grbl_commands", fake_run_grbl_commands)

    grbl_service._set_arm_homed_zero()
    with grbl_service._ARM_POSITION_LOCK:
        grbl_service._ARM_XY_POSITION["x"] = 4.0

    result = grbl_service.manual_xy_move(1.0, 0.0)

    assert result["bounded_by_soft_limit"] is True
    assert result["skipped"] is True
    assert result["results"] == []
    assert commands == []


def test_wait_for_grbl_idle_polls_until_idle(monkeypatch):
    class FakeSerial:
        def __init__(self):
            self.writes = []
            self.responses = [
                b"<Run|MPos:0.000,0.000,0.000|FS:0,0>\n",
                b"<Idle|MPos:1.000,0.000,0.000|FS:0,0>\n",
            ]

        def write(self, data):
            self.writes.append(data)

        def readline(self):
            if self.responses:
                return self.responses.pop(0)
            return b""

    monkeypatch.setenv("APP_GRBL_READ_TIMEOUT_S", "0.01")
    monkeypatch.setenv("APP_GRBL_MOTION_TIMEOUT_S", "0.2")

    fake_serial = FakeSerial()
    result = grbl_service._wait_for_grbl_idle(fake_serial)

    assert result["state"] == "Idle"
    assert fake_serial.writes == [b"?", b"?"]
    assert result["response"][-1].startswith("<Idle|")


def test_wait_for_grbl_idle_stops_when_limit_becomes_active(monkeypatch):
    class FakeSerial:
        def __init__(self):
            self.writes = []
            self.responses = [
                b"<Run|MPos:0.000,0.000,0.000|FS:60,60>\n",
                b"<Run|MPos:0.000,0.000,0.000|Pn:X|FS:60,60>\n",
            ]

        def write(self, data):
            self.writes.append(data)

        def readline(self):
            if self.responses:
                return self.responses.pop(0)
            return b""

    monkeypatch.setenv("APP_GRBL_READ_TIMEOUT_S", "0.01")
    monkeypatch.setenv("APP_GRBL_MOTION_TIMEOUT_S", "0.2")
    monkeypatch.setattr(grbl_service, "_stop_grbl_motion_for_limit", lambda ser: {"stopped": True})

    fake_serial = FakeSerial()
    result = grbl_service._wait_for_grbl_idle(fake_serial, moving_limit_axes={"x"}, initial_limit_axes=set())

    assert result["limit_triggered"] is True
    assert result["limit_axes"] == ["x"]
    assert result["stop"] == {"stopped": True}


def test_run_grbl_commands_reuses_existing_serial_connection(monkeypatch):
    created_serials = []
    startup_calls = []
    sent_commands = []

    class FakeSerial:
        def __init__(self):
            self.port = None
            self.baudrate = None
            self.timeout = None
            self.dtr = True
            self.rts = True
            self.is_open = False
            created_serials.append(self)

        def open(self):
            self.is_open = True

        def close(self):
            self.is_open = False

        def reset_input_buffer(self):
            return None

        def reset_output_buffer(self):
            return None

    def fake_prepare_grbl_serial(ser):
        startup_calls.append(ser)
        return ["Grbl ready"]

    def fake_send_grbl_on_serial(ser, command, wait_for_ok=True):
        sent_commands.append((ser, command, wait_for_ok))
        return {"command": command, "wait_for_ok": wait_for_ok}

    grbl_service._close_grbl_serial()
    monkeypatch.setattr(grbl_service.serial, "Serial", FakeSerial)
    monkeypatch.setattr(grbl_service, "_prepare_grbl_serial", fake_prepare_grbl_serial)
    monkeypatch.setattr(grbl_service, "_send_grbl_on_serial", fake_send_grbl_on_serial)

    try:
        first = grbl_service._run_grbl_commands([("G21", True)])
        second = grbl_service._run_grbl_commands([("G91", True)])
    finally:
        grbl_service._close_grbl_serial()

    assert len(created_serials) == 1
    assert startup_calls == [created_serials[0]]
    assert sent_commands == [
        (created_serials[0], "G21", True),
        (created_serials[0], "G91", True),
    ]
    assert first[0]["startup"] == ["Grbl ready"]
    assert "startup" not in second[0]
