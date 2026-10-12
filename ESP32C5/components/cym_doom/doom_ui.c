/* Touch-only lab launcher. ALL LVGL calls occur on CYM's main LVGL owner.
 * Worker owns engine + SD validation only. The fixed mailbox drops frames
 * rather than blocking engine/display, and never lends a worker buffer to DMA.
 */
#include "doom_ui.h"
#include "doom_session.h"
#include "doom_metrics.h"
#include "doom_contracts.h"
#include "selector_art.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "psa/crypto.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifndef WAD_PATH
#define WAD_PATH "/sdcard/doom/doom1.wad"
#endif
extern SemaphoreHandle_t sd_spi_mutex;
static const char *TAG="CYM_DOOM";
static bool (*idle_gate)(void);
static bool isolated;
static void (*selector_rotate)(bool),(*selector_back)(void);
static const char *(*record_reboot)(void);
static void selector_dialog(void);
static void license_dialog(void);
static void launch_game(void);
static void error_view(void);
static bool error_shown;
static bool (*sd_ready_gate)(void);
static void (*return_home)(void);
static doom_trigger unlock;
static lv_timer_t *navigation_timer;
static void (*normal_navigation)(void);
static void cancel_navigation(void){if(navigation_timer){lv_timer_del(navigation_timer);navigation_timer=NULL;}doom_trigger_reset(&unlock);}
static lv_obj_t *overlay,*status,*canvas,*status_scroll;
static lv_timer_t *timer;
static lv_color_t *surface;
static uint8_t *mailbox,*snapshot;
static lv_color_t frame_colors[256];
static uint16_t scale_x[480],scale_y[320];
static doom_game_layout controls;
static uint16_t mailbox_palette[256];
static SemaphoreHandle_t frame_lock;
static TaskHandle_t worker;
static bool cancel,done,started,go_home,running_view;
static unsigned held_keys,touch_keys;
static bool boot_raw,boot_fire;
static uint32_t boot_changed_ms;
static uint32_t last_hold_ms,frames,dropped;
static uint32_t displayed,overwritten,last_sequence,scale_us,ui_updates,ui_last_log,shown_fps10;
static uint32_t last_frames,last_displayed,last_dropped,last_overwritten,last_ticks,last_tick_us,last_audio_us,last_audio_writes,last_sd_us,last_sd_reads,last_sleep_us,last_frame_us,last_input_events,last_input_sum,last_scale_us,last_ui_updates,last_panel_flushes,last_panel_us;
/* Worker publishes numeric state only. Main owns all animation and text. */
enum { LOAD_STRUCTURE,LOAD_HASH,LOAD_INIT,LOAD_RUNNING };
static uint32_t load_phase,hash_bytes,hash_total,boot_ms,cooperate_ms;
static void cooperate(void){uint32_t now=(uint32_t)(esp_timer_get_time()/1000);if((uint32_t)(now-cooperate_ms)>=20){vTaskDelay(1);cooperate_ms=(uint32_t)(esp_timer_get_time()/1000);}}
static void phase(uint32_t p,const char *marker){__atomic_store_n(&load_phase,p,__ATOMIC_RELEASE);ESP_LOGI(TAG,"%s elapsed_ms=%lu",marker,(unsigned long)((uint32_t)(esp_timer_get_time()/1000)-boot_ms));}
static doom_rect fit;
#define ASSET_URL "https://github.com/JimGat/CYM-SD-Assets/tree/feature/doom-sd-assets/sdcard"
#define ASSET_HELP "\n\nGet official Freedoom Phase 1 v0.13.0:\n" ASSET_URL "\n\nCopy the contents of sdcard/ to the FAT32 SD root. Required: doom/doom1.wad (runtime /sdcard/doom/doom1.wad). License and credits accompany the separate SD assets."
static char worker_status[768];
_Static_assert(sizeof(worker_status) > sizeof(ASSET_HELP) + 128, "Asset instructions must not truncate");
static bool quitting(void){return __atomic_load_n(&cancel,__ATOMIC_ACQUIRE);}
static bool transport_take(void){return sd_spi_mutex&&xSemaphoreTake(sd_spi_mutex,pdMS_TO_TICKS(2000))==pdTRUE;}
static void transport_give(void){xSemaphoreGive(sd_spi_mutex);}
static bool bounded_read(void *ctx,uint64_t off,void *dst,size_t n){if(quitting()||off>INT32_MAX||!transport_take())return false;FILE *f=ctx;bool ok=fseek(f,(long)off,SEEK_SET)==0&&fread(dst,1,n,f)==n;transport_give();cooperate();return ok;}
static void heap_marker(const char *phase){ESP_LOGI(TAG,"%s free_psram=%lu largest_psram=%lu free_internal=%lu",phase,(unsigned long)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),(unsigned long)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM),(unsigned long)heap_caps_get_free_size(MALLOC_CAP_INTERNAL));}
/* Known-content allowlist avoids accepting arbitrary hostile lump internals
 * into the legacy renderer. Hash in fixed chunks, one shared-bus lock per read.
 * No mount, directory creation, write, download or user-SD maintenance occurs.
 */
