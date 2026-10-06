# QHV5160 on Arduino Mega GRBL

This patch configures three QHV5160/TMC5160 drivers from the Arduino Mega at
GRBL boot. It uses bit-banged SPI so every driver input has its own Mega pin
and no signal wire needs to be split. One optional wire enables X diagnostics.

For QHV5160 modules with 0.075 ohm sense resistors, all three axes use about
846 mA RMS run current (IRUN=16), 348 mA RMS hold current, and
GLOBAL_SCALER=133. These are calculated current targets, not measured coil
currents or analog Vref voltages.

All axes use full steps without interpolation to match the previous DRV8825
drivers with M0/M1/M2 disconnected. At the current GRBL setting of 250 steps/mm,
a 0.004 mm command is one full step (1.8 degrees on the bare motor shaft); a
0.1 mm command is 25 steps / 45 degrees. Begin with one step. Actual arm travel
depends on the mechanics and calibration.

## Apply

From the repo root on the Mac:

```bash
python3 code/megacode/qhv5160_grbl_mega_spi/apply_to_arduino_grbl.py
```

Then upload:

```text
code/megacode/grblUpload_copy_20260304140826/grblUpload_copy_20260304140826.ino
```

with board `Arduino Mega or Mega 2560`.

## Wiring

Set QHV5160 `VIO` to 5V and connect all grounds together.

X driver:

- Mega D24 -> `REFL_STEP`
- Mega D30 -> `DIR_REFR_DIR`
- Mega D40 -> `SCK_CFG2`
- Mega D41 -> `SDI_CFG1`
- Mega D42 -> `CSN_CFG3`

Y driver:

- Mega D25 -> `REFL_STEP`
- Mega D31 -> `DIR_REFR_DIR`
- Mega D43 -> `SCK_CFG2`
- Mega D44 -> `SDI_CFG1`
- Mega D45 -> `CSN_CFG3`

Z driver:

- Mega D26 -> `REFL_STEP`
- Mega D32 -> `DIR_REFR_DIR`
- Mega D46 -> `SCK_CFG2`
- Mega D47 -> `SDI_CFG1`
- Mega D48 -> `CSN_CFG3`

Enable:

- Minimum wiring: each QHV5160 `EN` -> GND.
- Or one shared GRBL enable line: Mega D13 -> each `EN`.

Mode pins on every driver:

- `SD_MODE` -> VIO
- `SPI_MODE` -> VIO

Leave Y/Z `SDO_CFG0` disconnected.

## Optional X Diagnostics

With all power and USB disconnected, add **X `SDO_CFG0` -> Mega D49**.
Keep the existing SCK/SDI/CSN wiring and common ground. D49 is an input with a
weak pull-up, not a 5V output. This adds just one wire (four SPI wires for X).

After uploading this patch, send `$T` through GRBL while idle or in alarm.
The command reads registers only: it does not move the motor, clear driver
faults, or change current settings.

- `IOIN`: chip version in bits 31..24 (expected 0x30), EN level in bit 4
  (0=enabled), SD_MODE in bit 6 (1=STEP/DIR mode).
- `GSTAT`: reset in bit 0, driver shutdown in bit 1, charge-pump undervoltage
  history in bit 2. Read `DRV_STATUS` for details before clearing faults.
- `GCONF`: expected 0x00000000.
- `CHOPCONF`: expected 0x08408158 for X (full steps, driver enabled). Y and Z
  receive the same setting at boot; their SDO pins are intentionally unwired.
- `DRV_STATUS`: raw driver status, including protection flags and CS_ACTUAL.
- `MSCNT`: microstep counter; compare before/after a small commanded move to
  check whether the driver is receiving STEP pulses.
- `BOOT_CURRENT_ECHO`: 1 means the driver echoed both current-setting payloads
  during Mega boot. It is not a measurement of coil current. GLOBAL_SCALER and
  IHOLD_IRUN are write-only, so `$T` does not pretend to read their contents.

All-ones reads typically mean no SDO response; all-zero reads also do not
establish communication. Check IOIN version and several register values.
`BOOT_CURRENT_ECHO=0` can also mean SDO was missing at boot; after connecting
it, restart the Mega with the driver powered before judging this field.

Reference: [TMC5160 datasheet, sections 4 and 6](https://www.analog.com/media/en/technical-documentation/data-sheets/TMC5160A_datasheet_rev1.18.pdf).
