#include "xpt2046.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <string.h>

static const char *TAG = "XPT2046";

// XPT2046 SPI bus speed — must be ≤ 2 MHz (125 kHz internal ADC)
#define XPT2046_SPI_CLK_HZ  (2 * 1000 * 1000)

// Number of averaged samples per axis read (reduces noise)
#define XPT2046_SAMPLES  4

// ─── Internal helpers ────────────────────────────────────────────────────────

/**
 * Software SPI helper: send one 8-bit command, receive one 16-bit response.
 *
 * XPT2046 uses SPI mode 0 (CPOL=0 CPHA=0): CLK idles LOW, data captured on
 * rising edge, data output on falling edge.  Three bytes are clocked (24 bits):
 *   TX: [cmd] [0x00] [0x00]
 *   RX: [don't-care] [BUSY|D11..D5] [D4..D0|000]
 * Result: ((rx[1] << 8) | rx[2]) >> 3 gives the 12-bit ADC value.
 */
static uint16_t xpt2046_read_raw_sw(xpt2046_handle_t *handle, uint8_t cmd)
{
    int sck  = handle->sck_gpio;
    int mosi = handle->mosi_gpio;
    int miso = handle->miso_gpio;

    uint8_t tx[3] = {cmd, 0x00, 0x00};
    uint8_t rx[3] = {0, 0, 0};

    gpio_set_level(handle->cs_gpio, 0);   // Assert CS (active LOW)

    for (int b = 0; b < 3; b++) {
        uint8_t out = tx[b];
        uint8_t in  = 0;
        for (int bit = 7; bit >= 0; bit--) {
            gpio_set_level(sck, 0);                        // CLK falling edge
            gpio_set_level(mosi, (out >> bit) & 1);       // drive MOSI before rising edge
            gpio_set_level(sck, 1);                        // CLK rising edge — XPT2046 captures MOSI
            if (gpio_get_level(miso)) in |= (1 << bit);   // sample MISO on rising edge
        }
        rx[b] = in;
    }

    gpio_set_level(sck, 0);               // leave CLK LOW (SPI mode 0 idle)
    gpio_set_level(handle->cs_gpio, 1);   // De-assert CS

    uint16_t raw = ((uint16_t)rx[1] << 8 | rx[2]) >> 3;
    return raw & 0x0FFF;
}

/**
 * Send one 8-bit command, receive one 16-bit response (hardware SPI path).
 * The 12-bit result sits in bits [14:3] of the 16-bit word → shift right 3.
 */
static uint16_t xpt2046_read_raw(xpt2046_handle_t *handle, uint8_t cmd)
{
    if (handle->use_sw_spi) return xpt2046_read_raw_sw(handle, cmd);

    uint8_t tx[3] = {cmd, 0x00, 0x00};
    uint8_t rx[3] = {0, 0, 0};

    spi_transaction_t t = {
        .length    = 24,
        .tx_buffer = tx,
        .rx_buffer = rx,
    };

    // CS driven manually — driver has spics_io_num=-1 so it never touches the pin.
    gpio_set_level(handle->cs_gpio, 0);
    esp_err_t ret = spi_device_polling_transmit(handle->spi, &t);
    gpio_set_level(handle->cs_gpio, 1);

    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI tx failed (cmd=0x%02x): %s", cmd, esp_err_to_name(ret));
        return 0;
    }

    // Result is in rx[1] (high byte) and rx[2] (low byte), bits [14:3]
    uint16_t raw = ((uint16_t)rx[1] << 8 | rx[2]) >> 3;
    return raw & 0x0FFF;
}

/**
 * Read an axis N times and return the average.
 * The first sample is discarded — the XPT2046 ADC capacitor always needs one
 * settling cycle when switching channels, producing a spurious high reading.
 */
