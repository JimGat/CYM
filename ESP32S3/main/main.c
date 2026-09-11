/**
 * CYM ESP32-S3 — Hosyond 3.5" (ES3C35P) bring-up / BSP verification
 *
 * Phase: Board bring-up — not a full CYM port yet.
 * Tests:  display (ST77922 QSPI), touch (I2C 0x55), SD card (SPI mode).
 *
 * Once this boots and paints the screen, the full main.c port from ESP32C5
 * can be brought in behind CONFIG_BOARD_HOSYOND_S3_35 guards.
 */

#include <stdio.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

#include "esp_log.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/i2c_master.h"
#include "driver/ledc.h"

#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_st77922.h"

#include "lvgl.h"

/* SD card (SPI mode via sdspi host) */
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "driver/sdspi_host.h"
#include "sdmmc_cmd.h"

#include "board_hal.h"

static const char *TAG = "CYM-S3";

/* ── LVGL state ──────────────────────────────────────────────────────────────*/
static SemaphoreHandle_t   s_lvgl_mutex;
static esp_lcd_panel_handle_t s_panel;
static lv_disp_draw_buf_t  s_draw_buf;
static lv_color_t         *s_buf1;
static lv_color_t         *s_buf2;
static volatile bool       s_flush_done = true;

/* ── Touch state ─────────────────────────────────────────────────────────────*/
static esp_lcd_touch_handle_t s_touch;

/* ── SD mutex (same pattern as all other CYM boards) ────────────────────────*/
SemaphoreHandle_t sd_spi_mutex;

/* ── Backlight: LEDC ─────────────────────────────────────────────────────────*/
static void bl_init(void)
{
    ledc_timer_config_t timer = {
        .speed_mode      = LEDC_LOW_SPEED_MODE,
        .timer_num       = LEDC_TIMER_0,
        .duty_resolution = LEDC_TIMER_8_BIT,
        .freq_hz         = 1000,
        .clk_cfg         = LEDC_AUTO_CLK,
    };
    ledc_timer_config(&timer);

    ledc_channel_config_t ch = {
        .gpio_num   = BOARD_BACKLIGHT_GPIO,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel    = LEDC_CHANNEL_1,
        .timer_sel  = LEDC_TIMER_0,
        .duty       = 200,       /* ~78% initial brightness */
        .hpoint     = 0,
    };
    ledc_channel_config(&ch);
}

/* ── LVGL flush done callback ────────────────────────────────────────────────*/
static bool IRAM_ATTR on_color_trans_done(esp_lcd_panel_io_handle_t io,
                                           esp_lcd_panel_io_event_data_t *edata,
                                           void *user_ctx)
{
    BaseType_t need_yield = pdFALSE;
    lv_disp_t *disp = (lv_disp_t *)user_ctx;
    lv_disp_flush_ready(disp->driver);
    s_flush_done = true;
    return need_yield == pdTRUE;
}

/* ── LVGL flush callback ─────────────────────────────────────────────────────*/
static void lvgl_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_map)
{
    esp_lcd_panel_draw_bitmap(s_panel,
                              area->x1, area->y1,
                              area->x2 + 1, area->y2 + 1,
                              color_map);
}

/* ── LVGL touch read callback ────────────────────────────────────────────────*/
static void lvgl_touch_cb(lv_indev_drv_t *drv, lv_indev_data_t *data)
{
    uint16_t touch_x[1], touch_y[1], touch_strength[1];
    uint8_t touch_count = 0;

    esp_lcd_touch_read_data(s_touch);
    bool touched = esp_lcd_touch_get_coordinates(s_touch,
                                                  touch_x, touch_y,
                                                  touch_strength, &touch_count, 1);
    if (touched && touch_count > 0) {
        data->point.x = touch_x[0];
        data->point.y = touch_y[0];
        data->state   = LV_INDEV_STATE_PR;
    } else {
        data->state = LV_INDEV_STATE_REL;
    }
}

/* ── LVGL tick timer ─────────────────────────────────────────────────────────*/
static void lvgl_tick_cb(void *arg)
{
    lv_tick_inc(10);
}

