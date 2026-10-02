#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/uart.h"
#include "esp_heap_caps.h"
#include "esp_lcd_ili9341.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#define LCD_HOST SPI3_HOST
#define LCD_WIDTH 240
#define LCD_HEIGHT 320
#define LCD_SCK GPIO_NUM_14
#define LCD_MOSI GPIO_NUM_13
#define LCD_MISO GPIO_NUM_12
#define LCD_CS GPIO_NUM_15
#define LCD_DC GPIO_NUM_2
#define LCD_BACKLIGHT GPIO_NUM_21
#define TEST_UART UART_NUM_2
#define TEST_WINDOW_MS 4000
#define SAMPLE_BYTES 20
#define RESULT_COUNT 9

#define RGB565(r, g, b) (uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3))
#define COLOR_BLACK RGB565(0, 0, 0)
#define COLOR_WHITE RGB565(255, 255, 255)
#define COLOR_YELLOW RGB565(255, 220, 0)
#define COLOR_GREEN RGB565(0, 255, 80)
#define COLOR_CYAN RGB565(0, 220, 255)
#define COLOR_RED RGB565(255, 60, 60)
#define COLOR_GRAY RGB565(120, 120, 120)

typedef struct {
    gpio_num_t pin;
    int baud;
    uint32_t bytes;
    uint32_t frame_errors;
    uint32_t parity_errors;
    uint32_t overflow_errors;
    uint32_t break_errors;
    uint32_t dollar_count;
    uint32_t line_count;
    uint32_t valid_checksums;
    uint8_t sample[SAMPLE_BYTES];
    size_t sample_len;
    char sample_hex[SAMPLE_BYTES * 3 + 1];
    bool sentence_active;
    bool checksum_active;
    uint8_t checksum_calc;
    uint8_t checksum_read;
    uint8_t checksum_digits;
} scan_result_t;

static const gpio_num_t scan_pins[] = {GPIO_NUM_1, GPIO_NUM_3, GPIO_NUM_26};
static const int scan_bauds[] = {9600, 38400, 115200};
static scan_result_t results[RESULT_COUNT];
static uint16_t *framebuffer;
static esp_lcd_panel_handle_t panel;
static QueueHandle_t uart_events;
static bool found;
static gpio_num_t found_pin;
static int found_baud;
static bool completed_cycle;

static uint16_t spi_color(uint16_t color)
{
    return (uint16_t)((color << 8) | (color >> 8));
}

static const uint8_t *glyph(char ch)
{
    static const uint8_t blank[5] = {0, 0, 0, 0, 0};
    static const uint8_t digits[10][5] = {
        {0x3E,0x51,0x49,0x45,0x3E},{0x00,0x42,0x7F,0x40,0x00},
        {0x42,0x61,0x51,0x49,0x46},{0x21,0x41,0x45,0x4B,0x31},
        {0x18,0x14,0x12,0x7F,0x10},{0x27,0x45,0x45,0x45,0x39},
        {0x3C,0x4A,0x49,0x49,0x30},{0x01,0x71,0x09,0x05,0x03},
        {0x36,0x49,0x49,0x49,0x36},{0x06,0x49,0x49,0x29,0x1E}
    };
    static const uint8_t letters[26][5] = {
        {0x7E,0x11,0x11,0x11,0x7E},{0x7F,0x49,0x49,0x49,0x36},
        {0x3E,0x41,0x41,0x41,0x22},{0x7F,0x41,0x41,0x22,0x1C},
        {0x7F,0x49,0x49,0x49,0x41},{0x7F,0x09,0x09,0x09,0x01},
        {0x3E,0x41,0x49,0x49,0x7A},{0x7F,0x08,0x08,0x08,0x7F},
        {0x00,0x41,0x7F,0x41,0x00},{0x20,0x40,0x41,0x3F,0x01},
        {0x7F,0x08,0x14,0x22,0x41},{0x7F,0x40,0x40,0x40,0x40},
        {0x7F,0x02,0x0C,0x02,0x7F},{0x7F,0x04,0x08,0x10,0x7F},
        {0x3E,0x41,0x41,0x41,0x3E},{0x7F,0x09,0x09,0x09,0x06},
        {0x3E,0x41,0x51,0x21,0x5E},{0x7F,0x09,0x19,0x29,0x46},
        {0x46,0x49,0x49,0x49,0x31},{0x01,0x01,0x7F,0x01,0x01},
        {0x3F,0x40,0x40,0x40,0x3F},{0x1F,0x20,0x40,0x20,0x1F},
        {0x3F,0x40,0x38,0x40,0x3F},{0x63,0x14,0x08,0x14,0x63},
        {0x07,0x08,0x70,0x08,0x07},{0x61,0x51,0x49,0x45,0x43}
    };
    static const uint8_t colon[5] = {0x00,0x36,0x36,0x00,0x00};
    static const uint8_t dash[5] = {0x08,0x08,0x08,0x08,0x08};
    static const uint8_t slash[5] = {0x20,0x10,0x08,0x04,0x02};
    static const uint8_t dollar[5] = {0x24,0x2A,0x7F,0x2A,0x12};
    static const uint8_t dot[5] = {0x00,0x60,0x60,0x00,0x00};
    static const uint8_t equal[5] = {0x14,0x14,0x14,0x14,0x14};
    static const uint8_t star[5] = {0x14,0x08,0x3E,0x08,0x14};
    static const uint8_t question[5] = {0x02,0x01,0x51,0x09,0x06};
    static const uint8_t hash[5] = {0x14,0x7F,0x14,0x7F,0x14};
    if (ch >= '0' && ch <= '9') return digits[ch - '0'];
    ch = (char)toupper((unsigned char)ch);
    if (ch >= 'A' && ch <= 'Z') return letters[ch - 'A'];
    switch (ch) {
        case ':': return colon; case '-': return dash; case '/': return slash;
        case '$': return dollar; case '.': return dot; case '=': return equal;
        case '*': return star; case '?': return question; case '#': return hash;
        default: return blank;
    }
}

