// Classic CYD / HackerBox common-anode RGB, exposed through the LED API.
#include "classic_rgb_led.h"
#include "board_hal.h"
#if defined(CONFIG_BOARD_CYD2USB)
#include "driver/gpio.h"
#include "driver/ledc.h"
#include <stdbool.h>
#include <stdint.h>
// Keep timer 2/channel 4 (vibrator) and timer 3/channel 5 (IR HAT) untouched.
// Classic backlight is GPIO-controlled. No RMT, task or heap allocation.
static const int rgb_pins[3] = {BOARD_LED_R_GPIO, BOARD_LED_G_GPIO, BOARD_LED_B_GPIO};
static const int rgb_channels[3] = {LEDC_CHANNEL_0, LEDC_CHANNEL_1, LEDC_CHANNEL_2};
static uint8_t rgb_pending[3];
static bool rgb_ready;
static void classic_rgb_idle(unsigned configured)
{
    for (unsigned i = 0; i < configured; i++)
        ledc_stop(LEDC_LOW_SPEED_MODE, rgb_channels[i], 1);
    for (unsigned i = 0; i < 3; i++) gpio_set_level(rgb_pins[i], 1);
    const gpio_config_t pins = {
        .pin_bit_mask = (1ULL << BOARD_LED_R_GPIO) | (1ULL << BOARD_LED_G_GPIO) | (1ULL << BOARD_LED_B_GPIO),
        .mode = GPIO_MODE_OUTPUT, .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&pins);
}
static esp_err_t classic_rgb_set(led_strip_handle_t strip, uint32_t index, uint32_t r, uint32_t g, uint32_t b)
{
    (void)strip;
    if (index != 0 || r > 255 || g > 255 || b > 255) return ESP_ERR_INVALID_ARG;
    rgb_pending[0] = r; rgb_pending[1] = g; rgb_pending[2] = b;
    return ESP_OK;
}
static esp_err_t classic_rgb_set_rgbw(led_strip_handle_t strip, uint32_t index, uint32_t r, uint32_t g, uint32_t b, uint32_t w)
{
    (void)w;
    return classic_rgb_set(strip, index, r, g, b);
}
static esp_err_t classic_rgb_refresh(led_strip_handle_t strip)
{
    (void)strip;
    for (unsigned i = 0; i < 3; i++) {
        esp_err_t ret = ledc_set_duty(LEDC_LOW_SPEED_MODE, rgb_channels[i], rgb_pending[i]);
        if (ret != ESP_OK) return ret;
        ret = ledc_update_duty(LEDC_LOW_SPEED_MODE, rgb_channels[i]);
        if (ret != ESP_OK) return ret;
    }
    return ESP_OK;
}
static esp_err_t classic_rgb_clear(led_strip_handle_t strip)
{
    rgb_pending[0] = rgb_pending[1] = rgb_pending[2] = 0;
    return classic_rgb_refresh(strip);
}
static esp_err_t classic_rgb_del(led_strip_handle_t strip)
{
    (void)strip;
    classic_rgb_idle(3);
    rgb_ready = false;
    return ESP_OK;
}
static led_strip_t classic_rgb = {
    .set_pixel = classic_rgb_set, .set_pixel_rgbw = classic_rgb_set_rgbw,
    .refresh = classic_rgb_refresh, .clear = classic_rgb_clear, .del = classic_rgb_del,
};
#endif
esp_err_t classic_rgb_led_init(led_strip_handle_t *out)
{
    if (!out) return ESP_ERR_INVALID_ARG;
    *out = NULL;
#if defined(CONFIG_BOARD_CYD2USB)
    if (rgb_ready) { *out = &classic_rgb; return ESP_OK; }
    classic_rgb_idle(0);
    const ledc_timer_config_t timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = LEDC_TIMER_8_BIT,
        .timer_num = LEDC_TIMER_1, .freq_hz = 5000, .clk_cfg = LEDC_AUTO_CLK,
    };
    esp_err_t ret = ledc_timer_config(&timer);
    if (ret != ESP_OK) return ret;
    unsigned configured = 0;
    for (unsigned i = 0; i < 3; i++) {
        const ledc_channel_config_t channel = {
            .gpio_num = rgb_pins[i], .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel = rgb_channels[i], .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_1, .duty = 0, .hpoint = 0,
            // Hardware inversion: zero duty is truly HIGH/off, not 255/256 PWM.
            .flags.output_invert = 1,
        };
        ret = ledc_channel_config(&channel);
        if (ret != ESP_OK) { classic_rgb_idle(configured); return ret; }
        configured++;
    }
    rgb_pending[0] = rgb_pending[1] = rgb_pending[2] = 0;
    rgb_ready = true;
    *out = &classic_rgb;
    return ESP_OK;
#else
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