static bool validate_asset(void){FILE *f=NULL;uint64_t size=0;if(!transport_take()){snprintf(worker_status,sizeof(worker_status),"SD transport busy");return false;}struct stat st;if(stat(WAD_PATH,&st)==0&&st.st_size>0){size=(uint64_t)st.st_size;f=fopen(WAD_PATH,"rb");}transport_give();if(!f){snprintf(worker_status,sizeof(worker_status),"Missing WAD: /sdcard/doom/doom1.wad" ASSET_HELP);return false;}
 phase(LOAD_STRUCTURE,"STRUCTURE_BEGIN");
 doom_wad_result result=doom_wad_validate(bounded_read,f,size);
 ESP_LOGI(TAG,"STRUCTURE_END result=%d elapsed_ms=%lu",result,(unsigned long)((uint32_t)(esp_timer_get_time()/1000)-boot_ms));bool valid=result==DOOM_WAD_OK;psa_hash_operation_t hash=PSA_HASH_OPERATION_INIT;uint8_t digest[32],chunk[4096];size_t digest_n=0;
 if(valid){__atomic_store_n(&hash_total,(uint32_t)size,__ATOMIC_RELEASE);phase(LOAD_HASH,"HASH_BEGIN");uint32_t hash_start=(uint32_t)(esp_timer_get_time()/1000);valid=psa_crypto_init()==PSA_SUCCESS&&psa_hash_setup(&hash,PSA_ALG_SHA_256)==PSA_SUCCESS;for(uint64_t off=0;valid&&off<size;){size_t n=size-off<sizeof(chunk)?(size_t)(size-off):sizeof(chunk);valid=bounded_read(f,off,chunk,n)&&psa_hash_update(&hash,chunk,n)==PSA_SUCCESS;if(valid){off+=n;__atomic_store_n(&hash_bytes,(uint32_t)off,__ATOMIC_RELEASE);}cooperate();}if(valid)valid=psa_hash_finish(&hash,digest,sizeof(digest),&digest_n)==PSA_SUCCESS&&digest_n==32&&doom_wad_trusted_hash(digest);psa_hash_abort(&hash);ESP_LOGI(TAG,"HASH_END bytes=%lu total=%lu hash_ms=%lu trusted=%d",(unsigned long)__atomic_load_n(&hash_bytes,__ATOMIC_ACQUIRE),(unsigned long)size,(unsigned long)((uint32_t)(esp_timer_get_time()/1000)-hash_start),valid);}
 /* Never surrender file ownership on transport failure; cancellation remains
  * pending and UI stays intact until close succeeds and worker signals done. */
 while(!transport_take())vTaskDelay(pdMS_TO_TICKS(20));fclose(f);transport_give();if(!valid)snprintf(worker_status,sizeof(worker_status),"Invalid/unsupported WAD. Use official Freedoom 0.13.0 Phase 1." ASSET_HELP);return valid;
}
static void frame_ready(const uint8_t *pixels,void *unused){(void)unused;if(xSemaphoreTake(frame_lock,pdMS_TO_TICKS(5))==pdTRUE){memcpy(mailbox,pixels,320*200);for(unsigned i=0;i<256;i++)mailbox_palette[i]=doom_session_color565((uint8_t)i);if(__atomic_load_n(&frames,__ATOMIC_RELAXED)!=__atomic_load_n(&last_sequence,__ATOMIC_RELAXED))__atomic_fetch_add(&overwritten,1,__ATOMIC_RELAXED);__atomic_fetch_add(&frames,1,__ATOMIC_RELAXED);xSemaphoreGive(frame_lock);}else __atomic_fetch_add(&dropped,1,__ATOMIC_RELAXED);}
static void engine_worker(void *unused){(void)unused;heap_marker("WORKER_BEGIN");snprintf(worker_status,sizeof(worker_status),"Validating assets...");bool valid=validate_asset();if(valid&&!quitting()){doom_gate g={.supported=true,.idle=true,.sd_ready=true,.licensed=true,.assets_valid=true,.psram_free=heap_caps_get_free_size(MALLOC_CAP_SPIRAM),.psram_largest=heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM)};if(!doom_gate_ready(g))snprintf(worker_status,sizeof(worker_status),"Not enough PSRAM: need 6 MiB contiguous + overhead.");else{phase(LOAD_INIT,"INIT_BEGIN");doom_session_set_frame(frame_ready,NULL);int rc=doom_session_start(WAD_PATH);if(!rc){phase(LOAD_RUNNING,"INIT_END");__atomic_store_n(&started,true,__ATOMIC_RELEASE);ESP_LOGI(TAG,"ENGINE_STARTED state_bytes=%lu",(unsigned long)doom_session_state_bytes());snprintf(worker_status,sizeof(worker_status),"Running - SFX only");while(!quitting()&&!rc){rc=doom_session_tick();vTaskDelay(1);}}if(rc&&!quitting())snprintf(worker_status,sizeof(worker_status),"Engine fault: %.120s",doom_session_error());while(doom_session_stop()!=0)vTaskDelay(pdMS_TO_TICKS(20));}}
heap_marker("WORKER_CLEAN");ESP_LOGI(TAG,"ENGINE_JOIN_READY frames=%lu dropped=%lu owned=%lu",(unsigned long)frames,(unsigned long)dropped,(unsigned long)doom_session_owned());/* Last worker access is publishing done. No UI/buffer access after this store. */__atomic_store_n(&done,true,__ATOMIC_RELEASE);vTaskSuspend(NULL);for(;;)vTaskDelay(pdMS_TO_TICKS(1000));}
/* Joining uses the FreeRTOS task lifecycle, not merely an arbitrary delay. UI
 * waits for done (all engine resources gone) then checks task deletion before
 * freeing the mailbox. The worker has no memory access after publishing done.
 */
