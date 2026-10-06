#include "tmc5160_spi.h"
#include "grbl.h"

#include <avr/io.h>
#include <stdint.h>

#define TMC5160_REG_WRITE 0x80
#define TMC5160_REG_GCONF 0x00
#define TMC5160_REG_GSTAT 0x01
#define TMC5160_REG_IOIN 0x04
#define TMC5160_REG_GLOBAL_SCALER 0x0B
#define TMC5160_REG_IHOLD_IRUN 0x10
#define TMC5160_REG_TPOWERDOWN 0x11
#define TMC5160_REG_CHOPCONF 0x6C
#define TMC5160_REG_MSCNT 0x6A
#define TMC5160_REG_DRV_STATUS 0x6F
#define TMC5160_REG_PWMCONF 0x70

#define TMC5160_IHOLD_IRUN_VALUE(run) \
  (((uint32_t)TMC5160_IHOLD_DELAY << 16) | ((uint32_t)(run) << 8) | TMC5160_IHOLD)

// The previous DRV8825 drivers had M0/M1/M2 open, which selects full steps.
// Use the same mode for every axis. Interpolation is off so one STEP pulse is
// one 1.8-degree motor step on the connected NEMA17 motors.
#define TMC5160_CHOPCONF_FULLSTEP 0x08408158UL
#define TMC5160_PWMCONF_DEFAULT 0xC40C001EUL

typedef struct {
  volatile uint8_t *ddr;
  volatile uint8_t *port;
  uint8_t bit;
} Tmc5160Pin;

typedef struct {
  Tmc5160Pin sck;
  Tmc5160Pin sdi;
  Tmc5160Pin cs;
} Tmc5160DriverPins;

// Arduino Mega pin map:
// D40=PG1, D41=PG0, D42=PL7, D43=PL6, D44=PL5, D45=PL4,
// D46=PL3, D47=PL2, D48=PL1.
static const Tmc5160DriverPins tmc5160_drivers[] = {
  {{&DDRG, &PORTG, 1}, {&DDRG, &PORTG, 0}, {&DDRL, &PORTL, 7}}, // X
  {{&DDRL, &PORTL, 6}, {&DDRL, &PORTL, 5}, {&DDRL, &PORTL, 4}}, // Y
  {{&DDRL, &PORTL, 3}, {&DDRL, &PORTL, 2}, {&DDRL, &PORTL, 1}}, // Z
};

// Optional X-driver SDO on D49=PL0. The input pull-up identifies a missing wire.
static uint8_t tmc5160_x_boot_current_echo_ok;

static void tmc5160_pin_output(Tmc5160Pin pin)
{
  *pin.ddr |= (1 << pin.bit);
}

static void tmc5160_pin_high(Tmc5160Pin pin)
{
  *pin.port |= (1 << pin.bit);
}

static void tmc5160_pin_low(Tmc5160Pin pin)
{
  *pin.port &= ~(1 << pin.bit);
}

static void tmc5160_delay(void)
{
  for (uint8_t i = 0; i < 16; i++) {
    __asm__ __volatile__("nop");
  }
}

static uint8_t tmc5160_transfer_byte(const Tmc5160DriverPins *pins, uint8_t value)
{
  uint8_t received = 0;
  for (int8_t bit = 7; bit >= 0; bit--) {
    tmc5160_pin_low(pins->sck);
    if (value & (1 << bit)) {
      tmc5160_pin_high(pins->sdi);
    } else {
      tmc5160_pin_low(pins->sdi);
    }
    tmc5160_delay();
    tmc5160_pin_high(pins->sck);
    received = (received << 1) | ((PINL & (1 << 0)) != 0);
    tmc5160_delay();
  }
  return received;
}

static uint32_t tmc5160_transfer(const Tmc5160DriverPins *pins, uint8_t address, uint32_t value)
{
  uint32_t received = 0;
  tmc5160_pin_low(pins->cs);
  tmc5160_delay();
  tmc5160_transfer_byte(pins, address); // Discard the SPI status byte.
  for (int8_t shift = 24; shift >= 0; shift -= 8) {
    received = (received << 8) | tmc5160_transfer_byte(pins, (uint8_t)(value >> shift));
  }
  tmc5160_pin_high(pins->cs);
  tmc5160_delay();
  return received;
}