static void clear_frame(uint16_t color)
{
    const uint16_t wire = spi_color(color);
    for (size_t i = 0; i < LCD_WIDTH * LCD_HEIGHT; ++i) framebuffer[i] = wire;
}

static void draw_text(int row, int col, const char *text, uint16_t color)
{
    const int y0 = row * 10;
    const uint16_t wire = spi_color(color);
    for (int ci = 0; text[ci] && col + ci < 40; ++ci) {
        const uint8_t *g = glyph(text[ci]);
        const int x0 = (col + ci) * 6;
        for (int x = 0; x < 5; ++x) {
            for (int y = 0; y < 7; ++y) {
                if ((g[x] >> y) & 1U) framebuffer[(y0 + y) * LCD_WIDTH + x0 + x] = wire;
            }
        }
    }
}

static void present(void)
{
    esp_lcd_panel_draw_bitmap(panel, 0, 0, LCD_WIDTH, LCD_HEIGHT, framebuffer);
}

static void display_status(const scan_result_t *current, uint32_t elapsed_ms)
{
    char line[64];
    clear_frame(COLOR_BLACK);
    draw_text(0, 0, "CLASSICCYDGPSTEST", COLOR_YELLOW);
    draw_text(1, 0, "RX ONLY  GPS RX DISCONNECTED", COLOR_CYAN);
    snprintf(line, sizeof(line), "SCAN GPIO%d  %d BAUD  %lus",
             current->pin, current->baud, (unsigned long)(elapsed_ms / 1000));
    draw_text(3, 0, line, COLOR_WHITE);
    snprintf(line, sizeof(line), "B:%lu F:%lu P:%lu O:%lu BR:%lu",
             (unsigned long)current->bytes, (unsigned long)current->frame_errors,
             (unsigned long)current->parity_errors, (unsigned long)current->overflow_errors,
             (unsigned long)current->break_errors);
    draw_text(4, 0, line, COLOR_WHITE);
    snprintf(line, sizeof(line), "$:%lu L:%lu C:%lu IDLE:%d",
             (unsigned long)current->dollar_count, (unsigned long)current->line_count,
             (unsigned long)current->valid_checksums, gpio_get_level(current->pin));
    draw_text(5, 0, line, COLOR_WHITE);
    draw_text(7, 0, "PIN BAUD    B     F P O $ L C", COLOR_GRAY);
    for (int i = 0; i < RESULT_COUNT; ++i) {
        const scan_result_t *r = &results[i];
        snprintf(line, sizeof(line), "%2d %6d %5lu %lu %lu %lu %lu %lu %lu",
                 r->pin, r->baud, (unsigned long)r->bytes,
                 (unsigned long)r->frame_errors, (unsigned long)r->parity_errors,
                 (unsigned long)r->overflow_errors, (unsigned long)r->dollar_count,
                 (unsigned long)r->line_count, (unsigned long)r->valid_checksums);
        draw_text(8 + i, 0, line, r == current ? COLOR_CYAN : COLOR_WHITE);
    }
    draw_text(18, 0, "HEX FIRST BYTES:", COLOR_GRAY);
    draw_text(19, 0, current->sample_hex[0] ? current->sample_hex : "NONE", COLOR_WHITE);
    if (found) {
        snprintf(line, sizeof(line), "FOUND RX GPIO%d AT %d BAUD", found_pin, found_baud);
        draw_text(22, 0, line, COLOR_GREEN);
        draw_text(23, 0, "VALID NMEA CHECKSUM RECEIVED", COLOR_GREEN);
    } else if (completed_cycle) {
        bool any = false;
        for (int i = 0; i < RESULT_COUNT; ++i) any |= results[i].bytes > 0;
        if (!any) draw_text(22, 0, "NO UART BYTES ON GPIO1/3/26", COLOR_RED);
        else draw_text(22, 0, "UART BYTES SEEN - NO VALID NMEA", COLOR_YELLOW);
    } else {
        draw_text(22, 0, "FULL SCAN TAKES 36 SECONDS", COLOR_GRAY);
    }
    draw_text(26, 0, "SECOND MICRO-USB MUST BE UNPLUGGED", COLOR_YELLOW);
    draw_text(28, 0, "REBOOTS RESCAN ALL COMBINATIONS", COLOR_GRAY);
    present();
}

