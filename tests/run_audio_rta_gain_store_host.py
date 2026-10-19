#!/usr/bin/env python3
"""ASan/UBSan fault injection against the production worker-only NVS boundary."""
from pathlib import Path
import os,subprocess
from audio_rta_nvs_stubs import write_nvs_stub
R=Path(__file__).resolve().parents[1];D=Path(os.environ['CYM_TEST_OUT'])/'rta-gain-store';D.mkdir(parents=True,exist_ok=True)
write_nvs_stub(D)
(D/'esp_err.h').write_text('typedef int esp_err_t;\n#define ESP_ERR_INVALID_ARG 2\n')
(D/'host.c').write_text(r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include "audio_rta.h"
#include "audio_rta_gain_store.inc"
static void reset(void){nvs_open_error=nvs_read_error=nvs_set_error=nvs_commit_error=nvs_present=nvs_sets=nvs_commits=nvs_opens=nvs_closes=0;}
int main(void){int p,e;audio_rta_store_stage_t s;
 reset();assert(gain_load(&p,&e,&s)==24&&p==-1&&!e&&s==RTA_STORE_OK);assert(nvs_opens==nvs_closes);
 nvs_open_error=ESP_ERR_NVS_NOT_FOUND;assert(gain_load(&p,&e,&s)==24&&p==-1&&!e);
 reset();nvs_open_error=51;assert(gain_load(&p,&e,&s)==24&&p==-1&&e==51&&s==RTA_STORE_OPEN&&!nvs_closes);
 reset();nvs_read_error=52;assert(gain_load(&p,&e,&s)==24&&p==-1&&e==52&&s==RTA_STORE_READ&&nvs_opens==nvs_closes);
 for(int v=-12;v<=55;v++){
  reset();nvs_present=1;nvs_value=v;int g=gain_load(&p,&e,&s);
  if(v>=0&&v<=42&&v%6==0){assert(g==v&&p==v&&!e);gain_save(v,&p,&e,&s);assert(!nvs_sets&&!nvs_commits);}
  else assert(g==24&&p==-1&&e==ESP_ERR_INVALID_ARG&&s==RTA_STORE_INVALID);
 }
 for(int v=0;v<=42;v+=6){reset();p=-1;gain_save(v,&p,&e,&s);assert(p==v&&!e&&nvs_sets==1&&nvs_commits==1);assert(gain_load(&p,&e,&s)==v&&p==v);gain_save(v,&p,&e,&s);assert(nvs_sets==1&&nvs_commits==1);}
 for(int step=0;step<3;step++){
  reset();nvs_present=1;nvs_value=0;p=0;
  if(step==0)nvs_open_error=61;if(step==1)nvs_set_error=62;if(step==2)nvs_commit_error=63;
  gain_save(42,&p,&e,&s);assert(p==0&&nvs_value==0&&e==61+step&&s==(step==0?RTA_STORE_OPEN:step==1?RTA_STORE_SET:RTA_STORE_COMMIT));
  assert(nvs_sets==(step>0)&&nvs_commits==(step>1));
  nvs_open_error=nvs_set_error=nvs_commit_error=0;assert(gain_load(&p,&e,&s)==0&&p==0);
  gain_save(42,&p,&e,&s);assert(p==42&&nvs_value==42&&!e);assert(nvs_opens==nvs_closes+(step==0));
 }
 reset();p=0;gain_save(7,&p,&e,&s);assert(s==RTA_STORE_INVALID&&p==0&&!nvs_opens);
 puts("PASS production NVS: absent/corrupt/open/read, all 8 steps including saved0, invalid values, unchanged, open/set/commit failures, reopen and retry");return 0;
}
""")
subprocess.run(['cc','-std=gnu11','-g','-O1','-fsanitize=address,undefined','-I'+str(D),'-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(D/'host')],check=True)
subprocess.run([str(D/'host')],check=True)