static uint32_t tmc5160_write_register(const Tmc5160DriverPins *pins, uint8_t address, uint32_t value)
{
  return tmc5160_transfer(pins, address | TMC5160_REG_WRITE, value);
}

static uint32_t tmc5160_read_x_register(uint8_t address)
{
  // SPI replies contain the result of the preceding transaction.
  tmc5160_transfer(&tmc5160_drivers[0], address, 0);
  return tmc5160_transfer(&tmc5160_drivers[0], address, 0);
}

static void tmc5160_configure_driver(const Tmc5160DriverPins *pins)
{
  uint32_t current_setting = TMC5160_IHOLD_IRUN_VALUE(TMC5160_IRUN);
  tmc5160_write_register(pins, TMC5160_REG_GSTAT, 0x00000007UL);
  tmc5160_write_register(pins, TMC5160_REG_GCONF, 0x00000000UL);
  tmc5160_write_register(pins, TMC5160_REG_GLOBAL_SCALER, TMC5160_GLOBAL_SCALER);
  uint32_t scaler_echo = tmc5160_write_register(pins, TMC5160_REG_IHOLD_IRUN, current_setting);
  uint32_t current_echo = tmc5160_write_register(pins, TMC5160_REG_TPOWERDOWN, 0x0000000AUL);
  if (pins == &tmc5160_drivers[0]) {
    // These registers are write-only; the next SPI frame echoes the received data.
    tmc5160_x_boot_current_echo_ok = (scaler_echo == TMC5160_GLOBAL_SCALER)
      && (current_echo == current_setting);
  }
  tmc5160_write_register(pins, TMC5160_REG_CHOPCONF, TMC5160_CHOPCONF_FULLSTEP);
  tmc5160_write_register(pins, TMC5160_REG_PWMCONF, TMC5160_PWMCONF_DEFAULT);
}

void tmc5160_spi_init(void)
{
  uint8_t index;
  DDRL &= ~(1 << 0);
  PORTL |= (1 << 0);
  for (index = 0; index < (sizeof(tmc5160_drivers) / sizeof(tmc5160_drivers[0])); index++) {
    const Tmc5160DriverPins *pins = &tmc5160_drivers[index];
    tmc5160_pin_output(pins->sck);
    tmc5160_pin_output(pins->sdi);
    tmc5160_pin_output(pins->cs);
    tmc5160_pin_high(pins->sck);
    tmc5160_pin_low(pins->sdi);
    tmc5160_pin_high(pins->cs);
  }

  for (index = 0; index < (sizeof(tmc5160_drivers) / sizeof(tmc5160_drivers[0])); index++) {
    tmc5160_configure_driver(&tmc5160_drivers[index]);
  }
}

static void tmc5160_report_value(const char *name, uint32_t value)
{
  printPgmString(PSTR("[QHV:X "));
  printPgmString(name);
  printPgmString(PSTR("=0x"));
  for (int8_t shift = 28; shift >= 0; shift -= 4) {
    uint8_t digit = (value >> shift) & 0x0F;
    serial_write(digit < 10 ? '0' + digit : 'A' + digit - 10);
  }
  printPgmString(PSTR("]\r\n"));
}

void tmc5160_report_x(void)
{
  tmc5160_report_value(PSTR("IOIN"), tmc5160_read_x_register(TMC5160_REG_IOIN));
  tmc5160_report_value(PSTR("GSTAT"), tmc5160_read_x_register(TMC5160_REG_GSTAT));
  tmc5160_report_value(PSTR("GCONF"), tmc5160_read_x_register(TMC5160_REG_GCONF));
  tmc5160_report_value(PSTR("CHOPCONF"), tmc5160_read_x_register(TMC5160_REG_CHOPCONF));
  tmc5160_report_value(PSTR("DRV_STATUS"), tmc5160_read_x_register(TMC5160_REG_DRV_STATUS));
  tmc5160_report_value(PSTR("MSCNT"), tmc5160_read_x_register(TMC5160_REG_MSCNT));
  tmc5160_report_value(PSTR("BOOT_CURRENT_ECHO"), tmc5160_x_boot_current_echo_ok);
}
