# v3.0.17 Dev: console stream correction

The USB debug worker now binds the same task-local input/output streams as the
installed ESP-IDF line editor. Explicit debug command replies use that stream;
other tasks and global log routes are not redirected. Primary-versus-secondary
USB VFS selection and console Kconfig are unchanged.

Idle, zero-length and interrupted reads yield without restarting the line reader
or flooding prompts. A detected disconnect or hard read error discards a partial
command; reconnect starts a fresh line. This retains the IDF line editor and
command parser, not a second UART parser. The adapter matches installed IDF 6.0.2
Picolibc TLS symbols without SDK edits or private-header include paths, with pure
Picolibc and Newlib branches retained.

Host verification: production worker/settings plus unchanged installed linenoise,
32 stream scenarios across primary/secondary USB and Picolibc compatibility/pure
modes, 34 startup/route/failure-unwind cases, ASan/UBSan; Newlib task-reentrancy
adapter model. Full existing suite: 660 tests, one unavailable external-fixture
skip, plus nine targeted harnesses. Optional diagnostics gating is unchanged:
essential startup/errors and explicit command replies remain visible.

All eight boards require independent v3.0.17 build/package verification before
publication. Host checks and build success are not physical acceptance.

After parent review and authorized installation, use the physical USB console:
wait idle (no repeated prompts), enter `debug status` (Debug OFF or ON), `debug on`
(Debug ON persisted; applied immediately), `debug status` (Debug ON), `debug off`
(Debug OFF persisted; applied immediately), then `debug status` (Debug OFF).
Try CR, LF and backspace editing; empty Enter must not report input failure.
Disconnect mid-command, reconnect and send a fresh complete `debug status` line;
no stale partial command may execute. Confirm the Hardware debug switch follows
commands and the selected state survives an authorized reboot. With debug off,
optional high-volume reports stop but essential startup/errors remain.

Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28) and Waveshare
ESP32-C5-Touch-LCD-3.5 (WS-C5-35) retain their existing hardware qualification
limits. No new physical validation is claimed here.
