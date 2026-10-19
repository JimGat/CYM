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
#include "debug_settings.h"
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
 TaskHandle_t worker;
 uint32_t generation;
 size_t initial_internal;
 int64_t last_yield_us,last_diag_us;
 uint32_t last_frames;
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
/* All device callbacks are quiescent before the worker releases owned buffers.
 * The dynamic worker's stack/TCB belong to FreeRTOS, not to session_t. They
 * must never be freed here: vTaskDelete(NULL) leaves their reclamation to idle.
 * No second cleanup task/stack is needed. closed() means session resources are
 * released; kernel-owned task storage may still await the next idle pass. */
static void session_release(session_t*c){
 portENTER_CRITICAL(&mux);owner=NULL;portEXIT_CRITICAL(&mux);
 heap_caps_free(c->board);heap_caps_free(c->pcm);heap_caps_free(c->dsp);
 heap_caps_free(c);
 portENTER_CRITICAL(&mux);busy=false;portEXIT_CRITICAL(&mux);
}
static void memory_boundary(const char*stage){
 ESP_LOGI("AUDIO_RTA","stage=%s internal_free=%u internal_largest=%u dma_free=%u dma_largest=%u",
 stage,(unsigned)heap_caps_get_free_size(INTERNAL),(unsigned)heap_caps_get_largest_free_block(INTERNAL),
 (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA),
 (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA));
}
/* A ready I2S queue is not a scheduling point. A real tick block lets
 * lower-priority main/UI and IDLE run; taskYIELD alone cannot do that. */
static bool prepare_checkpoint(void *arg){
 session_t*c=arg;vTaskDelay(1);c->last_yield_us=esp_timer_get_time();return !stopping(c);
}
/* Runtime checkpoints check cancellation often; unlike immutable preparation,
 * they block only when the scheduling budget expires, never once per read/FFT. */
