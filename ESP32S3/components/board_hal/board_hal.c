#include "board_hal.h"
#include "esp_log.h"

static const char *TAG = "board_hal";

void board_hal_log_info(void)
{
    ESP_LOGI(TAG, "Board: %s  Display: %s  Touch: %s",
             BOARD_NAME, BOARD_DISPLAY_DRIVER, BOARD_TOUCH_DRIVER);
}