/* A release store is cleanup acknowledgement, NOT a scheduling join. A worker
 * may be preempted before vTaskSuspend on SMP or at any task priority. */
static bool join_worker(TaskHandle_t *task, const bool *clean)
{
    if (!*task) return true;
    if (!__atomic_load_n(clean, __ATOMIC_ACQUIRE) ||
        eTaskGetState(*task) != eSuspended) return false;
    vTaskDelete(*task);
    *task = NULL;
    return true;
}
static void release_ui(void){/* Done publishes cleanup, not task deletion. Explicit deletion joins before UI free. */if(!join_worker(&worker,&done))return;if(timer){lv_timer_del(timer);timer=NULL;}if(overlay){lv_obj_del(overlay);overlay=NULL;}status=canvas=status_scroll=NULL;free(surface);surface=NULL;free(mailbox);mailbox=NULL;free(snapshot);snapshot=NULL;if(frame_lock){vSemaphoreDelete(frame_lock);frame_lock=NULL;}worker=NULL;held_keys=touch_keys=0;boot_raw=boot_fire=false;started=false;done=false;doom_trigger_reset(&unlock);heap_marker("UI_RELEASED");}
static void update(lv_timer_t *t){(void)t;uint32_t now=(uint32_t)(esp_timer_get_time()/1000);if(quitting()){doom_session_request_stop();}if(touch_keys&&(uint32_t)(now-last_hold_ms)>250){touch_keys=0;held_keys=boot_fire?DOOM_KEY_FIRE:0;doom_session_set_keys(held_keys);}if(__atomic_load_n(&done,__ATOMIC_ACQUIRE)){if(!join_worker(&worker,&done))return;/* Task has completed its own engine cleanup and will never touch mailbox. */if(quitting()){bool home=go_home;release_ui();if(home&&return_home)return_home();return;}if(!error_shown){error_shown=true;error_view();}return;}
 bool running=__atomic_load_n(&started,__ATOMIC_ACQUIRE);
 bool new_frame=false;
 if(running&&canvas&&surface&&xSemaphoreTake(frame_lock,0)==pdTRUE){
  if(__atomic_load_n(&frames,__ATOMIC_RELAXED)!=__atomic_load_n(&last_sequence,__ATOMIC_RELAXED)){
   memcpy(snapshot,mailbox,320*200);
   for(unsigned i=0;i<256;i++){uint16_t c=mailbox_palette[i];frame_colors[i]=lv_color_make((uint8_t)((c>>11)<<3),(uint8_t)(((c>>5)&63)<<2),(uint8_t)((c&31)<<3));}
   __atomic_store_n(&last_sequence,__atomic_load_n(&frames,__ATOMIC_RELAXED),__ATOMIC_RELAXED);new_frame=true;
  }
  xSemaphoreGive(frame_lock);
 }
 /* Main-owned snapshot isolates scaling from the engine mailbox mutex.
  * No worker/snapshot pointer is ever passed to DMA; surface stays main-owned. */
 if(new_frame){uint32_t before=(uint32_t)esp_timer_get_time();
  for(int y=0;y<fit.h;y++){const uint8_t *row=snapshot+scale_y[y]*320;lv_color_t *dst=surface+y*fit.w;
   for(int x=0;x<fit.w;x++)dst[x]=frame_colors[row[scale_x[x]]];}
  displayed++;scale_us+=(uint32_t)esp_timer_get_time()-before;lv_obj_invalidate(canvas);
 }
 if(status&&!quitting()){
  char text[160];uint32_t elapsed=(now-boot_ms)/1000,p=__atomic_load_n(&load_phase,__ATOMIC_ACQUIRE);
  static const char *markers[]={"[o...]","[.o..]","[..o.]","[...o]"};
  if(running){
   if(!running_view){running_view=true;lv_obj_set_pos(status,controls.frame.x,2);lv_obj_set_size(status,96,16);
   lv_label_set_long_mode(status,LV_LABEL_LONG_CLIP);}
   snprintf(text,sizeof(text),"%lu.%lu fps",(unsigned long)(shown_fps10/10),(unsigned long)(shown_fps10%10));
  }
  else if(p==LOAD_HASH){uint32_t n=__atomic_load_n(&hash_bytes,__ATOMIC_ACQUIRE),total=__atomic_load_n(&hash_total,__ATOMIC_ACQUIRE);
   snprintf(text,sizeof(text),"%s Hash %lu%% %lu/%lu B | %lus",markers[(now/250)%4],(unsigned long)(total?(uint64_t)n*100/total:0),(unsigned long)n,(unsigned long)total,(unsigned long)elapsed);
  }else snprintf(text,sizeof(text),"%s %s | %lus | Exit below",markers[(now/250)%4],p==LOAD_INIT?"Engine init":"Structure check",(unsigned long)elapsed);
  if(strcmp(lv_label_get_text(status),text)){lv_label_set_text(status,text);ui_updates++;}
 }
 if((uint32_t)(now-ui_last_log)>=5000){
  uint32_t ticks=DM_GET(ticks),tu=DM_GET(tick_us),au=DM_GET(audio_us),aw=DM_GET(audio_writes),su=DM_GET(sd_us),sr=DM_GET(sd_reads),sl=DM_GET(sleep_us),fu=DM_GET(frame_us),ie=DM_GET(input_events),is=DM_GET(input_age_sum);
  ESP_LOGI(TAG,"PERF interval_ms=%lu published=%lu displayed=%lu overwritten=%lu lock_dropped=%lu scale_us=%lu ticks=%lu tick_us=%lu frame_copy_us=%lu sleep_us=%lu sd_reads=%lu sd_us=%lu audio_writes=%lu audio_us=%lu audio_waits_total=%lu audio_faults_total=%lu input_events=%lu input_age_sum_ms=%lu input_age_max_ms=%lu loading_redraws=%lu panel_flushes=%lu panel_us=%lu",
   (unsigned long)(now-ui_last_log),(unsigned long)(__atomic_load_n(&frames,__ATOMIC_RELAXED)-last_frames),(unsigned long)(displayed-last_displayed),(unsigned long)(__atomic_load_n(&overwritten,__ATOMIC_RELAXED)-last_overwritten),(unsigned long)(__atomic_load_n(&dropped,__ATOMIC_RELAXED)-last_dropped),(unsigned long)(scale_us-last_scale_us),(unsigned long)(ticks-last_ticks),(unsigned long)(tu-last_tick_us),(unsigned long)(fu-last_frame_us),(unsigned long)(sl-last_sleep_us),(unsigned long)(sr-last_sd_reads),(unsigned long)(su-last_sd_us),(unsigned long)(aw-last_audio_writes),(unsigned long)(au-last_audio_us),(unsigned long)DM_GET(audio_waits),(unsigned long)DM_GET(audio_faults),(unsigned long)(ie-last_input_events),(unsigned long)(is-last_input_sum),(unsigned long)DM_GET(input_age_max),(unsigned long)(ui_updates-last_ui_updates),(unsigned long)(DM_GET(panel_flushes)-last_panel_flushes),(unsigned long)(DM_GET(panel_us)-last_panel_us));
  ESP_LOGI(TAG,"AUDIO_DIAG starts=%lu rejected=%lu samples=%lu nonzero=%lu starved=%lu overruns=%lu",
   (unsigned long)DM_GET(sfx_starts),(unsigned long)DM_GET(sfx_rejected),(unsigned long)DM_GET(audio_samples),(unsigned long)DM_GET(audio_nonzero),(unsigned long)DM_GET(audio_starved),(unsigned long)DM_GET(audio_overruns));
  shown_fps10=(uint32_t)((uint64_t)(displayed-last_displayed)*10000/(now-ui_last_log));ui_last_log=now;last_frames=__atomic_load_n(&frames,__ATOMIC_RELAXED);last_displayed=displayed;last_overwritten=__atomic_load_n(&overwritten,__ATOMIC_RELAXED);last_dropped=__atomic_load_n(&dropped,__ATOMIC_RELAXED);last_scale_us=scale_us;last_ticks=ticks;last_tick_us=tu;last_frame_us=fu;last_sleep_us=sl;last_sd_reads=sr;last_sd_us=su;last_audio_writes=aw;last_audio_us=au;last_input_events=ie;last_input_sum=is;last_ui_updates=ui_updates;last_panel_flushes=DM_GET(panel_flushes);last_panel_us=DM_GET(panel_us);
 }
}
bool doom_ui_active(void){return overlay!=NULL;}
bool doom_ui_exclusive(void){return isolated;}
static void close_selector(void)
{
 release_ui();
 if(selector_rotate)selector_rotate(false);
 if(selector_back)selector_back();
}
void doom_ui_request_exit(void){if(!overlay)return;go_home=true;held_keys=touch_keys=0;boot_raw=boot_fire=false;
 if(worker){__atomic_store_n(&cancel,true,__ATOMIC_RELEASE);doom_session_set_keys(0);doom_session_request_stop();if(status)lv_label_set_text(status,"Stopping - waiting for engine cleanup...");ESP_LOGI(TAG,"EXIT_REQUESTED");}
 else if(isolated){release_ui();if(return_home)return_home();}
 else close_selector();
}
/* Parent navigation cannot free an engine callback target. Selector owns a
 * dedicated full-screen overlay, and restores live rotation before Settings rebuild. */
