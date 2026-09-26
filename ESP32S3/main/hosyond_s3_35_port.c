#include "hosyond_s3_35_port.h"

#include <stddef.h>

#include "board_hal.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_st77922.h"
#include "esp_log.h"
#include "hosyond_s3_35_lcd_init.h"

static const char *TAG = "es3c35p_port";
static esp_lcd_touch_handle_t s_touch;

static bool IRAM_ATTR on_color_trans_done(esp_lcd_panel_io_handle_t io,
                                           esp_lcd_panel_io_event_data_t *edata,
                                           void *user_ctx)
{
    (void)io;
    (void)edata;
    hosyond_s3_35_display_t *display = user_ctx;
    BaseType_t higher_priority_task_woken = pdFALSE;
    xSemaphoreGiveFromISR(display->flush_done, &higher_priority_task_woken);
    return higher_priority_task_woken == pdTRUE;
}

esp_err_t hosyond_s3_35_display_init(hosyond_s3_35_display_t *display)
{
    if (display == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    display->panel = NULL;
    display->flush_done = xSemaphoreCreateBinary();
    if (display->flush_done == NULL) {
        return ESP_ERR_NO_MEM;
    }

    spi_bus_config_t bus_config = ST77922_PANEL_BUS_QSPI_CONFIG(
        BOARD_LCD_SCK, BOARD_LCD_D0, BOARD_LCD_D1, BOARD_LCD_D2, BOARD_LCD_D3,
        BOARD_LCD_BUF_SIZE);
    esp_err_t err = spi_bus_initialize(BOARD_LCD_HOST, &bus_config, SPI_DMA_CH_AUTO);
    if (err != ESP_OK) {
        return err;
    }

    esp_lcd_panel_io_spi_config_t io_config = ST77922_PANEL_IO_QSPI_CONFIG(
        BOARD_LCD_CS, on_color_trans_done, display);
    io_config.pclk_hz = 40000000;
    esp_lcd_panel_io_handle_t io = NULL;
    err = esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)BOARD_LCD_HOST,
                                   &io_config, &io);
    if (err != ESP_OK) {
        return err;
    }

    st77922_vendor_config_t vendor_config = {
        .init_cmds = hosyond_s3_35_lcd_init,
        .init_cmds_size = HOSYOND_S3_35_LCD_INIT_SIZE,
        .flags = { .use_qspi_interface = 1 },
    };
    esp_lcd_panel_dev_config_t panel_config = {
        .reset_gpio_num = BOARD_LCD_RST,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
        .data_endian = LCD_RGB_DATA_ENDIAN_BIG,
        .bits_per_pixel = 16,
        .vendor_config = &vendor_config,
    };
    err = esp_lcd_new_panel_st77922(io, &panel_config, &display->panel);
    if (err != ESP_OK) {
        return err;
    }
    if ((err = esp_lcd_panel_reset(display->panel)) != ESP_OK ||
        (err = esp_lcd_panel_init(display->panel)) != ESP_OK ||
        (err = esp_lcd_panel_mirror(display->panel,
                                    BOARD_LCD_MIRROR_X,
                                    BOARD_LCD_MIRROR_Y)) != ESP_OK ||
        (err = esp_lcd_panel_invert_color(display->panel,
                                          BOARD_LCD_INVERT_COLORS)) != ESP_OK ||
        (err = esp_lcd_panel_disp_on_off(display->panel, true)) != ESP_OK) {
        return err;
    }

    gpio_config_t backlight_config = {
        .pin_bit_mask = 1ULL << BOARD_BACKLIGHT_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    if ((err = gpio_config(&backlight_config)) != ESP_OK) {
        return err;
    }
    gpio_set_level(BOARD_BACKLIGHT_GPIO, 1);
    ESP_LOGI(TAG, "ST77922 QSPI display ready at 40000000 Hz");
    return ESP_OK;
}

esp_err_t hosyond_s3_35_draw(hosyond_s3_35_display_t *display,
                             int x_start, int y_start,
                             int x_end, int y_end,
                             const void *pixels)
{
    if (display == NULL || display->panel == NULL ||
        display->flush_done == NULL || pixels == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(display->flush_done, 0);
    esp_err_t err = esp_lcd_panel_draw_bitmap(display->panel,
                                               x_start, y_start,
                                               x_end, y_end, pixels);
    if (err != ESP_OK) {
        return err;
    }
    if (xSemaphoreTake(display->flush_done, pdMS_TO_TICKS(1000)) != pdTRUE) {
        ESP_LOGE(TAG, "ST77922 QSPI transfer timed out");
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

void hosyond_s3_35_round_area(lv_area_t *area)
{
    if (area == NULL) {
        return;
    }
    area->x1 = (area->x1 / BOARD_LCD_DRAW_ROUNDING) * BOARD_LCD_DRAW_ROUNDING;
    area->x2 = ((area->x2 / BOARD_LCD_DRAW_ROUNDING) * BOARD_LCD_DRAW_ROUNDING)
             + (BOARD_LCD_DRAW_ROUNDING - 1);
    if (area->x2 >= BOARD_LCD_WIDTH) {
        area->x2 = BOARD_LCD_WIDTH - 1;
    }
}

esp_err_t hosyond_s3_35_touch_init(void)
{
    i2c_master_bus_config_t bus_config = {
        .i2c_port = BOARD_I2C_NUM,
        .sda_io_num = BOARD_I2C_SDA,
        .scl_io_num = BOARD_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    i2c_master_bus_handle_t bus = NULL;
    esp_err_t err = i2c_new_master_bus(&bus_config, &bus);
    if (err != ESP_OK) {
        return err;
    }

    esp_lcd_panel_io_i2c_config_t io_config = ESP_LCD_TOUCH_IO_I2C_ST77922_CONFIG();
    io_config.dev_addr = BOARD_TOUCH_I2C_ADDR;
    io_config.scl_speed_hz = BOARD_TOUCH_I2C_HZ;
    esp_lcd_panel_io_handle_t io = NULL;
    err = esp_lcd_new_panel_io_i2c(bus, &io_config, &io);
    if (err != ESP_OK) {
        return err;
    }

    esp_lcd_touch_config_t touch_config = {
        .x_max = BOARD_LCD_WIDTH,
        .y_max = BOARD_LCD_HEIGHT,
        .rst_gpio_num = BOARD_TOUCH_RST,
        .int_gpio_num = BOARD_TOUCH_INT,
        .levels = { .reset = 0, .interrupt = 0 },
        .flags = { .swap_xy = 0, .mirror_x = 0, .mirror_y = 0 },
    };
    err = esp_lcd_touch_new_i2c_st77922(io, &touch_config, &s_touch);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "touch ready at I2C address 0x%02X", BOARD_TOUCH_I2C_ADDR);
    }
    return err;
}

bool hosyond_s3_35_touch_read(uint16_t *x, uint16_t *y, bool *pressed)
{
    if (x == NULL || y == NULL || pressed == NULL || s_touch == NULL) {
        return false;
    }
    *pressed = false;
    if (esp_lcd_touch_read_data(s_touch) != ESP_OK) {
        return false;
    }
    uint16_t strength = 0;
    uint8_t count = 0;
    bool touched = esp_lcd_touch_get_coordinates(s_touch, x, y, &strength, &count, 1);
    *pressed = touched && count > 0;
    return true;
}
