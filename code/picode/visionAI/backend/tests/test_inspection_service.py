from services.inspection_service import build_inspection_plan, execute_inspection_plan


def test_build_inspection_plan_summary_counts():
    plan = build_inspection_plan(
        imei="490154203237518",
        model="iPhone 13",
        max_value_eur=350,
    )

    assert plan["device"]["imei"] == "490154203237518"
    assert plan["device"]["model"] == "iPhone 13"
    assert plan["summary"]["phase_count"] == 5
    assert plan["summary"]["step_count"] == 29
    assert plan["summary"]["live_supported_step_count"] == 7


def test_execute_inspection_plan_dry_run_marks_steps_planned():
    result = execute_inspection_plan(dry_run=True)

    first_step = result["phases"][0]["steps"][0]
    assert result["dry_run"] is True
    assert first_step["status"] == "planned"
    assert "Dry-run" in first_step["detail"]


def test_execute_inspection_plan_live_marks_unwired_steps_pending():
    result = execute_inspection_plan(dry_run=False)

    unsupported_step = result["phases"][2]["steps"][0]
    assert unsupported_step["live_supported"] is False
    assert unsupported_step["status"] == "pending_integration"
