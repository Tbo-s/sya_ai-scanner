from __future__ import annotations

from typing import Any, Callable

from services.machine_service import close_gate, emergency_stop, open_gate, tray_in, tray_out
from services.wrist_sequence_service import run_wrist_sequence


BOOT = "BOOT"
WELCOME = "WELCOME"
IMEI_SCAN = "IMEI_SCAN"
DEVICE_LOOKUP = "DEVICE_LOOKUP"
WAIT_POWER_OFF = "WAIT_POWER_OFF"
LOAD_DEVICE = "LOAD_DEVICE"
CLOSE_BOX = "CLOSE_BOX"
CAPTURE_FRONT = "CAPTURE_FRONT"
CAPTURE_BACK = "CAPTURE_BACK"
UPLOAD_RESULTS = "UPLOAD_RESULTS"
RETURN_DEVICE = "RETURN_DEVICE"
SHOW_PRICE = "SHOW_PRICE"
DONE = "DONE"
ERROR = "ERROR"
EMERGENCY_STOP = "EMERGENCY_STOP"


STATE_ORDER = [
    BOOT,
    WELCOME,
    IMEI_SCAN,
    DEVICE_LOOKUP,
    WAIT_POWER_OFF,
    LOAD_DEVICE,
    CLOSE_BOX,
    CAPTURE_FRONT,
    CAPTURE_BACK,
    UPLOAD_RESULTS,
    RETURN_DEVICE,
    SHOW_PRICE,
    DONE,
]


TERMINAL_STATES = {DONE, ERROR, EMERGENCY_STOP}


TRANSITIONS = {
    BOOT: WELCOME,
    WELCOME: IMEI_SCAN,
    IMEI_SCAN: DEVICE_LOOKUP,
    DEVICE_LOOKUP: WAIT_POWER_OFF,
    WAIT_POWER_OFF: LOAD_DEVICE,
    LOAD_DEVICE: CLOSE_BOX,
    CLOSE_BOX: CAPTURE_FRONT,
    CAPTURE_FRONT: CAPTURE_BACK,
    CAPTURE_BACK: UPLOAD_RESULTS,
    UPLOAD_RESULTS: RETURN_DEVICE,
    RETURN_DEVICE: SHOW_PRICE,
    SHOW_PRICE: DONE,
}


