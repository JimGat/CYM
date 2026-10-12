#include "sdkconfig.h"
#include <stdint.h>
#include <stdbool.h>
#if defined(CONFIG_BOARD_WS_C5_35)
// Waveshare ESP32-C5-Touch-LCD-3.5 board adapter.
// ST7796 display (320x480 SPI), FT6336 touch (I2C), CH32V006 IO expander (I2C).
// Uses the vendor BSP pin map and display settings from commit
// 04e6134cf3e37309b2bec9915189efeace1161bc as the initial experimental baseline.
#include "ws_c5_35_port.h"
#include "board_hal.h"
#include "driver/spi_master.h"
#include "driver/i2c_master.h"
#include "esp_lcd_st7796.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_touch_ft6336.h"
#include "esp_log.h"
#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "ws_c5_35";

// ── CH32V006 IO Expander — 16-bit little-endian I2C protocol ────────────────
// The WS-C5-35 uses a CH32V006 (not the WS-C5-28's CH32V003). The register
// protocol uses 16-bit little-endian values for mode, output, and input.
// This adapter drives it with raw I2C — not the WS-C5-28's CH32V003 expander API.
#define WS35_EXIO_REG_MODE   0x02   // 16-bit direction: 0=output, 1=input per pin
#define WS35_EXIO_REG_OUTPUT 0x03   // 16-bit output level: 0=low, 1=high per pin
#define WS35_EXIO_REG_PWM    0x05   // 8-bit PWM duty for backlight

static i2c_master_bus_handle_t s_i2c_bus;
static i2c_master_dev_handle_t s_exio_dev;
static i2c_master_dev_handle_t s_pmic_dev;
static bool s_battery_adc_ready;
static uint16_t mode_shadow; /* accepted direction write, not a physical read */
static uint16_t output_shadow;   // tracks the 16-bit output register state
static esp_lcd_touch_handle_t s_touch;

// Write a 16-bit value to a CH32V006 register in little-endian byte order.
static esp_err_t ws35_exio_write16(uint8_t reg, uint16_t val)
{
    uint8_t buf[3] = { reg, output_shadow & 0xff, output_shadow >> 8 };
    if (reg != WS35_EXIO_REG_OUTPUT) {
        buf[1] = val & 0xff;
        buf[2] = val >> 8;
    }
    esp_err_t err = i2c_master_transmit(s_exio_dev, buf, sizeof(buf), 100);
    if (err == ESP_OK && reg == WS35_EXIO_REG_MODE) mode_shadow = val;
    return err;
}

// Write the output shadow register to the CH32V006.
static esp_err_t ws35_exio_flush_output(void)
{
    uint8_t buf[3] = { WS35_EXIO_REG_OUTPUT, output_shadow & 0xff, output_shadow >> 8 };
    return i2c_master_transmit(s_exio_dev, buf, sizeof(buf), 100);
}

// Set a single EXIO pin high or low in the output shadow and flush.
static esp_err_t ws35_exio_set_pin(uint8_t pin, bool level)
{
    if (level)
        output_shadow |= (1u << pin);
    else
        output_shadow &= ~(1u << pin);
    return ws35_exio_flush_output();
}

// Write an 8-bit value to the CH32V006 PWM register.
static esp_err_t ws35_exio_set_pwm(uint8_t duty)
{
    uint8_t buf[2] = { WS35_EXIO_REG_PWM, duty };
    return i2c_master_transmit(s_exio_dev, buf, sizeof(buf), 100);
}

// ── I2C bus and IO expander init ────────────────────────────────────────────