void doom_ui_screen_stop(void){cancel_navigation();if(worker||isolated)doom_ui_request_exit();else if(overlay){release_ui();if(selector_rotate)selector_rotate(false);}}
/* Board snapshot path, main LVGL owner only. Normal CYM still reads one
 * point via LVGL. In isolated running/loading mode consume both points here,
 * suppress LVGL button events so its single-point releases cannot erase fire. */
bool doom_ui_touch_snapshot(const int *x,const int *y,unsigned count){
 if(!isolated||!worker||!canvas||error_shown)return false;
 unsigned mask=quitting()?0:doom_game_touch_keys(controls,x,y,count);
 if(mask&DOOM_KEY_EXIT){doom_ui_request_exit();return true;}
 last_hold_ms=(uint32_t)(esp_timer_get_time()/1000);touch_keys=mask;held_keys=quitting()?0:(touch_keys|(boot_fire?DOOM_KEY_FIRE:0));doom_session_set_keys(held_keys);return true;
}
/* Main-owner GPIO poll; no normal-CYM mapping and no startup key injection. */
void doom_ui_boot_fire(bool pressed){
 uint32_t now=(uint32_t)(esp_timer_get_time()/1000);
 if(!isolated||!worker||!canvas||error_shown||!__atomic_load_n(&started,__ATOMIC_ACQUIRE)||quitting()){
  boot_raw=boot_fire=false;boot_changed_ms=now;
  if(quitting())touch_keys=held_keys=0;
  return;
 }
 if(pressed!=boot_raw){boot_raw=pressed;boot_changed_ms=now;}
 if((uint32_t)(now-boot_changed_ms)>=20)boot_fire=boot_raw;
 held_keys=touch_keys|(boot_fire?DOOM_KEY_FIRE:0);doom_session_set_keys(held_keys);
}
static void control_event(lv_event_t *e){
 /* Fallback for host events; hardware isolated game snapshots bypass LVGL. */
 unsigned mask=(unsigned)(uintptr_t)lv_event_get_user_data(e);lv_event_code_t code=lv_event_get_code(e);
 if(code==LV_EVENT_PRESSED||code==LV_EVENT_PRESSING){last_hold_ms=(uint32_t)(esp_timer_get_time()/1000);if(mask==DOOM_KEY_EXIT){doom_ui_request_exit();return;}touch_keys|=mask;}
 else if(code==LV_EVENT_RELEASED||code==LV_EVENT_PRESS_LOST)touch_keys&=~mask;
 else return;
 held_keys=touch_keys|(boot_fire?DOOM_KEY_FIRE:0);doom_session_set_keys(held_keys);
}
static lv_obj_t *button(lv_obj_t *p,const char *text,int x,int y,int w,int h,lv_event_cb_t cb,void *data){lv_obj_t *b=lv_btn_create(p);lv_obj_set_pos(b,x,y);lv_obj_set_size(b,w,h);lv_obj_t *l=lv_label_create(b);lv_obj_set_style_text_font(l,&lv_font_montserrat_16,0);lv_label_set_text(l,text);lv_obj_center(l);lv_obj_add_event_cb(b,cb,LV_EVENT_ALL,data);return b;}
static void error_return_event(lv_event_t *e){if(lv_event_get_code(e)==LV_EVENT_CLICKED)doom_ui_request_exit();}
static void error_view(void)
{
 /* Worker is already joined. Replace controls with one accessible recovery
  * action; retain UI allocations until normal Exit releases them safely. */
 int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);
 lv_obj_clean(overlay);canvas=NULL;
 status_scroll=lv_obj_create(overlay);lv_obj_set_size(status_scroll,w,h-56);
 lv_obj_set_scroll_dir(status_scroll,LV_DIR_VER);
 status=lv_label_create(status_scroll);lv_obj_set_width(status,lv_pct(100));
 lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP);lv_obj_set_style_text_font(status,&lv_font_montserrat_12,0);
 lv_label_set_text(status,worker_status);
 button(overlay,"Return CYM",4,h-52,w-8,44,error_return_event,NULL);
 ESP_LOGW(TAG,"GAME_BOOT_ERROR intent_consumed=1 error=%s",worker_status);
}
static void launch_game(void){if(!isolated){lv_label_set_text(status,"Game startup requires reboot isolation");return;}int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);lv_obj_set_size(overlay,w,h);controls=doom_game_layout_make(w,h);fit=controls.frame;if(!fit.w||!fit.h)return;heap_marker("CONTINUE");surface=heap_caps_calloc((size_t)fit.w*fit.h,sizeof(*surface),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);mailbox=heap_caps_calloc(320*200,1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);snapshot=heap_caps_calloc(320*200,1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);frame_lock=xSemaphoreCreateMutex();if(!surface||!mailbox||!snapshot||!frame_lock){free(surface);surface=NULL;free(mailbox);mailbox=NULL;free(snapshot);snapshot=NULL;if(frame_lock){vSemaphoreDelete(frame_lock);frame_lock=NULL;}lv_label_set_text(status,"Insufficient memory for game surface");return;}lv_obj_clean(overlay);status_scroll=NULL;
 status=lv_label_create(overlay);lv_obj_set_pos(status,controls.frame.x,2);lv_obj_set_width(status,fit.w);lv_obj_set_style_text_color(status,lv_color_hex(0xd9efff),0);
 lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP);lv_obj_set_style_text_font(status,&lv_font_montserrat_12,0);lv_label_set_text(status,"Validating assets...");
 canvas=lv_canvas_create(overlay);lv_canvas_set_buffer(canvas,surface,fit.w,fit.h,LV_IMG_CF_TRUE_COLOR);lv_obj_set_pos(canvas,fit.x,fit.y);
 for(int x=0;x<fit.w;x++)scale_x[x]=x*320/fit.w;
 for(int y=0;y<fit.h;y++)scale_y[y]=y*200/fit.h;
 lv_obj_t *pad=lv_obj_create(overlay);lv_obj_remove_style_all(pad);lv_obj_set_pos(pad,controls.pad.x,controls.pad.y);lv_obj_set_size(pad,controls.pad.w,controls.pad.h);
 lv_obj_set_style_bg_color(pad,lv_color_hex(0x162d42),0);lv_obj_set_style_bg_opa(pad,LV_OPA_COVER,0);lv_obj_set_style_radius(pad,12,0);lv_obj_clear_flag(pad,LV_OBJ_FLAG_SCROLLABLE);
 static const char *directions[]={"FWD","<  >","BACK"};
 for(unsigned i=0;i<3;i++){lv_obj_t *l=lv_label_create(pad);lv_obj_set_style_text_font(l,&lv_font_montserrat_12,0);lv_obj_set_style_text_color(l,lv_color_hex(0xd9efff),0);lv_label_set_text(l,directions[i]);lv_obj_align(l,LV_ALIGN_TOP_MID,0,8+(int)i*(controls.pad.h-28)/2);}
 lv_obj_t *center=lv_obj_create(pad);lv_obj_remove_style_all(center);lv_obj_set_pos(center,controls.pad.w/2-controls.pad.w/6,controls.pad.h/2-controls.pad.h/6);lv_obj_set_size(center,controls.pad.w/3,controls.pad.h/3);lv_obj_set_style_border_width(center,1,0);lv_obj_set_style_border_color(center,lv_color_hex(0x59aec8),0);lv_obj_clear_flag(center,LV_OBJ_FLAG_CLICKABLE|LV_OBJ_FLAG_SCROLLABLE);
 doom_rect r=controls.fire;lv_obj_t *fire=button(overlay,"Fire",r.x,r.y,r.w,r.h,control_event,(void *)(uintptr_t)DOOM_KEY_FIRE);lv_obj_set_style_pad_all(fire,0,0);
 r=controls.use;lv_obj_t *use=button(overlay,"Use",r.x,r.y,r.w,r.h,control_event,(void *)(uintptr_t)DOOM_KEY_USE);lv_obj_set_style_pad_all(use,0,0);
 static const char *labels[]={"Menu","OK","Exit"};static const unsigned masks[]={DOOM_KEY_MENU,DOOM_KEY_CONFIRM,DOOM_KEY_EXIT};
 for(unsigned i=0;i<3;i++){lv_obj_t *b=button(overlay,labels[i],(int)i*w/3,h-28,w/3,28,control_event,(void *)(uintptr_t)masks[i]);lv_obj_set_style_pad_all(b,0,0);}

 cancel=done=started=go_home=error_shown=running_view=false;frames=dropped=0;shown_fps10=0;displayed=overwritten=last_sequence=scale_us=ui_updates=0;
 boot_ms=cooperate_ms=ui_last_log=(uint32_t)(esp_timer_get_time()/1000);
 load_phase=LOAD_STRUCTURE;hash_bytes=hash_total=0;memset(&doom_metrics,0,sizeof(doom_metrics));
 last_frames=last_displayed=last_dropped=last_overwritten=last_ticks=last_tick_us=last_audio_us=last_audio_writes=last_sd_us=last_sd_reads=last_sleep_us=last_frame_us=last_input_events=last_input_sum=last_scale_us=last_ui_updates=last_panel_flushes=last_panel_us=0;
 held_keys=touch_keys=0;boot_raw=boot_fire=false;boot_changed_ms=boot_ms;timer=lv_timer_create(update,20,NULL);if(!timer){lv_label_set_text(status,"Cannot allocate game timer");free(surface);surface=NULL;free(mailbox);mailbox=NULL;free(snapshot);snapshot=NULL;vSemaphoreDelete(frame_lock);frame_lock=NULL;lv_obj_del(canvas);canvas=NULL;return;}if(xTaskCreate(engine_worker,"cym_doom",24576,NULL,2,&worker)!=pdPASS){worker=NULL;lv_timer_del(timer);timer=NULL;lv_label_set_text(status,"Cannot allocate game worker");free(surface);surface=NULL;free(mailbox);mailbox=NULL;free(snapshot);snapshot=NULL;vSemaphoreDelete(frame_lock);frame_lock=NULL;lv_obj_del(canvas);canvas=NULL;return;}ESP_LOGI(TAG,"LAUNCH_REQUESTED path=%s",WAD_PATH);}
