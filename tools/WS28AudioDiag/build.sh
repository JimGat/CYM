#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
: "${IDF_PATH:?Source /home/dev/esp/esp-idf/export.sh first}"
idf.py -B build -DIDF_TARGET=esp32c5 -DSDKCONFIG_DEFAULTS=sdkconfig.defaults build
# Use the actual generated esptool arguments, including real offsets/settings.
(cd build; python -m esptool --chip esp32c5 merge-bin -o ../WS28AudioDiag-full.bin @flash_args)
sha256sum WS28AudioDiag-full.bin
stat --format='size=%s bytes' WS28AudioDiag-full.bin
