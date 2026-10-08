/* Startup/lifetime HAL only. No scheduler or controller backend. */
#define lv_obj_set_style_text_align(...) ((void)0)
#define lv_label_set_long_mode(...) ((void)0)
#define lv_obj_align(...) ((void)0)
#define lv_obj_set_size(...) ((void)0)
#define lv_obj_set_style_border_width(...) ((void)0)
#define lv_obj_set_flex_flow(...) ((void)0)
#define lv_obj_set_style_pad_row(...) ((void)0)
#define lv_obj_set_style_pad_all(...) ((void)0)
#define lv_obj_set_scrollbar_mode(...) ((void)0)
#define lv_obj_set_flex_align(...) ((void)0)
#define lv_obj_clear_flag(...) ((void)0)
#define lv_obj_add_flag(...) ((void)0)
#define lv_obj_add_event_cb(...) ((void)0)
#define lv_bar_set_range(...) ((void)0)
#define lv_obj_set_style_radius(...) ((void)0)
#define lv_obj_center(...) ((void)0)
#define apply_menu_bg() ((void)0)
#define lv_disp_get_ver_res(x) 320
#define LV_SYMBOL_LEFT "<"
#define LV_ANIM_OFF 0
static lv_obj_t objects[48];static int object_n=0;
static lv_obj_t *function_page=&objects[0];
static void (*g_screen_stop_fn)(void)=NULL;
static lv_obj_t *new_object(lv_obj_t *o){(void)o;assert(object_n<48);return &objects[object_n++];}
#define lv_label_create new_object
#define lv_obj_create new_object
#define lv_bar_create new_object
#define lv_btn_create new_object
static void create_function_page_base(const char *s){(void)s;if(g_screen_stop_fn)g_screen_stop_fn();object_n=0;memset(objects,0,sizeof(objects));}
static int alloc_calls=0,fail_alloc_at=0,scan_rc=0,cancel_calls=0,deinit_calls=0;
static void *dd_alloc(size_t n){alloc_calls++;return alloc_calls==fail_alloc_at?NULL:calloc(1,n);}
#define heap_caps_free free
#define RADIO_MODE_BLE 1
#define RADIO_MODE_NONE 0
static int current_radio_mode=RADIO_MODE_BLE;
static void bt_nimble_deinit(void){deinit_calls++;}
static int ble_gap_disc_cancel(void){cancel_calls++;return 0;}
static int bspam_start_scan(void){return scan_rc;}
