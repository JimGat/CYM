/* Touch-only lab launcher. ALL LVGL calls occur on CYM's main LVGL owner.
 * Worker owns engine + SD validation only. The fixed mailbox drops frames
 * rather than blocking engine/display, and never lends a worker buffer to DMA.
 */
#include "doom_ui.h"
#include "doom_session.h"
#include "doom_contracts.h"
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
#define WAD_PATH "/sdcard/doom/doom1.wad"
extern SemaphoreHandle_t sd_spi_mutex;
static const char *TAG="CYM_DOOM";
static bool (*idle_gate)(void);
static void (*return_home)(void);
static doom_trigger unlock;
static lv_obj_t *overlay,*status,*canvas,*status_scroll;
static lv_timer_t *timer;
static lv_color_t *surface;
static uint8_t *mailbox;
static uint16_t mailbox_palette[256];
static SemaphoreHandle_t frame_lock;
static TaskHandle_t worker;
static bool cancel,done,started,go_home;
static unsigned held_keys;
static uint32_t last_hold_ms,frames,dropped;
static doom_rect fit;
#define ASSET_URL "https://github.com/JimGat/CYM-SD-Assets/tree/feature/doom-sd-assets/sdcard"
#define ASSET_HELP "\n\nGet official Freedoom Phase 1 v0.13.0:\n" ASSET_URL "\n\nCopy the contents of sdcard/ to the FAT32 SD root. Required: doom/doom1.wad (runtime /sdcard/doom/doom1.wad). License and credits accompany the separate SD assets."
static char worker_status[768];
_Static_assert(sizeof(worker_status) > sizeof(ASSET_HELP) + 128, "Asset instructions must not truncate");
static bool quitting(void){return __atomic_load_n(&cancel,__ATOMIC_ACQUIRE);}
static bool transport_take(void){return sd_spi_mutex&&xSemaphoreTake(sd_spi_mutex,pdMS_TO_TICKS(2000))==pdTRUE;}
static void transport_give(void){xSemaphoreGive(sd_spi_mutex);}
static bool bounded_read(void *ctx,uint64_t off,void *dst,size_t n){if(quitting()||off>INT32_MAX||!transport_take())return false;FILE *f=ctx;bool ok=fseek(f,(long)off,SEEK_SET)==0&&fread(dst,1,n,f)==n;transport_give();return ok;}
static void heap_marker(const char *phase){ESP_LOGI(TAG,"%s free_psram=%lu largest_psram=%lu free_internal=%lu",phase,(unsigned long)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),(unsigned long)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM),(unsigned long)heap_caps_get_free_size(MALLOC_CAP_INTERNAL));}
/* Known-content allowlist avoids accepting arbitrary hostile lump internals
 * into the legacy renderer. Hash in fixed chunks, one shared-bus lock per read.
 * No mount, directory creation, write, download or user-SD maintenance occurs.
 */
