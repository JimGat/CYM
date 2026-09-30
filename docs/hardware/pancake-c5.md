# C5Lab Pancake-C5 DIY Beta

CYM's `pancake-c5` target is a narrow board-profile port of the shared application, based on C5Lab reference commit `02528ded8feb242a8400e575b14e489ada1f960b`.[1]

The build is dedicated to **D3h420, Janek, and OyczE**. C5Lab's Pancake concept also inspired the original CYM direction on NM-CYD-C5.

## Reference pin map

| Function | Assignment |
|---|---|
| Display SPI2 | MOSI GPIO24, MISO GPIO4, clock GPIO23 |
| Display control | CS GPIO5, DC GPIO3, reset GPIO2, backlight GPIO26 |
| Display | 480×320, 40 MHz, BGR, inverted, mirrored X/Y, swapped axes |
| FT6336U touch | I2C `0x38`, SDA GPIO9, SCL GPIO10, INT GPIO25, reset GPIO8 |
| microSD | shared SPI2, CS GPIO7, 20 MHz |
| GPS UART1 | TX GPIO13, RX GPIO14 |
| WS2812 | GPIO27 |
| Battery ADC | GPIO6, reference divider ratio 3.2 |
| Flash / PSRAM | 8 MB / 8 MB |

The board has no fitted RTC. Clock can use UART GPS, public NTP, validated GPS-module RTC holdover, and disciplined RTOS holdover.

## Flashing

Use `https://jimgat.github.io/CYM/?beta=1` and select **Pancake-C5 DIY (Beta)**. The merged `CYM-Pancake-C5-full.bin` is flashed at offset `0x0000`.

## Remote qualification checklist

Automated contracts and a successful ESP-IDF build prove integration, not hardware. Validate on the actual board:

1. Boot identity and absence of reset loops.
2. Full-screen 480×320 output, correct color order, orientation, inversion, and backlight.
3. FT6336U center and four-corner mapping with no mirrored/swapped axis fault.
4. SD mount/read/write under UI activity.
5. 2.4/5-GHz Wi-Fi, BLE, and 802.15.4.
6. GPS UART GPIO13/14, Clock GPS lock, Maidenhead grid, and AP NTP.
7. Battery reading and WS2812 behavior.
8. Classic and Modern navigation plus at least a 30-minute soak.

Report serial logs and photos for any mismatch. Do not infer controller or PCB revision from appearance alone.

Sources:

- [1] [C5Lab Pancake repository](https://github.com/C5Lab/pancake)
