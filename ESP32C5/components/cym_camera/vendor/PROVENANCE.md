Register program and types from waveshareteam/ESP32-C5-Touch-LCD-3.5 commit
04e6134cf3e37309b2bec9915189efeace1161bc, example/ESP-IDF-V554/01_factory/
components/espressif__esp_cam_sensor/sensors/bf3901/. Apache-2.0, notices retained.
Only BF3901 2-bit RGB565 240x320 register program is imported. No vendor UI,
SPI-slave controller, camera/video stack, button, or shared-bus deletion.
Native PARLIO backend uses the IDF 6.0.2 private fake-EOF API for >64 KiB frames.
A link-level TX admission guard reserves exclusivity while the camera is open.
