#!/usr/bin/env python3
"""Production Messenger core native tests. Requires cc and OpenSSL development headers.
No target SDK, serial, RF, fixtures or message/key logging. Synthetic test key only.
"""
from pathlib import Path
import os,subprocess,tempfile,sys,json
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ['CYM_TEST_OUT']);OUT.mkdir(exist_ok=True,parents=True)
if '--verify-mutations' in sys.argv:
 records=[]
 for mode in ['accepted','tag-bypass','delivery-pending']:
  cmd=[sys.executable,'-B',__file__]+([] if mode=='accepted' else ['--mutate-'+mode])
  x=subprocess.run(cmd,env=dict(os.environ,CYM_TEST_OUT=str(OUT/mode)),capture_output=True,text=True)
  log=x.stdout+x.stderr;(OUT/(mode+'.log')).write_text(log)
  ok=x.returncode==0 if mode=='accepted' else x.returncode!=0 and 'Assertion' in log and 'failed' in log and 'Sanitizer' not in log and 'CalledProcessError' in log
  records.append(dict(mode=mode,exit_code=x.returncode,semantic=ok));print(mode,ok)
 (OUT/'mutations.json').write_text(json.dumps(records,indent=2))
 raise SystemExit(0 if all(r['semantic'] for r in records) else 1)
