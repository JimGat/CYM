# WS-C5-35 battery/RTC candidate v2.15.73

Jim reports his delivered WS-C5-35 display/touch/keyboard work (320x480 native); UI density is left unchanged. CH32V006 remains distinct from WS28 CH32V003. QMI8658 IMU, BF3901 camera and ES8311 audio are present in vendor references but not enabled by this cycle.

## Source and scope

Vendor https://github.com/waveshareteam/ESP32-C5-Touch-LCD-3.5 revision 04e6134cf3e37309b2bec9915189efeace1161bc. ESP-IDF-V554/05_pcf85063 and 08_AXP2101 with bundled XPowersLib establish shared I2C SDA27/SCL26, PCF85063A 0x51, PMIC 0x34. AXP ID is 0x4A. VBAT is status0 bit3 presence + registers 0x34/35 H5:L8 millivolts. Only reg0x30 bit0 battery ADC enable may be written via checked read-modify-write, preserving all other bits. No rail, charge current/voltage, temperature or regulator changes.

RTC reuses CYM timekeeper/driver, oscillator-invalid/trust rules and bounded transactions. No demo hardcoded date is written. Battery uses PMIC voltage and the existing estimated percent curve; FULL is a voltage threshold, NOT charging completion or measured fuel-gauge capacity. BAT ERR means measurement/init failed; NO BAT means presence bit clear. ADC first-enable may briefly show BAT ERR until the next poll. Acquisition never holds LVGL mutex; task polling follows existing 10-second cadence. WS28 pins/ADC/calibration and code branches unchanged.

## Hardware check

Flash exact WS-C5-35 Dev candidate. Confirm touch/display unchanged. With battery attached, wait up to 15 seconds for badge, compare VBAT to meter; if BAT ERR capture boot/PMIC logs. USB-only should say NO BAT. Check clock RTC fitted/available versus untrusted or oscillator-invalid state: presence is not trustworthy time. Use Client NTP to obtain valid UTC, then test reboot and RTC holdover/backup. Keep Display Only network-silent. Check battery/clock UI in both navigation layouts and repeated start/exit. Do not infer peripheral qualification from builds/host mocks.

## Owner hardware result on v2.15.73

Jim confirms battery estimate displayed; RTC fitted and updated through NTP. After removing USB, using the board power button and restarting, Display Only showed correct time with RTC HOLDOVER. RTC synchronization and startup holdover are accepted on this sample. Battery-powered operation was observed for a few hours. Estimate dropped from about 90% with USB to 40% without USB; voltage-based percentage/charge-state accuracy remain unqualified. No scaling adjustment is justified without USB/battery voltage measurements. No hardware Doom result yet.
