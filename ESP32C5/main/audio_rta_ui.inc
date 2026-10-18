/* Screen-local LVGL owner. No PCM pointers and no global-loop polling. */
#include "audio_rta.h"
static lv_timer_t *rta_timer;
static lv_obj_t *rta_body,*rta_status,*rta_chart,*rta_detail,*rta_overlay;
static lv_obj_t *rta_freeze_label,*rta_speed_label,*rta_gain_label;
static audio_rta_snapshot_t rta_model;
static uint32_t rta_generation;
static int rta_selected=12,rta_gain;
static bool rta_frozen,rta_slow;
static uint32_t rta_metadata_tick;
/* LVGL invalidates even when set_text receives identical text. Keep labels
 * stable, and rate-limit changing metadata separately from the 50 ms plot. */
static void rta_text(lv_obj_t*label,const char*text){
 if(label&&strcmp(lv_label_get_text(label),text))lv_label_set_text(label,text);
}
static void audio_rta_ui_stop(void){
 uint32_t gen=rta_generation;rta_generation=0;
 if(rta_timer){lv_timer_del(rta_timer);rta_timer=NULL;}
 if(rta_overlay){lv_obj_del(rta_overlay);rta_overlay=NULL;}
 rta_body=rta_status=rta_chart=rta_detail=NULL;
 rta_freeze_label=rta_speed_label=rta_gain_label=NULL;
 memset(&rta_model,0,sizeof(rta_model));
 audio_rta_stop(gen);
}
static void rta_detail_update(void){
 if(!rta_detail)return;
 unsigned b=rta_selected;
 char text[160];
 /* LVGL float formatting is disabled. libc formats into a bounded copy. */
 if(rta_model.spectrum.valid&(1u<<b))
  snprintf(text,sizeof(text),"%.2f-%.2f Hz  %.1f dBFS\nAge %.0f ms / %s",audio_rta_dsp_edge(b),audio_rta_dsp_edge(b+1),(double)rta_model.spectrum.band[b],rta_model.spectrum.age[b]/48.0,b<9?"683 ms bass window":"85 ms window");
 else snprintf(text,sizeof(text),"%.2f-%.2f Hz / warming up\n%s",audio_rta_dsp_edge(b),audio_rta_dsp_edge(b+1),b<9?"Bass needs 683 ms of fresh input":"Full-rate needs 85 ms of fresh input");
 rta_text(rta_detail,text);
}
static void rta_plot_text(lv_draw_ctx_t*ctx,int x,int y,int width,const char*text){
 /* Partial bar damage must not execute static title/axis text drawing. */
 if(x>ctx->clip_area->x2||x+width-1<ctx->clip_area->x1||y>ctx->clip_area->y2||y+16<ctx->clip_area->y1)return;
 lv_draw_label_dsc_t d;lv_draw_label_dsc_init(&d);d.font=&lv_font_montserrat_12;d.color=lv_color_hex(0xcbd5e1);
 lv_area_t a={x,y,x+width-1,y+16};lv_draw_label(ctx,&d,&a,text,NULL);
}
static int rta_y(float db,int top,int height){
 if(db<-90)db=-90;
 if(db>0)db=0;
 return top+(int)((-db)*height/90);
}
/* Damage only the union of the previous/new bar and peak within one band.
 * Clearing the old extent via normal chart background drawing prevents ghosts
 * on decreases, validity loss, Reset Peaks and overlay expose/full refresh. */
