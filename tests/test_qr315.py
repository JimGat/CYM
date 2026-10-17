
# Execute full production QR UI with observable LVGL ownership/style boundaries.
import unittest
import test_qr_worker309 as worker
import test_qr311 as base
ORIGINAL=worker.PRE
class Modal315(unittest.TestCase):
 def test_modal_reset_stop_reentry(self):
  text=(worker.ROOT/'ESP32C5/main/qr_decoder_ui.c').read_text()
  self.assertIn('result_backdrop',text,'result still drawn over the scanning page')
  pre=ORIGINAL.replace('internal_free=4734,internal_largest=2304','internal_free=32768,internal_largest=16384')
  pre=pre.replace('typedef struct {int unused;} lv_obj_t;', 'typedef struct obj_t {struct obj_t *parent;int opa,flags,deleted;} lv_obj_t;')
  pre=pre.replace('#define lv_obj_create(...) (&obj)',r"""
static lv_obj_t nodes[128];static int node_count;
static lv_obj_t* make_obj(lv_obj_t*p){assert(node_count<128);lv_obj_t*n=&nodes[node_count++];n->parent=p;return n;}
#define lv_obj_create(p) make_obj(p)
""")
  pre=pre.replace('#define lv_obj_add_flag(...) ((void)0)', '#define lv_obj_add_flag(p,f) ((p)->flags|=(f))')
  pre=pre.replace('#define lv_obj_clear_flag(...) ((void)0)', '#define lv_obj_clear_flag(p,f) ((p)->flags&=~(f))')
  pre=pre.replace('#define lv_obj_set_style_bg_opa(...) ((void)0)', '#define lv_obj_set_style_bg_opa(p,o,s) ((p)->opa=(o))')
  pre=pre.replace('#define lv_obj_del(...) ((void)0)', '#define lv_obj_del(p) ((p)->deleted=1)')
  old=base.PRE;base.PRE=pre
  try:
   base.Lifecycle311.run_case(self,r"""
 assert(result_backdrop&&result_card&&result_status);
 assert(result_backdrop->parent==&obj&&result_card->parent==result_backdrop);
 assert(result_backdrop->opa==LV_OPA_COVER&&result_card->opa==LV_OPA_COVER);
 assert(result_backdrop->flags&LV_OBJ_FLAG_CLICKABLE);
 assert(result_backdrop->flags&LV_OBJ_FLAG_HIDDEN);
 bool opaque_body=false;for(int i=0;i<node_count;i++)if(nodes[i].parent==&obj&&&nodes[i]!=result_backdrop&&nodes[i].opa==LV_OPA_COVER)opaque_body=true;assert(opaque_body);
 atomic_store(&session->phase,QR_SAVING);poll(NULL);assert(!(result_backdrop->flags&LV_OBJ_FLAG_HIDDEN));
 run_worker();poll(NULL);assert(!(result_backdrop->flags&LV_OBJ_FLAG_HIDDEN));retry(NULL);assert(result_backdrop->flags&LV_OBJ_FLAG_HIDDEN);
 lv_obj_t *old_window=result_backdrop;finish_at=ticks+2;qr_decoder_ui_stop();assert(!result_backdrop&&!result_card&&!result_status&&!result_label&&old_window->deleted);
 setup();assert(result_backdrop&&result_backdrop!=old_window);assert(result_backdrop->flags&LV_OBJ_FLAG_HIDDEN);
 """)
  finally:base.PRE=old
 run_case=base.Lifecycle311.run_case
if __name__=='__main__':unittest.main()