static esp_err_t ws35_init_i2c(void)
{
    if (s_i2c_bus) return ESP_OK;  // already initialised

    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = BOARD_I2C_SDA,
        .scl_io_num = BOARD_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_RETURN_ON_ERROR(i2c_new_master_bus(&bus_cfg, &s_i2c_bus), TAG, "I2C bus");
    ESP_LOGI(TAG, "I2C bus OK (SDA=GPIO%d, SCL=GPIO%d)", BOARD_I2C_SDA, BOARD_I2C_SCL);

    // Add CH32V006 expander device
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = BOARD_IO_EXPANDER_I2C_ADDR,
        .scl_speed_hz = 400000,
    };
    ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(s_i2c_bus, &dev_cfg, &s_exio_dev),
                        TAG, "CH32V006 device");
    ESP_LOGI(TAG, "CH32V006 IO expander OK (I2C 0x%02X)", BOARD_IO_EXPANDER_I2C_ADDR);

    // Match the vendor BSP: EXIO0 (touch RST), EXIO1 (LCD RST), and
    // EXIO5 (board power/amp enable) are outputs; EXIO6 remains an input.
    // The CH32V006 example defines direction bits as 0=output, 1=input.
    uint16_t mode = 0xFFFF;
    mode &= ~(1u << BOARD_TOUCH_RESET_EXIO);
    mode &= ~(1u << BOARD_LCD_RESET_EXIO);
    mode &= ~(1u << BOARD_POWER_ENABLE_EXIO);
    ESP_RETURN_ON_ERROR(ws35_exio_write16(WS35_EXIO_REG_MODE, mode), TAG, "EXIO mode");

    // Vendor sequence is high -> low -> high for both reset lines, with EXIO5
    // held high. Keep a complete 16-bit shadow for every output write.
    output_shadow = (1u << BOARD_TOUCH_RESET_EXIO) |
                    (1u << BOARD_LCD_RESET_EXIO) |
                    (1u << BOARD_POWER_ENABLE_EXIO);
    ESP_RETURN_ON_ERROR(ws35_exio_flush_output(), TAG, "EXIO initial high");
    vTaskDelay(pdMS_TO_TICKS(50));
    ESP_RETURN_ON_ERROR(ws35_exio_set_pin(BOARD_TOUCH_RESET_EXIO, false), TAG, "touch reset low");
    ESP_RETURN_ON_ERROR(ws35_exio_set_pin(BOARD_LCD_RESET_EXIO, false), TAG, "LCD reset low");
    vTaskDelay(pdMS_TO_TICKS(50));
    ESP_RETURN_ON_ERROR(ws35_exio_set_pin(BOARD_TOUCH_RESET_EXIO, true), TAG, "touch reset high");
    ESP_RETURN_ON_ERROR(ws35_exio_set_pin(BOARD_LCD_RESET_EXIO, true), TAG, "LCD reset high");
    ESP_RETURN_ON_ERROR(ws35_exio_set_pin(BOARD_POWER_ENABLE_EXIO, true), TAG, "EXIO5 enable");
    vTaskDelay(pdMS_TO_TICKS(50));
    ESP_LOGI(TAG, "Touch RST (EXIO%d) + LCD RST (EXIO%d) pulsed",
             BOARD_TOUCH_RESET_EXIO, BOARD_LCD_RESET_EXIO);

    // Probe AXP2101 PMIC — report presence without full rail programming.
    // Full AXP2101 control is not necessary for display bring-up.
    // Retain one adapter-owned PMIC handle for telemetry.
    i2c_device_config_t pmic_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = BOARD_PMIC_I2C_ADDR,
        .scl_speed_hz = 400000,
    };
    if (i2c_master_bus_add_device(s_i2c_bus, &pmic_cfg, &s_pmic_dev) == ESP_OK) {
        uint8_t probe_buf[1] = {0x03};  // chip ID register
        uint8_t chip_id = 0;
        if (i2c_master_transmit_receive(s_pmic_dev, probe_buf, 1, &chip_id, 1, 100) == ESP_OK) {
            ESP_LOGI(TAG, "AXP2101 PMIC detected at 0x%02X (chip ID: 0x%02X)",
                     BOARD_PMIC_I2C_ADDR, chip_id);
        } else {
            ESP_LOGW(TAG, "AXP2101 at 0x%02X: probe read failed", BOARD_PMIC_I2C_ADDR);
        }
    } else {
        ESP_LOGW(TAG, "AXP2101 at 0x%02X: device add failed", BOARD_PMIC_I2C_ADDR);
    }

    return ESP_OK;
}

// Vendor XPowersLib at 04e6134: chip=0x4A, status0 bit3=battery present,
// ADC_CHANNEL_CTRL 0x30 bit0=VBAT measurement, VBAT 0x34/35 = H5:L8 in mV.
// Only measurement enable is written; rails/charger/TS settings are untouched.
i2c_master_bus_handle_t ws_c5_35_i2c_bus(void)
{
    return ws35_init_i2c() == ESP_OK ? s_i2c_bus : NULL;
}

static esp_err_t ws35_pmic_read(uint8_t reg, uint8_t *data, size_t len)
{
    if (!s_pmic_dev) return ESP_ERR_INVALID_STATE;
    return i2c_master_transmit_receive(s_pmic_dev, &reg, 1, data, len, 100);
}