/* No game allocator exists on the normal selector/license path. Art is flash
 * indexed data; these screens and decoder cache die in reboot, not live handover. */
static void back_event(lv_event_t *e){if(lv_event_get_code(e)==LV_EVENT_CLICKED&&!isolated)close_selector();}
static void cancel_event(lv_event_t *e){if(lv_event_get_code(e)==LV_EVENT_CLICKED&&!isolated){ESP_LOGI(TAG,"LICENSE_CANCEL no_engine_allocations");selector_dialog();}}
static void continue_event(lv_event_t *e){
 if(lv_event_get_code(e)!=LV_EVENT_CLICKED||worker||isolated)return;
 if(!sd_ready_gate||!sd_ready_gate()){lv_label_set_text(status,"Missing WAD or SD not mounted: /sdcard/doom/doom1.wad" ASSET_HELP);return;}
 /* NVS set+commit and named storage refusal live in the main owner. It never
  * calls esp_restart until write admission is frozen and SD transport is held. */
 const char *error=record_reboot?record_reboot():"Reboot mode unavailable";
 if(error){lv_label_set_text_fmt(status,"Launch refused: %s. Finish that operation, then retry. CYM remains unchanged.",error);ESP_LOGW(TAG,"REBOOT_REFUSED owner=%s",error);}
}
static void doom_card_event(lv_event_t *e){if(lv_event_get_code(e)==LV_EVENT_CLICKED&&!isolated)license_dialog();}
static lv_obj_t *panel(lv_obj_t *p,int x,int y,int w,int h,uint32_t border)
{
 lv_obj_t *v=lv_obj_create(p);lv_obj_remove_style_all(v);lv_obj_set_pos(v,x,y);lv_obj_set_size(v,w,h);
 lv_obj_set_style_bg_color(v,lv_color_hex(0x0c1725),0);lv_obj_set_style_bg_opa(v,LV_OPA_80,0);
 lv_obj_set_style_border_color(v,lv_color_hex(border),0);lv_obj_set_style_border_width(v,2,0);
 lv_obj_set_style_radius(v,8,0);lv_obj_clear_flag(v,LV_OBJ_FLAG_SCROLLABLE);return v;
}
static void caption(lv_obj_t *p,const char *text,int x,int y,int width,const lv_font_t *font,uint32_t color)
{
 lv_obj_t *l=lv_label_create(p);lv_label_set_text(l,text);lv_obj_set_pos(l,x,y);lv_obj_set_width(l,width);
 lv_label_set_long_mode(l,LV_LABEL_LONG_CLIP);lv_obj_set_style_text_font(l,font,0);lv_obj_set_style_text_color(l,lv_color_hex(color),0);
}
static void make_overlay(void)
{
 if(overlay)return;
 overlay=lv_obj_create(lv_scr_act());lv_obj_remove_style_all(overlay);
 lv_obj_set_size(overlay,lv_disp_get_hor_res(NULL),lv_disp_get_ver_res(NULL));
 lv_obj_set_style_bg_color(overlay,lv_color_black(),0);lv_obj_set_style_bg_opa(overlay,LV_OPA_COVER,0);
 lv_obj_clear_flag(overlay,LV_OBJ_FLAG_SCROLLABLE);
}
static void selector_dialog(void)
{
 cancel_navigation();if(selector_rotate)selector_rotate(true);make_overlay();lv_obj_clean(overlay);status=canvas=status_scroll=NULL;
 int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);lv_obj_set_size(overlay,w,h);
 /* WS28 320x240, WS35 480x320 in software rotation 270. 8 px margins;
  * title y6..54; cards y64..h-60; Back y(h-52)..h-8 (44 px touch). */
 lv_obj_t *art=lv_img_create(overlay);lv_img_set_src(art,w==320?&selector_lab_ws28:&selector_lab_ws35);
 lv_obj_clear_flag(art,LV_OBJ_FLAG_CLICKABLE);
 lv_obj_t *head=panel(overlay,8,6,w-16,48,0x24d8e5);
 caption(head,"PinZero LABS",10,2,w-36,&lv_font_montserrat_20,0x53f0f1);
 caption(head,"AFTER HOURS / Professor Zero + ZeroBot",10,28,w-36,&lv_font_montserrat_12,0xffc277);
 int cw=(w-28)/2,ch=h-124;
 for(int i=0;i<2;i++){
  lv_obj_t *card=panel(overlay,8+i*(cw+12),64,cw,ch,i?0xee68be:0x2ddfea);
  lv_obj_t *icon=lv_img_create(card);lv_img_set_src(icon,i?&selector_handheld:&selector_portal);lv_obj_set_pos(icon,(cw-128)/2,8);
  lv_obj_clear_flag(icon,LV_OBJ_FLAG_CLICKABLE);
  caption(card,i?"ARDUBOY":"DOOM",12,ch-44,cw-24,&lv_font_montserrat_20,i?0xee68be:0x2ddfea);
  caption(card,i?"COMING SOON":"SFX / SD LIBRARY",12,ch-21,cw-24,&lv_font_montserrat_12,0xffffff);
  if(!i){lv_obj_add_flag(card,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(card,doom_card_event,LV_EVENT_CLICKED,NULL);}
  else lv_obj_clear_flag(card,LV_OBJ_FLAG_CLICKABLE); /* explicitly disabled, no emulator */
 }
 lv_obj_t *back=button(overlay,"BACK / CANCEL",8,h-52,w-16,44,back_event,NULL);
 lv_obj_set_style_bg_color(back,lv_color_hex(0x132332),0);lv_obj_set_style_border_color(back,lv_color_hex(0xeeb567),0);lv_obj_set_style_border_width(back,1,0);
 ESP_LOGI(TAG,"SELECTOR_SHOWN logical=%dx%d rotation=270 art=flash Arduboy=disabled",w,h);
}
static void license_dialog(void)
{
 make_overlay();lv_obj_clean(overlay);int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);
 lv_obj_t *scroll=lv_obj_create(overlay);lv_obj_set_size(scroll,w,h-56);lv_obj_set_scroll_dir(scroll,LV_DIR_VER);
 status=lv_label_create(scroll);lv_obj_set_width(status,lv_pct(100));lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP);lv_obj_set_style_text_font(status,&lv_font_montserrat_12,0);
 lv_label_set_text(status,"Reboot-isolated game beta - SFX only\n\nDoom engine: id Software, Simon Howard, doomgeneric and rear16/ESP-DOOM contributors. GPL version 2 or later. NO WARRANTY, including merchantability or fitness.\n\nFirmware embeds no WAD. Separately supplied official Freedoom Phase 1 v0.13.0 is licensed data, with license and credits in the SD assets.\n\nCorresponding source, build scripts, provenance, actual engine patches and full GPL license are distributed in JimGat/CYM with this firmware. See ESP32C5/components/cym_doom and docs/ws-c5-game-beta.md. Use the exact firmware commit for matching source.\n\nContinue records a one-shot mode and reboots this SAME image. Live storage owners must finish first. Game uses 270-degree controls; saved CYM orientation is unchanged. Music disabled. Exit reboots to CYM. Cancel returns to the selector.");
 button(overlay,"Continue",4,h-52,w/2-8,44,continue_event,NULL);button(overlay,"Cancel",w/2+4,h-52,w/2-8,44,cancel_event,NULL);
 ESP_LOGI(TAG,"LICENSE_SHOWN engine_not_started");
}
static void return_cym_event(lv_event_t *e){if(lv_event_get_code(e)==LV_EVENT_CLICKED)doom_ui_request_exit();}
void doom_ui_boot_start(void (*home)(void),bool sd_ready)
{
 isolated=true;return_home=home;make_overlay();int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);
 status_scroll=lv_obj_create(overlay);lv_obj_set_size(status_scroll,w,h-56);lv_obj_set_scroll_dir(status_scroll,LV_DIR_VER);
 status=lv_label_create(status_scroll);lv_obj_set_width(status,lv_pct(100));lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP);
 lv_label_set_text(status,"Game boot - intent already consumed");button(overlay,"Return CYM",4,h-52,w-8,44,return_cym_event,NULL);
 if(!sd_ready){lv_label_set_text(status,"SD unavailable / missing WAD. Return CYM reboots." ASSET_HELP);return;}
 launch_game();
}
void doom_ui_configure_selector(void (*rotate)(bool),void (*back)(void),const char *(*reboot)(void))
{selector_rotate=rotate;selector_back=back;record_reboot=reboot;}
static void navigation_due(lv_timer_t *t)
{
    lv_timer_del(t);
    navigation_timer = NULL;
    doom_trigger_reset(&unlock);
    if (!overlay && normal_navigation) normal_navigation();
}

void doom_ui_tile_click(void)
{
    if (overlay) return;
    if (navigation_timer) { lv_timer_del(navigation_timer); navigation_timer = NULL; }
    uint32_t now = (uint32_t)(esp_timer_get_time() / 1000);
    // Tile callbacks are CLICKED: each event represents a completed tap/release.
    doom_trigger_update(&unlock, now, true, true, true);
    if (doom_trigger_update(&unlock, now, false, true, true)) {
        selector_dialog();
        return;
    }
    navigation_timer = lv_timer_create(navigation_due, 800, NULL);
    if (!navigation_timer) {
        doom_trigger_reset(&unlock);
        if (normal_navigation) normal_navigation();
    }
}

void doom_ui_configure(bool (*gate)(void), void (*home)(void),
                       bool (*sd_gate)(void), void (*navigate)(void))
{
    cancel_navigation();
    idle_gate = gate;
    return_home = home;
    sd_ready_gate = sd_gate;
    normal_navigation = navigate;
}
