# CYM v3.0.16-zx4: WS-C5-35 isolated popup test

Application-only: flash CYM-WS-C5-35-v3.0.16-zx4-app.bin at 0x10000, ERASE ALL OFF, primary USB-C.
Only WS-C5-35 with the existing matching factory partition layout. Not other boards.
No NVS, bootloader or partition table image is included.

Change from v3.0.15-zx3: explicitly apply CYM text color/font to the opaque QR card and both result labels, and show the full /sdcard/lab/QR/filename path after successful saving. Decode, camera, SD, Observer and navigation logic unchanged. Shared QR page serves both Classic and Modern layouts on this board.

Verification: targeted production-C popup regression reproduced the missing text-style override before repair and passed afterward, covering result text, full saved path and save-error presentation. Existing modal lifecycle (Scan Again/Stop/reentry) and Observer tests passed. Guarded WS35 -j1 build and partition-size check passed. Per-board memory map regenerated. No physical visual acceptance yet; test both UI layouts, light/dark theme and rotations. Broad historical regression remains unresolved; this is not a canonical all-board release. Dev/Stable unchanged.

Size: 4131280 bytes
SHA-256: dd81f846ac56c0dc94e9ff6c1c766d50ce0ceca30da7069f691bb1918e8300d1

Test: scan, read payload and full saved path, Scan Again, Back/Home; repeat after Observer. Long payloads scroll inside the card. Failed saves must say Not saved and retain decoded text.