/* ── Display init (ST77922 QSPI) ─────────────────────────────────────────────*/
static void display_init(lv_disp_t **ret_disp)
{
    /* QSPI bus */
    spi_bus_config_t buscfg = ST77922_PANEL_BUS_QSPI_CONFIG(
        BOARD_LCD_SCK, BOARD_LCD_D0, BOARD_LCD_D1, BOARD_LCD_D2, BOARD_LCD_D3,
        BOARD_LCD_WIDTH * BOARD_LCD_BUF_LINES * 2
    );
    /* DMA_CH_AUTO: let IDF pick a DMA channel */
    ESP_ERROR_CHECK(spi_bus_initialize(BOARD_LCD_HOST, &buscfg, SPI_DMA_CH_AUTO));

    /* Panel IO: QSPI mode, 80 MHz, trans_done callback wired for flush */
    esp_lcd_panel_io_handle_t io_handle;
    esp_lcd_panel_io_spi_config_t io_config = ST77922_PANEL_IO_QSPI_CONFIG(
        BOARD_LCD_CS, on_color_trans_done, NULL   /* user_ctx set after disp created */
    );
    /* Attach LCD to SPI bus */
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(
        (esp_lcd_spi_bus_handle_t)BOARD_LCD_HOST, &io_config, &io_handle));

    /* Panel: ST77922, 320×480, 16-bit colour */
    st77922_vendor_config_t vendor_cfg = {
        .flags = { .use_qspi_interface = 1 },
    };
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = BOARD_LCD_RST,
        .data_endian    = LCD_RGB_DATA_ENDIAN_BIG,
        .bits_per_pixel = 16,
        .vendor_config  = &vendor_cfg,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st77922(io_handle, &panel_cfg, &s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(s_panel));
    /* Mirror/invert to match portrait orientation */
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(s_panel, true, false));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(s_panel, true));

    /* LVGL: two buffers in internal SRAM (PSRAM too slow at 80 MHz QSPI) */
    s_buf1 = heap_caps_malloc(BOARD_LCD_BUF_SIZE, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    s_buf2 = heap_caps_malloc(BOARD_LCD_BUF_SIZE, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    assert(s_buf1 && s_buf2);

    lv_init();

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    lv_disp_draw_buf_init(&s_draw_buf, s_buf1, s_buf2,
                           BOARD_LCD_WIDTH * BOARD_LCD_BUF_LINES);
    disp_drv.hor_res    = BOARD_LCD_WIDTH;
    disp_drv.ver_res    = BOARD_LCD_HEIGHT;
    disp_drv.flush_cb   = lvgl_flush_cb;
    disp_drv.draw_buf   = &s_draw_buf;
    *ret_disp = lv_disp_drv_register(&disp_drv);

    /* Wire the flush-done callback now that the display object exists */
    io_config.on_color_trans_done = on_color_trans_done;
    io_config.user_ctx = *ret_disp;

    /* Backlight on */
    bl_init();
    ESP_LOGI(TAG, "ST77922 QSPI display init OK — 320×480");
}

/* ── Touch init (ST77922 I2C companion at 0x55) ──────────────────────────────*/
static void touch_init(lv_disp_t *disp)
{
    /* I2C master bus */
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port      = BOARD_I2C_NUM,
        .sda_io_num    = BOARD_I2C_SDA,
        .scl_io_num    = BOARD_I2C_SCL,
        .clk_source    = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    i2c_master_bus_handle_t i2c_bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &i2c_bus));

    /* Panel IO for touch (I2C) */
    esp_lcd_panel_io_handle_t tp_io;
    esp_lcd_panel_io_i2c_config_t tp_io_cfg = ESP_LCD_TOUCH_IO_I2C_ST77922_CONFIG();
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c(i2c_bus, &tp_io_cfg, &tp_io));

    /* Touch driver */
    esp_lcd_touch_config_t tp_cfg = {
        .x_max      = BOARD_LCD_WIDTH,
        .y_max      = BOARD_LCD_HEIGHT,
        .rst_gpio_num = BOARD_TOUCH_RST,
        .int_gpio_num = BOARD_TOUCH_INT,
        .levels = {
            .reset     = 0,
            .interrupt = 0,
        },
        .flags = {
            .swap_xy  = 0,
            .mirror_x = 0,
            .mirror_y = 0,
        },
    };
    ESP_ERROR_CHECK(esp_lcd_touch_new_i2c_st77922(tp_io, &tp_cfg, &s_touch));

    /* LVGL indev */
    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type    = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = lvgl_touch_cb;
    lv_indev_drv_register(&indev_drv);

    ESP_LOGI(TAG, "ST77922 touch I2C init OK — addr 0x55");
}

