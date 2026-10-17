"""Production popup presentation: theme overrides and full saved path."""
import unittest
import test_qr_worker309 as worker
import test_qr311 as base
class Popup316(unittest.TestCase):
 def test_result_text_and_path(self):
  pre=worker.PRE.replace('internal_free=4734,internal_largest=2304','internal_free=32768,internal_largest=16384')
  pre=pre.replace('typedef struct {int unused;} lv_obj_t;', 'typedef struct node {int color;const lv_font_t *font;char text[512];} lv_obj_t;')
  pre=pre.replace('static lv_obj_t obj;', 'static lv_obj_t obj,nodes[128];static unsigned used;static lv_obj_t *make_node(void){assert(used<128);nodes[used].color=99;return &nodes[used++];}')
  for kind in ['obj','label','img','btn']:
   pre=pre.replace('#define lv_'+kind+'_create(...) (&obj)', '#define lv_'+kind+'_create(...) make_node()')
  pre=pre.replace('#define lv_obj_set_style_text_color(...) ((void)0)', '#define lv_obj_set_style_text_color(p,c,s) ((p)->color=(c))')
  pre=pre.replace('#define lv_obj_set_style_text_font(...) ((void)0)', '#define lv_obj_set_style_text_font(p,f,s) ((p)->font=(f))')
  pre=pre.replace('(void)p;snprintf(displayed', 'snprintf(p->text,sizeof(p->text),"%s",s);snprintf(displayed')
  old=base.PRE;base.PRE=pre
  try:
   base.Lifecycle311.run_case(self,r"""
 assert(result_status->color==style.text && result_label->color==style.text);
 assert(result_status->font==style.font && result_label->font==style.font);
 run_worker();poll(NULL);
 assert(!strcmp(result_label->text,"x"));
 assert(strstr(result_status->text,"/sdcard/lab/QR/test.json"));
 retry(NULL);save_error=ENOSPC;run_worker();poll(NULL);
 assert(strstr(result_status->text,"Not saved"));assert(!strcmp(result_label->text,"x"));
 assert(!strstr(result_status->text,"Saved /sdcard"));
 """)
  finally:base.PRE=old

 def test_actual_action_buttons_theme_states(self):
  # Observe every node and selector; resolve label inheritance just as LVGL's
  # label theme does. Deliberately hostile card defaults catch missing setters.
  pre=base.PRE
  pre=pre.replace('typedef struct {int unused;} lv_obj_t;', 'typedef struct node {struct node *parent;int bg[3],color[3],opa[3];const lv_font_t *font;char text[160];} lv_obj_t;')
  pre=pre.replace('static lv_obj_t obj;', 'static lv_obj_t obj,nodes[128];static unsigned used;static lv_obj_t *make_node(lv_obj_t *p){assert(used<128);lv_obj_t *n=&nodes[used++];n->parent=p;for(int i=0;i<3;i++){n->bg[i]=99;n->color[i]=-1;}return n;}')
  for kind in ['obj','label','img','btn']:
   pre=pre.replace('#define lv_'+kind+'_create(...) (&obj)', '#define lv_'+kind+'_create(p) make_node(p)')
  pre=pre.replace('#define lv_obj_set_style_bg_color(...) ((void)0)', '#define lv_obj_set_style_bg_color(p,c,s) ((p)->bg[s]=(c))')
  pre=pre.replace('#define lv_obj_set_style_bg_opa(...) ((void)0)', '#define lv_obj_set_style_bg_opa(p,c,s) ((p)->opa[s]=(c))')
  pre=pre.replace('#define lv_obj_set_style_text_color(...) ((void)0)', '#define lv_obj_set_style_text_color(p,c,s) ((p)->color[s]=(c))')
  pre=pre.replace('#define lv_obj_set_style_text_font(...) ((void)0)', '#define lv_obj_set_style_text_font(p,f,s) ((p)->font=(f))')
  pre=pre.replace('(void)p;snprintf(displayed', 'snprintf(p->text,sizeof(p->text),"%s",s);snprintf(displayed')
  old=base.PRE;base.PRE=pre
  try:
   base.Lifecycle311.run_case(self,r"""
 static lv_font_t font;
 /* Two contrasting page/card/text schemes; action palette independent of it. */
 for(int light=0;light<2;light++){
  style.panel=light?0xffffff:0x121212;style.card=light?0xf5f5f5:0x263238;
  style.text=light?0x212121:0xffffff;style.muted=light?0x616161:0xb0bec5;
  style.action=0x2196f3;style.action_pressed=0x4ca9f5;style.action_text=0xffffff;style.font=&font;
  lv_obj_t *buttons[]={capture_button,retry_button};
  const char *names[]={"Save Debug Frame","Scan Again / Retry"};
  for(int b=0;b<2;b++){
   lv_obj_t *button=buttons[b];theme_button(button);
   assert(button->bg[0]==style.action && button->bg[LV_STATE_PRESSED]==style.action_pressed);
   assert(button->bg[LV_STATE_DISABLED]==style.card && button->opa[0]==LV_OPA_COVER);
   assert(button->color[0]==style.action_text && button->color[LV_STATE_DISABLED]==style.muted);
   assert(button->font==&font);
   lv_obj_t *caption=NULL;
   for(unsigned n=0;n<used;n++)if(nodes[n].parent==button&&!strcmp(nodes[n].text,names[b]))caption=&nodes[n];
   assert(caption);
   for(int state=0;state<3;state++){
    int foreground=caption->color[state];
    if(foreground<0)foreground=button->color[state];
    if(foreground<0)foreground=button->color[0];
    assert(foreground==(state==LV_STATE_DISABLED?style.muted:style.action_text));
   }
  }
 }
 /* Styling does not change consent, disabled-save state or explicit retry. */
 pending();assert(atomic_load(&session->capture)==1);
 run_worker();poll(NULL);assert(save_calls==1&&atomic_load(&session->phase)==QR_RESULT);
 retry(NULL);assert(atomic_load(&session->phase)==QR_STARTING);
 """)
  finally:base.PRE=old

 def test_action_palette_comes_from_existing_cym_blue(self):
  text=(worker.ROOT/'ESP32C5/main/main.c').read_text()
  start=text.index('static void show_qr_decoder(void)\n{')
  screen=text[start:text.index('\n#endif',start)]
  self.assertIn('.action=UI_ACCENT_BLUE',screen)
  self.assertIn('.action_pressed=lv_color_lighten(UI_ACCENT_BLUE,50)',screen)
  self.assertIn('.action_text=lv_color_white()',screen)

if __name__=='__main__':unittest.main()
