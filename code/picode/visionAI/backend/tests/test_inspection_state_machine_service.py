from services.inspection_state_machine_service import (
    BOOT,
    DONE,
    EMERGENCY_STOP,
    build_inspection_state_machine_definition,
    run_inspection_state_machine,
)


def test_definition_has_expected_initial_state():
    definition = build_inspection_state_machine_definition()
    assert definition["initial_state"] == BOOT


def test_definition_includes_flow_steps():
    definition = build_inspection_state_machine_definition()
    assert len(definition["flow_steps"]) >= 60


def test_dry_run_reaches_done_state():
    result = run_inspection_state_machine(dry_run=True)
    assert result["final_state"] == DONE
    assert len(result["states"]) > 0


def test_emergency_stop_path():
    result = run_inspection_state_machine(dry_run=True, trigger_emergency_stop=True)
    assert result["final_state"] == EMERGENCY_STOP
    assert result["states"][0]["state"] == EMERGENCY_STOP
