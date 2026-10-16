/* Narrow BF3901/PARLIO backend. All hardware calls are owned by one worker;
 * there is no rearm task/queue and no SPI2/BOOT/GPS pin ownership. */
#include "camera_backend.h"
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "driver/parlio_rx.h"
#include "driver/parlio_tx.h"
#include "esp_private/parlio_rx_private.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "debug_settings.h"
#include "esp_memory_utils.h"
#include "esp_cache.h"
#include "esp_private/esp_cache_private.h"
#include "esp_idf_version.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "bf3901_regs.h"
#include "bf3901_types.h"
#define RGB 0x04
#define G3LB5 0x05
#include "bf3901_rgb565_regs.h"
#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(6,0,2)
#error "Re-audit PARLIO fake EOF and disable semantics before changing IDF"
#endif
#define PACKET_BYTES (4+486*320)
#define CAMERA_CS 12
/* Admission includes in-progress TX creation: no time-of-check/open race.
 * All app TX creation/deletion references are linker-wrapped on WS35 only. */
static portMUX_TYPE admission_lock=portMUX_INITIALIZER_UNLOCKED;
static bool reserved;
static unsigned tx_owners;
esp_err_t __real_parlio_new_tx_unit(const parlio_tx_unit_config_t *,parlio_tx_unit_handle_t *);
esp_err_t __real_parlio_del_tx_unit(parlio_tx_unit_handle_t);
esp_err_t __wrap_parlio_new_tx_unit(const parlio_tx_unit_config_t *cfg,parlio_tx_unit_handle_t *out)
{
    portENTER_CRITICAL(&admission_lock);
    bool busy=reserved;if(!busy)tx_owners++;
    portEXIT_CRITICAL(&admission_lock);
    if(busy)return ESP_ERR_INVALID_STATE;
    esp_err_t e=__real_parlio_new_tx_unit(cfg,out);
    if(e){portENTER_CRITICAL(&admission_lock);tx_owners--;portEXIT_CRITICAL(&admission_lock);}return e;
}
esp_err_t __wrap_parlio_del_tx_unit(parlio_tx_unit_handle_t tx)
{
    esp_err_t e=__real_parlio_del_tx_unit(tx);
    if(!e){portENTER_CRITICAL(&admission_lock);if(tx_owners)tx_owners--;portEXIT_CRITICAL(&admission_lock);}return e;
}
typedef struct {
    i2c_master_dev_handle_t sensor;
    parlio_rx_unit_handle_t rx;
    parlio_rx_delimiter_handle_t delimiter;
    SemaphoreHandle_t done;
    uint8_t *packet,*rgb;
    size_t packet_size;
    atomic_bool armed;
    atomic_bool frame_complete;
    atomic_uint recv_bytes;
    unsigned incomplete,header_errors,row_errors,shape_errors;
    int64_t invalid_report_at;
    bool enabled,isr_added,owns_reservation;
} ws_camera_t;
static esp_err_t reg_write(ws_camera_t *c,uint8_t reg,uint8_t value)
{uint8_t bytes[]={reg,value};return i2c_master_transmit(c->sensor,bytes,2,100);}
static bool receive_done(parlio_rx_unit_handle_t rx,const parlio_rx_event_data_t *event,void *ctx)
{
    (void)rx;ws_camera_t *c=ctx;BaseType_t wake=pdFALSE;
    if(atomic_load(&c->armed)){
        atomic_store(&c->recv_bytes,event->recv_bytes);
        atomic_store(&c->frame_complete,event->recv_bytes >= PACKET_BYTES);
        xSemaphoreGiveFromISR(c->done,&wake);
    }
    return wake==pdTRUE;
}
static void end_frame(void *ctx)
{
    ws_camera_t *c=ctx;
    /* C5 is single-core: disabling this GPIO interrupt in the owner task
     * excludes this ISR before deleting the RX unit/context. */
    if(atomic_exchange(&c->armed,false)){
        bool wake=false;
        /* callback needs armed=true while fake EOF executes synchronously */
        atomic_store(&c->armed,true);
        esp_err_t e=parlio_rx_unit_trigger_fake_eof(c->rx,&wake);
        atomic_store(&c->armed,false);
        if(e){BaseType_t w=pdFALSE;xSemaphoreGiveFromISR(c->done,&w);wake|=w==pdTRUE;}
        if(wake)portYIELD_FROM_ISR();
    }
}
static esp_err_t halt(ws_camera_t *c)
{
    if(c->isr_added){esp_err_t e=gpio_intr_disable(CAMERA_CS);if(e)return e;}
    atomic_store(&c->armed,false);
    if(c->enabled){esp_err_t e=parlio_rx_unit_disable(c->rx);if(e)return e;c->enabled=false;}
    /* IDF 6.0.2 disable stops GDMA, invalidates delimiter, clears current trans,
     * and returns the transaction semaphore. No user callback can rearm. */
    return ESP_OK;
}
esp_err_t camera_backend_close(void *ctx)
{
    ws_camera_t *c=ctx;if(!c)return ESP_OK;
    esp_err_t e=halt(c);if(e)return e;
    if(c->isr_added){e=gpio_isr_handler_remove(CAMERA_CS);if(e)return e;c->isr_added=false;}
    if(c->rx){e=parlio_del_rx_unit(c->rx);if(e)return e;c->rx=NULL;}
    if(c->delimiter){e=parlio_del_rx_delimiter(c->delimiter);if(e)return e;c->delimiter=NULL;}
    if(c->sensor){
        /* Best effort standby: a missing sensor cannot continue DMA, which is
         * already quiesced. Remove only our device, NEVER the borrowed bus. */
        reg_write(c,0x09,0x13);
        e=i2c_master_bus_rm_device(c->sensor);if(e)return e;c->sensor=NULL;
    }
    if(c->done)vSemaphoreDelete(c->done);
    free(c->packet);free(c->rgb);
    if(c->owns_reservation){portENTER_CRITICAL(&admission_lock);reserved=false;portEXIT_CRITICAL(&admission_lock);}
    memset(c,0,sizeof(*c));free(c);return ESP_OK;
}
esp_err_t camera_backend_open(void **out,void *bus)
{
    if(!out||!bus)return ESP_ERR_INVALID_ARG;
    *out=NULL;
    portENTER_CRITICAL(&admission_lock);
    bool busy=reserved||tx_owners;if(!busy)reserved=true;
    portEXIT_CRITICAL(&admission_lock);
    if(busy)return ESP_ERR_INVALID_STATE;
    ws_camera_t *c=heap_caps_calloc(1,sizeof(*c),MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    if(!c){portENTER_CRITICAL(&admission_lock);reserved=false;portEXIT_CRITICAL(&admission_lock);return ESP_ERR_NO_MEM;}
    c->owns_reservation=true;
    esp_err_t e=ESP_ERR_NO_MEM;
    c->done=xSemaphoreCreateBinary();if(!c->done)goto fail;
    size_t alignment=0;
    e=esp_cache_get_alignment(MALLOC_CAP_SPIRAM,&alignment);if(e)goto fail;
    if(alignment<64)alignment=64;
    c->packet_size=(PACKET_BYTES+alignment-1)&~(alignment-1);
    c->packet=heap_caps_aligned_calloc(alignment,1,c->packet_size,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    c->rgb=heap_caps_malloc(240*320*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    e=ESP_ERR_NO_MEM;if(!c->packet||!c->rgb)goto fail;
    /* Independent DMA admission, not merely a successful PSRAM malloc.
     * RX driver configures GDMA external-memory access and cache splitting. */
    e=ESP_ERR_NOT_SUPPORTED;if(!esp_ptr_dma_ext_capable(c->packet))goto fail;
    i2c_device_config_t cfg={.dev_addr_length=I2C_ADDR_BIT_LEN_7,.device_address=0x6e,.scl_speed_hz=100000};
    e=i2c_master_bus_add_device(bus,&cfg,&c->sensor);if(e)goto fail;
    uint8_t reg=0xfc,hi=0,lo=0;
    e=i2c_master_transmit_receive(c->sensor,&reg,1,&hi,1,100);if(e)goto fail;
    reg=0xfd;e=i2c_master_transmit_receive(c->sensor,&reg,1,&lo,1,100);if(e)goto fail;
    e=ESP_ERR_NOT_FOUND;if(hi!=0x39||lo!=0x01)goto fail;
    for(size_t i=0;i<sizeof(bf3901_spi_2bit_24Minput_240x320_rgb565_le_20fps)/sizeof(bf3901_reginfo_t);++i){
        bf3901_reginfo_t r=bf3901_spi_2bit_24Minput_240x320_rgb565_le_20fps[i];
        if(r.reg==BF3901_REG_DELAY)vTaskDelay(pdMS_TO_TICKS(r.val)+1);
        else {e=reg_write(c,r.reg,r.val);if(e)goto fail;}
    }
    parlio_rx_unit_config_t rx={.trans_queue_depth=1,.max_recv_size=c->packet_size,.dma_burst_size=32,.data_width=2,
        .clk_src=PARLIO_CLK_SRC_EXTERNAL,.ext_clk_freq_hz=24000000,.exp_clk_freq_hz=24000000,
        .clk_in_gpio_num=11,.clk_out_gpio_num=-1,.valid_gpio_num=CAMERA_CS};
    for(int i=0;i<PARLIO_RX_UNIT_MAX_DATA_WIDTH;i++)rx.data_gpio_nums[i]=-1;
    rx.data_gpio_nums[0]=0;rx.data_gpio_nums[1]=1;
    e=parlio_new_rx_unit(&rx,&c->rx);if(e)goto fail;
    parlio_rx_level_delimiter_config_t delim={.valid_sig_line_id=PARLIO_RX_UNIT_MAX_DATA_WIDTH-1,
        .sample_edge=PARLIO_SAMPLE_EDGE_POS,.bit_pack_order=PARLIO_BIT_PACK_ORDER_MSB,.eof_data_len=0,.flags.active_low_en=1};
    e=parlio_new_rx_level_delimiter(&delim,&c->delimiter);if(e)goto fail;
    parlio_rx_event_callbacks_t cb={.on_receive_done=receive_done};
    e=parlio_rx_unit_register_event_callbacks(c->rx,&cb,c);if(e)goto fail;
    e=gpio_install_isr_service(0);if(e!=ESP_OK&&e!=ESP_ERR_INVALID_STATE)goto fail;
    e=gpio_set_intr_type(CAMERA_CS,GPIO_INTR_POSEDGE);if(e)goto fail;
    e=gpio_isr_handler_add(CAMERA_CS,end_frame,c);if(e)goto fail;c->isr_added=true;
    e=gpio_intr_disable(CAMERA_CS);if(e)goto fail;
    *out=c;return ESP_OK;
fail:
    if(camera_backend_close(c)!=ESP_OK)*out=c; /* retained, blocks all reentry */
    return e;
}
/* Owner-task only: no formatting/logging in ISR. Error counts are bounded
 * summaries, never packet headers, pixels or decoded content. Zero denotes
 * incomplete RX; unpack returns distinct shape/frame-header/row-header codes. */
static esp_err_t invalid_response(ws_camera_t *c,int unpack_error)
{
    if(!unpack_error)c->incomplete++;
    else if(unpack_error==-2)c->header_errors++;
    else if(unpack_error==-3)c->row_errors++;
    else c->shape_errors++;
    if(cym_debug_enabled()){
        int64_t now=esp_timer_get_time();
        if(!c->invalid_report_at||now-c->invalid_report_at>=5000000){
            c->invalid_report_at=now;
            ESP_LOGI("qr_camera","invalid_response incomplete=%u header=%u row=%u shape=%u recv_bytes=%u",
                c->incomplete,c->header_errors,c->row_errors,c->shape_errors,(unsigned)atomic_load(&c->recv_bytes));
        }
    }
    return ESP_ERR_INVALID_RESPONSE;
}
esp_err_t camera_backend_acquire(void *ctx,cym_camera_frame_t *f,unsigned timeout)
{
    ws_camera_t *c=ctx;
    if(!c||!f||timeout>500)return ESP_ERR_INVALID_ARG;
    while(xSemaphoreTake(c->done,0)==pdTRUE){}
    atomic_store(&c->frame_complete,false);
    atomic_store(&c->recv_bytes,0);
    esp_err_t e=parlio_rx_unit_enable(c->rx,true);if(e)return e;c->enabled=true;
    parlio_receive_config_t recv={.delimiter=c->delimiter};
    e=parlio_rx_unit_receive(c->rx,c->packet,c->packet_size,&recv);if(e)goto done;
    atomic_store(&c->armed,true);
    e=gpio_intr_enable(CAMERA_CS);if(e)goto done;
    e=reg_write(c,0x09,0x03);if(e)goto done;
    e=xSemaphoreTake(c->done,pdMS_TO_TICKS(timeout))==pdTRUE ? ESP_OK : ESP_ERR_TIMEOUT;
done:
    {esp_err_t stop=halt(c);if(stop)return stop;}
    reg_write(c,0x09,0x13);
    if(e)return e;
    if(!atomic_load(&c->frame_complete))return invalid_response(c,0);
    int unpack=cym_camera_unpack_bf3901(c->packet,atomic_load(&c->recv_bytes),c->rgb,153600);
    if(unpack)return invalid_response(c,unpack);
    *f=(cym_camera_frame_t){c->rgb,240,320,480,CYM_CAMERA_RGB565_LE};return ESP_OK;
}
void camera_backend_release(void *ctx){(void)ctx;}
