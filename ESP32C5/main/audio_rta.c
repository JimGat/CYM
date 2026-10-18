/* On-demand detached session owner. UI calls copy/control/stop only.
 * One dynamic IDF task owns hardware and buffers through final cleanup; it
 * never borrows LVGL. No caller-owned stack/TCB: ordinary xTaskCreate uses
 * IDF internal stack/TCB allocation and kernel idle reclamation on self-delete.
 * Cancellation never deletes a live task. Busy stays asserted across delayed
 * channel cleanup, including after the UI has detached and navigated away.
 */
#include "audio_rta.h"
#include "audio_rta_board.h"
#ifdef AUDIO_RTA_HOST
#include "audio_rta_host_port.h"
#else
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#endif
#include <string.h>
#define INTERNAL (MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)
#define EXTERNAL (MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)
typedef struct {
 void *dsp,*bus;
 audio_rta_board_t *board;
 int16_t *pcm;
 bool stop,freeze,slow,reset;
 int gain;
 TaskHandle_t worker,reaper;
 uint32_t generation;
 size_t initial_internal;
} session_t;
static portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;
static session_t *owner;
static bool busy;
static uint32_t next_generation;
static audio_rta_snapshot_t latest;
/* All public state/control accesses use the same internal critical section.
 * The worker's numerical state and hardware handles have exactly one owner. */
static bool stopping(session_t*c){portENTER_CRITICAL(&mux);bool v=c->stop;portEXIT_CRITICAL(&mux);return v;}
static void report_error(session_t*c,int error){
 portENTER_CRITICAL(&mux);latest.state=RTA_ERROR;latest.error=error;latest.timestamp_us=esp_timer_get_time();portEXIT_CRITICAL(&mux);
 ESP_LOGE("AUDIO_RTA","generation=%lu error=%d",(unsigned long)c->generation,error);
}
/* Reaper is reserved before capture, so an OOM during exit cannot strand live
 * storage. Worker voluntarily parks AFTER its final use; eSuspended is checked
 * separately from completion. On this single-core target synchronous deletion
 * of that quiescent, non-running task lets the kernel free stack/TCB safely.
 * No force-deletion of a running/blocked capture task is ever used. */
static void session_reaper(void *arg){
 session_t*c=arg;ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
 if(c->worker){
  while(eTaskGetState(c->worker)!=eSuspended)vTaskDelay(pdMS_TO_TICKS(1));
  vTaskDelete(c->worker);c->worker=NULL;
 }
 heap_caps_free(c->board);heap_caps_free(c->pcm);heap_caps_free(c->dsp);
 portENTER_CRITICAL(&mux);owner=NULL;portEXIT_CRITICAL(&mux);
 heap_caps_free(c);
 portENTER_CRITICAL(&mux);busy=false;portEXIT_CRITICAL(&mux);
 vTaskDelete(NULL);
}
static void session_worker(void *arg){
 session_t*c=arg;ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
 int error=ESP_OK,actual_gain=0;bool was_frozen=false;
 if(stopping(c))goto finish;
 error=audio_rta_board_open(c->board,c->bus,0);
 if(error)goto finish;
 size_t now=heap_caps_get_free_size(INTERNAL);
 size_t delta=c->initial_internal>now?c->initial_internal-now:0;
 portENTER_CRITICAL(&mux);latest.internal_delta=delta;portEXIT_CRITICAL(&mux);
 ESP_LOGI("AUDIO_RTA","configured48k mono16 internal_delta=%u psram=%u largest_internal=%u hardware_input_unqualified",(unsigned)delta,(unsigned)(audio_rta_dsp_bytes()+1024),(unsigned)heap_caps_get_largest_free_block(INTERNAL));
 if(delta>24*1024){error=ESP_ERR_NO_MEM;goto finish;}
 audio_rta_dsp_init(c->dsp);
 while(!stopping(c)){
  bool frozen,slow,reset;int gain;
  portENTER_CRITICAL(&mux);frozen=c->freeze;slow=c->slow;gain=c->gain;reset=c->reset;c->reset=false;portEXIT_CRITICAL(&mux);
  if(gain!=actual_gain){
   if((error=audio_rta_board_gain(c->board,gain)))break;
   actual_gain=gain;audio_rta_dsp_init(c->dsp);frozen=false;
   portENTER_CRITICAL(&mux);c->freeze=false;latest.spectrum.valid=0;latest.gain_db=gain;portEXIT_CRITICAL(&mux);
  }
  if(was_frozen&&!frozen)audio_rta_dsp_init(c->dsp);
  was_frozen=frozen;
  if(reset)audio_rta_dsp_reset_peaks(c->dsp);
  audio_rta_dsp_slow(c->dsp,slow);
  size_t count=0;int rc=audio_rta_board_read(c->board,c->pcm,512,&count);
  if(stopping(c))break;
  if(rc==ESP_ERR_INVALID_STATE){
   audio_rta_dsp_init(c->dsp);
   portENTER_CRITICAL(&mux);latest.overruns++;latest.spectrum.valid=0;portEXIT_CRITICAL(&mux);
   continue;
  }
  if(rc!=ESP_OK&&rc!=ESP_ERR_TIMEOUT){error=rc;break;}
  if(rc==ESP_ERR_TIMEOUT&&!count){error=rc;break;}
  /* Keep clocking/draining while Frozen, but leave the entire displayed model
   * and peak history alone. Re-entering Live warms fresh windows. */
  if(frozen){portENTER_CRITICAL(&mux);latest.state=RTA_FROZEN;portEXIT_CRITICAL(&mux);continue;}
  if(count)audio_rta_dsp_push(c->dsp,c->pcm,count);
  audio_rta_snapshot_t copy={0};audio_rta_dsp_snapshot(c->dsp,&copy.spectrum);
  copy.timestamp_us=esp_timer_get_time();
  portENTER_CRITICAL(&mux);
  latest.spectrum=copy.spectrum;latest.timestamp_us=copy.timestamp_us;latest.sequence++;
  latest.state=RTA_RUNNING;latest.gain_db=actual_gain;
  portEXIT_CRITICAL(&mux);
 }
finish:
 if(error)report_error(c,error);
 /* Retry ONLY resource release, never retry input startup or force deletion.
  * This detached owner survives the screen until channel callbacks are gone. */
 unsigned retries=0;
 while(audio_rta_board_close(c->board)!=ESP_OK){
  report_error(c,ESP_FAIL);retries++;vTaskDelay(pdMS_TO_TICKS(50));
  if(retries%20==1)ESP_LOGE("AUDIO_RTA","delayed_cleanup generation=%lu retry=%u",(unsigned long)c->generation,retries);
 }
 portENTER_CRITICAL(&mux);if(!error)latest.state=RTA_CLOSED;portEXIT_CRITICAL(&mux);
 xTaskNotifyGive(c->reaper);
 vTaskSuspend(NULL); /* voluntary terminal park, no buffer access after this */
}

