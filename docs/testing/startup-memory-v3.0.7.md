# v3.0.7: startup memory allocation — Stable promotion

## Scope

Both supported Waveshare C5 profiles use explicit SPIRAM|8BIT allocation for
4096 bytes of copied PCM queue payload and an internal static queue control
block. There is no internal-RAM fallback. Queue depth (eight blocks), audio
worker stack (4096 bytes), priority (3), I2S/codec/amp configuration, actual DMA
buffers, display ownership, SD 20 MHz, GPS and console routing are unchanged.
Only task-context copies touch queue payload; no ISR or direct DMA borrows it.
The worker must acknowledge and suspend before deletion, queue deletion and
payload release. A timeout retains all ownership. Static queue deletion alone
does not free caller-owned storage. PSRAM exhaustion fails checked startup.

## Operator procedure

Use the primary USB-C at 115200 baud. Prefer application-only flashing at
`0x10000` with erase-all disabled, after verifying matching installed partition
layout. A merged full image at `0x0000` can overwrite NVS/PHY/settings, including
padding. Do not erase NVS, format SD, replace validated files or change wiring.

1. Confirm `App version: v3.0.7` and the correct board-HAL identity.
2. Enter `debug on`; expect `Debug ON persisted; applied immediately`.
3. Enter `debug status`; expect `Debug ON`.
4. Capture the same established startup sequence through intentional reboot,
   startup, sustained running or failure, and clean exit to normal CYM.
5. Keep all `STARTUP_MEMORY`, `WAD_SEEK_FAILED`, `WAD_READ_SHORT`, SD errors,
   frame/audio counters and cleanup messages. The read and seek diagnostics
   share a four-failure-per-session limit and log after transport unlock.
6. Compare `PCM_QUEUE_BEFORE/AFTER` and `AUDIO_TASK_AFTER` DMA free/largest with
   v3.0.6. Queue allocation should no longer consume copied payload from DMA RAM;
   do not assume a specific recovered margin before measurement.
7. Success requires continued SD reads, advancing frames, personally confirmed
   audible output, repeated clean exit/relaunch and usable normal UI. Test WS35
   first and then WS28 using the same release and workload.
8. Enter `debug off` afterward. Debug off performs no diagnostic heap sampling.

Jim confirmed that the WS-C5-35 startup repair worked with audible sound on
hardware. Repeated exit/relaunch, extended soak, post-fix DMA-margin capture and
the matching WS-C5-28 workflow remain separately unqualified. Host/build checks
do not supply those measurements. Owner-approved promotion refreshes the existing
v3.0.0 release and Stable to these exact v3.0.7 packages; bootloader, partition
layout and SD contents are not changed by this documentation/promotion step.
