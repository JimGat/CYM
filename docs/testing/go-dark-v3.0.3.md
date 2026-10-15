# v3.0.3 Development: Go Dark touch recovery

Scope: add WS-C5-35 FT6336 polling to the existing dark-state five-second
hold path; gate dialog BOOT wording on `BOOT_BTN_GPIO >= 0`; consume the
wake finger until release. No GPS mapping, console, touch-controller setup,
partition, task allocation or navigation changes. Stable and the v3.0.0
release are not updated by this Development cycle.

## Source/host evidence

`tests/test_go_dark_wake.py` compiles the actual production polling,
confirmation-label statements and input-release guard. RED reproduced missing
WS-C5-35 wake and invalid BOOT copy; GREEN covers continuous hold threshold,
release/read-failure reset, repeated touch-wake sessions, wake-finger suppression,
five other touch backend selections, BOOT-present/absent wording, GPS ownership
and shared confirmation routes. Host checks are not physical FT6336/I2C proof.

## Owner operator acceptance

1. Select WS-C5-35 and Development v3.0.3 in the web flasher. Retain existing
   settings: do not erase NVS or format SD. Use the primary USB console only.
2. Confirm normal touch and GPS reception/LOCK with the existing setup.
   UART1 RX remains GPIO28, TX disabled. Do not press physical BOOT to wake.
3. From both Classic and Modern home layouts, open Go Dark via the power icon
   or existing menu route. Expected: confirmation offers `Hold screen 5 seconds`
   and contains no BOOT wake instruction.
4. Confirm Go Dark. Hold anywhere for less than five seconds and release.
   Expected: stays dark. Hold again for five continuous seconds.
   Expected: screen returns at the saved brightness; releasing the finger is
   required before normal controls act. No control beneath it should activate.
5. Repeat enter/hold/wake/release at least three times; also verify GPS continues
   and an active capture/wardrive is not stopped by the wake operation.
6. On other touch boards, verify the same five-second hold and release behavior.
   BOOT instructions must remain only on profiles with application BOOT input;
   WS-S3-5B remains touch-only. Their independent physical results are not implied
   by the WS-C5-35 correction or host/build success.

Physical acceptance of this correction is pending Jim's test.
