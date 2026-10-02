cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../../ESP32C5/components/espressif__esp_lcd_ili9341")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(ClassicCYDgpsTest)
