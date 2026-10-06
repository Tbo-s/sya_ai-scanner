#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys


def default_grbl_dir() -> Path:
    candidates = [
        Path.home() / "Documents" / "Arduino" / "libraries" / "grbl",
        Path.home() / "Arduino" / "libraries" / "grbl",
        Path("/Users/tbo/Documents/Arduino/libraries/grbl"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def ensure_contains(path: Path, needle: str, replacement: str) -> None:
    text = path.read_text()
    if replacement in text:
        return
    if needle not in text:
        raise RuntimeError(f"Could not find patch anchor in {path}: {needle!r}")
    path.write_text(text.replace(needle, replacement, 1))


def backup_once(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".qhv5160.bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def main() -> int:
    grbl_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_grbl_dir()
    if not grbl_dir.exists():
        raise SystemExit(f"GRBL library directory not found: {grbl_dir}")

    here = Path(__file__).resolve().parent
    for filename in ("tmc5160_spi.c", "tmc5160_spi.h"):
        shutil.copy2(here / filename, grbl_dir / filename)

    grbl_h = grbl_dir / "grbl.h"
    main_c = grbl_dir / "main.c"
    system_c = grbl_dir / "system.c"
    backup_once(grbl_h)
    backup_once(main_c)
    backup_once(system_c)

    ensure_contains(
        grbl_h,
        '#include "sleep.h"\n',
        '#include "sleep.h"\n#include "tmc5160_spi.h"\n',
    )
    ensure_contains(
        main_c,
        "  stepper_init();  // Configure stepper pins and interrupt timers\n",
        "  stepper_init();  // Configure stepper pins and interrupt timers\n"
        "  tmc5160_spi_init(); // Configure QHV5160/TMC5160 drivers over bit-banged SPI\n",
    )
    ensure_contains(
        system_c,
        "        case '#' : // Print Grbl NGC parameters\n",
        "        case 'T' : // Read-only X-driver SPI diagnostics [IDLE/ALARM]\n"
        "          if (line[2] != 0) { return(STATUS_INVALID_STATEMENT); }\n"
        "          tmc5160_report_x();\n"
        "          break;\n"
        "        case '#' : // Print Grbl NGC parameters\n",
    )

    print(f"Patched GRBL library: {grbl_dir}")
    print("Backup files end with .qhv5160.bak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
