"""Production-source native regressions for Chameleon Patch08 integration."""
from pathlib import Path
import subprocess, tempfile, unittest, re
ROOT = Path(__file__).resolve().parents[1]

def function(source, signature):
    assert signature in source, 'Missing production definition: '+signature
    start=source.index(signature); opening=source.index('{',start); depth=0
    for i in range(opening,len(source)):
        if source[i]=='{': depth+=1
        elif source[i]=='}':
            depth-=1
            if depth==0: return source[start:i+1]
    raise AssertionError('Unterminated definition')

class Chameleon96(unittest.TestCase):
    def native(self, code):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'probe.c').write_text(code)
            q=subprocess.run(['cc','-std=c11',str(p/'probe.c'),'-o',str(p/'probe')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr[-3000:])
            q=subprocess.run([str(p/'probe')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stdout+q.stderr)

    def test_actual_chunk_sender_bounded_default_large_and_final_chunks(self):
        s=(ROOT/'ESP32C5/main/main.c').read_text()
        defines='\n'.join(re.findall(r'^#define CHAM_(?:MFC_CHUNK_BLOCKS|NTAG_CHUNK_PAGES)\s+[^\n]+',s,re.M))
        self.assertTrue('CHAM_MFC_CHUNK_BLOCKS' in defines and 'CHAM_NTAG_CHUNK_PAGES' in defines)
        body=function(s,'static void s_clone_hf_send_next_chunk(void)\n{')
        self.native(r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t *s_clone_hf_buf;
static unsigned s_clone_hf_buf_len;
static int label_object;
static void *s_clone_status_lbl=&label_object;
static bool s_clone_hf_is_mfc;
static int s_clone_hf_chunk_total,s_clone_hf_chunk_idx,calls;
static uint16_t capacity,last_length;
static uint8_t last_data[1024];
static char label_text[128];
static uint16_t cham_max_cmd_payload(void){return capacity;}
static void lv_label_set_text(void *p,const char *s){assert(p);snprintf(label_text,sizeof(label_text),"%s",s);}
static void s_clone_hf_chunk_cb(bool ok,const uint8_t *p,uint16_t n){(void)ok;(void)p;(void)n;}
static bool cham_send_cmd(uint16_t cmd,const uint8_t *p,uint16_t n,void (*cb)(bool,const uint8_t*,uint16_t)){
 assert(cmd==(s_clone_hf_is_mfc?4000:4022));assert(cb==s_clone_hf_chunk_cb);assert(n<=capacity);assert(n<=sizeof(last_data));
 calls++;last_length=n;memcpy(last_data,p,n);return true;
}
"""+defines+'\n'+body+r"""
static void run(bool mfc,uint16_t cap,int total,int already,int expected){
 capacity=cap;calls=0;s_clone_hf_is_mfc=mfc;s_clone_hf_chunk_total=total;s_clone_hf_chunk_idx=already;
 s_clone_hf_buf_len=4096;s_clone_hf_buf=malloc(s_clone_hf_buf_len);assert(s_clone_hf_buf);
 for(unsigned i=0;i<s_clone_hf_buf_len;i++)s_clone_hf_buf[i]=(uint8_t)(i%251);
 s_clone_hf_send_next_chunk();
 if(expected==0){assert(calls==0);assert(s_clone_hf_chunk_idx==already);assert(!s_clone_hf_buf);assert(s_clone_hf_buf_len==0);assert(strstr(label_text,"MTU"));}
 else {assert(calls==1);assert(s_clone_hf_chunk_idx==already+expected);assert(last_length==(mfc?1+16*expected:2+4*expected));assert(last_data[0]==already);
  if(!mfc)assert(last_data[1]==expected);
  assert(memcmp(last_data+(mfc?1:2),s_clone_hf_buf+already*(mfc?16:4),expected*(mfc?16:4))==0);
 }
 free(s_clone_hf_buf);s_clone_hf_buf=NULL;
}
int main(void){
 run(true,10,64,0,0);run(true,16,64,0,0);run(true,17,64,0,1);
 run(false,5,100,0,0);run(false,6,100,0,1);run(false,10,100,0,2);
 run(true,234,64,0,14);run(false,234,100,0,58);
 run(true,504,64,0,CHAM_MFC_CHUNK_BLOCKS);run(false,504,200,0,CHAM_NTAG_CHUNK_PAGES);
 run(true,234,18,14,4);run(false,234,60,58,2);
 puts("Actual chunk sender: bounded payloads/data offsets/abort cleanup PASS");return 0;
}
""")

    def test_live_mtu_authority_disconnected_and_fallback(self):
        s=(ROOT/'ESP32C5/main/chameleon_ble.c').read_text()
        body=function(s,'uint16_t cham_max_cmd_payload(void)\n{')
        self.native(r"""
#include <assert.h>
#include <stdint.h>
#define BLE_HS_CONN_HANDLE_NONE 65535
static uint16_t s_conn_handle=7,s_att_mtu,live_mtu;
static unsigned queries;
static uint16_t ble_att_mtu(uint16_t h){assert(h==7);queries++;return live_mtu;}
"""+body+r"""
int main(void){
 live_mtu=23;s_att_mtu=247;assert(cham_max_cmd_payload()==10);
 live_mtu=247;s_att_mtu=517;assert(cham_max_cmd_payload()==234);
 live_mtu=517;s_att_mtu=0;assert(cham_max_cmd_payload()==504);
 live_mtu=0;s_att_mtu=247;assert(cham_max_cmd_payload()==234);
 live_mtu=0;s_att_mtu=0;assert(cham_max_cmd_payload()==10);
 s_conn_handle=BLE_HS_CONN_HANDLE_NONE;s_att_mtu=247;queries=0;assert(cham_max_cmd_payload()==0);assert(queries==0);
 return 0;
}
""")

    def test_mtu_event_filters_connection_and_att_channel(self):
        s=(ROOT/'ESP32C5/main/chameleon_ble.c').read_text();token='    case BLE_GAP_EVENT_MTU:'
        self.assertTrue(token in s,'Missing MTU event handling')
        start=s.index(token);stop=s.index('\n        break;',start)+len('\n        break;');body=s[start:stop]
        self.native(r"""
#include <assert.h>
#include <stdint.h>
#define BLE_GAP_EVENT_MTU 15
#define BLE_L2CAP_CID_ATT 4
#define ESP_LOGI(...) ((void)0)
struct ble_gap_event{int type;struct{uint16_t conn_handle,channel_id,value;}mtu;};
static uint16_t s_conn_handle=7,s_att_mtu;
static void handle(struct ble_gap_event *event){switch(event->type){
"""+body+r"""
}}
int main(void){struct ble_gap_event e={BLE_GAP_EVENT_MTU,{8,4,247}};handle(&e);assert(s_att_mtu==0);
 e.mtu.conn_handle=7;e.mtu.channel_id=64;handle(&e);assert(s_att_mtu==0);
 e.mtu.channel_id=4;e.mtu.value=247;handle(&e);assert(s_att_mtu==247);return 0;}
""")

    def test_autoclose_timer_identity_and_idempotent_cancel(self):
        s=(ROOT/'ESP32C5/main/main.c').read_text()
        cancel=function(s,'static void s_clone_close_timer_cancel(void)\n{')
        close=function(s,'static void s_clone_autoclose_cb(lv_timer_t *t)\n{')
        self.native(r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
typedef struct{int id;}lv_timer_t;
typedef struct{int id;}lv_obj_t;
static lv_timer_t *s_clone_close_tmr;
static lv_obj_t *s_clone_popup,*s_clone_status_lbl;
static int timer_deletes,popup_deletes;
static void lv_timer_del(lv_timer_t *t){assert(t);timer_deletes++;}
static bool lv_obj_is_valid(lv_obj_t *p){return p!=NULL;}
static void lv_obj_del(lv_obj_t *p){assert(p);popup_deletes++;}
"""+cancel+'\n'+close+r"""
int main(void){lv_timer_t old={1},current={2};lv_obj_t popup={1},label={2};
 s_clone_close_tmr=&current;s_clone_popup=&popup;s_clone_status_lbl=&label;
 s_clone_autoclose_cb(&old);assert(s_clone_close_tmr==&current);assert(s_clone_popup==&popup);assert(popup_deletes==0);
 s_clone_close_timer_cancel();s_clone_close_timer_cancel();assert(timer_deletes==1);assert(!s_clone_close_tmr);
 s_clone_autoclose_cb(&old);assert(popup_deletes==0);
 s_clone_close_tmr=&current;s_clone_autoclose_cb(&current);assert(!s_clone_close_tmr);assert(!s_clone_popup);assert(!s_clone_status_lbl);assert(popup_deletes==1);return 0;
}
""")

    def test_every_popup_owner_cancels_before_teardown_or_replacement(self):
        s=(ROOT/'ESP32C5/main/main.c').read_text()
        owners=['cham_lf_read_stop(void)','cham_slots_stop(void)','cham_saved_cards_stop(void)',
                's_clone_close_cb(lv_event_t *e)','s_lf_show_clone_picker(lv_obj_t *parent)',
                's_fb_file_tap_cb(lv_event_t *e)','s_cards_slot_pick_cb(lv_event_t *e)']
        for name in owners:
            body=function(s,'static void '+name+'\n{')
            self.assertTrue('s_clone_close_timer_cancel();' in body,'Missing timer cancellation: '+name)
            deletion=body.find('lv_obj_del(s_clone_popup)')
            if deletion>=0:self.assertLess(body.index('s_clone_close_timer_cancel();'),deletion,name)

    def test_saved_slot_picker_cancel_does_not_cover_second_row(self):
        s=(ROOT/'ESP32C5/main/main.c').read_text()
        body=function(s,'static void s_cards_click_cb(lv_event_t *e)\n{')
        self.assertTrue('lv_obj_set_size(s_cards_slot_popup, 220, 140);' in body,'Slot picker still has overlapping 120px height')

if __name__=='__main__':unittest.main()