static int hex_value(uint8_t c)
{
    if (c >= '0' && c <= '9') return c - '0';
    c = (uint8_t)toupper(c);
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static void nmea_byte(scan_result_t *r, uint8_t c)
{
    if (c == '$' || c == '!') {
        r->dollar_count++;
        r->sentence_active = true;
        r->checksum_active = false;
        r->checksum_calc = 0;
        r->checksum_read = 0;
        r->checksum_digits = 0;
        return;
    }
    if (!r->sentence_active) return;
    if (c == '\r' || c == '\n') {
        if (r->checksum_active && r->checksum_digits == 2 && r->checksum_read == r->checksum_calc)
            r->valid_checksums++;
        r->line_count++;
        r->sentence_active = false;
        return;
    }
    if (r->checksum_active) {
        int n = hex_value(c);
        if (n < 0 || r->checksum_digits >= 2) {
            r->sentence_active = false;
            return;
        }
        r->checksum_read = (uint8_t)((r->checksum_read << 4) | n);
        r->checksum_digits++;
    } else if (c == '*') {
        r->checksum_active = true;
    } else {
        r->checksum_calc ^= c;
    }
}

static void record_bytes(scan_result_t *r, const uint8_t *data, size_t length)
{
    r->bytes += length;
    for (size_t i = 0; i < length; ++i) {
        if (r->sample_len < SAMPLE_BYTES) r->sample[r->sample_len++] = data[i];
        nmea_byte(r, data[i]);
    }
    size_t pos = 0;
    for (size_t i = 0; i < r->sample_len && pos + 3 < sizeof(r->sample_hex); ++i) {
        pos += (size_t)snprintf(r->sample_hex + pos, sizeof(r->sample_hex) - pos,
                                "%02X%s", r->sample[i], i + 1 == r->sample_len ? "" : " ");
    }
}

static void configure_receiver(gpio_num_t pin, int baud)
{
    uart_driver_delete(TEST_UART);
    gpio_reset_pin(pin);
    gpio_set_direction(pin, GPIO_MODE_INPUT);
    gpio_set_pull_mode(pin, GPIO_FLOATING);
    const uart_config_t config = {
        .baud_rate = baud,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_param_config(TEST_UART, &config);
    uart_set_pin(TEST_UART, UART_PIN_NO_CHANGE, pin, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    uart_driver_install(TEST_UART, 2048, 0, 20, &uart_events, 0);
    uart_flush_input(TEST_UART);
    xQueueReset(uart_events);
}

static void run_scan(scan_result_t *r)
{
    gpio_num_t selected_pin = r->pin;
    int selected_baud = r->baud;
    memset(r, 0, sizeof(*r));
    r->pin = selected_pin;
    r->baud = selected_baud;
    configure_receiver(r->pin, r->baud);
    const int64_t start = esp_timer_get_time();
    int64_t last_display = 0;
    while (!found && (esp_timer_get_time() - start) / 1000 < TEST_WINDOW_MS) {
        uart_event_t event;
        if (xQueueReceive(uart_events, &event, pdMS_TO_TICKS(100))) {
            if (event.type == UART_DATA) {
                uint8_t buffer[128];
                size_t remaining = event.size;
                while (remaining) {
                    const size_t want = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
                    int got = uart_read_bytes(TEST_UART, buffer, want, pdMS_TO_TICKS(20));
                    if (got <= 0) break;
                    record_bytes(r, buffer, (size_t)got);
                    remaining -= (size_t)got;
                }
            } else if (event.type == UART_FIFO_OVF || event.type == UART_BUFFER_FULL) {
                r->overflow_errors++;
                uart_flush_input(TEST_UART);
                xQueueReset(uart_events);
            } else if (event.type == UART_BREAK) {
                r->break_errors++;
            } else if (event.type == UART_PARITY_ERR) {
                r->parity_errors++;
            } else if (event.type == UART_FRAME_ERR) {
                r->frame_errors++;
            }
        }
        if (r->valid_checksums > 0) {
            found = true;
            found_pin = r->pin;
            found_baud = r->baud;
        }
        int64_t now = esp_timer_get_time();
        if (now - last_display >= 500000) {
            display_status(r, (uint32_t)((now - start) / 1000));
            last_display = now;
        }
    }
    display_status(r, TEST_WINDOW_MS);
}

static void display_init(void)
{
    framebuffer = heap_caps_malloc(LCD_WIDTH * LCD_HEIGHT * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!framebuffer) abort();
    gpio_config_t backlight = {
        .pin_bit_mask = 1ULL << LCD_BACKLIGHT,
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&backlight);
    gpio_set_level(LCD_BACKLIGHT, 0);
    spi_bus_config_t bus = {
        .mosi_io_num = LCD_MOSI,
        .miso_io_num = LCD_MISO,
        .sclk_io_num = LCD_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = LCD_WIDTH * LCD_HEIGHT * sizeof(uint16_t),
    };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &bus, SPI_DMA_CH_AUTO));
    esp_lcd_panel_io_handle_t io = NULL;
    esp_lcd_panel_io_spi_config_t io_config = {
        .dc_gpio_num = LCD_DC,
        .cs_gpio_num = LCD_CS,
        .pclk_hz = 40 * 1000 * 1000,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
        .spi_mode = 0,
        .trans_queue_depth = 1,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST, &io_config, &io));
    esp_lcd_panel_dev_config_t panel_config = {
        .reset_gpio_num = -1,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel = 16,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_ili9341(io, &panel_config, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel, false));
    ESP_ERROR_CHECK(esp_lcd_panel_swap_xy(panel, true));
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(panel, true, true));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));
    clear_frame(COLOR_BLACK);
    present();
    vTaskDelay(pdMS_TO_TICKS(50));
    gpio_set_level(LCD_BACKLIGHT, 1);
}

void app_main(void)
{
    display_init();
    for (int p = 0; p < 3; ++p) {
        for (int b = 0; b < 3; ++b) {
            int i = p * 3 + b;
            results[i].pin = scan_pins[p];
            results[i].baud = scan_bauds[b];
        }
    }
    while (true) {
        found = false;
        completed_cycle = false;
        for (int i = 0; i < RESULT_COUNT && !found; ++i) {
            gpio_num_t pin = results[i].pin;
            int baud = results[i].baud;
            run_scan(&results[i]);
            results[i].pin = pin;
            results[i].baud = baud;
        }
        completed_cycle = true;
        if (found) {
            scan_result_t *winner = NULL;
            for (int i = 0; i < RESULT_COUNT; ++i)
                if (results[i].pin == found_pin && results[i].baud == found_baud) winner = &results[i];
            while (winner) {
                display_status(winner, TEST_WINDOW_MS);
                vTaskDelay(pdMS_TO_TICKS(1000));
            }
        }
        display_status(&results[RESULT_COUNT - 1], TEST_WINDOW_MS);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
