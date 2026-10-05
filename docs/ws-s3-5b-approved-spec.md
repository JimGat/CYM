# Approved WS-S3-5B beta spec and implementation plan
Sole writer, authoritative Jimgat_Dev worktree; canonical CYM app, no fork.
1024x600 RGB565, 16MB flash, 8MB OPI PSRAM, GT911, CH422G, PCF85063.
No verified GPS UART, RF-HAT, C5-only radios. GPIO0 belongs to RGB.
RTC retention requires a coin cell; restore only valid, previously disciplined UTC.

1. RED executable viewport/pixel tests + integration contracts.
2. Add profile/build/package adapter, shared main-owned I2C bus borrowed by RTC/touch/expander. CH422G function-address writes and locked masked output shadow. Dedicated SD SPI with expander CS wrapped around host commands; CS high through idle-clock preamble.
3. Reusable integer logical viewport: 512x300 at scale 2 fills 1024x600. Scale canonical rendered scene, not LVGL internals/source coordinates. Fonts/images/buttons/popups/lists scale together: 12/16/28 become 24/32/56 physical pixels. Inverse touch shares same geometry. Both menu layouts reflow at logical landscape resolution. Small panels unchanged. Future P4 can reuse geometry, NOT P4 hardware support. Pixel replication, not native high-DPI font rasterization.
4. Two PSRAM RGB framebuffers, internal 10-line bounce buffers, full logical PSRAM draw buffers. Only render into retired framebuffer; persistent internal ISR context registered before panel init. Two frame-complete boundaries after submission, bounded wait, fail-closed buffer ownership on timeout. No SPI completion callback. Native RGB565, no SPI byte swap.
5. Reuse full timekeeper and universal Clock Client/AP paths. OS/unset/trust/epoch/rollback gates on startup. Existing NTP cadence/cancellation and UTC/display offsets unchanged.
6. GREEN tests, patch bump before sequential changed-binary build cycle, all 7 current consumers plus new beta. Stop at ~3 fix cycles. Verify manifests/descriptors/maps/partitions/merged bytes/hashes.
7. Explicit stage/commit/push after all four release boards green. Capture stable bytes, dispatch isolated beta, verify pinned assets and live beta browser. No hardware claims; Jim tests physical board.
