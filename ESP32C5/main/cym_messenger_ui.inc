/* Canonical UI include: existing CYM keyboard/text-area styling, no SDK work.
 * LVGL owns every pointer below; the worker sees only copied bytes/status. */
typedef struct {
 lv_obj_t *body,*selector,*setup,*peer,*key,*channel,*own,*hint,*history,*composer,*counter,*state,*keyboard,*bar,*send,*start;
 lv_timer_t *timer;unsigned protocol,rows;bool editing;
} messenger_ui;
#define msg_ui ((messenger_ui *)lv_obj_get_user_data(function_page))
static void messenger_layout(void){
 messenger_ui *u=msg_ui;if(!u)return;int h=lv_disp_get_ver_res(NULL),kh=u->editing?h*40/100:0;
 lv_obj_set_size(u->keyboard,lv_pct(100),kh?kh:1);lv_obj_align(u->keyboard,LV_ALIGN_BOTTOM_MID,0,0);
 if(u->editing)lv_obj_clear_flag(u->keyboard,LV_OBJ_FLAG_HIDDEN);else lv_obj_add_flag(u->keyboard,LV_OBJ_FLAG_HIDDEN);
 lv_obj_set_size(u->bar,lv_pct(100),36);lv_obj_align(u->bar,LV_ALIGN_BOTTOM_MID,0,-kh);
 lv_obj_set_size(u->body,lv_pct(100),h-30-36-kh);lv_obj_align(u->body,LV_ALIGN_TOP_MID,0,30);
}
static lv_obj_t *messenger_label(lv_obj_t *parent,const char *text){
 lv_obj_t *l=lv_label_create(parent);lv_label_set_recolor(l,false);lv_obj_set_width(l,lv_pct(100));lv_label_set_long_mode(l,LV_LABEL_LONG_WRAP);
 lv_obj_set_style_text_font(l,&lv_font_montserrat_12,0);lv_obj_set_style_text_color(l,ui_text_color(),0);lv_label_set_text(l,text);return l;
}
static void messenger_count(void){if(!msg_ui)return;size_t n=strlen(lv_textarea_get_text(msg_ui->composer));char b[48];snprintf(b,sizeof(b),"%u / 160 bytes%s",(unsigned)n,n>160?" - too long":"");lv_label_set_text(msg_ui->counter,b);}
static void messenger_focus(lv_event_t *e){if(!msg_ui)return;lv_obj_t *ta=lv_event_get_target(e);msg_ui->editing=true;messenger_layout();lv_keyboard_set_textarea(msg_ui->keyboard,ta);lv_obj_scroll_to_view(ta,LV_ANIM_OFF);}
static lv_obj_t *messenger_entry(lv_obj_t *p,const char *hint,unsigned max){
 lv_obj_t *ta=lv_textarea_create(p);lv_obj_set_width(ta,lv_pct(100));lv_obj_set_height(ta,38);lv_textarea_set_one_line(ta,true);lv_textarea_set_max_length(ta,max);lv_textarea_set_placeholder_text(ta,hint);
 lv_obj_set_style_text_font(ta,&lv_font_montserrat_12,0);lv_obj_set_style_bg_color(ta,ui_bg_color(),0);lv_obj_set_style_text_color(ta,ui_text_color(),0);lv_obj_set_style_border_color(ta,ui_accent_color(),0);
 lv_obj_set_style_bg_opa(ta,LV_OPA_TRANSP,LV_PART_CURSOR|LV_STATE_FOCUSED);lv_obj_set_style_border_color(ta,UI_ACCENT_CYAN,LV_PART_CURSOR|LV_STATE_FOCUSED);lv_obj_set_style_border_width(ta,2,LV_PART_CURSOR|LV_STATE_FOCUSED);lv_obj_set_style_border_side(ta,LV_BORDER_SIDE_LEFT,LV_PART_CURSOR|LV_STATE_FOCUSED);
 lv_obj_add_event_cb(ta,messenger_focus,LV_EVENT_CLICKED,NULL);return ta;
}
static void messenger_row(const char *prefix,const char *text){
 messenger_ui *u=msg_ui;if(!u)return;if(u->rows==4){lv_obj_del(lv_obj_get_child(u->history,0));u->rows--;}
 lv_obj_t *l=messenger_label(u->history,"");lv_label_set_text_fmt(l,"%s %s",prefix,text);u->rows++;
}
static void messenger_protocol(lv_event_t *e){(void)e;messenger_ui *u=msg_ui;if(!u)return;
 unsigned next=lv_dropdown_get_selected(u->selector);if(next!=u->protocol)cym_messenger_stop();u->protocol=next;
 const char *hint="Both devices: enter each other's STA MAC and the same key/channel. Session only; nothing saved.";
 if(next==1)hint="BLE: Not implemented.";
 if(next==2)hint="LocalSend: Not implemented.";
 if(next==3)hint="LoRa / Reticulum: Not implemented. No automatic compatibility or bridging.";
 if(next==4){
#if CONFIG_BOARD_HAS_RF_HAT
  hint=g_rf_hat_enabled?"IR / CardputerZero: Not implemented. HAT configured, not physically detected.":"IR unavailable: enable the supported NM-RF-HAT profile. Transport not implemented.";
#else
  hint="IR unavailable on this profile. Separate IR board config deferred; transport not implemented.";
#endif
 }
 lv_label_set_text(u->hint,hint); // Composer is never rewritten/truncated on a toggle.
}
static void messenger_key_reveal(lv_event_t *e){(void)e;if(msg_ui)lv_textarea_set_password_mode(msg_ui->key,!lv_textarea_get_password_mode(msg_ui->key));}
static void messenger_key_generate(lv_event_t *e){(void)e;if(msg_ui){if(cym_messenger_busy())lv_label_set_text(msg_ui->state,"Stop before generating a key.");else if(!cym_messenger_key_request())lv_label_set_text(msg_ui->state,"Key worker busy/allocation failed.");}}
static void messenger_toggle_setup(lv_event_t *e){(void)e;if(!msg_ui)return;if(lv_obj_has_flag(msg_ui->setup,LV_OBJ_FLAG_HIDDEN))lv_obj_clear_flag(msg_ui->setup,LV_OBJ_FLAG_HIDDEN);else lv_obj_add_flag(msg_ui->setup,LV_OBJ_FLAG_HIDDEN);msg_ui->editing=false;messenger_layout();}
static void messenger_start_click(lv_event_t *e){(void)e;messenger_ui *u=msg_ui;if(!u)return;
 if(cym_messenger_busy()){cym_messenger_stop();return;}if(u->protocol){lv_label_set_text(u->state,"Not implemented; no automatic transport switching.");return;}
 cym_messenger_config c={0};const char *ch=lv_textarea_get_text(u->channel);char *end=NULL;unsigned long channel=strtoul(ch,&end,10);
 if(!cym_messenger_parse_mac(lv_textarea_get_text(u->peer),c.peer)||!cym_messenger_parse_key(lv_textarea_get_text(u->key),c.key)||!ch[0]||*end||channel<1||channel>11){memset(&c,0,sizeof(c));lv_label_set_text(u->state,"Use unicast STA MAC, nonzero 32-hex key, channel 1-11.");return;}
 c.channel=(uint8_t)channel;bool ok=cym_messenger_start(&c);memset(&c,0,sizeof(c));u->editing=false;messenger_layout();lv_label_set_text(u->state,ok?"Starting; settings are session only.":"Start busy/allocation failed.");
}
static void messenger_send_click(lv_event_t *e){(void)e;messenger_ui *u=msg_ui;if(!u)return;const char *text=lv_textarea_get_text(u->composer);size_t n=strlen(text);
 if(u->protocol||!cm_text_valid((const uint8_t *)text,n)){lv_label_set_text(u->state,"Use 1-160 UTF-8 bytes; no controls or # markup.");return;}
 if(!cym_messenger_send(text,n)){lv_label_set_text(u->state,"Not ready, stopping, or one message already pending.");return;}
 messenger_row("You:",text);lv_textarea_set_text(u->composer,"");messenger_count();
}
static lv_obj_t *messenger_button(lv_obj_t *p,const char *title,lv_event_cb_t fn){lv_obj_t *b=lv_btn_create(p);lv_obj_set_size(b,70,28);lv_obj_set_style_bg_color(b,UI_ACCENT_BLUE,0);lv_obj_set_style_pad_all(b,2,0);lv_obj_t *l=lv_label_create(b);lv_label_set_text(l,title);lv_obj_set_style_text_font(l,&lv_font_montserrat_12,0);lv_obj_center(l);lv_obj_add_event_cb(b,fn,LV_EVENT_CLICKED,NULL);return b;}
static void messenger_text_changed(lv_event_t *e){(void)e;messenger_count();}
static void messenger_keyboard_event(lv_event_t *e){(void)e;if(msg_ui){msg_ui->editing=false;messenger_layout();}}
static void messenger_poll(lv_timer_t *timer){(void)timer;messenger_ui *u=msg_ui;if(!u)return;
 cym_messenger_status s;cym_messenger_snapshot(&s);char b[160];
 snprintf(b,sizeof(b),"Own STA: %02X:%02X:%02X:%02X:%02X:%02X",s.own_mac[0],s.own_mac[1],s.own_mac[2],s.own_mac[3],s.own_mac[4],s.own_mac[5]);lv_label_set_text(u->own,b);
 static const char *states[]={"Stopped","Starting","Waiting for peer (check key/channel; restart both after timeout)","Session ready","Radio busy: stop other tools; return Home, then retry","Start failed; check setup/WiFi state","Stopping","Cleanup uncertain: owner retained. Press Stop to retry"};
 const char *delivery=s.delivery==CM_PENDING?"Pending application ACK":s.delivery==CM_CONFIRMED?"Delivered (not read)":s.delivery==CM_UNCONFIRMED?"Delivery unconfirmed (may have arrived)":"No message pending";
 snprintf(b,sizeof(b),"%s | %s%s",states[(unsigned)s.state<8?s.state:MSG_FAILED],delivery,s.error?" | setup/radio error":"");lv_label_set_text(u->state,b);
 if(s.can_send&&!u->protocol)lv_obj_clear_state(u->send,LV_STATE_DISABLED);else lv_obj_add_state(u->send,LV_STATE_DISABLED);
 lv_obj_t *start_label=lv_obj_get_child(u->start,0);lv_label_set_text(start_label,cym_messenger_busy()?"Stop":"Start");
 char key[33];if(cym_messenger_key_take(key)){lv_textarea_set_password_mode(u->key,true);lv_textarea_set_text(u->key,key);memset(key,0,sizeof(key));}
 cm_message m;while(cym_messenger_take(&m)){messenger_row("Peer:",m.text);memset(&m,0,sizeof(m));}
 messenger_count();
}
static void messenger_screen_stop(void){
 cym_messenger_stop();messenger_ui *u=msg_ui;lv_obj_set_user_data(function_page,NULL);if(!u)return;if(u->timer)lv_timer_del(u->timer);
 /* Explicitly retire plaintext/key LVGL buffers before the parent's page delete. */
 lv_textarea_set_text(u->key,"");lv_textarea_set_text(u->composer,"");memset(u,0,sizeof(*u));lv_mem_free(u);
}
static void show_messenger_screen(void){
 create_function_page_base("Chat");g_screen_stop_fn = messenger_screen_stop;
 g_screen_back_fn=g_home_layout_4cat?show_cat_tools:show_main_tiles;apply_menu_bg();
 messenger_ui *u=lv_mem_alloc(sizeof(*u));if(!u){messenger_label(function_page,"Messenger UI allocation failed");return;}memset(u,0,sizeof(*u));lv_obj_set_user_data(function_page,u);
 u->body=lv_obj_create(function_page);lv_obj_set_style_bg_color(u->body,ui_bg_color(),0);lv_obj_set_style_border_width(u->body,0,0);lv_obj_set_style_pad_all(u->body,6,0);lv_obj_set_style_pad_row(u->body,6,0);lv_obj_set_flex_flow(u->body,LV_FLEX_FLOW_COLUMN);
 u->selector=lv_dropdown_create(u->body);lv_obj_set_width(u->selector,lv_pct(100));lv_dropdown_set_options(u->selector,"ESP-NOW\nBLE (planned)\nLocalSend (planned)\nLoRa / Reticulum (planned)\nIR / CardputerZero (planned)");lv_obj_add_event_cb(u->selector,messenger_protocol,LV_EVENT_VALUE_CHANGED,NULL);
 u->own=messenger_label(u->body,"Own STA: reading...");u->hint=messenger_label(u->body,"");u->state=messenger_label(u->body,"Stopped; session-only settings.");
 u->setup=lv_obj_create(u->body);lv_obj_set_width(u->setup,lv_pct(100));lv_obj_set_height(u->setup,LV_SIZE_CONTENT);lv_obj_set_style_bg_color(u->setup,ui_card_color(),0);lv_obj_set_style_border_color(u->setup,ui_border_color(),0);lv_obj_set_style_pad_all(u->setup,6,0);lv_obj_set_flex_flow(u->setup,LV_FLEX_FLOW_COLUMN);lv_obj_clear_flag(u->setup,LV_OBJ_FLAG_SCROLLABLE);
 u->peer=messenger_entry(u->setup,"Peer STA MAC AA:BB:CC:DD:EE:FF",17);u->channel=messenger_entry(u->setup,"Channel 1-11 (default 1)",2);lv_textarea_set_text(u->channel,"1");
 u->key=messenger_entry(u->setup,"Shared LMK: 32 hex digits",32);lv_textarea_set_password_mode(u->key,true);
 messenger_button(u->setup,"Reveal",messenger_key_reveal);messenger_button(u->setup,"New key",messenger_key_generate);
 messenger_label(u->setup,"New key requires active WiFi hardware entropy. Copy to peer privately. No NVS save or message log. Missing font glyphs are possible.");
 u->history=lv_obj_create(u->body);lv_obj_set_size(u->history,lv_pct(100),LV_SIZE_CONTENT);lv_obj_set_style_bg_color(u->history,ui_card_color(),0);lv_obj_set_style_pad_all(u->history,4,0);lv_obj_set_flex_flow(u->history,LV_FLEX_FLOW_COLUMN);lv_obj_clear_flag(u->history,LV_OBJ_FLAG_SCROLLABLE);
 u->composer=messenger_entry(u->body,"Message (160 UTF-8 bytes)",160);lv_obj_add_event_cb(u->composer,messenger_text_changed,LV_EVENT_VALUE_CHANGED,NULL);u->counter=messenger_label(u->body,"0 / 160 bytes");
 u->bar=lv_obj_create(function_page);lv_obj_set_style_bg_color(u->bar,ui_bg_color(),0);lv_obj_set_style_border_width(u->bar,0,0);lv_obj_set_style_pad_all(u->bar,2,0);lv_obj_set_flex_flow(u->bar,LV_FLEX_FLOW_ROW);lv_obj_set_flex_align(u->bar,LV_FLEX_ALIGN_SPACE_EVENLY,LV_FLEX_ALIGN_CENTER,LV_FLEX_ALIGN_CENTER);lv_obj_clear_flag(u->bar,LV_OBJ_FLAG_SCROLLABLE);
 messenger_button(u->bar,"Setup",messenger_toggle_setup);u->start=messenger_button(u->bar,"Start",messenger_start_click);u->send=messenger_button(u->bar,"Send",messenger_send_click);
 u->keyboard=lv_keyboard_create(function_page);lv_keyboard_set_textarea(u->keyboard,u->composer);lv_obj_set_style_text_font(u->keyboard,&lv_font_montserrat_12,0);
 lv_obj_set_style_bg_color(u->keyboard,ui_bg_color(),LV_PART_MAIN);lv_obj_set_style_text_color(u->keyboard,ui_text_color(),LV_PART_MAIN);lv_obj_set_style_bg_color(u->keyboard,lv_color_make(0,100,0),LV_PART_ITEMS);lv_obj_set_style_bg_color(u->keyboard,lv_color_make(0,150,0),LV_PART_ITEMS|LV_STATE_PRESSED);lv_obj_set_style_text_color(u->keyboard,ui_text_color(),LV_PART_ITEMS);lv_obj_set_style_border_color(u->keyboard,ui_border_color(),LV_PART_ITEMS);
 lv_obj_add_event_cb(u->keyboard,messenger_keyboard_event,LV_EVENT_READY,NULL);lv_obj_add_event_cb(u->keyboard,messenger_keyboard_event,LV_EVENT_CANCEL,NULL);
 messenger_layout();messenger_protocol(NULL);cym_messenger_info_request();u->timer=lv_timer_create(messenger_poll,100,NULL);messenger_poll(NULL);
}