static bool validate_asset(void){FILE *f=NULL;uint64_t size=0;if(!transport_take()){snprintf(worker_status,sizeof(worker_status),"SD transport busy");return false;}struct stat st;if(stat(WAD_PATH,&st)==0&&st.st_size>0){size=(uint64_t)st.st_size;f=fopen(WAD_PATH,"rb");}transport_give();if(!f){snprintf(worker_status,sizeof(worker_status),"Missing WAD: /sdcard/doom/doom1.wad" ASSET_HELP);return false;}
 doom_wad_result result=doom_wad_validate(bounded_read,f,size);bool valid=result==DOOM_WAD_OK;psa_hash_operation_t hash=PSA_HASH_OPERATION_INIT;uint8_t digest[32],chunk[4096];size_t digest_n=0;
 if(valid){valid=psa_crypto_init()==PSA_SUCCESS&&psa_hash_setup(&hash,PSA_ALG_SHA_256)==PSA_SUCCESS;for(uint64_t off=0;valid&&off<size;){size_t n=size-off<sizeof(chunk)?(size_t)(size-off):sizeof(chunk);valid=bounded_read(f,off,chunk,n)&&psa_hash_update(&hash,chunk,n)==PSA_SUCCESS;off+=n;vTaskDelay(1);}if(valid)valid=psa_hash_finish(&hash,digest,sizeof(digest),&digest_n)==PSA_SUCCESS&&digest_n==32&&doom_wad_trusted_hash(digest);psa_hash_abort(&hash);}
 /* Never surrender file ownership on transport failure; cancellation remains
  * pending and UI stays intact until close succeeds and worker signals done. */
 while(!transport_take())vTaskDelay(pdMS_TO_TICKS(20));fclose(f);transport_give();if(!valid)snprintf(worker_status,sizeof(worker_status),"Invalid/unsupported WAD. Use official Freedoom 0.13.0 Phase 1." ASSET_HELP);return valid;
}
static void frame_ready(const uint8_t *pixels,void *unused){(void)unused;if(xSemaphoreTake(frame_lock,pdMS_TO_TICKS(5))==pdTRUE){memcpy(mailbox,pixels,320*200);for(unsigned i=0;i<256;i++)mailbox_palette[i]=doom_session_color565((uint8_t)i);frames++;xSemaphoreGive(frame_lock);}else dropped++;}
static void engine_worker(void *unused){(void)unused;heap_marker("WORKER_BEGIN");snprintf(worker_status,sizeof(worker_status),"Validating assets...");bool valid=validate_asset();if(valid&&!quitting()){doom_gate g={.supported=true,.idle=true,.sd_ready=true,.licensed=true,.assets_valid=true,.psram_free=heap_caps_get_free_size(MALLOC_CAP_SPIRAM),.psram_largest=heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM)};if(!doom_gate_ready(g))snprintf(worker_status,sizeof(worker_status),"Not enough PSRAM: need 6 MiB contiguous + overhead.");else{doom_session_set_frame(frame_ready,NULL);int rc=doom_session_start(WAD_PATH);if(!rc){__atomic_store_n(&started,true,__ATOMIC_RELEASE);ESP_LOGI(TAG,"ENGINE_STARTED state_bytes=%lu",(unsigned long)doom_session_state_bytes());snprintf(worker_status,sizeof(worker_status),"Running - silent");while(!quitting()&&!rc){rc=doom_session_tick();vTaskDelay(1);}}if(rc&&!quitting())snprintf(worker_status,sizeof(worker_status),"Engine fault: %.120s",doom_session_error());while(doom_session_stop()!=0)vTaskDelay(pdMS_TO_TICKS(20));}}
heap_marker("WORKER_CLEAN");ESP_LOGI(TAG,"ENGINE_JOIN_READY frames=%lu dropped=%lu owned=%lu",(unsigned long)frames,(unsigned long)dropped,(unsigned long)doom_session_owned());/* Last worker access is publishing done. No UI/buffer access after this store. */__atomic_store_n(&done,true,__ATOMIC_RELEASE);vTaskSuspend(NULL);for(;;)vTaskDelay(pdMS_TO_TICKS(1000));}
/* Joining uses the FreeRTOS task lifecycle, not merely an arbitrary delay. UI
 * waits for done (all engine resources gone) then checks task deletion before
 * freeing the mailbox. The worker has no memory access after publishing done.
 */
static void release_ui(void){/* Done publishes cleanup, not task deletion. Explicit deletion joins before UI free. */if(worker){if(!__atomic_load_n(&done,__ATOMIC_ACQUIRE))return;vTaskDelete(worker);worker=NULL;}if(timer){lv_timer_del(timer);timer=NULL;}if(overlay){lv_obj_del(overlay);overlay=NULL;}status=canvas=status_scroll=NULL;free(surface);surface=NULL;free(mailbox);mailbox=NULL;if(frame_lock){vSemaphoreDelete(frame_lock);frame_lock=NULL;}worker=NULL;held_keys=0;started=false;done=false;doom_trigger_reset(&unlock);heap_marker("UI_RELEASED");}
static void update(lv_timer_t *t){(void)t;uint32_t now=(uint32_t)(esp_timer_get_time()/1000);if(quitting()){doom_session_request_stop();}if(held_keys&&(uint32_t)(now-last_hold_ms)>250){held_keys=0;doom_session_set_keys(0);}if(__atomic_load_n(&done,__ATOMIC_ACQUIRE)){/* Task has completed its own engine cleanup and will never touch mailbox. */if(quitting()){bool home=go_home;release_ui();if(home&&return_home)return_home();return;}if(status){lv_label_set_text(status,worker_status);if(status_scroll){lv_obj_set_height(status_scroll,lv_disp_get_ver_res(NULL)-90);lv_obj_move_foreground(status_scroll);}if(canvas)lv_obj_add_flag(canvas,LV_OBJ_FLAG_HIDDEN);}return;}
 if(__atomic_load_n(&started,__ATOMIC_ACQUIRE)&&canvas&&surface&&xSemaphoreTake(frame_lock,0)==pdTRUE){for(int y=0;y<fit.h;y++)for(int x=0;x<fit.w;x++){uint8_t i=mailbox[(y*200/fit.h)*320+x*320/fit.w];uint16_t c=mailbox_palette[i];surface[y*fit.w+x]=lv_color_make((uint8_t)((c>>11)<<3),(uint8_t)(((c>>5)&63)<<2),(uint8_t)((c&31)<<3));}xSemaphoreGive(frame_lock);lv_obj_invalidate(canvas);}if(status&&!__atomic_load_n(&started,__ATOMIC_ACQUIRE))lv_label_set_text(status,"Validating assets...");}
