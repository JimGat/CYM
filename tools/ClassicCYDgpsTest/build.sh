#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
: "${IDF_PATH:?Source ESP-IDF export.sh before running this script}"
rm -rf build sdkconfig
idf.py -B build -D SDKCONFIG_DEFAULTS=sdkconfig.defaults set-target esp32
idf.py -B build -D SDKCONFIG_DEFAULTS=sdkconfig.defaults build
python -m esptool --chip esp32 merge-bin \
  -o ClassicCYDgpsTest-full.bin \
  --flash-mode dio --flash-freq 40m --flash-size 4MB \
  0x1000 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0x10000 build/ClassicCYDgpsTest.bin
sha256sum ClassicCYDgpsTest-full.bin
stat --format='size=%s bytes' ClassicCYDgpsTest-full.bin
