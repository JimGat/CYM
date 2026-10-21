from pathlib import Path
import os, re, subprocess, json
R=Path(__file__).resolve().parents[1]
D=Path(os.environ['CYM_TEST_OUT'])/'classic-ble-fallback'
D.mkdir(parents=True,exist_ok=True)
M=(R/'ESP32C5/main/main.c').read_text()
L=(R/'ESP32C5/main/lvgl_memory.c').read_text()
F=(R/'tests/fixtures/classic_ble_fallback.c').read_text()
def fn(s,n):
 m=re.search(r'(?:static\s+)?(?:void\s*\*?|bool|BaseType_t)\s*'+n+r'\([^;]*?\)\s*\{',s); assert m,n
 i=m.end();d=1
 while d:
  d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
for n in ['bt_scan_worker_start','bt_scan_task','bt_alloc_failed']:
 F=F.replace(fn(F,n),fn(M,n))
for n in ['lvgl_malloc','lvgl_realloc','lvgl_free']:
 F=F.replace(fn(F,n),fn(L,n))
(D/'host.c').write_text(F)
results=[]
for classic,hacker,psram,dbg in [(1,0,0,d) for d in [0,1]]+[(1,1,0,d) for d in [0,1]]+[(0,0,0,d) for d in [0,1]]+[(0,0,1,d) for d in [0,1]]:
 exe=D/f'host-{classic}-{hacker}-{psram}-{dbg}'
 cmd=['cc','-std=gnu11','-O1','-DHZ=100',f'-DDBG={dbg}',f'-DCLASSIC={classic}',f'-DCONFIG_BOARD_CYD2USB={classic or psram}',f'-DCONFIG_BOARD_HACKERBOX_CYD={hacker}',f'-DCONFIG_BOARD_HAS_PSRAM={psram}',f'-DCONFIG_SPIRAM={psram}','-I'+str(R/'ESP32C5/main'),str(D/'host.c'),'-o',str(exe)]
 subprocess.run(cmd,check=True)
 for case in ['control','malloc','realloc','cancel','start-fail','cancel-retry','create-fail','early-cancel']:
  p=subprocess.run([str(exe),case],capture_output=True,text=True)
  results.append(dict(classic=classic,hackerbox=hacker,psram=psram,debug=dbg,case=case,exit=p.returncode,output=p.stdout+p.stderr))
  print(results[-1])
(D/'results.json').write_text(json.dumps(results,indent=2))
assert all(r['exit']==0 for r in results)
