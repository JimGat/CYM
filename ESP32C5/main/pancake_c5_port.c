#include "sdkconfig.h"
#if defined(CONFIG_BOARD_PANCAKE_C5)
#include "pancake_c5_port.h"
#include "pancake_ft6336.h"
#include "board_hal.h"
#include "driver/spi_master.h"
#include "esp_lcd_ili9341.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "esp_log.h"
#include "esp_check.h"

static const char *TAG = "pancake_c5";
static ft6336_handle_t s_touch;
static i2c_master_bus_handle_t s_touch_bus;
static i2c_master_dev_handle_t s_touch_dev;
#if BOARD_TOUCH_I2C_ADDR != FT6336_I2C_ADDR
#error "Pancake board profile and FT6336 driver disagree on I2C address"
#endif

esp_err_t pancake_c5_display_init(esp_lcd_panel_handle_t *panel,
                                  esp_lcd_panel_io_handle_t *io)
{
    if (!panel || !io) return ESP_ERR_INVALID_ARG;
    spi_bus_config_t bus = {
        .mosi_io_num = BOARD_SPI_MOSI,
        .miso_io_num = BOARD_SPI_MISO,
        .sclk_io_num = BOARD_SPI_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = BOARD_LCD_WIDTH * 15 * sizeof(uint16_t),
    };
    esp_err_t err = spi_bus_initialize(BOARD_SPI_HOST, &bus, SPI_DMA_CH_AUTO);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) return err;

    esp_lcd_panel_io_spi_config_t io_cfg = {
        .dc_gpio_num = BOARD_LCD_DC,
        .cs_gpio_num = BOARD_LCD_CS,
        .pclk_hz = 40000000,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
        .spi_mode = 0,
        .trans_queue_depth = 10,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_spi(BOARD_SPI_HOST, &io_cfg, io), TAG, "panel I/O");
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = BOARD_LCD_RST,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_BGR,
        .bits_per_pixel = 16,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_ili9341(*io, &panel_cfg, panel), TAG, "panel create");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(*panel), TAG, "panel reset");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(*panel), TAG, "panel init");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_invert_color(*panel, true), TAG, "panel invert");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_mirror(*panel, true, true), TAG, "panel mirror");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_swap_xy(*panel, true), TAG, "panel swap");
    ESP_LOGI(TAG, "Pancake display ready: 480x320 at 40 MHz");
    return ESP_OK;
}

esp_err_t pancake_c5_touch_init(void)
{
    if (!s_touch_bus) {
        i2c_master_bus_config_t bus_cfg = {
            .i2c_port = BOARD_I2C_NUM,
            .sda_io_num = BOARD_I2C_SDA,
            .scl_io_num = BOARD_I2C_SCL,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .flags.enable_internal_pullup = true,
        };
        ESP_RETURN_ON_ERROR(i2c_new_master_bus(&bus_cfg, &s_touch_bus), TAG,
                            "I2C bus");
    }
    if (!s_touch_dev) {
        i2c_device_config_t dev_cfg = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = BOARD_TOUCH_I2C_ADDR,
            .scl_speed_hz = 400000,
        };
        ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(s_touch_bus, &dev_cfg,
                                                      &s_touch_dev), TAG,
                            "FT6336 device");
    }
    return ft6336_init(&s_touch, s_touch_dev, BOARD_TOUCH_INT, BOARD_TOUCH_RST,
                       BOARD_LCD_WIDTH, BOARD_LCD_HEIGHT);
}

bool pancake_c5_touch_read(uint16_t *x, uint16_t *y, bool *touched)
{
    if (!x || !y || !touched) return false;
    ft6336_touch_point_t point = {0};
    bool ok = ft6336_read_touch(&s_touch, &point);
    *touched = ok && point.touched;
    if (*touched) {
        *x = point.x;
        *y = point.y;
    }
    return ok;
}
#else
#include "pancake_c5_port.h"
esp_err_t pancake_c5_display_init(esp_lcd_panel_handle_t *panel, esp_lcd_panel_io_handle_t *io) { (void)panel; (void)io; return ESP_ERR_NOT_SUPPORTED; }
esp_err_t pancake_c5_touch_init(void) { return ESP_ERR_NOT_SUPPORTED; }
bool pancake_c5_touch_read(uint16_t *x, uint16_t *y, bool *touched) { (void)x; (void)y; if (touched) *touched=false; return false; }
#endif
