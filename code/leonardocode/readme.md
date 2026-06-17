te ontvangen :
GATE_OPEN
GATE_CLOSE
TRAY_OUT
TRAY_IN
STATUS
STOP_ALL

stoppers:
- bovenste gate-stopper: A4
- onderste gate-stopper: A5
- lade-uit-stopper: D4
- lade-in-stopper: D5
- alle stopper-switches zijn normally closed en gebruiken INPUT_PULLUP
- sluit elke stopper naar GND: niet geraakt = LOW, stopper geraakt/contact open = HIGH

leonardo verstuurd:
ACK:GATE_OPEN
ACK:GATE_CLOSE
ACK:TRAY_OUT
ACK:TRAY_IN
ACK:STATUS,gateState=...,gatePos=...,trayState=...,trayPos=...

De Pi/backend bepaalt of de gate klaar is via `STATUS`: `gateState=0` en `gatePos=UP`
of `gatePos=DOWN`.
