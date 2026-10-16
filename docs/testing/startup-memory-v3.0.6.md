# v3.0.6 startup-memory diagnostic operator checks

Instrumentation only; no gameplay, sound or performance acceptance claimed.
Use primary USB-C at 115200 baud; leave all other UARTs and GPS routing unchanged.
Use a backed-up existing card; do not format, provision or replace assets for this test.

Prefer the matching-layout application at 0x10000, erase-all disabled. Full merged
images at 0x0000 can overwrite NVS/PHY settings even where they contain padding.
Enable diagnostics again after flashing if necessary:

    debug on
    debug status

Expect `Debug ON persisted; applied immediately` and `Debug ON`.
Record the complete launch, intentional reboot, validation, initialization and
failure/cleanup or running result. Preserve `STARTUP_MEMORY` phases
`ENGINE_INIT_ENTRY`, `I2S_CHANNEL_BEFORE/AFTER`, `I2S_STD_BEFORE/AFTER`,
`PCM_QUEUE_BEFORE/AFTER`, `AUDIO_TASK_BEFORE/AFTER`, and `WAD_READ_SHORT`
plus `WAD_READ_MEMORY` if present. Memory and stack fields are bytes; audio
stack zero means not sampled because no successful task handle was supplied.
I2S result uses ESP_OK=0; queue result is 1=created/0=failed; task result
is pdPASS=1 on the installed port. BEFORE result=0 is only a placeholder.
Short-read errno is the value immediately after fread; if ferror is zero,
errno can be stale and is not independently an error diagnosis.
At most four short reads per session are reported. Successful reads are quiet.

Collect WS-C5-35 first. If practical collect WS-C5-28 at the same version and
with the same approved asset content as a working comparison. Successful
launch is separate from audible sound and repeated-run acceptance. Preserve
normal UI/GPS qualification separately. No host result proves device DMA headroom.

    debug off

Expect `Debug OFF persisted; applied immediately`. New checkpoint messages and
heap sampling must be quiet with debug off. Timing can differ with debug enabled.
