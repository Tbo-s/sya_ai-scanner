from services.wrist_sequence_service import (
    ServoLogicalConfig,
    map_logical_to_physical_angle,
    run_wrist_sequence,
)


def test_map_logical_basic_non_inverted():
    cfg = ServoLogicalConfig(min_angle=10, center_angle=95, max_angle=170, inverted=False)
    assert map_logical_to_physical_angle(-90, cfg) == 10
    assert map_logical_to_physical_angle(0, cfg) == 95
    assert map_logical_to_physical_angle(90, cfg) == 170


def test_map_logical_with_inversion():
    cfg = ServoLogicalConfig(min_angle=0, center_angle=90, max_angle=180, inverted=True)
    assert map_logical_to_physical_angle(-90, cfg) == 180
    assert map_logical_to_physical_angle(90, cfg) == 0


def test_sequence_order_and_targets_in_simulation():
    result = run_wrist_sequence(
        simulate=True,
        step_delay_ms=0,
        servo1_config_payload={"min_angle": 0, "center_angle": 90, "max_angle": 180, "inverted": False},
        servo2_config_payload={"min_angle": 0, "center_angle": 90, "max_angle": 180, "inverted": False},
    )
    sequence = result["sequence"]

    assert len(sequence) == 8
    assert sequence[0]["name"] == "S1_START_MINUS_90"
    assert sequence[0]["servo"] == "servo1"
    assert sequence[0]["logical_angle"] == -90

    assert sequence[4]["name"] == "S2_TO_PLUS_90"
    assert sequence[4]["servo"] == "servo2"
    assert sequence[4]["logical_angle"] == 90

    assert sequence[7]["name"] == "S2_BACK_TO_CENTER_0"
    assert sequence[7]["servo"] == "servo2"
    assert sequence[7]["logical_angle"] == 0