bool doom_ui_active(void){return overlay!=NULL;}
void doom_ui_request_exit(void){if(!overlay)return;go_home=true;if(worker){__atomic_store_n(&cancel,true,__ATOMIC_RELEASE);doom_session_set_keys(0);doom_session_request_stop();if(status)lv_label_set_text(status,"Stopping - waiting for engine cleanup...");ESP_LOGI(TAG,"EXIT_REQUESTED");}else{release_ui();if(return_home)return_home();}}
/* Screen stop never deletes engine-owned memory or callback targets while a
 * worker remains live. The overlay is a child of lv_scr_act, NOT function_page;
 * unexpected underlying navigation cannot delete the worker's visible surface.
 */
void doom_ui_screen_stop(void){doom_trigger_reset(&unlock);if(worker)doom_ui_request_exit();}
static void control_event(lv_event_t *e){unsigned mask=(unsigned)(uintptr_t)lv_event_get_user_data(e);lv_event_code_t code=lv_event_get_code(e);if(code==LV_EVENT_PRESSED||code==LV_EVENT_PRESSING){last_hold_ms=(uint32_t)(esp_timer_get_time()/1000);if(mask==DOOM_KEY_EXIT){doom_ui_request_exit();return;}held_keys=mask;doom_session_set_keys(mask);}else if(code==LV_EVENT_RELEASED||code==LV_EVENT_PRESS_LOST){held_keys=0;doom_session_set_keys(0);}}
static lv_obj_t *button(lv_obj_t *p,const char *text,int x,int y,int w,int h,lv_event_cb_t cb,void *data){lv_obj_t *b=lv_btn_create(p);lv_obj_set_pos(b,x,y);lv_obj_set_size(b,w,h);lv_obj_t *l=lv_label_create(b);lv_label_set_text(l,text);lv_obj_center(l);lv_obj_add_event_cb(b,cb,LV_EVENT_ALL,data);return b;}
static void continue_event(lv_event_t *e){if(lv_event_get_code(e)!=LV_EVENT_CLICKED||worker)return;if(!idle_gate||!idle_gate()){lv_label_set_text(status,"Launch refused: CYM tools/radios/SD are not idle.");return;}int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);fit=doom_scale_fit(w,h-120);if(!fit.w||!fit.h)return;heap_marker("CONTINUE");surface=heap_caps_calloc((size_t)fit.w*fit.h,sizeof(*surface),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);mailbox=heap_caps_calloc(320*200,1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);frame_lock=xSemaphoreCreateMutex();if(!surface||!mailbox||!frame_lock){free(surface);surface=NULL;free(mailbox);mailbox=NULL;if(frame_lock){vSemaphoreDelete(frame_lock);frame_lock=NULL;}lv_label_set_text(status,"Insufficient memory for game surface");return;}lv_obj_clean(overlay);status_scroll=lv_obj_create(overlay);lv_obj_set_pos(status_scroll,0,0);lv_obj_set_size(status_scroll,w,30);lv_obj_set_scroll_dir(status_scroll,LV_DIR_VER);lv_obj_set_style_pad_all(status_scroll,4,0);status=lv_label_create(status_scroll);lv_label_set_text(status,"Validating assets...");lv_obj_set_width(status,lv_pct(100));lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP);lv_obj_set_style_text_font(status,&lv_font_montserrat_12,0);canvas=lv_canvas_create(overlay);lv_canvas_set_buffer(canvas,surface,fit.w,fit.h,LV_IMG_CF_TRUE_COLOR);lv_obj_set_pos(canvas,fit.x,30+fit.y);
 static const char *labels[]={"Left","Move","Right","Back","Fire","Use","Menu","OK","Exit"};static const unsigned masks[]={DOOM_KEY_LEFT,DOOM_KEY_FORWARD,DOOM_KEY_RIGHT,DOOM_KEY_BACK,DOOM_KEY_FIRE,DOOM_KEY_USE,DOOM_KEY_MENU,DOOM_KEY_CONFIRM,DOOM_KEY_EXIT};for(unsigned i=0;i<9;i++){int x=(int)(i%3)*w/3;button(overlay,labels[i],x,h-90+(int)(i/3)*30,w/3,29,control_event,(void *)(uintptr_t)masks[i]);}
 cancel=done=started=go_home=false;frames=dropped=0;held_keys=0;timer=lv_timer_create(update,33,NULL);if(!timer){lv_label_set_text(status,"Cannot allocate game timer");free(surface);surface=NULL;free(mailbox);mailbox=NULL;vSemaphoreDelete(frame_lock);frame_lock=NULL;lv_obj_del(canvas);canvas=NULL;return;}if(xTaskCreate(engine_worker,"cym_doom",24576,NULL,2,&worker)!=pdPASS){worker=NULL;lv_timer_del(timer);timer=NULL;lv_label_set_text(status,"Cannot allocate game worker");free(surface);surface=NULL;free(mailbox);mailbox=NULL;vSemaphoreDelete(frame_lock);frame_lock=NULL;lv_obj_del(canvas);canvas=NULL;return;}ESP_LOGI(TAG,"LAUNCH_REQUESTED path=%s",WAD_PATH);}
