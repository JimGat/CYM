# CYM v2.15.99 — WS-C5-35 GPIO28 GPS receive trial

Only CONFIG_BOARD_WS_C5_35 changes to UART1 RX=GPIO28, TX=-1 (detached), one GPS candidate and no alternate-pin/EXIO polling. All eight release boards share this cycle version; other boards retain their GPS/BOOT mappings. Primary USB-C Serial/JTAG logging stays separate. Saved baud is honored; select 9600 for Jim's confirmed module. No GPS configuration writes or baud autodetection.

## Pin ownership and hardware evidence

WS-C5-35 firmware no longer configures/polls GPIO28 as BOOT: GPS pulses cannot trigger game fire/cancel or Go Dark button actions. Physical BOOT/download strapping is unchanged. Touch controls and five-second screen-hold Go Dark wake remain available. Avoid pressing physical BOOT against an actively connected GPS transmitter.

Jim reports several successful reboots with GPS attached to GPIO28. This is boot evidence on his assembly, not GPS reception/NMEA/fix qualification. The six continuity-confirmed disconnected J3 routes remain disconnected; no resistor or helper-controller modifications are made.

## Operator procedure

1. Prefer the app-only WS-C5-35 image at 0x10000, erase-all disabled, to preserve NVS/PHY/partitions. The supplied full image starts at 0x0000 and can overwrite settings.
2. Keep qualified GPS TX -> GPIO28, common GND and the module's qualified supply. GPS RX remains disconnected. No other transmitter or 5 V serial signal on GPIO28.
3. Use the primary USB-C console, not CH340/secondary USB or J3 TX/RX.
4. In GPS Monitor select 9600 and enable existing debug/raw diagnostics.

Ask: "Does the new image use only GPIO28 for GPS?"
Expected startup fields: GPS_RX_OWNER board=WS35 uart=1 rx=28 tx_detached=-1 baud=9600 reader=monitor config_writes=0 console=primary_USB ... candidates=1 boot_button=disabled.

Ask: "Is data arriving before a satellite fix?"
Expected diagnostic fields: GPS_RAW_RX board=WS35 uart=1 rx=28 baud=9600 bytes=... total=... chunks=... preview=...
Increasing byte counts qualify reception; readable $G... sentences qualify NMEA framing. Satellite fix is a separate gate. Zero bytes means no received transport, not merely no fix. Return that raw line and GPS Monitor status.

Ask: "Will GPS traffic activate BOOT actions?"
Expected: no WS-C5-35 firmware BOOT polling; use touch controls. Physical BOOT/reset remains hardware behavior.

## Verification scope

The actual production GPS initialization and guarded BOOT routines are compiled/exercised in a host harness. It checks GPIO28-only pin access, detached TX/RTS/CTS, baud selection, all five initialization error stages and cleanup after installed-UART configuration failures. Other boards' GPS initialization/profile source equivalence is checked. This is not physical reception proof.