static void rta_band_damage(unsigned b,const audio_rta_spectrum_t*old,const audio_rta_spectrum_t*next){
 if(!rta_chart)return;
 lv_area_t a;lv_obj_get_coords(rta_chart,&a);
 int left=a.x1+32,w=a.x2-3-left+1,top=a.y1+20,bottom=a.y2-20,h=bottom-top;
 bool ov=(old->valid&(1u<<b))!=0,nv=(next->valid&(1u<<b))!=0;
 int oy=rta_y(old->band[b],top,h),ny=rta_y(next->band[b],top,h);
 int op=rta_y(old->peak[b],top,h),np=rta_y(next->peak[b],top,h);
 int oc=old->band[b]>-6?2:old->band[b]>-18?1:0,nc=next->band[b]>-6?2:next->band[b]>-18?1:0;
 if(ov==nv&&(!ov||(oy==ny&&op==np&&oc==nc)))return;
 int y=bottom;if(ov){if(oy<y)y=oy;if(op<y)y=op;}if(nv){if(ny<y)y=ny;if(np<y)y=np;}
 lv_area_t damage={left+(int)b*w/24,y,left+(int)(b+1)*w/24-2,bottom+1};
 lv_obj_invalidate_area(rta_chart,&damage);
}
static void rta_selection_damage(int b){
 lv_area_t a;lv_obj_get_coords(rta_chart,&a);int left=a.x1+32,w=a.x2-3-left+1,bottom=a.y2-20;
 lv_area_t damage={left+b*w/24,bottom+1,left+(b+1)*w/24-2,bottom+3};lv_obj_invalidate_area(rta_chart,&damage);
}
static void rta_chart_event(lv_event_t*e){
 lv_obj_t*obj=lv_event_get_target(e);lv_area_t a;lv_obj_get_coords(obj,&a);
 int left=a.x1+32,right=a.x2-3,top=a.y1+20,bottom=a.y2-20,w=right-left+1,h=bottom-top;
 if(lv_event_get_code(e)==LV_EVENT_DRAW_MAIN){
  lv_draw_ctx_t*ctx=lv_event_get_draw_ctx(e);
  lv_draw_rect_dsc_t rect;lv_draw_rect_dsc_init(&rect);rect.bg_color=lv_color_hex(0x080c14);rect.border_width=0;rect.radius=0;
  lv_draw_rect(ctx,&rect,&a);
  rta_plot_text(ctx,a.x1+3,a.y1+1,lv_area_get_width(&a)-6,"24 log bands / uncalibrated dBFS");
  rta_plot_text(ctx,a.x1+2,top-4,30,"0");rta_plot_text(ctx,a.x1+1,top+h/2-7,31,"-45");rta_plot_text(ctx,a.x1+1,bottom-12,31,"-90");
  for(unsigned b=0;b<24;b++){
   int x1=left+(int)b*w/24,x2=left+(int)(b+1)*w/24-2;
   if(x1>ctx->clip_area->x2||x2<ctx->clip_area->x1)continue;
   if(rta_model.spectrum.valid&(1u<<b)){
    float db=rta_model.spectrum.band[b];int y=rta_y(db,top,h);
    lv_area_t bar={x1,y,x2,bottom};rect.bg_color=lv_color_hex(db>-6?0xef4444:db>-18?0xf59e0b:0x22c55e);
    lv_draw_rect(ctx,&rect,&bar);
    int py=rta_y(rta_model.spectrum.peak[b],top,h);lv_area_t peak={x1,py,x2,py+1};rect.bg_color=lv_color_hex(0xf1f5f9);lv_draw_rect(ctx,&rect,&peak);
   }
   if((int)b==rta_selected){lv_area_t mark={x1,bottom+1,x2,bottom+3};rect.bg_color=lv_color_hex(0x38bdf8);lv_draw_rect(ctx,&rect,&mark);}
  }
  rta_plot_text(ctx,left,a.y2-16,35,"20");rta_plot_text(ctx,left+w/3-8,a.y2-16,38,"200");rta_plot_text(ctx,left+2*w/3-8,a.y2-16,35,"2k");rta_plot_text(ctx,right-26,a.y2-16,30,"20k");
 }else if(lv_event_get_code(e)==LV_EVENT_PRESSING||lv_event_get_code(e)==LV_EVENT_PRESSED){
  lv_indev_t*in=lv_indev_get_act();if(!in)return;lv_point_t p;lv_indev_get_point(in,&p);
  int b=(p.x-left)*24/w;if(b<0)b=0;if(b>23)b=23;if(b!=rta_selected){rta_selection_damage(rta_selected);rta_selected=b;rta_selection_damage(b);rta_detail_update();}
 }
}
static void rta_send(bool reset){audio_rta_controls(rta_generation,rta_frozen,rta_slow,rta_gain,reset);}
static lv_obj_t*rta_button(lv_obj_t*parent,const char*text,int x,int y,int w,lv_event_cb_t cb,int value){
 lv_obj_t*b=lv_btn_create(parent);lv_obj_set_pos(b,x,y);lv_obj_set_size(b,w,44);
 lv_obj_set_style_bg_color(b,UI_ACCENT_BLUE,0);lv_obj_set_style_bg_color(b,lv_color_lighten(UI_ACCENT_BLUE,50),LV_STATE_PRESSED);
 lv_obj_set_style_pad_all(b,3,0);lv_obj_set_style_shadow_width(b,0,0);
 lv_obj_t*l=lv_label_create(b);lv_obj_set_style_text_font(l,&lv_font_montserrat_14,0);lv_obj_set_style_text_color(l,lv_color_white(),0);lv_label_set_text(l,text);lv_obj_center(l);
 lv_obj_add_event_cb(b,cb,LV_EVENT_CLICKED,(void*)(intptr_t)value);return l;
}
static void rta_gain_choose(lv_event_t*e){
 int gain=(int)(intptr_t)lv_event_get_user_data(e);
 if(gain>=0){rta_gain=gain;rta_frozen=false;lv_label_set_text(rta_freeze_label,"Freeze");rta_send(false);}
 if(rta_overlay){lv_obj_del(rta_overlay);rta_overlay=NULL;}
}
static void rta_control(lv_event_t*e){
 int key=(int)(intptr_t)lv_event_get_user_data(e);
 if(key==0){rta_frozen=!rta_frozen;lv_label_set_text(rta_freeze_label,rta_frozen?"Resume":"Freeze");}
 if(key==1)rta_slow=!rta_slow;
 if(key==2){rta_send(true);return;}
 if(key==3){
  if(rta_overlay)return;
  rta_overlay=lv_obj_create(function_page);int w=lv_obj_get_width(function_page)-24,h=lv_obj_get_height(function_page)-54;
  lv_obj_set_size(rta_overlay,w,h);lv_obj_set_pos(rta_overlay,12,40);lv_obj_set_style_bg_color(rta_overlay,lv_color_hex(0x111827),0);lv_obj_set_style_bg_opa(rta_overlay,LV_OPA_COVER,0);
  lv_obj_set_style_pad_all(rta_overlay,8,0);lv_obj_set_scroll_dir(rta_overlay,LV_DIR_VER);lv_obj_set_scrollbar_mode(rta_overlay,LV_SCROLLBAR_MODE_AUTO);
  lv_obj_t*l=lv_label_create(rta_overlay);lv_label_set_text(l,"Manual mic gain (no AGC)\nSession only; resets analysis");lv_obj_set_width(l,w-36);lv_obj_set_style_text_font(l,&lv_font_montserrat_14,0);
  for(int i=0;i<8;i++){char text[20];snprintf(text,sizeof(text),"%d dB",i*6);rta_button(rta_overlay,text,(i%2)*(w-32)/2,48+(i/2)*48,(w-40)/2,rta_gain_choose,i*6);}
  rta_button(rta_overlay,"Close",0,244,w-36,rta_gain_choose,-1);return;
 }
 lv_label_set_text(rta_speed_label,rta_slow?"Slow":"Fast");rta_send(false);
}
static void rta_error_text(int error){
 if(rta_overlay){lv_obj_del(rta_overlay);rta_overlay=NULL;}
 lv_label_set_text_fmt(rta_status,"Audio unavailable: %s (%d). Back/Home exits safely. If audio is busy or cleanup is delayed, wait then reopen. Insufficient memory is not retried automatically.",esp_err_to_name(error),error);
 lv_obj_set_height(rta_status,LV_SIZE_CONTENT);
 for(unsigned i=1;i<lv_obj_get_child_cnt(rta_body);i++)lv_obj_add_flag(lv_obj_get_child(rta_body,i),LV_OBJ_FLAG_HIDDEN);
 lv_obj_add_flag(rta_body,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_scroll_dir(rta_body,LV_DIR_VER);
}
static void rta_refresh(lv_timer_t*t){
 (void)t;if(!rta_generation||!rta_status)return;
 audio_rta_snapshot_t next;if(!audio_rta_snapshot(rta_generation,&next))return;
 if(next.state==RTA_ERROR){
  if(rta_model.state!=RTA_ERROR||rta_model.error!=next.error)rta_error_text(next.error);
  rta_model=next;return;
 }
 bool metadata=lv_tick_elaps(rta_metadata_tick)>=250||next.state!=rta_model.state||
  next.stale!=rta_model.stale||next.gain_db!=rta_model.gain_db||next.spectrum.valid!=rta_model.spectrum.valid||!rta_model.sequence;
 for(unsigned b=0;b<24;b++)rta_band_damage(b,&rta_model.spectrum,&next.spectrum);
 rta_model=next;
 if(metadata){
  rta_metadata_tick=lv_tick_get();char text[160];
  if(!rta_model.sequence){
   const char*state=rta_model.state==RTA_FROZEN?"Frozen":rta_model.state==RTA_STOPPING||rta_model.state==RTA_CLOSED?"Stopping":"Starting";
   snprintf(text,sizeof(text),"%s 48k input / gain %d dB\nWaiting for fresh analysis windows",state,rta_model.gain_db);
   rta_text(rta_status,text);
  }
  else{
   const char*state=rta_model.state==RTA_FROZEN?"Frozen":rta_model.state==RTA_STARTING?"Starting":
    rta_model.state!=RTA_RUNNING?"Stopping":rta_model.stale?"Stale":!rta_model.spectrum.valid?"Warming":
    rta_model.spectrum.valid!=0xffffff?"Partial":rta_model.spectrum.rms<=-119?"No signal":"Live";
   snprintf(text,sizeof(text),"%s RMS %.1f Pk %.1f dBFS\n%s%lu / Gain %d dB",state,(double)rta_model.spectrum.rms,(double)rta_model.spectrum.sample_peak,rta_model.spectrum.clips?"CLIP ":"Clips ",(unsigned long)rta_model.spectrum.clips,rta_model.gain_db);
   rta_text(rta_status,text);
  }
  snprintf(text,sizeof(text),"Gain %d",rta_model.gain_db);rta_text(rta_gain_label,text);rta_detail_update();
 }
}
static void show_audio_rta(void){
 create_function_page_base("Audio RTA");
 g_screen_stop_fn = audio_rta_ui_stop;
 g_screen_back_fn = g_home_layout_4cat ? show_cat_tools : show_main_tiles;
 apply_menu_bg();
 memset(&rta_model,0,sizeof(rta_model));rta_frozen=false;rta_slow=false;rta_gain=0;rta_metadata_tick=lv_tick_get();
 /* Existing page title is measured, never replaced or overdrawn. */
 lv_obj_update_layout(function_page);int title_h=lv_obj_get_height(lv_obj_get_child(function_page,0));
 int w=lv_obj_get_content_width(function_page),h=lv_obj_get_content_height(function_page)-title_h-4;bool land=w>h;
 rta_body=lv_obj_create(function_page);lv_obj_set_pos(rta_body,4,title_h+2);lv_obj_set_size(rta_body,w-8,h);
 lv_obj_set_style_pad_all(rta_body,0,0);lv_obj_set_style_border_width(rta_body,0,0);lv_obj_set_style_bg_color(rta_body,lv_color_hex(0x080c14),0);lv_obj_set_style_bg_opa(rta_body,LV_OPA_COVER,0);lv_obj_set_style_text_color(rta_body,lv_color_white(),0);lv_obj_set_style_text_font(rta_body,&lv_font_montserrat_14,0);lv_obj_clear_flag(rta_body,LV_OBJ_FLAG_SCROLLABLE);
 int width=w-8,status_h=36,detail_h=36,control_h=land?44:92,plot_h=h-status_h-detail_h-control_h-12;
 rta_status=lv_label_create(rta_body);lv_obj_set_pos(rta_status,2,0);lv_obj_set_size(rta_status,width-4,status_h);lv_label_set_long_mode(rta_status,LV_LABEL_LONG_WRAP);
 rta_chart=lv_obj_create(rta_body);lv_obj_remove_style_all(rta_chart);lv_obj_set_pos(rta_chart,0,status_h+2);lv_obj_set_size(rta_chart,width,plot_h);lv_obj_add_flag(rta_chart,LV_OBJ_FLAG_CLICKABLE);lv_obj_clear_flag(rta_chart,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_event_cb(rta_chart,rta_chart_event,LV_EVENT_ALL,NULL);
 rta_detail=lv_label_create(rta_body);lv_obj_set_pos(rta_detail,2,status_h+plot_h+4);lv_obj_set_size(rta_detail,width-4,detail_h);lv_label_set_long_mode(rta_detail,LV_LABEL_LONG_WRAP);
 const char*labels[]={"Freeze","Fast","Reset Peaks","Gain 0"};lv_obj_t**dest[]={&rta_freeze_label,&rta_speed_label,NULL,&rta_gain_label};
 for(int i=0;i<4;i++){int cols=land?4:2,bw=(width-(cols-1)*4)/cols,x=(i%cols)*(bw+4),y=h-control_h+(i/cols)*48;lv_obj_t*l=rta_button(rta_body,labels[i],x,y,bw,rta_control,i);if(dest[i])*dest[i]=l;}
 esp_err_t rc=audio_rta_start(ws_c5_35_i2c_bus(),&rta_generation);
 if(rc){rta_model.state=RTA_ERROR;rta_model.error=rc;rta_error_text(rc);rta_detail_update();return;}
 rta_timer=lv_timer_create(rta_refresh,50,NULL);
 if(!rta_timer){audio_rta_stop(rta_generation);lv_label_set_text(rta_status,"Refresh timer unavailable. Back to exit.");return;}
 rta_refresh(NULL);
}
