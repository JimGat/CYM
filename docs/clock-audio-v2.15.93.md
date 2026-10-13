# v2.15.93 targeted Clock and audio check

Game audio uses a single -15 dB setting for the existing supported Waveshare ES8311 paths, shared with AUDIO_STARTED logging. This is an authorized audibility experiment, not a demonstrated silence fix. PA/codec readiness gates, 22050 Hz 16-bit mono TX-only I2S without MCLK, copied-buffer audio ownership and native gameplay remain unchanged.

The Clock callback compares current label contents before setting text. Unchanged strings no longer trigger LVGL text invalidation/reallocation; changing seconds and other real values still update on the existing one-second timer. No global text caches, menu changes, radio lifecycle changes or display/DMA bypasses were introduced.

## Operator checks

On WS-C5-35, launch gameplay and capture AUDIO_PA, CODEC_DIAG, I2S_DIAG and AUDIO_STARTED. Expect verified PA OFF/ON with mode_shadow=0023 and volume_db=-15 after unchanged codec/readback checks. Trigger actual sound effects and report audible/inaudible; successful I2S writes do not prove sound. Exit must return through the existing orderly same-image restart. Qualify WS-C5-28 separately.

In both Classic and Modern menus, open Clock, observe live seconds, close/reopen and check saved orientation. Compare visible completed painting and UI_DIAG/UI_WORK timing against .92. Exercise service/status transitions and retry/exit where applicable. Host tests establish content-sensitive setters and unchanged cadence/lifecycle, not physical responsiveness or universal sub-second latency. Startup loading-screen admission timeouts and normal Home radio-reset latency remain separate, unmodified issues.

Software checks: all eight board profiles packaged at v2.15.93; parent regression suite 458 tests passed in 72.427 seconds. All sixteen board bootloader/partition artifacts are unchanged from .92. Hardware audio and latency acceptance remain pending.