static uint16_t xpt2046_read_averaged(xpt2046_handle_t *handle, uint8_t cmd)
{
    xpt2046_read_raw(handle, cmd);  // discard: ADC capacitor settling artifact
    uint32_t sum = 0;
    for (int i = 0; i < XPT2046_SAMPLES; i++) {
        sum += xpt2046_read_raw(handle, cmd);
    }
    return (uint16_t)(sum / XPT2046_SAMPLES);
}

/** Clamp and map a raw ADC value to screen pixels. */
static uint16_t xpt2046_map(int raw, int raw_min, int raw_max, int screen_max)
{
    if (raw <= raw_min) return 0;
    if (raw >= raw_max) return (uint16_t)screen_max;
    return (uint16_t)(((long)(raw - raw_min) * screen_max) / (raw_max - raw_min));
}

// ─── Public API ──────────────────────────────────────────────────────────────

esp_err_t xpt2046_init(xpt2046_handle_t *handle,
                       spi_host_device_t host,
                       int               cs_gpio,
                       uint16_t          screen_w,
                       uint16_t          screen_h)
{
    if (!handle) return ESP_ERR_INVALID_ARG;

    memset(handle, 0, sizeof(*handle));
    handle->cs_gpio  = cs_gpio;
    handle->screen_w = screen_w;
    handle->screen_h = screen_h;
    handle->x_min    = XPT2046_X_MIN_DEFAULT;
    handle->x_max    = XPT2046_X_MAX_DEFAULT;
    handle->y_min    = XPT2046_Y_MIN_DEFAULT;
    handle->y_max    = XPT2046_Y_MAX_DEFAULT;

    // Configure CS GPIO manually — driver gets spics_io_num=-1 so it never
    // touches the pin. xpt2046_read_raw() toggles it via gpio_set_level() which
    // correctly handles any GPIO number including GPIO32-39.
    gpio_set_direction((gpio_num_t)cs_gpio, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)cs_gpio, 1);   // idle HIGH (de-asserted)

    spi_device_interface_config_t devcfg = {
        .clock_speed_hz = XPT2046_SPI_CLK_HZ,
        .mode           = 0,               // SPI mode 0 (CPOL=0, CPHA=0)
        .spics_io_num   = -1,              // manual CS — driver must not touch it
        .queue_size     = 1,
        .pre_cb         = NULL,
        .post_cb        = NULL,
    };

    esp_err_t ret = spi_bus_add_device(host, &devcfg, &handle->spi);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "spi_bus_add_device failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "XPT2046 initialised — CS=GPIO%d, SPI %d Hz, screen %dx%d",
             cs_gpio, XPT2046_SPI_CLK_HZ, screen_w, screen_h);
    ESP_LOGI(TAG, "Calibration: X %d–%d → 0–%d, Y %d–%d → 0–%d",
             handle->x_min, handle->x_max, screen_w - 1,
             handle->y_min, handle->y_max, screen_h - 1);

    // Send dummy Z1 + Z2 reads to wake the XPT2046 from power-down mode.
    // Untouched: z1≈10-50 (low), z2≈4000-4095 (high). If MISO is stuck LOW
    // (wrong pin or external pull-down), both return 0 — chip not responding.
    uint16_t wakeup_z1 = xpt2046_read_raw(handle, XPT2046_CMD_Z1);
    uint16_t wakeup_z2 = xpt2046_read_raw(handle, XPT2046_CMD_Z2);
    const char *diag = (wakeup_z1 == 0 && wakeup_z2 == 0)
                       ? "MISO stuck LOW — chip not responding; check MISO pin"
                       : (wakeup_z2 > 3000) ? "OK — chip responding"
                                            : "unexpected — verify wiring";
    ESP_LOGI(TAG, "XPT2046 wakeup: z1=%u z2=%u [%s]", wakeup_z1, wakeup_z2, diag);

    return ESP_OK;
}

