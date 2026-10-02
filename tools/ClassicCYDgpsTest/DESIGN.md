# ClassicCYDgpsTest design

A standalone ESP-IDF diagnostic image scans UART2 receive-only on GPIO1, GPIO3,
and GPIO26 at 9600, 38400, and 115200 baud. It owns no transmit pin and disables
all boot/application console output. The ILI9341 screen reports byte counts, UART
errors, NMEA markers/checksums, and raw sample bytes. A valid checksum locks the
display on the detected pin and baud. The utility is packaged as a merged 4 MB
ESP32 image for flashing at offset 0x0000. Production CYM sources are unchanged.