static bool work_checkpoint(void*arg){
 session_t*c=arg;if(stopping(c))return false;
 if(esp_timer_get_time()-c->last_yield_us>=50000)return prepare_checkpoint(c);
 return true;
}
static void reset_history(session_t*c,bool keep_display){
 audio_rta_dsp_reset(c->dsp);c->last_frames=0;
 portENTER_CRITICAL(&mux);latest.history_resets++;if(!keep_display)latest.spectrum.valid=0;portEXIT_CRITICAL(&mux);
}
static void record_work(session_t*c,int64_t start){
 uint32_t elapsed=(uint32_t)(esp_timer_get_time()-start);
 portENTER_CRITICAL(&mux);if(elapsed>latest.max_work_us)latest.max_work_us=elapsed;portEXIT_CRITICAL(&mux);
 int64_t now=esp_timer_get_time();if(now-c->last_diag_us<1000000)return;c->last_diag_us=now;
 if(!cym_debug_enabled())return;
 audio_rta_snapshot_t s;portENTER_CRITICAL(&mux);s=latest;portEXIT_CRITICAL(&mux);
 /* Existing primary USB logger only. No raw PCM, files, upload or UART change.
  * Deci-dB integers avoid expensive/unsupported logging float format paths. */
 ESP_LOGI("AUDIO_RTA","diag generation=%lu state=%d samples=%llu history_samples=%llu sequence=%lu frames=%llu valid=%06lx overruns=%lu resets=%lu reads=%llu read_us=%llu process_us=%llu max_read_us=%lu max_process_us=%lu max_work_us=%lu rms_x10=%d peak_x10=%d clips=%lu",
 (unsigned long)s.generation,s.state,(unsigned long long)s.input_samples,(unsigned long long)s.spectrum.samples,
 (unsigned long)s.sequence,(unsigned long long)s.analysis_frames,(unsigned long)s.spectrum.valid,
 (unsigned long)s.overruns,(unsigned long)s.history_resets,(unsigned long long)s.read_calls,
 (unsigned long long)s.read_us,(unsigned long long)s.process_us,(unsigned long)s.max_read_us,
 (unsigned long)s.max_process_us,(unsigned long)s.max_work_us,(int)(s.spectrum.rms*10),
 (int)(s.spectrum.sample_peak*10),(unsigned long)s.spectrum.clips);
}
static void session_worker(void *arg){
 session_t*c=arg;ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
 int error=ESP_OK,actual_gain=0;bool was_frozen=false;c->last_diag_us=esp_timer_get_time();
 if(stopping(c))goto finish;
 memory_boundary("before_dsp_prepare");
 /* Prepare before enabling RX: software-float table work must not overflow it. */
 if(!audio_rta_dsp_prepare(c->dsp,prepare_checkpoint,c)||stopping(c))goto finish;
 memory_boundary("before_i2s");
 error=audio_rta_board_open(c->board,c->bus,0);
 if(error)goto finish;
 size_t now=heap_caps_get_free_size(INTERNAL);
 size_t delta=c->initial_internal>now?c->initial_internal-now:0;
 portENTER_CRITICAL(&mux);latest.internal_delta=delta;portEXIT_CRITICAL(&mux);
 ESP_LOGI("AUDIO_RTA","configured48k mono16 internal_delta=%u psram=%u largest_internal=%u hardware_input_unqualified",(unsigned)delta,(unsigned)(audio_rta_dsp_bytes()+1024),(unsigned)heap_caps_get_largest_free_block(INTERNAL));
 if(delta>24*1024){error=ESP_ERR_NO_MEM;goto finish;}
 while(!stopping(c)){
  /* Applies to every path, even frozen/overrun/empty immediately-ready reads.
   * Do not sleep per read: a 100-Hz tick nearly fills the 512-sample period. */
  if(esp_timer_get_time()-c->last_yield_us>=50000&&!prepare_checkpoint(c))break;
  int64_t work_start=esp_timer_get_time();
  bool frozen,slow,reset;int gain;
  portENTER_CRITICAL(&mux);frozen=c->freeze;slow=c->slow;gain=c->gain;reset=c->reset;c->reset=false;portEXIT_CRITICAL(&mux);
  if(gain!=actual_gain){
   if((error=audio_rta_board_gain(c->board,gain))){record_work(c,work_start);break;}
   actual_gain=gain;reset_history(c,false);frozen=false;
   portENTER_CRITICAL(&mux);c->freeze=false;latest.spectrum.valid=0;latest.gain_db=gain;portEXIT_CRITICAL(&mux);
  }
  if(was_frozen&&!frozen)reset_history(c,false);
  was_frozen=frozen;
  if(reset)audio_rta_dsp_reset_peaks(c->dsp);
  audio_rta_dsp_slow(c->dsp,slow);
  int64_t read_start=esp_timer_get_time();
  bool discontinuity=false;
  size_t count=0;int rc=audio_rta_board_read(c->board,c->pcm,512,&count,&discontinuity);
  uint32_t read_elapsed=(uint32_t)(esp_timer_get_time()-read_start);
  portENTER_CRITICAL(&mux);latest.read_calls++;latest.input_samples+=count;latest.read_us+=read_elapsed;
  if(read_elapsed>latest.max_read_us)latest.max_read_us=read_elapsed;
  portEXIT_CRITICAL(&mux);
  if(stopping(c)){record_work(c,work_start);break;}
  /* A driver failure is terminal, even if an ISR also reported lost data.
   * Only an otherwise successful/partial-timeout read may recover as a gap. */
  if(rc!=ESP_OK&&rc!=ESP_ERR_TIMEOUT){error=rc;record_work(c,work_start);break;}
  if(discontinuity){
   reset_history(c,frozen);
   portENTER_CRITICAL(&mux);latest.overruns++;if(frozen)latest.state=RTA_FROZEN;portEXIT_CRITICAL(&mux);
   record_work(c,work_start);continue;
  }
  if(rc==ESP_ERR_TIMEOUT&&!count){error=rc;record_work(c,work_start);break;}
  /* Keep clocking/draining while Frozen, but leave the entire displayed model
   * and peak history alone. Re-entering Live warms fresh windows. */
  if(frozen){portENTER_CRITICAL(&mux);latest.state=RTA_FROZEN;portEXIT_CRITICAL(&mux);record_work(c,work_start);continue;}
  if(!count){record_work(c,work_start);continue;}
  int64_t process_start=esp_timer_get_time();
  bool processed=audio_rta_dsp_push_checked(c->dsp,c->pcm,count,work_checkpoint,c);
  audio_rta_snapshot_t copy={0};if(processed)audio_rta_dsp_snapshot(c->dsp,&copy.spectrum);
  uint32_t process_elapsed=(uint32_t)(esp_timer_get_time()-process_start);
  portENTER_CRITICAL(&mux);latest.process_us+=process_elapsed;
  if(process_elapsed>latest.max_process_us)latest.max_process_us=process_elapsed;
  portEXIT_CRITICAL(&mux);
  if(!processed||stopping(c)){record_work(c,work_start);break;}
  copy.timestamp_us=esp_timer_get_time();
  portENTER_CRITICAL(&mux);
  latest.analysis_frames+=copy.spectrum.frames-c->last_frames;c->last_frames=copy.spectrum.frames;
  latest.spectrum=copy.spectrum;latest.timestamp_us=copy.timestamp_us;latest.sequence++;
  latest.state=RTA_RUNNING;latest.gain_db=actual_gain;
  portEXIT_CRITICAL(&mux);record_work(c,work_start);
 }
finish:
 if(error){memory_boundary("failure");report_error(c,error);}
 /* Retry ONLY resource release, never retry input startup or force deletion.
  * This detached owner survives the screen until channel callbacks are gone. */
 unsigned retries=0;
 while(audio_rta_board_close(c->board)!=ESP_OK){
  report_error(c,ESP_FAIL);retries++;vTaskDelay(pdMS_TO_TICKS(50));
  if(retries%20==1)ESP_LOGE("AUDIO_RTA","delayed_cleanup generation=%lu retry=%u",(unsigned long)c->generation,retries);
 }
 portENTER_CRITICAL(&mux);if(!error)latest.state=RTA_CLOSED;portEXIT_CRITICAL(&mux);
 memory_boundary("device_released");
 session_release(c); /* final access to caller-owned context */
 vTaskDelete(NULL); /* kernel-owned stack/TCB: idle reclaims, never application */
}

