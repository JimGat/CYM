/* UI half of @birolt29's FSD, reconciled for owned requests and UI-only access.
 * Included after navigation definitions, so no extra public application API. */
#if !CONFIG_ESP_CONSOLE_NONE
#include "fsd_lifecycle.h"
static const char *fsd_text_of(lv_obj_t *o)
{
    if(lv_obj_check_type(o,&lv_label_class))return lv_label_get_text(o);
    const char *first=NULL;
    for(uint32_t i=0;i<lv_obj_get_child_cnt(o);i++){
        lv_obj_t *c=lv_obj_get_child(o,i);
        if(!lv_obj_check_type(c,&lv_label_class))continue;
        const char *t=lv_label_get_text(c);
        if(!t||!*t)continue;
        if((unsigned char)*t<0x80)return t;
        if(!first)first=t;
    }
    return first;
}
static bool fsd_text_match(const char *t,const char *want)
{
    if(!t||!want)return false;
    for(;*t&&*want;t++,want++){
        char a=*t=='\n'?' ':*t,b=*want;
        if(a>='A'&&a<='Z')a+=32;
        if(b>='A'&&b<='Z')b+=32;
        if(a!=b)return false;
    }
    return !*t&&!*want;
}
/* Treat any visible non-brightness top overlay conservatively as modal. A tap
 * must never fall through it to a destructive/transmitting widget underneath. */