/* ── SD card init (SPI mode on SPI3) ─────────────────────────────────────────*/
static void sd_init(void)
{
    sd_spi_mutex = xSemaphoreCreateMutex();

    /* Pull D1/D2 high: unused in SPI mode; card checks them during init */
    gpio_config_t pull_cfg = {
        .pin_bit_mask = (1ULL << BOARD_SD_PULLUP_D1) | (1ULL << BOARD_SD_PULLUP_D2),
        .mode         = GPIO_MODE_INPUT,
        .pull_up_en   = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&pull_cfg);

    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = BOARD_SD_SPI_HOST;

    sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_config.gpio_cs   = BOARD_SD_CS;
    slot_config.host_id   = BOARD_SD_SPI_HOST;

    /* SPI bus for SD (separate from display SPI2) */
    spi_bus_config_t sd_buscfg = {
        .mosi_io_num = BOARD_SD_MOSI,
        .miso_io_num = BOARD_SD_MISO,
        .sclk_io_num = BOARD_SD_SCK,
        .quadhd_io_num = -1,
        .quadwp_io_num = -1,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(BOARD_SD_SPI_HOST, &sd_buscfg, SPI_DMA_CH_AUTO));

    esp_vfs_fat_sdmmc_mount_config_t mount_cfg = {
        .format_if_mount_failed = false,
        .max_files              = 5,
        .allocation_unit_size   = 16 * 1024,
    };

    sdmmc_card_t *card;
    esp_err_t ret = esp_vfs_fat_sdspi_mount(BOARD_SD_MOUNT_POINT, &host,
                                              &slot_config, &mount_cfg, &card);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "SD mount failed: %s — continuing without SD", esp_err_to_name(ret));
        return;
    }
    sdmmc_card_print_info(stdout, card);
    ESP_LOGI(TAG, "SD mounted at %s", BOARD_SD_MOUNT_POINT);
}

/* ── LVGL main loop task ─────────────────────────────────────────────────────*/
static void lvgl_task(void *arg)
{
    while (1) {
        if (xSemaphoreTake(s_lvgl_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
            lv_timer_handler();
            xSemaphoreGive(s_lvgl_mutex);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

/* ── Splash UI ───────────────────────────────────────────────────────────────*/
static void build_splash(void)
{
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x0D1B2A), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);

    lv_obj_t *title = lv_label_create(scr);
    lv_label_set_text(title, "CYM ESP32-S3");
    lv_obj_set_style_text_color(title, lv_color_hex(0x00CFFF), 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_28, 0);
    lv_obj_align(title, LV_ALIGN_CENTER, 0, -60);

    lv_obj_t *board = lv_label_create(scr);
    lv_label_set_text(board, "Hosyond 3.5\" ES3C35P");
    lv_obj_set_style_text_color(board, lv_color_hex(0xA0B8CC), 0);
    lv_obj_set_style_text_font(board, &lv_font_montserrat_16, 0);
    lv_obj_align(board, LV_ALIGN_CENTER, 0, -25);

    lv_obj_t *disp_lbl = lv_label_create(scr);
    lv_label_set_text(disp_lbl, "ST77922 QSPI 320x480");
    lv_obj_set_style_text_color(disp_lbl, lv_color_hex(0x607080), 0);
    lv_obj_set_style_text_font(disp_lbl, &lv_font_montserrat_12, 0);
    lv_obj_align(disp_lbl, LV_ALIGN_CENTER, 0, 10);

    lv_obj_t *touch_lbl = lv_label_create(scr);
    lv_label_set_text(touch_lbl, "Touch: I2C 0x55  |  SD: SPI3");
    lv_obj_set_style_text_color(touch_lbl, lv_color_hex(0x607080), 0);
    lv_obj_set_style_text_font(touch_lbl, &lv_font_montserrat_12, 0);
    lv_obj_align(touch_lbl, LV_ALIGN_CENTER, 0, 30);

    lv_obj_t *ver = lv_label_create(scr);
    lv_label_set_text(ver, FW_VERSION);
    lv_obj_set_style_text_color(ver, lv_color_hex(0x405060), 0);
    lv_obj_set_style_text_font(ver, &lv_font_montserrat_12, 0);
    lv_obj_align(ver, LV_ALIGN_BOTTOM_MID, 0, -16);
}

/* ── app_main ────────────────────────────────────────────────────────────────*/
void app_main(void)
{
    ESP_LOGI(TAG, "CYM ESP32-S3 boot — Hosyond 3.5\" (ES3C35P)");

    /* LVGL tick timer: 10 ms interval */
    const esp_timer_create_args_t tick_args = {
        .callback = lvgl_tick_cb,
        .name     = "lvgl_tick",
    };
    esp_timer_handle_t tick_timer;
    ESP_ERROR_CHECK(esp_timer_create(&tick_args, &tick_timer));
    ESP_ERROR_CHECK(esp_timer_start_periodic(tick_timer, 10 * 1000)); /* 10 ms */

    s_lvgl_mutex = xSemaphoreCreateMutex();

    /* Display → LVGL init */
    lv_disp_t *disp;
    display_init(&disp);

    /* Touch */
    touch_init(disp);

    /* SD card */
    sd_init();

    /* Build the splash screen */
    xSemaphoreTake(s_lvgl_mutex, portMAX_DELAY);
    build_splash();
    xSemaphoreGive(s_lvgl_mutex);

    /* LVGL loop task pinned to Core 0; jammer / heavy tasks go to Core 1 */
    xTaskCreatePinnedToCore(lvgl_task, "lvgl", 8192, NULL, 5, NULL, 0);

    ESP_LOGI(TAG, "Board bring-up complete");
}
