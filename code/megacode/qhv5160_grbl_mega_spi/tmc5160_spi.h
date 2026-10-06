#ifndef tmc5160_spi_h
#define tmc5160_spi_h

#include <stdint.h>

// QHV5160/TMC5160 init for Arduino Mega 2560 + Grbl.
//
// Each driver has its own bit-banged SCK, SDI and CS, with optional X readback.
// No SPI signal wire needs to be split.
//
// X: SCK D40, SDI D41, CS D42
// Y: SCK D43, SDI D44, CS D45
// Z: SCK D46, SDI D47, CS D48
// Optional X diagnostics: SDO D49 (input only), query with $T while idle.
//
// QHV5160 has 0.075 ohm sense resistors.
// I_RMS = GLOBALSCALER/256 * (CS+1)/32 * 0.325/Rsense/sqrt(2)
// GLOBALSCALER=133 and IRUN=16 gives about 846 mA RMS on every axis.

#define TMC5160_GLOBAL_SCALER 133
#define TMC5160_IRUN 16
#define TMC5160_IHOLD 6
#define TMC5160_IHOLD_DELAY 6

void tmc5160_spi_init(void);
void tmc5160_report_x(void);

#endif