esp_err_t xpt2046_init_sw(xpt2046_handle_t *handle,
                           int sck_gpio, int mosi_gpio, int miso_gpio,
                           int cs_gpio,
                           uint16_t screen_w, uint16_t screen_h)
{
    if (!handle) return ESP_ERR_INVALID_ARG;

    memset(handle, 0, sizeof(*handle));
    handle->use_sw_spi = true;
    handle->cs_gpio    = cs_gpio;
    handle->sck_gpio   = sck_gpio;
    handle->mosi_gpio  = mosi_gpio;
    handle->miso_gpio  = miso_gpio;
    handle->screen_w   = screen_w;
    handle->screen_h   = screen_h;
    handle->x_min      = XPT2046_X_MIN_DEFAULT;
    handle->x_max      = XPT2046_X_MAX_DEFAULT;
    handle->y_min      = XPT2046_Y_MIN_DEFAULT;
    handle->y_max      = XPT2046_Y_MAX_DEFAULT;

    // Configure GPIO pins
    gpio_set_direction((gpio_num_t)sck_gpio,  GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)sck_gpio,  0);   // SCK idle LOW (SPI mode 0)
    gpio_set_direction((gpio_num_t)mosi_gpio, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)mosi_gpio, 0);
    // MISO may be an input-only pin (e.g. GPIO39 on ESP32 — no pull-up/down capable)
    gpio_set_direction((gpio_num_t)miso_gpio, GPIO_MODE_INPUT);
    gpio_set_direction((gpio_num_t)cs_gpio,   GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)cs_gpio,   1);   // CS idle HIGH (de-asserted)

    ESP_LOGI(TAG, "XPT2046 initialised (SW SPI) — SCK=%d MOSI=%d MISO=%d CS=%d, screen %dx%d",
             sck_gpio, mosi_gpio, miso_gpio, cs_gpio, screen_w, screen_h);
    ESP_LOGI(TAG, "Calibration: X %d-%d -> 0-%d, Y %d-%d -> 0-%d",
             handle->x_min, handle->x_max, screen_w - 1,
             handle->y_min, handle->y_max, screen_h - 1);

    // Wakeup read: untouched = z1 low (~10-50), z2 high (~4000-4095).
    // If both are 0, MISO is unresponsive (wrong pin or chip not powered).
    uint16_t wakeup_z1 = xpt2046_read_raw(handle, XPT2046_CMD_Z1);
    uint16_t wakeup_z2 = xpt2046_read_raw(handle, XPT2046_CMD_Z2);
    const char *diag = (wakeup_z1 == 0 && wakeup_z2 == 0)
                       ? "MISO stuck LOW — chip not responding; check MISO pin"
                       : (wakeup_z2 > 3000) ? "OK — chip responding"
                                            : "unexpected — verify wiring";
    ESP_LOGI(TAG, "XPT2046 wakeup: z1=%u z2=%u [%s]", wakeup_z1, wakeup_z2, diag);

    return ESP_OK;
}

void xpt2046_set_calibration(xpt2046_handle_t *handle,
                              int x_min, int x_max,
                              int y_min, int y_max)
{
    if (!handle) return;
    handle->x_min = x_min;
    handle->x_max = x_max;
    handle->y_min = y_min;
    handle->y_max = y_max;
    ESP_LOGI(TAG, "Calibration updated: X %d–%d, Y %d–%d", x_min, x_max, y_min, y_max);
}

