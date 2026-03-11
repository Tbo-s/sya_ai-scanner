from __future__ import annotations

from typing import Any, Callable

from services.machine_service import close_gate, open_gate, tray_in, tray_out


def _step(
    step_id: str,
    title: str,
    action_type: str,
    description: str,
    *,
    command: str | None = None,
    live_supported: bool = False,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "type": action_type,
        "description": description,
        "command": command,
        "live_supported": live_supported,
    }


def _phase(phase_id: str, title: str, description: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": phase_id,
        "title": title,
        "description": description,
        "steps": steps,
    }


def build_inspection_plan(
    imei: str = "",
    model: str = "",
    max_value_eur: float = 0.0,
) -> dict[str, Any]:
    normalized_imei = str(imei or "").strip()
    normalized_model = str(model or "").strip() or "Unknown device"
    normalized_value = float(max_value_eur or 0.0)

    phases = [
        _phase(
            "intake",
            "Klant intake",
            "UI-stappen voor voorbereiding, IMEI-detectie en toestelverificatie.",
            [
                _step(
                    "welcome",
                    "Welkom en start",
                    "ui",
                    "Toon welkomstscherm en vraag of de klant een prijsberekening wil.",
                ),
                _step(
                    "prep_remove_case",
                    "Voorbereiding toestel",
                    "manual",
                    "Vraag om case en screenprotector te verwijderen en het toestel proper te maken.",
                ),
                _step(
                    "capture_imei",
                    "IMEI uitlezen",
                    "vision",
                    "Open de camera, lees de barcode van *#06# en zet deze om naar een 15-cijferige IMEI.",
                ),
                _step(
                    "lookup_device",
                    "Toestel lookup",
                    "api",
                    "Zoek via IMEI het model op en toon de maximale richtprijs.",
                ),
                _step(
                    "power_off",
                    "Toestel uitschakelen",
                    "manual",
                    "Vraag de klant om het toestel volledig uit te schakelen voor de mechanische cyclus start.",
                ),
            ],
        ),
        _phase(
            "loading",
            "Toestel inladen",
            "Open de box, laat de klant het toestel plaatsen en sluit daarna veilig af.",
            [
                _step(
                    "gate_open",
                    "Gate openen",
                    "leonardo",
                    "Open de gate zodat de inlegzone toegankelijk wordt.",
                    command="GATE_OPEN",
                    live_supported=True,
                ),
                _step(
                    "tray_out",
                    "Lade uitschuiven",
                    "leonardo",
                    "Schuif de smartphone-lade naar buiten voor de klant.",
                    command="TRAY_OUT",
                    live_supported=True,
                ),
                _step(
                    "wait_phone_inserted",
                    "Wachten op toestel",
                    "manual",
                    "Wacht op klantbevestiging dat het toestel correct in de lade ligt.",
                ),
                _step(
                    "tray_in",
                    "Lade inschuiven",
                    "leonardo",
                    "Breng de lade terug naar de centrale positie.",
                    command="TRAY_IN",
                    live_supported=True,
                ),
                _step(
                    "gate_close",
                    "Gate sluiten",
                    "leonardo",
                    "Sluit de gate zodat de capture-zone afgeschermd is.",
                    command="GATE_CLOSE",
                    live_supported=True,
                ),
            ],
        ),
        _phase(
            "front_capture",
            "Front capture",
            "Pak het toestel op, positioneer het voor de camera en neem de eerste reeks foto's.",
            [
                _step(
                    "front_xy_pick",
                    "Arm naar voorkant",
                    "grbl",
                    "Beweeg de CoreXY-arm naar de voorzijde van het toestel.",
                ),
                _step(
                    "front_distance_stop",
                    "Afstandssensor stop",
                    "sensor",
                    "Stop wanneer de arm de ingestelde pick-up afstand bereikt.",
                ),
                _step(
                    "front_vacuum_on",
                    "Vacuum aan",
                    "vacuum",
                    "Activeer de vacuümtubes zodat het toestel vastgenomen wordt.",
                ),
                _step(
                    "front_lift",
                    "Toestel optillen",
                    "grbl",
                    "Breng de Z-as omhoog zodat het toestel vrij van de lade hangt.",
                ),
                _step(
                    "front_camera_position",
                    "Positioneren voor camera",
                    "servo",
                    "Beweeg wrist en slider naar de eerste camerahoek.",
                ),
                _step(
                    "front_capture_series",
                    "Foto's voorkant nemen",
                    "camera",
                    "Neem meerdere foto's door de wrist-servos op de gewenste hoeken te zetten.",
                ),
                _step(
                    "front_return",
                    "Terugzetten voorkant",
                    "grbl",
                    "Laat het toestel zakken en schakel vacuum uit.",
                ),
            ],
        ),
        _phase(
            "back_capture",
            "Back capture",
            "Herhaal de pick-up en capture aan de achterzijde van het toestel.",
            [
                _step(
                    "back_xy_pick",
                    "Arm naar achterkant",
                    "grbl",
                    "Positioneer de arm aan de achterkant van het toestel.",
                ),
                _step(
                    "back_distance_stop",
                    "Afstandssensor stop",
                    "sensor",
                    "Stop op de ingestelde contactafstand.",
                ),
                _step(
                    "back_vacuum_on",
                    "Vacuum aan",
                    "vacuum",
                    "Neem het toestel op met de vacuümtubes.",
                ),
                _step(
                    "back_lift",
                    "Toestel optillen",
                    "grbl",
                    "Til het toestel op voor de tweede fotoserie.",
                ),
                _step(
                    "back_camera_position",
                    "Positioneren voor camera",
                    "servo",
                    "Draai wrist en slider door de achterzijde-hoeken.",
                ),
                _step(
                    "back_capture_series",
                    "Foto's achterkant nemen",
                    "camera",
                    "Neem de tweede reeks foto's en koppel die aan de IMEI.",
                ),
                _step(
                    "back_return",
                    "Terugzetten achterkant",
                    "grbl",
                    "Laat het toestel opnieuw zakken en schakel vacuum uit.",
                ),
            ],
        ),
        _phase(
            "pricing",
            "Prijs en afronding",
            "Upload resultaten, geef het toestel terug en toon de prijs.",
            [
                _step(
                    "upload_photos",
                    "Foto's uploaden",
                    "api",
                    "Stuur de foto's en IMEI naar de pricing API.",
                ),
                _step(
                    "gate_open_return",
                    "Gate openen voor retour",
                    "leonardo",
                    "Open de gate voor de retourfase.",
                    command="GATE_OPEN",
                    live_supported=True,
                ),
                _step(
                    "tray_out_return",
                    "Lade uitschuiven voor retour",
                    "leonardo",
                    "Schuif de lade uit zodat de klant het toestel kan nemen.",
                    command="TRAY_OUT",
                    live_supported=True,
                ),
                _step(
                    "show_price",
                    "Prijs tonen",
                    "ui",
                    "Toon de finale prijs en laat de klant bevestigen of weigeren.",
                ),
                _step(
                    "thank_you",
                    "Bedankt-scherm",
                    "ui",
                    "Toon een bedankbericht en reset daarna naar het startscherm.",
                ),
            ],
        ),
    ]

    total_steps = sum(len(phase["steps"]) for phase in phases)
    live_supported_steps = sum(
        1 for phase in phases for step in phase["steps"] if step["live_supported"]
    )

    return {
        "device": {
            "imei": normalized_imei,
            "model": normalized_model,
            "max_value_eur": normalized_value,
        },
        "summary": {
            "phase_count": len(phases),
            "step_count": total_steps,
            "live_supported_step_count": live_supported_steps,
        },
        "phases": phases,
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


def _execute_step(step: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    result = {
        "id": step["id"],
        "title": step["title"],
        "type": step["type"],
        "live_supported": step["live_supported"],
        "status": "planned" if dry_run else "pending",
        "detail": None,
    }

    if dry_run:
        result["detail"] = "Dry-run: geen hardware aangestuurd."
        return result

    if not step["live_supported"]:
        result["status"] = "pending_integration"
        result["detail"] = "Nog niet live gekoppeld aan hardware of API."
        return result

    command = step.get("command")
    if step["type"] == "leonardo" and command:
        execution = _execute_leonardo_command(command)
        result["status"] = "executed" if execution.get("ok") else "failed"
        result["detail"] = execution
        return result

    result["status"] = "pending_integration"
    result["detail"] = "Geen executor gedefinieerd voor dit type stap."
    return result


def execute_inspection_plan(
    imei: str = "",
    model: str = "",
    max_value_eur: float = 0.0,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    plan = build_inspection_plan(imei=imei, model=model, max_value_eur=max_value_eur)
    phase_results = []

    for phase in plan["phases"]:
        executed_steps = [_execute_step(step, dry_run=dry_run) for step in phase["steps"]]
        phase_results.append(
            {
                "id": phase["id"],
                "title": phase["title"],
                "description": phase["description"],
                "steps": executed_steps,
            }
        )

    return {
        "dry_run": dry_run,
        "device": plan["device"],
        "summary": plan["summary"],
        "phases": phase_results,
    }