esp_err_t audio_rta_start(void*bus,uint32_t*generation){
 if(!bus||!generation)return ESP_ERR_INVALID_ARG;
 portENTER_CRITICAL(&mux);
 if(busy){portEXIT_CRITICAL(&mux);return ESP_ERR_INVALID_STATE;}
 busy=true;uint32_t gen=++next_generation;memset(&latest,0,sizeof(latest));latest.generation=gen;latest.state=RTA_STARTING;
 latest.spectrum.rms=latest.spectrum.sample_peak=AUDIO_RTA_FLOOR;
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
 memory_boundary("before_task");
 if(xTaskCreate(session_worker,"audio_rta",6144,c,2,&c->worker)!=pdPASS)goto fail;
 xTaskNotifyGive(c->worker);
 return ESP_OK;
fail:
 /* Unpublish before any free; concurrent Stop/Controls must see no owner. */
 portENTER_CRITICAL(&mux);owner=NULL;portEXIT_CRITICAL(&mux);
 if(c){heap_caps_free(c->board);heap_caps_free(c->dsp);heap_caps_free(c->pcm);heap_caps_free(c);}
 portENTER_CRITICAL(&mux);owner=NULL;busy=false;latest.state=RTA_ERROR;latest.error=ESP_ERR_NO_MEM;portEXIT_CRITICAL(&mux);
 return ESP_ERR_NO_MEM;
}
bool audio_rta_snapshot(uint32_t gen,audio_rta_snapshot_t*copy){
 if(!copy)return false;
 portENTER_CRITICAL(&mux);bool ok=gen==latest.generation;if(ok)*copy=latest;portEXIT_CRITICAL(&mux);
 if(ok)copy->stale=copy->state==RTA_RUNNING&&copy->sequence&&esp_timer_get_time()-copy->timestamp_us>500000;
 return ok;
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
