#pragma once
// C5Lab Pancake DIY — ESP32-C5-WIFI6-KIT carrier with 3.5-inch capacitive display.
// Hardware source: https://github.com/C5Lab/pancake
// Pinned reference commit: 02528ded8feb242a8400e575b14e489ada1f960b
// This beta profile follows the reference source pin map and transforms exactly.

#define BOARD_SPI_HOST             SPI2_HOST
#define BOARD_SPI_MOSI             24
#define BOARD_SPI_MISO              4
#define BOARD_SPI_SCK              23

#define BOARD_LCD_HOST             BOARD_SPI_HOST
#define BOARD_LCD_CS                5
#define BOARD_LCD_DC                3
#define BOARD_LCD_RST               2
#define BOARD_BACKLIGHT_GPIO       26
#define BOARD_LCD_WIDTH           480
#define BOARD_LCD_HEIGHT          320
#define BOARD_LCD_PCLK_HZ          40000000

#define BOARD_TOUCH_CS             -1
#define BOARD_TOUCH_I2C_ADDR       0x38
#define BOARD_TOUCH_INT            25
#define BOARD_TOUCH_RST             8
#define BOARD_I2C_SDA               9
#define BOARD_I2C_SCL              10
#define BOARD_I2C_NUM               I2C_NUM_0

#define BOARD_SD_SPI_HOST          BOARD_SPI_HOST
#define BOARD_SD_SCK               BOARD_SPI_SCK
#define BOARD_SD_MOSI              BOARD_SPI_MOSI
#define BOARD_SD_MISO              BOARD_SPI_MISO
#define BOARD_SD_CS                 7
#define BOARD_SD_SPI_FREQ_HZ       20000000

#define BOARD_GPS_UART_NUM         UART_NUM_1
#define BOARD_GPS_TX               13
#define BOARD_GPS_RX               14
#define BOARD_GPS_TX_GPIO          BOARD_GPS_TX
#define BOARD_GPS_RX_GPIO          BOARD_GPS_RX

#define BOARD_RGB_LED_GPIO         27
#define BOARD_RGB_LED_COUNT         1
#define BOARD_RGB_PIN              BOARD_RGB_LED_GPIO
#define BOARD_BATTERY_ADC_GPIO      6
#define BOARD_BATTERY_DIVIDER_NUM  16
#define BOARD_BATTERY_DIVIDER_DEN   5
#define BOARD_BOOT_BTN_GPIO        28
#define BOARD_VIBRATOR_GPIO        -1
#define BOARD_RFHAT_PIN_A          -1
#define BOARD_RFHAT_PIN_B          -1

#define BOARD_HAS_PSRAM             1
#define BOARD_HAS_SD                1
#define BOARD_HAS_RGB_LED           1
#define BOARD_HAS_BATTERY_ADC       1
#define BOARD_HAS_GPS               1
#define BOARD_HAS_5GHZ              1
#define BOARD_HAS_IEEE802154        1
#define BOARD_HAS_AUDIO             0
#define BOARD_HAS_VIBRATOR          0
#define BOARD_HAS_RF_HAT            0

// Conservative and explicitly uncharacterized UART-RMC timing profile.
#define BOARD_TIME_HAS_RTC                    0
#define BOARD_TIME_HAS_GPS_UART               1
#define BOARD_TIME_RTC_DRIFT_PPM              0
#define BOARD_TIME_RTOS_DRIFT_PPM             100
#define BOARD_TIME_GPS_UNCERTAINTY_US         500000
#define BOARD_TIME_NTP_UNCERTAINTY_US         250000
#define BOARD_TIME_GPS_RTC_UNCERTAINTY_US     2000000
#define BOARD_TIME_GPS_RTC_DRIFT_PPM           100
#define BOARD_TIME_HAS_MDNS                   1
#define BOARD_TIME_ESTIMATE_CHARACTERIZED     0

#define BOARD_NAME           "Pancake-C5"
#define BOARD_DISPLAY_DRIVER "ILI9341-compatible"
#define BOARD_TOUCH_DRIVER   "FT6336U"
