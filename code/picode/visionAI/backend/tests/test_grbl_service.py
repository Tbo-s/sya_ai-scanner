from services.grbl_service import _parse_sequence, is_safe_grbl_command


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
