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
#   cd ESP32S3
#   idf.py -B build_hosyond-s3-35 \
#     -DSDKCONFIG=build_hosyond-s3-35/sdkconfig \
#     "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.hosyond-s3-35" \
#     build
# ─────────────────────────────────────────────────────────────────────────────

set(PROJECT_VER "v2.13.79")

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/components")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# Suppress warnings-as-errors globally (pre-existing warnings in vendor drivers)
idf_build_set_property(COMPILE_OPTIONS "-Wno-error" APPEND)

project(CYM-S3)

# ===== POST-BUILD: board-specific export directory and binary name =====
# Each board gets its own output directory so binaries never overwrite each other.
if(CONFIG_BOARD_HOSYOND_S3_28)
    set(EXPORT_DIR "${CMAKE_SOURCE_DIR}/binaries-hosyond-s3-28")
    set(OUTPUT_BIN_NAME "CYM-hosyond-s3-28")
    set(FLASH_SIZE "16MB")
elseif(CONFIG_BOARD_HOSYOND_S3_40)
    set(EXPORT_DIR "${CMAKE_SOURCE_DIR}/binaries-hosyond-s3-40")
    set(OUTPUT_BIN_NAME "CYM-hosyond-s3-40")
    set(FLASH_SIZE "16MB")
else()
    # Default: Hosyond 3.5" ES3C35P
    set(EXPORT_DIR "${CMAKE_SOURCE_DIR}/binaries-hosyond-s3-35")
    set(OUTPUT_BIN_NAME "CYM-hosyond-s3-35")
    set(FLASH_SIZE "16MB")
endif()
file(MAKE_DIRECTORY "${EXPORT_DIR}")

add_custom_command(
    TARGET "gen_${CMAKE_PROJECT_NAME}_binary" POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy
            "${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin"
            "${EXPORT_DIR}/${OUTPUT_BIN_NAME}.bin"
    COMMAND ${CMAKE_COMMAND} -E copy
            "${CMAKE_BINARY_DIR}/bootloader/bootloader.bin"
            "${EXPORT_DIR}/bootloader.bin"
    COMMAND ${CMAKE_COMMAND} -E copy
            "${CMAKE_BINARY_DIR}/partition_table/partition-table.bin"
            "${EXPORT_DIR}/partition-table.bin"
    # Merged flat image — flash at 0x0000 with any single-binary flasher.
    COMMAND python -m esptool --chip esp32s3 merge_bin
            -o "${EXPORT_DIR}/${OUTPUT_BIN_NAME}-full.bin"
            --flash_mode dio --flash_freq 80m --flash_size ${FLASH_SIZE}
            0x0000  "${CMAKE_BINARY_DIR}/bootloader/bootloader.bin"
            0x8000  "${CMAKE_BINARY_DIR}/partition_table/partition-table.bin"
            0x10000 "${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin"
    COMMENT "Copying firmware and generating merged full image in ${EXPORT_DIR}"
)

# ===== POST-BUILD: memory budget doc =====
find_package(Python3 QUIET COMPONENTS Interpreter)
if(Python3_FOUND)
    add_custom_command(
        TARGET "gen_${CMAKE_PROJECT_NAME}_binary" POST_BUILD
        COMMAND ${Python3_EXECUTABLE}
                "${CMAKE_SOURCE_DIR}/tools/update_memory_map.py"
                "${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.map"
                "${CMAKE_SOURCE_DIR}/docs"
                "${PROJECT_VER}"
                "${EXPORT_DIR}/${OUTPUT_BIN_NAME}.bin"
                "memory-budget-${OUTPUT_BIN_NAME}.md"
        COMMENT "Updating docs/memory-budget-${OUTPUT_BIN_NAME}.md from linker map"
        VERBATIM
    )
else()
    message(STATUS "[memory_map] Python3 not found — skipping memory-budget update")
endif()