FLOW_STEPS = [
    {"number": 1, "state": BOOT, "description": "voedingknop gaat aan / voeding aansluiten op net"},
    {"number": 2, "state": BOOT, "description": "welkom text op device (sya) (opstarten)"},
    {"number": 3, "state": WELCOME, "description": "melding: wil je een prijsberekening voor uw toestel?"},
    {"number": 4, "state": WELCOME, "description": "‘start’ knop"},
    {"number": 5, "state": WELCOME, "description": "melding: screenprotector en case verwijderen"},
    {"number": 6, "state": WELCOME, "description": "‘ok’ knop"},
    {"number": 7, "state": WELCOME, "description": "melding: is het toestel proper? + anders toestel grondig reinigen"},
    {"number": 8, "state": WELCOME, "description": "‘ok’ knop"},
    {"number": 9, "state": IMEI_SCAN, "description": "melding: toets *#06# op het toestel voor imei"},
    {"number": 10, "state": IMEI_SCAN, "description": "‘scan’ knop"},
    {"number": 11, "state": IMEI_SCAN, "description": "camera openen en tonen"},
    {"number": 12, "state": IMEI_SCAN, "description": "camera leest imei uit"},
    {"number": 13, "state": IMEI_SCAN, "description": "pi vertaald foto naar imei nummer"},
    {"number": 14, "state": DEVICE_LOOKUP, "description": "pi stuurt imei naar api en krijgt producttype+grootte"},
    {"number": 15, "state": DEVICE_LOOKUP, "description": "melding: max prijs van toestel + overname mogelijk"},
    {"number": 16, "state": DEVICE_LOOKUP, "description": "‘ok’ knop voor producttype te bevestigen"},
    {"number": 17, "state": WAIT_POWER_OFF, "description": "melding: toestel nu volledig uitschakelen"},
    {"number": 18, "state": WAIT_POWER_OFF, "description": "‘ok’ knop"},
    {"number": 19, "state": LOAD_DEVICE, "description": "mg996r 360 gate omhoog"},
    {"number": 20, "state": LOAD_DEVICE, "description": "mg996r 360 schuif openen"},
    {"number": 21, "state": LOAD_DEVICE, "description": "melding: gsm toegevoegd?"},
    {"number": 22, "state": LOAD_DEVICE, "description": "‘ok’ knop"},
    {"number": 23, "state": CLOSE_BOX, "description": "mg996r 360 schuif dicht naar centrale positie"},
    {"number": 24, "state": CLOSE_BOX, "description": "mg996r 360 gate omlaag"},
    {"number": 25, "state": CAPTURE_FRONT, "description": "arm positioneert naar smartphone, afstandsensor stopt arm"},
    {"number": 27, "state": CAPTURE_FRONT, "description": "vacuummotors ON"},
    {"number": 28, "state": CAPTURE_FRONT, "description": "arm omhoog met nema17 z-as"},
    {"number": 29, "state": CAPTURE_FRONT, "description": "mg996r 360 schuift naar positie gate"},
    {"number": 30, "state": CAPTURE_FRONT, "description": "mg996r 180 (1) draait -90 -> 0"},
    {"number": 31, "state": CAPTURE_FRONT, "description": "camera trekt foto"},
    {"number": 32, "state": CAPTURE_FRONT, "description": "mg996r 180 (2) draait 0 -> -90"},
    {"number": 33, "state": CAPTURE_FRONT, "description": "camera trekt foto"},
    {"number": 34, "state": CAPTURE_FRONT, "description": "mg996r 180 (2) draait -90 -> 90"},
    {"number": 35, "state": CAPTURE_FRONT, "description": "camera trekt foto"},
    {"number": 36, "state": CAPTURE_FRONT, "description": "mg996r 180 (1) draait 0 -> 90"},
    {"number": 37, "state": CAPTURE_FRONT, "description": "mg996r 360 schuift terug centrale positie"},
    {"number": 38, "state": CAPTURE_FRONT, "description": "mg996r 180 terug startpositie"},
    {"number": 39, "state": CAPTURE_FRONT, "description": "nema17 z-as laat toestel zakken"},
    {"number": 40, "state": CAPTURE_FRONT, "description": "vacuummotors OFF"},
    {"number": 41, "state": CAPTURE_BACK, "description": "arm met nema17 x/y naar achterkant"},
    {"number": 42, "state": CAPTURE_BACK, "description": "afstandsensor stopt arm tegen gsm"},
    {"number": 43, "state": CAPTURE_BACK, "description": "vacuummotors ON"},
    {"number": 44, "state": CAPTURE_BACK, "description": "arm omhoog met nema17 z-as"},
    {"number": 45, "state": CAPTURE_BACK, "description": "mg996r 360 schuift naar positie gate"},
    {"number": 46, "state": CAPTURE_BACK, "description": "mg996r 180 (1) draait -90 -> 0"},
    {"number": 47, "state": CAPTURE_BACK, "description": "camera trekt foto"},
    {"number": 48, "state": CAPTURE_BACK, "description": "mg996r 180 (2) draait 0 -> -90"},
    {"number": 49, "state": CAPTURE_BACK, "description": "camera trekt foto"},
    {"number": 50, "state": CAPTURE_BACK, "description": "mg996r 180 (2) draait -90 -> 90"},
    {"number": 51, "state": CAPTURE_BACK, "description": "camera trekt foto"},
    {"number": 52, "state": CAPTURE_BACK, "description": "mg996r 180 (1) draait 0 -> 90"},
    {"number": 53, "state": UPLOAD_RESULTS, "description": "pi stuurt foto’s + imei naar api"},
    {"number": 54, "state": RETURN_DEVICE, "description": "mg996r 360 schuift terug naar centrale positie"},
    {"number": 55, "state": RETURN_DEVICE, "description": "mg996r 180 terug startpositie"},
    {"number": 56, "state": RETURN_DEVICE, "description": "nema17 z-as laat toestel terug zakken"},
    {"number": 57, "state": RETURN_DEVICE, "description": "vacuummotors OFF"},
    {"number": 58, "state": RETURN_DEVICE, "description": "mg996r 360 schuift gate open"},
    {"number": 59, "state": RETURN_DEVICE, "description": "mg996r 360 schuift lade terug uit box"},
    {"number": 60, "state": RETURN_DEVICE, "description": "toestel kan terug genomen worden"},
    {"number": 61, "state": SHOW_PRICE, "description": "pi krijgt prijs van api en toont die op scherm"},
    {"number": 62, "state": SHOW_PRICE, "description": "klant kan bevestigen of weigeren"},
    {"number": 63, "state": DONE, "description": "melding: bedankt"},
    {"number": 64, "state": DONE, "description": "delay 30 seconden / of home knop"},
    {"number": 65, "state": DONE, "description": "terug naar stap 1"},
]