esp_err_t ws_c5_35_battery_read(bool *present, uint16_t *millivolts)
{
    if (!present || !millivolts) return ESP_ERR_INVALID_ARG;
    *present = false;
    *millivolts = 0;
    uint8_t id = 0, status = 0, adc[2] = {0};
    esp_err_t err = ws35_pmic_read(0x03, &id, 1);
    if (err != ESP_OK) return err;
    if (id != 0x4A) return ESP_ERR_NOT_SUPPORTED;
    if (!s_battery_adc_ready) {
        uint8_t ctrl = 0;
        err = ws35_pmic_read(0x30, &ctrl, 1);
        if (err != ESP_OK) return err;
        if (!(ctrl & 1)) {
            uint8_t enable[2] = {0x30, (uint8_t)(ctrl | 1)};
            err = i2c_master_transmit(s_pmic_dev, enable, sizeof(enable), 100);
            if (err != ESP_OK) return err;
            // First conversion is not immediate; next bounded polling cycle samples.
            s_battery_adc_ready = true;
            return ESP_ERR_INVALID_STATE;
        }
        s_battery_adc_ready = true;
    }
    err = ws35_pmic_read(0x00, &status, 1);
    if (err != ESP_OK) return err;
    if (!(status & (1u << 3))) return ESP_OK; // USB-only: no fabricated battery level
    err = ws35_pmic_read(0x34, adc, sizeof(adc));
    if (err != ESP_OK) return err;
    uint16_t mv = ((uint16_t)(adc[0] & 0x1f) << 8) | adc[1];
    if (mv < 2500 || mv > 5000) return ESP_ERR_INVALID_RESPONSE;
    *millivolts = mv;
    *present = true;
    return ESP_OK;
}

// ── Display init (ST7796 SPI) ───────────────────────────────────────────────

esp_err_t ws_c5_35_display_init(esp_lcd_panel_handle_t *panel,
                                esp_lcd_panel_io_handle_t *io)
{
    if (!panel || !io) return ESP_ERR_INVALID_ARG;

    // I2C + IO expander must be up before display (LCD RST via EXIO1)
    ESP_RETURN_ON_ERROR(ws35_init_i2c(), TAG, "I2C init");

    // SPI bus shared with SD — CYM owns the lifecycle
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

    // Panel I/O on SPI2 at vendor-specified clock rate
    esp_lcd_panel_io_spi_config_t io_cfg = {
        .dc_gpio_num = BOARD_LCD_DC,
        .cs_gpio_num = BOARD_LCD_CS,
        .pclk_hz = BOARD_LCD_PCLK_HZ,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
        .spi_mode = 0,
        .trans_queue_depth = 10,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_spi(BOARD_SPI_HOST, &io_cfg, io),
                        TAG, "panel I/O");

    // ST7796 panel with BGR element order (vendor BSP default)
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = BOARD_LCD_RST,  // -1: RST already pulsed via EXIO1
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_BGR,
        .bits_per_pixel = 16,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_st7796(*io, &panel_cfg, panel),
                        TAG, "panel create");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(*panel), TAG, "panel reset");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(*panel), TAG, "panel init");

    // Vendor BSP defaults — UNVERIFIED on CYM hardware.
    // invert_color(true): ST7796 on this board uses inverted polarity.
    // mirror(true, false): X-axis mirrored, Y-axis normal.
    // No swap_xy: the panel is natively 320-wide x 480-tall portrait.
    ESP_RETURN_ON_ERROR(esp_lcd_panel_invert_color(*panel, true), TAG, "invert");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_mirror(*panel, true, false), TAG, "mirror");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_disp_on_off(*panel, true), TAG, "disp on");

    ESP_LOGI(TAG, "ST7796 display ready: %dx%d at %d Hz",
             BOARD_LCD_WIDTH, BOARD_LCD_HEIGHT, BOARD_LCD_PCLK_HZ);
    return ESP_OK;
}

// ── Touch init (FT6336 I2C) ─────────────────────────────────────────────────

esp_err_t ws_c5_35_touch_init(void)
{
    ESP_RETURN_ON_ERROR(ws35_init_i2c(), TAG, "I2C init");

    // FT6336 I2C panel IO
    esp_lcd_panel_io_i2c_config_t tp_io_cfg = ESP_LCD_TOUCH_IO_I2C_FT6336_CONFIG();
    tp_io_cfg.dev_addr = BOARD_TOUCH_I2C_ADDR;
    esp_lcd_panel_io_handle_t tp_io;
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_i2c(s_i2c_bus, &tp_io_cfg, &tp_io),
                        TAG, "touch I/O");

    // FT6336 touch config — vendor defaults, no transform
    esp_lcd_touch_config_t tp_cfg = {
        .x_max = BOARD_LCD_WIDTH,
        .y_max = BOARD_LCD_HEIGHT,
        .rst_gpio_num = -1,            // RST via CH32V006 EXIO0 (already pulsed)
        .int_gpio_num = BOARD_TOUCH_INT,
        .levels = {
            .reset = 0,
            .interrupt = 0,
        },
        .flags = {
            .swap_xy = 0,
            .mirror_x = 0,
            .mirror_y = 0,
        },
    };
    ESP_RETURN_ON_ERROR(esp_lcd_touch_new_i2c_ft6336(tp_io, &tp_cfg, &s_touch),
                        TAG, "FT6336 create");
    ESP_LOGI(TAG, "FT6336 touch ready (I2C 0x%02X, INT=GPIO%d)",
             BOARD_TOUCH_I2C_ADDR, BOARD_TOUCH_INT);
    return ESP_OK;
}