esp_err_t audio_rta_start(void*bus,uint32_t*generation){
 if(!bus||!generation)return ESP_ERR_INVALID_ARG;
 portENTER_CRITICAL(&mux);
 if(busy){portEXIT_CRITICAL(&mux);return ESP_ERR_INVALID_STATE;}
 busy=true;uint32_t gen=++next_generation;memset(&latest,0,sizeof(latest));latest.generation=gen;latest.state=RTA_STARTING;
 portEXIT_CRITICAL(&mux);
 *generation=gen;
 size_t before=heap_caps_get_free_size(INTERNAL);
 session_t*c=heap_caps_calloc(1,sizeof(*c),INTERNAL);
 if(!c)goto fail;
 c->generation=gen;c->bus=bus;c->initial_internal=before;
 c->board=heap_caps_calloc(1,audio_rta_board_bytes(),INTERNAL);
 c->dsp=heap_caps_malloc(audio_rta_dsp_bytes(),EXTERNAL);
 c->pcm=heap_caps_malloc(1024,EXTERNAL);
 if(!c->board||!c->dsp||!c->pcm)goto fail;
 portENTER_CRITICAL(&mux);owner=c;latest.psram_bytes=audio_rta_dsp_bytes()+1024;portEXIT_CRITICAL(&mux);
 /* Installed IDF heap_idf.c pvPortMallocStack/pvPortMallocTCB use INTERNAL.
  * 6144 bytes deliberately retained, never shrunk or moved to PSRAM. */
 if(xTaskCreate(session_reaper,"rta_reaper",3072,c,1,&c->reaper)!=pdPASS)goto fail;
 if(xTaskCreate(session_worker,"audio_rta",6144,c,2,&c->worker)!=pdPASS){
  portENTER_CRITICAL(&mux);latest.state=RTA_ERROR;latest.error=ESP_ERR_NO_MEM;portEXIT_CRITICAL(&mux);
  xTaskNotifyGive(c->reaper);return ESP_ERR_NO_MEM;
 }
 xTaskNotifyGive(c->worker);
 return ESP_OK;
fail:
 if(c){heap_caps_free(c->board);heap_caps_free(c->dsp);heap_caps_free(c->pcm);heap_caps_free(c);}
 portENTER_CRITICAL(&mux);owner=NULL;busy=false;latest.state=RTA_ERROR;latest.error=ESP_ERR_NO_MEM;portEXIT_CRITICAL(&mux);
 return ESP_ERR_NO_MEM;
}
bool audio_rta_snapshot(uint32_t gen,audio_rta_snapshot_t*copy){
 if(!copy)return false;
 portENTER_CRITICAL(&mux);bool ok=gen==latest.generation;if(ok)*copy=latest;portEXIT_CRITICAL(&mux);return ok;
}
void audio_rta_controls(uint32_t gen,bool freeze,bool slow,int gain,bool reset){
 portENTER_CRITICAL(&mux);
 if(owner&&owner->generation==gen&&!owner->stop&&gain>=0&&gain<=42&&gain%6==0){
  owner->freeze=freeze;owner->slow=slow;owner->gain=gain;owner->reset|=reset;
 }
 portEXIT_CRITICAL(&mux);
}
void audio_rta_stop(uint32_t gen){
 portENTER_CRITICAL(&mux);
 if(owner&&owner->generation==gen){owner->stop=true;latest.state=RTA_STOPPING;}
 portEXIT_CRITICAL(&mux);
 /* No join under the UI lock: detached owner is bounded by finite reads and
  * continues independently on delays. Status is observable via closed(). */
}
bool audio_rta_closed(void){portENTER_CRITICAL(&mux);bool done=!busy;portEXIT_CRITICAL(&mux);return done;}
