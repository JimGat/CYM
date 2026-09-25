# Hosyond/LCDWiki ESP32-S3 3.5-inch source documents

Board family: ES3C35P / existing CYM `hosyond-s3-35` bring-up target.

Current official source: https://www.lcdwiki.com/3.5inch_ESP32-S3_Display

The checked-in specification, schematic, IO workbook, ST77922/TDDI protocol documents, and audio/touch datasheets came from the earlier hardware package used for the existing CYM bring-up.

Important revision warning: the current LCDWiki ES3C35P page publishes a materially different GPIO map from the checked-in package and current `hosyond_s3_35.h`. Do not replace the existing map from the web table by assumption. Identify the exact PCB revision/SKU, compare the schematic/vendor demo, and probe the physical board before changing display, touch, SD, backlight, battery, RGB, or audio pins.

The current image remains a bring-up stub; this documentation does not mean full CYM support is complete.
