# Pancake-C5 Beta and Documentation Design

## Goal

Publish a fifth, beta-only CYM target for C5Lab's Pancake DIY ESP32-C5 board while documenting the verified physical T5577 clone flow and the universal Clock accurately in both README and Wiki.

## Constraints

- Work only on ESP32-Dev in the authoritative CYM checkout and a dedicated CYM Wiki clone.
- Preserve the shared CYM application; Pancake is a board profile, not a fork.
- Pin the hardware reference to C5Lab/pancake commit `02528ded8feb242a8400e575b14e489ada1f960b`.
- Treat the upstream Pancake display/touch wiring and initialization as the hardware contract; do not infer pins from photographs.
- Keep Pancake beta-only behind `?beta=1` until remote hardware validation.
- Do not claim hardware validation for Pancake. Compilation and source contracts are not physical proof.
- Do not promise sub-50-ms GPS time. Current UART RMC timing has no PPS and is uncharacterized.

## Pancake architecture

Add `CONFIG_BOARD_PANCAKE_C5` and `pancake_c5.h` to the existing ESP32-C5 board HAL. The profile uses the reference Pancake wiring:

- SPI2 display/SD: MOSI 24, MISO 4, SCK 23
- LCD: CS 5, DC 3, reset 2, backlight 26
- FT6336U touch: SDA 9, SCL 10, INT 25, reset 8, address 0x38
- SD CS 7
- GPS UART1: TX 13, RX 14
- WS2812: GPIO27
- battery ADC: GPIO6, conservative divider 3.2
- landscape 480x320 logical display, 40-MHz SPI

Use a narrow Pancake adapter only for board-specific ILI9341-compatible panel setup and FT6336U I2C touch. Reuse shared main.c, menus, radios, storage, Clock, and application components. Preserve the upstream display transform: BGR, inversion enabled, mirror X/Y, swap X/Y. Preserve the upstream touch transform.

Pancake has no fitted RTC in the reference design. It gets the same conservative uncharacterized UART-GPS timing profile as NM-CYD-C5. It supports Display Only, Client NTP, AP NTP, GPS lock, GPS-module RTC holdover, and RTOS/NTP holdover.

## Packaging and flasher

Add `pancake-c5` to the build dispatcher, `make all-boards`, package export, manifest, CI Pages workflow, and the flasher's BOARDS object. Keep it out of `DEFAULT_BOARD_IDS`; `?beta=1` reveals it and selects the dev channel. Publish app and merged full images, with the full image flashed at `0x0000`.

## Documentation

README and Wiki must:

1. Explain that `Clone T5577` physically writes EM410x or HID Prox credentials, is distinct from `Clone to Slot`, requires source removal/target placement, and performs bounded read-back verification.
2. Fully document the universal Clock modes, source priority, trust states, UTC semantics, Maidenhead display, offline FT4/FT8 use case, and a conservative accuracy/holdover grid.
3. State that PCF85063A is an external-crystal RTC; holdover depends on crystal tolerance, temperature, layout, aging, and calibration. The current 50-ppm allowance equals approximately 4.32 seconds/day and remains uncharacterized.
4. Explain that UART RMC without PPS is suitable as a practical FT4/FT8 aid when the displayed state is trusted, but is not a Stratum-1/PPS promise and not a guaranteed sub-50-ms source.
5. Credit the Pancake beta build inspiration to D3h420, Janek, and OyczE.

## Verification

- RED source contracts before board implementation.
- Focused Pancake and documentation tests.
- Full repository test suite.
- Clean builds/packages for all five release-cycle boards.
- Validate package versions, image metadata, manifests, and artifact hashes.
- Commit/push CYM and Wiki separately; verify both remote SHAs.
- Verify immutable raw artifacts and the live beta flasher.