bool xpt2046_read_touch(xpt2046_handle_t *handle, xpt2046_touch_point_t *point)
{
    if (!handle || !point) return false;

    point->touched = false;

    // Position-compensated pressure gate: Z1 + 4095 - Z2.
    // Z1 alone is X-position-dependent — at the right/top edges it reads low even
    // under real pressure, creating false dead zones. The datasheet-recommended
    // formula Z1+4095-Z2 cancels the position bias: untouched ≈ 0, any real touch
    // anywhere on the panel gives a consistent value well above XPT2046_Z_THRESHOLD.
    uint16_t z1 = xpt2046_read_raw(handle, XPT2046_CMD_Z1);
    uint16_t z2 = xpt2046_read_raw(handle, XPT2046_CMD_Z2);
    if ((int)z1 + 4095 - (int)z2 < XPT2046_Z_THRESHOLD) {
        return false;
    }

    uint16_t raw_x = xpt2046_read_averaged(handle, XPT2046_CMD_X);
    uint16_t raw_y = xpt2046_read_averaged(handle, XPT2046_CMD_Y);

    // Z1 is the sole touched/not-touched gate — do not range-check raw_x/raw_y here.
    // Near the physical screen edges the ADC legitimately reads above 4000 or below 100;
    // a range check silently drops those touches and creates dead zones at the edges.

    // Reject readings within the null zone (ghost touches at the panel resting position).
    if (handle->null_radius > 0) {
        int dx = (int)raw_x - handle->null_x;
        int dy = (int)raw_y - handle->null_y;
        if ((dx * dx + dy * dy) < (handle->null_radius * handle->null_radius)) {
            return false;
        }
    }

    // Apply axis swap / invert before mapping
    uint16_t map_x = handle->swap_xy ? raw_y : raw_x;
    uint16_t map_y = handle->swap_xy ? raw_x : raw_y;

    int x_min = handle->swap_xy ? handle->y_min : handle->x_min;
    int x_max = handle->swap_xy ? handle->y_max : handle->x_max;
    int y_min = handle->swap_xy ? handle->x_min : handle->y_min;
    int y_max = handle->swap_xy ? handle->x_max : handle->y_max;

    uint16_t px = xpt2046_map(map_x, x_min, x_max, handle->screen_w - 1);
    uint16_t py = xpt2046_map(map_y, y_min, y_max, handle->screen_h - 1);

    if (handle->invert_x) px = (handle->screen_w - 1) - px;
    if (handle->invert_y) py = (handle->screen_h - 1) - py;

    point->x       = px;
    point->y       = py;
    point->touched = true;

    ESP_LOGD(TAG, "TOUCH z1=%u raw_x=%u raw_y=%u → screen(%u,%u)", z1, raw_x, raw_y, px, py);
    return true;
}

bool xpt2046_read_raw_point(xpt2046_handle_t *handle, uint16_t *out_x, uint16_t *out_y)
{
    if (!handle || !out_x || !out_y) return false;

    // Same position-compensated pressure gate as xpt2046_read_touch.
    uint16_t rz1 = xpt2046_read_raw(handle, XPT2046_CMD_Z1);
    uint16_t rz2 = xpt2046_read_raw(handle, XPT2046_CMD_Z2);

    // Rate-limited diagnostic: log z1/z2 every 5 s so serial output stays readable.
    static int64_t s_last_diag_us = 0;
    int64_t now_us = esp_timer_get_time();
    if (now_us - s_last_diag_us >= 5000000LL) {
        ESP_LOGI(TAG, "touch poll z1=%u z2=%u pressure=%d",
                 rz1, rz2, (int)rz1 + 4095 - (int)rz2);
        s_last_diag_us = now_us;
    }

    // z1=0 && z2=0 → MISO stuck LOW (broken read — chip not responding).
    // Real untouched reads have z1≈0, z2≈4095. Guard prevents false pressure=4095.
    if (rz1 == 0 && rz2 == 0) return false;

    if ((int)rz1 + 4095 - (int)rz2 < XPT2046_Z_THRESHOLD) return false;

    // Discard first sample per axis (ADC settling), then average 4 samples
    xpt2046_read_raw(handle, XPT2046_CMD_X);
    uint32_t sx = 0;
    for (int i = 0; i < 4; i++) sx += xpt2046_read_raw(handle, XPT2046_CMD_X);

    xpt2046_read_raw(handle, XPT2046_CMD_Y);
    uint32_t sy = 0;
    for (int i = 0; i < 4; i++) sy += xpt2046_read_raw(handle, XPT2046_CMD_Y);

    *out_x = (uint16_t)(sx / 4);
    *out_y = (uint16_t)(sy / 4);
    return true;  // Z1 already confirmed touch; don't range-filter raw values
}