static bool fsd_has_overlay(void)
{
    lv_obj_t *top=lv_layer_top();
    for(uint32_t i=0;i<lv_obj_get_child_cnt(top);i++){
        lv_obj_t *c=lv_obj_get_child(top,i);
        if(c!=brightness_overlay&&lv_obj_is_visible(c))return true;
    }
    return false;
}
static bool fsd_clickable(lv_obj_t *o)
{
    if(!o||!lv_obj_is_visible(o)||!lv_obj_has_flag(o,LV_OBJ_FLAG_CLICKABLE))return false;
    for(lv_obj_t *p=o;p;p=lv_obj_get_parent(p))
        if(lv_obj_has_state(p,LV_STATE_DISABLED)||lv_obj_has_flag(p,LV_OBJ_FLAG_HIDDEN))return false;
    return true;
}
static bool fsd_on_top(lv_obj_t *o)
{
    for(lv_obj_t *p=o;p;p=lv_obj_get_parent(p))if(p==lv_layer_top())return true;
    return false;
}
static lv_obj_t *fsd_hit(lv_obj_t *o,const lv_point_t *pt)
{
    if(!o||!lv_obj_is_visible(o)||lv_obj_has_state(o,LV_STATE_DISABLED))return NULL;
    /* Clip to each ancestor. Deliberately conservative for overflowing widgets. */
    lv_area_t area;lv_obj_get_coords(o,&area);
    if(pt->x<area.x1||pt->x>area.x2||pt->y<area.y1||pt->y>area.y2)return NULL;
    for(int i=(int)lv_obj_get_child_cnt(o)-1;i>=0;i--){
        lv_obj_t *hit=fsd_hit(lv_obj_get_child(o,(uint32_t)i),pt);if(hit)return hit;
    }
    if(o==lv_layer_top()||o==lv_scr_act())return NULL;
    return fsd_clickable(o)&&lv_obj_hit_test(o,pt)?o:NULL;
}
static bool fsd_click(lv_obj_t *o)
{
    if(!fsd_clickable(o)||(fsd_has_overlay()&&!fsd_on_top(o)))return false;
    /* LVGL returns INV when an event deletes the target (or an ancestor).
     * Never dereference or send another event to that retired object. */
    const lv_event_code_t events[]={LV_EVENT_PRESSED,LV_EVENT_RELEASED,LV_EVENT_SHORT_CLICKED,LV_EVENT_CLICKED};
    for(size_t i=0;i<sizeof(events)/sizeof(events[0]);i++){
        if(!fsd_clickable(o)||(fsd_has_overlay()&&!fsd_on_top(o)))return false;
        if(lv_event_send(o,events[i],NULL)==LV_RES_INV)return true;
    }
    return true;
}
typedef struct {cym_fsd_request_t *r;int next;size_t off;lv_obj_t *found;bool overflow;} fsd_walk_t;
static const char *fsd_class(lv_obj_t *o)
{
    if(lv_obj_check_type(o,&lv_btn_class))return "btn";
    if(lv_obj_check_type(o,&lv_label_class))return "label";
    if(lv_obj_check_type(o,&lv_img_class))return "img";
    return "obj";
}
static void fsd_walk(fsd_walk_t *v,lv_obj_t *o,int depth)
{
    if(!o||v->found||v->overflow)return;
    if(depth>64){v->overflow=true;return;}
    int id=v->next++;
    cym_fsd_request_t *r=v->r;
    if(r->op==FSD_TREE){
        lv_area_t a;lv_obj_get_coords(o,&a);const char *t=fsd_text_of(o);char text[64]="";size_t j=0;
        if(t){for(;t[j]&&j<sizeof(text)-2;j++){unsigned char c=t[j];text[j]=c=='\n'?'|':c>=32&&c<127?(char)c:'.';}if(t[j])text[j++]='~';text[j]=0;}
        int n=snprintf(r->data+v->off,24576-v->off,"%d %d %s %d %d %d %d %c%c %s\n",id,depth,fsd_class(o),a.x1,a.y1,lv_area_get_width(&a),lv_area_get_height(&a),lv_obj_has_flag(o,LV_OBJ_FLAG_HIDDEN)?'H':lv_obj_is_visible(o)?'-':'h',fsd_clickable(o)?'C':'-',text);
        if(n<0||(size_t)n>=24576-v->off){v->overflow=true;return;}v->off+=(size_t)n;
    }else if((r->op==FSD_TAPT&&fsd_clickable(o)&&fsd_text_match(fsd_text_of(o),r->text)&&(!fsd_has_overlay()||fsd_on_top(o)))||(r->op!=FSD_TAPT&&id==r->id)){
        v->found=o;r->id=id;return;
    }
    for(uint32_t i=0;i<lv_obj_get_child_cnt(o)&&!v->found&&!v->overflow;i++)fsd_walk(v,lv_obj_get_child(o,i),depth+1);
}
#if CONFIG_BOARD_HAS_PSRAM
static void fsd_rgb(lv_color_t c,uint8_t *r,uint8_t *g,uint8_t *b)
{
#if LV_COLOR_DEPTH == 16
    *r=(c.ch.red<<3)|(c.ch.red>>2);uint8_t g6=LV_COLOR_GET_G16(c);*g=(g6<<2)|(g6>>4);*b=(c.ch.blue<<3)|(c.ch.blue>>2);
#else
    *r=LV_COLOR_GET_R(c);*g=LV_COLOR_GET_G(c);*b=LV_COLOR_GET_B(c);
#endif
}
static void fsd_capture(cym_fsd_request_t *r)
{
    unsigned w=lv_disp_get_hor_res(NULL),h=lv_disp_get_ver_res(NULL);
    if(!w||!h||w>800||h>800){strcpy(r->desc,"dimensions unsupported");return;}
    lv_img_dsc_t *d=lv_snapshot_take(lv_scr_act(),LV_IMG_CF_TRUE_COLOR),*td=NULL;
    if(!d){strcpy(r->desc,"snapshot allocation failed");return;}
    if(fsd_has_overlay()){
        bool hidden=!brightness_overlay||lv_obj_has_flag(brightness_overlay,LV_OBJ_FLAG_HIDDEN);
        if(!hidden)lv_obj_add_flag(brightness_overlay,LV_OBJ_FLAG_HIDDEN);
        td=lv_snapshot_take(lv_layer_top(),LV_IMG_CF_TRUE_COLOR_ALPHA);
        if(!hidden)lv_obj_clear_flag(brightness_overlay,LV_OBJ_FLAG_HIDDEN);
        if(!td){strcpy(r->desc,"overlay snapshot allocation failed");goto cleanup;}
    }
    if(d->header.w!=w||d->header.h!=h||(td&&(td->header.w!=w||td->header.h!=h))){strcpy(r->desc,"snapshot dimensions mismatch");goto cleanup;}
    r->data=fsd_alloc((size_t)w*h*3);
    if(!r->data){strcpy(r->desc,"RGB allocation failed");goto cleanup;}
    for(unsigned y=0;y<h;y++){
        if(__atomic_load_n(&r->cancelled,__ATOMIC_ACQUIRE)){strcpy(r->desc,"capture cancelled");goto cleanup;}
        for(unsigned x=0;x<w;x++){
            size_t i=(size_t)y*w+x;uint8_t red,green,blue;fsd_rgb(((const lv_color_t*)d->data)[i],&red,&green,&blue);
            if(td){const uint8_t *tp=td->data+i*LV_IMG_PX_SIZE_ALPHA_BYTE;uint8_t a=tp[LV_IMG_PX_SIZE_ALPHA_BYTE-1];lv_color_t c;memcpy(&c,tp,sizeof(c));uint8_t tr,tg,tb;fsd_rgb(c,&tr,&tg,&tb);red=(tr*a+red*(255-a))/255;green=(tg*a+green*(255-a))/255;blue=(tb*a+blue*(255-a))/255;}
            uint8_t *p=(uint8_t*)r->data+i*3;p[0]=red;p[1]=green;p[2]=blue;
        }
    }
    r->w=w;r->h=h;r->length=(size_t)w*h*3;r->status=1;
cleanup:
    /* All LVGL-owned descriptors die here, never in a console/timeout callback. */
    lv_snapshot_free(d);if(td)lv_snapshot_free(td);
}
#endif
static void fsd_execute(cym_fsd_request_t *r)
{
#if defined(CONFIG_BOARD_WS_C5_28) || defined(CONFIG_BOARD_WS_C5_35)
    /* Direct jumps must not bypass the application's exclusive-screen teardown. */
    if((r->op==FSD_NAV||r->op==FSD_ROTATE)&&doom_ui_active()){
        strcpy(r->desc,"screen transition busy; stop active screen normally");return;
    }
#endif

    if(!lv_disp_get_default()){strcpy(r->desc,"UI unavailable");return;}
    if(r->op==FSD_WHERE){
        int n=snprintf(r->desc,sizeof(r->desc),"depth=%d back_fn=%s stack=[",nav_stack_depth,g_screen_back_fn?"set":"none");
        size_t off=n>0?(size_t)n:sizeof(r->desc);
        for(int i=0;i<nav_stack_depth&&off<sizeof(r->desc);i++){n=snprintf(r->desc+off,sizeof(r->desc)-off,"%s%s",i?" > ":"",nav_stack[i]?nav_stack[i]:"?");if(n<0)break;off+=(size_t)n;}
        if(off+2>sizeof(r->desc)){strcpy(r->desc,"nav state exceeds response bound");return;}strcpy(r->desc+off,"]");r->status=1;return;
    }
    if(r->op==FSD_NAV){
        void(*fn)(void)=nav_show_lookup(r->text);
        if(!fn){strcpy(r->desc,"unknown screen");return;}
        if(fsd_has_overlay()){strcpy(r->desc,"overlay blocks navigation");return;}
        clock_cancel_radio_navigation();run_screen_stop_fn();fn();r->status=1;return;
    }
    if(r->op==FSD_BACK){if(fsd_has_overlay()){strcpy(r->desc,"overlay blocks Back; dismiss manually");return;}nav_back_cb(NULL);r->status=1;return;}
    if(r->op==FSD_ROTATE){
#if defined(CONFIG_BOARD_NM_CYD_C5) || defined(CONFIG_BOARD_WS_C5_28) || defined(CONFIG_BOARD_WS_C5_35) || defined(CONFIG_BOARD_CYD2USB)
        if(fsd_has_overlay()){strcpy(r->desc,"overlay blocks rotation");return;}
        screen_orientation=(uint8_t)r->a;apply_screen_orientation(screen_orientation);go_home();r->status=1;
#else
        strcpy(r->desc,"unsupported board orientation");
#endif
        return;
    }
    if(r->op==FSD_SHOT){
#if CONFIG_BOARD_HAS_PSRAM
        fsd_capture(r);
#else
        strcpy(r->desc,"unsupported: no PSRAM");
#endif
        return;
    }
    lv_obj_update_layout(lv_scr_act());lv_obj_update_layout(lv_layer_top());
    if(r->op==FSD_TAP){
        if(r->a<0||r->b<0||r->a>=lv_disp_get_hor_res(NULL)||r->b>=lv_disp_get_ver_res(NULL)){strcpy(r->desc,"coordinate outside logical display");return;}
        lv_point_t pt={(lv_coord_t)r->a,(lv_coord_t)r->b};lv_obj_t *o=fsd_hit(lv_layer_top(),&pt);
        if(!o&&!fsd_has_overlay())o=fsd_hit(lv_scr_act(),&pt);
        r->status=fsd_click(o);if(!r->status)strcpy(r->desc,"no eligible widget");return;
    }
    if(r->op==FSD_TREE){r->data=fsd_alloc(24576);if(!r->data){strcpy(r->desc,"tree allocation failed");return;}}
    fsd_walk_t v={.r=r};fsd_walk(&v,lv_layer_top(),0);fsd_walk(&v,lv_scr_act(),0);
    if(r->op==FSD_TREE){r->length=v.off;r->status=!v.overflow;if(v.overflow)strcpy(r->desc,"tree exceeds output/depth bound (24576 bytes, 64 levels); labels marked ~ are abbreviated");return;}
    lv_obj_t *o=v.found;if(!o){strcpy(r->desc,"widget not found");return;}
    if(r->op==FSD_TAPID||r->op==FSD_TAPT){r->status=fsd_click(o);if(!r->status)strcpy(r->desc,"widget hidden, disabled, not clickable, or blocked by overlay");return;}
    if(r->op==FSD_MOVE){lv_area_t a;lv_obj_get_coords(o,&a);lv_obj_set_pos(o,lv_obj_get_x_aligned(o)+(r->a-a.x1),lv_obj_get_y_aligned(o)+(r->b-a.y1));r->status=1;}
    if(r->op==FSD_SIZE){lv_obj_set_size(o,(lv_coord_t)r->a,(lv_coord_t)r->b);r->status=1;}
    if(r->op==FSD_TEXT){lv_obj_t *label=lv_obj_check_type(o,&lv_label_class)?o:NULL;
        for(uint32_t i=0;!label&&i<lv_obj_get_child_cnt(o);i++){lv_obj_t *c=lv_obj_get_child(o,i);if(lv_obj_check_type(c,&lv_label_class))label=c;}
        if(label){lv_label_set_text(label,r->text);r->status=1;}else strcpy(r->desc,"widget has no label");}
}
void cym_fsd_poll(void)
{
    cym_fsd_request_t *r=fsd_take();if(!r)return;
    if(!__atomic_load_n(&r->cancelled,__ATOMIC_ACQUIRE))fsd_execute(r);
    fsd_complete(r);
}
#endif
