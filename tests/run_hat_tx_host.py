#!/usr/bin/env python3
"""Production HAT admission and actual waveform extraction; no RF hardware."""
import os, subprocess, json, hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'hat-tx';D.mkdir(parents=True,exist_ok=True)
core=R/'ESP32C5/components/rf_hat/src/hat_tx.c'
assert core.exists(), 'Package C production admission missing'

def extract(s,sig):
    a=s.index(sig);b=s.index('{',a);depth=1;i=b+1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[a:i]
rf=(R/'ESP32C5/components/rf_hat/src/rf433_hat.c').read_text()
wave=extract(rf,'rf433_hat_err_t rf433_hat_replay_owned(')+'\n'+extract(rf,'rf433_hat_err_t rf433_hat_replay(')
pre=r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <pthread.h>
#include "hat_tx.h"
#define ESP_OK 0
#define RF_HAT_RF433_TX_GPIO 8
#define RF433_HAT_MAX_PULSES 512
typedef struct { uint32_t count;uint32_t pulses_us[512]; } rf433_signal_t;
typedef enum {RF433_HAT_OK,RF433_HAT_ERR_NOT_INIT,RF433_HAT_ERR_HW,RF433_HAT_ERR_BUSY} rf433_hat_err_t;
static bool s_init=true;
static int highs, lows, fail_low, inhibit_high;
static int64_t now;
static int gpio_set_level(int pin,int level) {
    assert(pin==8);
    if(level) { highs++;if(inhibit_high && highs==inhibit_high) hat_tx_inhibit(true); }
    else {lows++;if(fail_low)return -1;}
    return 0;
}
static int64_t esp_timer_get_time(void){return now++;}
#define pdMS_TO_TICKS(x) (x)
static void vTaskDelay(int t){now+=t*1000;}
"""
post=r"""
static pthread_barrier_t phase;
static void*producer(void*arg){for(int i=0;i<1000;i++){hat_tx_ticket_t t;pthread_barrier_wait(&phase);assert(hat_tx_begin(HAT_TX_CC1101,&t)&&hat_tx_enter(t));pthread_barrier_wait(&phase);pthread_barrier_wait(&phase);assert(!hat_tx_valid(t)&&!hat_tx_enter(t));hat_tx_leave(t);hat_tx_finish(t,true);pthread_barrier_wait(&phase);}return NULL;}
static void race(void){pthread_t p;assert(!pthread_barrier_init(&phase,NULL,2));assert(!pthread_create(&p,NULL,producer,NULL));for(int i=0;i<1000;i++){hat_tx_inhibit(false);pthread_barrier_wait(&phase);pthread_barrier_wait(&phase);hat_tx_inhibit(true);hat_tx_ticket_t t;assert(!hat_tx_claim_stop(HAT_TX_CC1101,&t));pthread_barrier_wait(&phase);pthread_barrier_wait(&phase);assert(!hat_tx_owned(HAT_TX_CC1101));}pthread_join(p,NULL);pthread_barrier_destroy(&phase);hat_tx_inhibit(false);}
int main(void) {
    race();
    hat_tx_ticket_t t,u;
    assert(!hat_tx_snapshot().inhibit);
    assert(hat_tx_begin(HAT_TX_CC1101,&t));assert(hat_tx_enter(t));
    hat_tx_inhibit(true);assert(!hat_tx_valid(t));
    assert(!hat_tx_claim_stop(HAT_TX_CC1101,&u));
    hat_tx_finish(t,true);assert(hat_tx_owned(HAT_TX_CC1101));
    hat_tx_leave(t);assert(hat_tx_claim_stop(HAT_TX_CC1101,&u));
    hat_tx_finish(u,false);assert(hat_tx_snapshot().state[0]==HAT_TX_ERROR);
    hat_tx_inhibit(false);assert(!hat_tx_valid(t));assert(!hat_tx_begin(HAT_TX_CC1101,&u));
    assert(hat_tx_claim_stop(HAT_TX_CC1101,&u));hat_tx_finish(u,true);
    assert(hat_tx_begin(HAT_TX_CC1101,&u));hat_tx_finish(t,true);assert(hat_tx_owned(HAT_TX_CC1101));
    hat_tx_cancel(HAT_TX_CC1101);assert(!hat_tx_enter(u));hat_tx_finish(u,true);
    rf433_signal_t sig={.count=4,.pulses_us={100,200,300,400}};
    assert(rf433_hat_replay(&sig,2)==RF433_HAT_OK);assert(highs==4);assert(!hat_tx_owned(HAT_TX_RF433));
    int h=highs;hat_tx_inhibit(true);assert(rf433_hat_replay(&sig,1)==RF433_HAT_ERR_BUSY);assert(highs==h);
    hat_tx_inhibit(false);inhibit_high=highs+1;
    assert(rf433_hat_replay(&sig,2)==RF433_HAT_ERR_BUSY);assert(highs==h+1);assert(!hat_tx_owned(HAT_TX_RF433));
    hat_tx_inhibit(false);inhibit_high=0;fail_low=1;
    assert(rf433_hat_replay(&sig,1)==RF433_HAT_ERR_HW);assert(hat_tx_snapshot().state[3]==HAT_TX_ERROR);
    assert(rf433_hat_replay(&sig,1)==RF433_HAT_ERR_BUSY);
    fail_low=0;assert(hat_tx_claim_stop(HAT_TX_RF433,&t));hat_tx_finish(t,true);
    sig.pulses_us[0]=0xffffffff;h=highs;
    assert(rf433_hat_replay(&sig,1)==RF433_HAT_ERR_HW);assert(highs==h);
    for(int i=0;i<100;i++){hat_tx_inhibit(true);hat_tx_inhibit(false);assert(!hat_tx_owned(HAT_TX_RF433));}
    puts("PASS production state + real RF433 emission boundary, bounds, cancel, stop failure retention, retry, stale completion and toggles");
}
"""
variants=[('production',core.read_text(),wave,False),
 ('admit-inhibited',core.read_text().replace('!s_inhibit && !o->owned','!o->owned'),wave,True),
 ('drop-error-owner',core.read_text().replace('o->error=true; o->cancel=true;','o->owned=false; o->error=true; o->cancel=true;'),wave,True),
 ('ignore-inflight',core.read_text().replace(' && !s_owner[t.id].requests',''),wave,True),
 ('ignore-cancel',core.read_text(),wave.replace('if (!hat_tx_valid(ticket))','if (false)'),True)]
results=[]
for name,c,w,mutant in variants:
    d=D/name;d.mkdir(exist_ok=True);(d/'core.c').write_text(c);(d/'wave.c').write_text(pre+w+post)
    cmd=['cc','-std=gnu11','-g','-O1','-DHAT_TX_HOST','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I'+str(R/'ESP32C5/components/rf_hat/include'),str(d/'core.c'),str(d/'wave.c'),'-o',str(d/'host')]
    b=subprocess.run(cmd,capture_output=True,text=True);(d/'compile.log').write_text(b.stdout+b.stderr);assert b.returncode==0,b.stderr
    run=subprocess.run([str(d/'host')],capture_output=True,text=True);(d/'run.log').write_text(run.stdout+run.stderr)
    ok=(run.returncode!=0 and 'Assertion' in run.stderr) if mutant else run.returncode==0
    print(name,'PASS' if ok else 'FAIL',run.stdout.strip());results.append(dict(name=name,exit=run.returncode,ok=ok,mutant=mutant))
(D/'results.json').write_text(json.dumps(dict(results=results,core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),wave_sha256=hashlib.sha256(wave.encode()).hexdigest()),indent=2))
assert all(x['ok'] for x in results)
