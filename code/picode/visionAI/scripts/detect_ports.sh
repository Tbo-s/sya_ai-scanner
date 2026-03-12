#!/usr/bin/env bash
# detect_ports.sh – list USB serial ports and identify Arduino boards
echo "=== USB Serial Devices ==="
ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "(none found)"
echo ""
echo "=== Port Details ==="
python3 - << 'PYEOF'
try:
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
    for p in ports:
        vid = f"{p.vid:#06x}" if p.vid else "N/A"
        pid = f"{p.pid:#06x}" if p.pid else "N/A"
        print(f"  {p.device}")
        print(f"    Description : {p.description}")
        print(f"    Manufacturer: {p.manufacturer}")
        print(f"    VID:PID     : {vid}:{pid}")
        print(f"    HWID        : {p.hwid}")
        print()
except ImportError:
    print("pyserial not installed. Run: pip install pyserial")
PYEOF

echo "=== Suggested config.env settings ==="
python3 - << 'PYEOF'
try:
    from serial.tools import list_ports
    LEONARDO_PIDS = {0x0036, 0x8036}
    MEGA_PIDS     = {0x0010, 0x0042, 0x0242}
    ARDUINO_VIDS  = {0x2341, 0x2A03}

    leo, mega = None, None
    for p in list_ports.comports():
        if p.vid in ARDUINO_VIDS:
            if p.pid in LEONARDO_PIDS:
                leo = p.device
            elif p.pid in MEGA_PIDS:
                mega = p.device

    if leo:
        print(f"APP_LEONARDO_PORT={leo}")
    else:
        print("# Leonardo not detected automatically")
        print("# APP_LEONARDO_PORT=/dev/ttyACM0")

    if mega:
        print(f"APP_GRBL_PORT={mega}")
    else:
        print("# Mega not detected automatically")
        print("# APP_GRBL_PORT=/dev/ttyACM1")
except ImportError:
    pass
PYEOF