static void cancel_event(lv_event_t *e){if(lv_event_get_code(e)==LV_EVENT_CLICKED){ESP_LOGI(TAG,"LICENSE_CANCEL no_engine_allocations");release_ui();}}
static void license_dialog(void){if(overlay)return;int w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);overlay=lv_obj_create(lv_scr_act());lv_obj_remove_style_all(overlay);lv_obj_set_size(overlay,w,h);lv_obj_set_style_bg_color(overlay,lv_color_black(),0);lv_obj_set_style_bg_opa(overlay,LV_OPA_COVER,0);lv_obj_clear_flag(overlay,LV_OBJ_FLAG_SCROLLABLE);lv_obj_t *scroll=lv_obj_create(overlay);lv_obj_set_size(scroll,w,h-42);lv_obj_set_scroll_dir(scroll,LV_DIR_VER);status=lv_label_create(scroll);lv_obj_set_width(status,lv_pct(100));lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP);lv_obj_set_style_text_font(status,&lv_font_montserrat_12,0);lv_label_set_text(status,"Silent game beta\n\nDoom engine: id Software, Simon Howard, doomgeneric and rear16/ESP-DOOM contributors. GPL version 2 or later. NO WARRANTY, including merchantability or fitness.\n\nFirmware embeds no WAD. Separately supplied official Freedoom Phase 1 v0.13.0 is licensed data, with license and credits in the SD assets.\n\nCorresponding source, build scripts, provenance, actual engine patches and full GPL license are distributed in JimGat/CYM with this firmware. See ESP32C5/components/cym_doom and docs/ws-c5-game-beta.md. Use the exact firmware commit for matching source.\n\nContinue validates assets before engine startup. Cancel leaves CYM unchanged.");button(overlay,"Continue",4,h-38,w/2-8,34,continue_event,NULL);button(overlay,"Cancel",w/2+4,h-38,w/2-8,34,cancel_event,NULL);ESP_LOGI(TAG,"LICENSE_SHOWN engine_not_started");}
static void footer_event(lv_event_t *e){lv_event_code_t c=lv_event_get_code(e);if(c==LV_EVENT_DELETE){doom_trigger_reset(&unlock);return;}if(c!=LV_EVENT_PRESSED&&c!=LV_EVENT_RELEASED&&c!=LV_EVENT_PRESS_LOST)return;if(c==LV_EVENT_PRESS_LOST){doom_trigger_reset(&unlock);return;}bool allowed=!overlay&&idle_gate&&idle_gate();if(doom_trigger_update(&unlock,(uint32_t)(esp_timer_get_time()/1000),c==LV_EVENT_PRESSED,true,allowed))license_dialog();}
void doom_ui_attach_footer(lv_obj_t *footer,bool (*gate)(void),void (*home)(void)){idle_gate=gate;return_home=home;doom_trigger_reset(&unlock);lv_obj_add_flag(footer,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(footer,footer_event,LV_EVENT_ALL,NULL);}