// ── Touch read ──────────────────────────────────────────────────────────────

bool ws_c5_35_touch_read_points(uint16_t *x,uint16_t *y,uint8_t *count,uint8_t max)
{
    if(!x||!y||!count||!s_touch||!max||max>2)return false;
    *count=0;
    if(esp_lcd_touch_read_data(s_touch)!=ESP_OK)return false;
    (void)esp_lcd_touch_get_coordinates(s_touch,x,y,NULL,count,max);
    return true;
}
bool ws_c5_35_touch_read(uint16_t *x,uint16_t *y,bool *touched)
{
    if(!touched)return false;
    uint8_t count=0;bool ok=ws_c5_35_touch_read_points(x,y,&count,1);
    *touched=ok&&count>0;return ok;
}

/* Factory Audio_PA_EN/DIS routes EXIO5. Keep the full adapter shadow,
 * including upper bits and LCD/touch reset lines. Vendor component1.0.2
 * documents INPUT04 as one byte;02/03 read APIs are shadows, not I2C reads.
 * Do not alter the accepted boot mode protocol in an audio lifecycle change. */
bool ws_c5_35_audio_amp(bool on)
{
    const uint16_t mask = 1u << BOARD_POWER_ENABLE_EXIO;
    if (!s_exio_dev || (mode_shadow & mask)) return false;
    uint16_t next = on ? output_shadow | mask : output_shadow & ~mask;
    uint8_t cmd[3] = {WS35_EXIO_REG_OUTPUT, next & 0xff, next >> 8};
    esp_err_t err = i2c_master_transmit(s_exio_dev, cmd, sizeof(cmd), 100);
    if (err == ESP_OK) output_shadow = next;
    uint8_t reg = 0x04, pins = 0;
    esp_err_t read = err == ESP_OK ? i2c_master_transmit_receive(s_exio_dev, &reg, 1, &pins, 1, 100) : err;
    bool verified = err == ESP_OK && read == ESP_OK && !!(pins & mask) == on;
    ESP_LOGI(TAG, "AUDIO_PA board=WS35 exio=5 requested=%d mode_shadow=%04x output_shadow=%04x pin_read=%02x write_rc=%d read_rc=%d verified=%d audible=unconfirmed", on, mode_shadow, output_shadow, pins, err, read, verified);
    return verified;
}

// ── Backlight control (CH32V006 PWM) ────────────────────────────────────────

void ws_c5_35_backlight_set(uint8_t level)
{
    if (!s_exio_dev) return;
    ws35_exio_set_pwm(level);
}

#else
bool ws_c5_35_touch_read_points(uint16_t *x,uint16_t *y,uint8_t *n,uint8_t max){(void)x;(void)y;(void)max;if(n)*n=0;return false;}
// Stubs for non-WS-C5-35 builds — ensures file compiles cleanly for all boards.
#include "ws_c5_35_port.h"
esp_err_t ws_c5_35_display_init(esp_lcd_panel_handle_t *panel, esp_lcd_panel_io_handle_t *io) { (void)panel; (void)io; return ESP_ERR_NOT_SUPPORTED; }
esp_err_t ws_c5_35_touch_init(void) { return ESP_ERR_NOT_SUPPORTED; }
bool ws_c5_35_touch_read(uint16_t *x, uint16_t *y, bool *touched) { (void)x; (void)y; if (touched) *touched=false; return false; }
void ws_c5_35_backlight_set(uint8_t level) { (void)level; }
i2c_master_bus_handle_t ws_c5_35_i2c_bus(void) { return NULL; }
esp_err_t ws_c5_35_battery_read(bool *present, uint16_t *millivolts) { if (present) *present=false; if (millivolts) *millivolts=0; return ESP_ERR_NOT_SUPPORTED; }
#endif
