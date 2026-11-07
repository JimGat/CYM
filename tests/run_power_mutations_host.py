#!/usr/bin/env python3
# Exact production-source mutations in disposable task-owned inputs, never live source.
import os,subprocess,json,hashlib,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=Path(os.environ["CYM_TEST_OUT"])/"power-mutations";O.mkdir(parents=True,exist_ok=False)
files=["ESP32C5/main/main.c","ESP32C5/components/wifi_cli/wifi_common.c","ESP32C5/components/wifi_cli/include/wifi_common.h"]
variants=[
 ("getter-ignored",files[1],"if (acquired != ESP_OK) return acquired;","if (false) return acquired;","power_paths","getter failure rejects override"),
 ("mutable-live-level",files[0],"esp_err_t wifi = wifi_power_apply_requested(level);","esp_err_t wifi = wifi_power_apply_requested(g_pwr_lvl);","power_worker","active Max to Normal must invoke immutable per-radio setters"),
 ("invalid-save-accepted",files[0],"if (level != PWR_LVL_NORMAL && level != PWR_LVL_MAX) return ESP_ERR_INVALID_ARG;","if (false) return ESP_ERR_INVALID_ARG;","power_storage","nvs_settings_save_power_level(0)!=0 && sets==0 && commits==0"),
 ("getter-invalid-accepted",files[0],"if (!pwr_ble_level_valid(v)) { ok = false; continue; }","if (false) { ok = false; continue; }","power_ble","invalid category getter cannot override"),
 ("center-overflow",files[0],"lv_obj_set_flex_align(dialog, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);","lv_obj_set_flex_align(dialog, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);","power_popup","FAIL first label visible at scroll zero"),
 ("restart-poisons-baseline",files[1],"esp_err_t rc = esp_wifi_start();","s_wifi_power->captured = false; esp_err_t rc = esp_wifi_start();","power_paths","plain restart must not recapture retained Max"),
 ("retired-claim",files[1],"__atomic_store_n(&s_wifi_power->applied, 0, __ATOMIC_RELEASE);","/* mutant: retain stale applied level */","power_paths","no stale claim after retirement"),
 ("ble-late-result",files[0],"if (!__atomic_compare_exchange_n(&s_ble_power->state, &stamp, result,\n            false, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) ok = false;","__atomic_store_n(&s_ble_power->state, result, __ATOMIC_RELEASE);","power_ble","reset during setter rejects stale publication"),
 ("ble-partial-success",files[0],"if (rc != ESP_OK || !pwr_ble_level_valid(actual) || actual != target) ok = false;","if (false) ok = false;","power_ble","partial category apply is not full success"),
]
results=[]
for name,path,old,new,test,semantic in variants:
 d=O/name;src=d/"source";out=d/"out";out.mkdir(parents=True)
 for f in files:
  p=src/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((R/f).read_bytes())
 p=src/path;text=p.read_text()
 # Center change restricted to the production power popup, not other dialogs.
 if name=="center-overflow":
  a=text.index("static void show_power_mode_popup(void)\n{");b=text.index("// ─── Hardware Options",a);part=text[a:b];assert part.count(old)==1;changed=text[:a]+part.replace(old,new,1)+text[b:]
 else:
  assert text.count(old)>=1,(name,text.count(old));changed=text.replace(old,new,1)
 assert changed!=text;p.write_text(changed)
 env=dict(os.environ,CYM_POWER_SOURCE=str(src),CYM_TEST_OUT=str(out))
 cmd=[sys.executable,"-B",str(R/"tests"/("run_"+test+"_host.py"))];run=subprocess.run(cmd,env=env,capture_output=True,text=True)
 log=run.stdout+run.stderr;(d/"driver.log").write_text(log)
 compile_failure="error:" in log or "must compile" in log
 assertion="Assertion" in log and "failed" in log
 is_ui=name=="center-overflow"
 ok=run.returncode!=0 and semantic in log and not compile_failure and (("RESULT checks=" in log and "failures=0" not in log)if is_ui else assertion)
 record=dict(name=name,command=cmd,exit_code=run.returncode,semantic_marker=semantic,passed=ok,input_changed=True,before_sha256=hashlib.sha256(text.encode()).hexdigest(),after_sha256=hashlib.sha256(changed.encode()).hexdigest())
 results.append(record);(O/"results.json").write_text(json.dumps(results,indent=2));print(name,"KILLED"if ok else "FAIL",run.returncode,flush=True)
 if not ok:print(log[-5000:]);raise SystemExit(1)
print("PASS 9/9 production semantic mutants killed; compile/startup crashes rejected")