source=ROOT/'ESP32C5/main/cym_messenger_core.c'
assert source.exists(), 'Messenger production codec/session is missing'
harness=r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <openssl/hmac.h>
#include "cym_messenger_core.h"
static bool auth(const uint8_t k[16],const uint8_t *p,size_t n,uint8_t out[32]){unsigned len=0;return HMAC(EVP_sha256(),k,16,p,n,out,&len)&&len==32;}
static const uint8_t key[16]={1,2,3}, ma[6]={2,1},mb[6]={2,2},na[16]={1},nb[16]={2};
static cm_core a,b;
static cm_frame f,g,h;
static void setup(void){cm_init(&a,key,ma,mb,na,auth);cm_init(&b,key,mb,ma,nb,auth);assert(cm_hello(&a,&f));assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_HANDSHAKE);assert(cm_receive(&a,mb,g.bytes,g.len,&h)==CM_HANDSHAKE);assert(a.ready);assert(cm_receive(&b,ma,h.bytes,h.len,&g)==CM_HANDSHAKE);assert(b.ready);}
int main(void){
 assert(CM_FRAME_MAX==234 && CM_TEXT_MAX==160);
 assert(cm_text_valid((const uint8_t*)"hello",5));
 assert(cm_text_valid((const uint8_t*)"\xc3\xa9",2));
 const uint8_t bad[][4]={{0xc0,0xaf},{0xed,0xa0,0x80},{0xf4,0x90,0x80,0x80},{0xe2,0x82},{0x80},{0},{0x1b},{0x7f}};
 const unsigned lens[]={2,3,4,2,1,1,1,1};
 for(unsigned i=0;i<8;i++)assert(!cm_text_valid(bad[i],lens[i]));
 assert(!cm_text_valid((const uint8_t*)"#ff0000 red#",12));
 uint8_t full[161];memset(full,'a',sizeof full);assert(cm_text_valid(full,160));assert(!cm_text_valid(full,161));assert(!cm_text_valid(full,0));
 setup();assert(cm_submit(&a,(const uint8_t*)"hi",2,0,&f));assert(a.delivery==CM_PENDING);assert(!cm_submit(&a,(const uint8_t*)"again",5,0,&g));
 assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_ACCEPTED);assert(b.in_count==1);assert(a.delivery==CM_PENDING);
 assert(cm_receive(&a,mb,g.bytes,g.len,&h)==CM_DELIVERED);assert(a.delivery==CM_CONFIRMED);
 assert(cm_receive(&b,ma,f.bytes,f.len,&h)==CM_DUPLICATE);assert(b.in_count==1);assert(h.len==g.len&&!memcmp(h.bytes,g.bytes,g.len));
 assert(cm_receive(&a,mb,h.bytes,h.len,&g)==CM_REJECTED); // ACK of ACK forbidden
 cm_message m;assert(cm_pop(&b,&m));assert(m.len==2&&!memcmp(m.text,"hi",2));assert(!cm_pop(&b,&m));
 for(size_t n=0;n<f.len;n++)assert(cm_receive(&b,ma,f.bytes,n,&g)==CM_REJECTED);
 cm_frame corrupt=f;corrupt.bytes[42]^=1;assert(cm_receive(&b,ma,corrupt.bytes,corrupt.len,&g)==CM_REJECTED);
 uint8_t wrongmac[6]={2,9};assert(cm_receive(&b,wrongmac,f.bytes,f.len,&g)==CM_REJECTED);
 cm_core wrong=b;wrong.key[0]^=1;assert(cm_receive(&wrong,ma,f.bytes,f.len,&g)==CM_REJECTED);
 // Fresh Start rejects previously authenticated DATA and ACK.
 uint8_t fresh[16]={3};cm_init(&b,key,mb,ma,fresh,auth);assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_REJECTED);
 setup();assert(cm_submit(&a,full,160,0xfffffff0u,&f));assert(f.len==234);
 assert(!cm_retry(&a,0x10,&g));assert(cm_retry(&a,0x310,&g));assert(a.attempts==2);
 assert(cm_retry(&a,0x630,&g));assert(a.attempts==3);assert(!cm_retry(&a,0x950,&g));assert(a.delivery==CM_UNCONFIRMED);
 // Inbox overflow has no ACK, no acceptance and no last-rx advance.
 setup();for(unsigned i=0;i<4;i++){assert(cm_submit(&a,full,1,i,&f));assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_ACCEPTED);assert(cm_receive(&a,mb,g.bytes,g.len,&h)==CM_DELIVERED);}
 assert(cm_submit(&a,full,1,5,&f));assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_OVERFLOW);assert(g.len==0);assert(b.in_count==4);assert(cm_pop(&b,&m));assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_ACCEPTED);
 // Stale ACK cannot confirm next message; DATA id does not roll over.
 cm_frame stale=g;assert(cm_receive(&a,mb,g.bytes,g.len,&h)==CM_DELIVERED);assert(cm_submit(&a,full,1,6,&f));assert(cm_receive(&a,mb,stale.bytes,stale.len,&g)==CM_REJECTED);assert(a.delivery==CM_PENDING);
 a.delivery=CM_CONFIRMED;a.next_id=0xffffffffu;assert(!cm_submit(&a,full,1,8,&f));
 // Authenticated stale HELLO cannot reset an established peer/session.
 assert(cm_hello(&a,&f));assert(cm_receive(&b,ma,f.bytes,f.len,&g)==CM_HANDSHAKE);assert(b.last_rx==5);
 puts("Messenger core behavioral scenarios PASS");return 0;
}
"""
(OUT/'messenger-test.c').write_text(harness)
if any(a.startswith('--mutate-') for a in sys.argv):
 text=source.read_text()
 if '--mutate-tag-bypass' in sys.argv:
  needle='||!same(mac,p+CM_HEADER+n,32)';assert needle in text;text=text.replace(needle,'',1)
 elif '--mutate-delivery-pending' in sys.argv:
  needle='c->delivery=CM_CONFIRMED;';assert needle in text;text=text.replace(needle,'c->delivery=CM_PENDING;',1)
 else:raise SystemExit('unknown mutation')
 source=OUT/'core-mutant.c';source.write_text(text)
cmd=['cc' ,'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I'+str(ROOT/'ESP32C5/main'),str(source),str(OUT/'messenger-test.c'),'-lcrypto','-o',str(OUT/'messenger-test')]
subprocess.run(cmd,check=True);subprocess.run([str(OUT/'messenger-test')],check=True)
