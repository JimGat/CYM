cmake_minimum_required(VERSION 3.16)

# ── CYM ESP32-S3 Build ────────────────────────────────────────────────────────
#
# Targets:
#   hosyond-s3-35  — Hosyond 3.5" ES3C35P, ST77922 QSPI, 320x480
#   hosyond-s3-28  — Hosyond 2.8" (pending GPIO confirmation)
#   hosyond-s3-40  — Hosyond 4.0" (not yet owned)
#
# Build from repo root:  make hosyond-s3-35
# Or directly:
#   idf.py -B build_hosyond-s3-35 \
#     -DSDKCONFIG=build_hosyond-s3-35/sdkconfig \
#     "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.hosyond-s3-35" \
#     build
# ─────────────────────────────────────────────────────────────────────────────

set(PROJECT_VER "v2.13.78-s3-preview")

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/components")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(CYM-S3)