STATE_ACTIONS = {
    LOAD_DEVICE: [
        {"id": "gate_open", "type": "leonardo", "command": "GATE_OPEN", "live_supported": True},
        {"id": "tray_out", "type": "leonardo", "command": "TRAY_OUT", "live_supported": True},
    ],
    CLOSE_BOX: [
        {"id": "tray_in", "type": "leonardo", "command": "TRAY_IN", "live_supported": True},
        {"id": "gate_close", "type": "leonardo", "command": "GATE_CLOSE", "live_supported": True},
    ],
    CAPTURE_FRONT: [
        {
            "id": "wrist_capture_front_sequence",
            "type": "wrist_sequence",
            "command": "WRIST_SEQUENCE",
            "live_supported": True,
        }
    ],
    CAPTURE_BACK: [
        {
            "id": "wrist_capture_back_sequence",
            "type": "wrist_sequence",
            "command": "WRIST_SEQUENCE",
            "live_supported": True,
        }
    ],
    RETURN_DEVICE: [
        {"id": "gate_open_return", "type": "leonardo", "command": "GATE_OPEN", "live_supported": True},
        {"id": "tray_out_return", "type": "leonardo", "command": "TRAY_OUT", "live_supported": True},
    ],
}


def _execute_leonardo_command(command: str) -> dict[str, Any]:
    commands: dict[str, Callable[[], dict[str, Any]]] = {
        "GATE_OPEN": open_gate,
        "GATE_CLOSE": close_gate,
        "TRAY_OUT": tray_out,
        "TRAY_IN": tray_in,
    }
    if command not in commands:
        return {"ok": False, "reason": f"Unsupported Leonardo command: {command}"}
    return {"ok": True, "result": commands[command]()}


def _execute_action(action: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    result = {
        "id": action["id"],
        "type": action["type"],
        "command": action.get("command"),
        "status": "planned" if dry_run else "pending",
        "detail": None,
    }

    if dry_run:
        result["detail"] = "Dry-run: geen hardware aangestuurd."
        return result

    if not action.get("live_supported"):
        result["status"] = "pending_integration"
        result["detail"] = "Nog niet live gekoppeld."
        return result

    if action["type"] == "leonardo":
        execution = _execute_leonardo_command(action["command"])
        result["status"] = "executed" if execution.get("ok") else "failed"
        result["detail"] = execution
        return result

    if action["type"] == "wrist_sequence":
        execution = run_wrist_sequence(simulate=False)
        result["status"] = "executed"
        result["detail"] = execution
        return result

    result["status"] = "pending_integration"
    result["detail"] = "Geen executor gedefinieerd voor dit type actie."
    return result


def build_inspection_state_machine_definition() -> dict[str, Any]:
    return {
        "initial_state": BOOT,
        "terminal_states": sorted(list(TERMINAL_STATES)),
        "states": STATE_ORDER + [ERROR, EMERGENCY_STOP],
        "transitions": TRANSITIONS,
        "flow_steps": FLOW_STEPS,
        "state_actions": STATE_ACTIONS,
    }


def run_inspection_state_machine(
    *,
    imei: str = "",
    model: str = "",
    max_value_eur: float = 0.0,
    dry_run: bool = True,
    trigger_emergency_stop: bool = False,
) -> dict[str, Any]:
    definition = build_inspection_state_machine_definition()
    executed_states = []
    current_state = BOOT

    if trigger_emergency_stop:
        stop_result = {"status": "planned", "detail": "Dry-run: emergency stop gesimuleerd."}
        if not dry_run:
            stop_result = {"status": "executed", "detail": emergency_stop()}
        return {
            "dry_run": dry_run,
            "device": {"imei": str(imei or ""), "model": str(model or ""), "max_value_eur": float(max_value_eur or 0.0)},
            "final_state": EMERGENCY_STOP,
            "states": [{"state": EMERGENCY_STOP, "actions": [stop_result]}],
            "definition": definition,
        }

    try:
        while current_state not in TERMINAL_STATES:
            actions = STATE_ACTIONS.get(current_state, [])
            action_results = [_execute_action(action, dry_run=dry_run) for action in actions]
            executed_states.append({"state": current_state, "actions": action_results})

            next_state = TRANSITIONS.get(current_state)
            if not next_state:
                current_state = ERROR
                break
            current_state = next_state

        if current_state == DONE:
            executed_states.append({"state": DONE, "actions": []})
    except Exception as e:
        current_state = ERROR
        executed_states.append(
            {
                "state": ERROR,
                "actions": [{"id": "runtime_exception", "status": "failed", "detail": str(e)}],
            }
        )

    return {
        "dry_run": dry_run,
        "device": {
            "imei": str(imei or ""),
            "model": str(model or ""),
            "max_value_eur": float(max_value_eur or 0.0),
        },
        "final_state": current_state,
        "states": executed_states,
        "definition": definition,
    }
