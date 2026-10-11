from pathlib import Path
import re, subprocess, unittest
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".hermes/doom-prototype/owner-host"

def function(source, name):
    match = re.search(r"(?m)^[a-zA-Z][^;\n]*\b" + name + r"\([^;]*?\)\s*\{", source)
    if not match: raise ValueError("missing production definition: "+name)
    start = match.start()
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]

class OwnerLifecycle(unittest.TestCase):
    def test_production_join_race(self):
        source = (ROOT / "ESP32C5/components/cym_doom/doom_ui.c").read_text()
        fn = function(source, "join_worker")
        code = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
typedef int *TaskHandle_t;
enum { eRunning, eSuspended };
static int state, deletes;
static int eTaskGetState(TaskHandle_t t) { assert(t); return state; }
static void vTaskDelete(TaskHandle_t t) { assert(t); assert(state==eSuspended); deletes++; }
""" + fn + r"""
int main(void) {
 int task; TaskHandle_t h=&task; bool done=false;
 state=eRunning; assert(!join_worker(&h,&done)); assert(h && !deletes);
 __atomic_store_n(&done,true,__ATOMIC_RELEASE);
 /* Publishing cleanup does NOT prove suspension. Lower/higher priority and
    SMP preemption must not permit deletion between publication and suspend. */
 assert(!join_worker(&h,&done)); assert(h && !deletes);
 state=eSuspended; assert(join_worker(&h,&done)); assert(!h && deletes==1);
 assert(join_worker(&h,&done)); assert(deletes==1);
 return 0;
}
"""
        self.run_c("join", code)

    def run_c(self, name, code, extra=(), includes=()):
        OUT.mkdir(parents=True,exist_ok=True)
        src=OUT/(name+".c"); exe=OUT/name; src.write_text(code)
        p=subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror",
             "-fsanitize=address,undefined","-fno-sanitize-recover=all","-g",*["-I"+i for i in includes],str(src),*extra,"-o",str(exe)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
        (OUT/(name+".log")).write_text(p.stdout+p.stderr)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_selector_transform_never_stops_radios(self):
        s=(ROOT/"ESP32C5/main/main.c").read_text();f=function(s,"game_selector_rotation")
        for driver in ("bt_nimble_deinit(","esp_wifi_stop(","esp_ieee802154_sleep(","nvs_settings_save"):
            self.assertNotIn(driver,f)
        self.assertIn("apply_screen_orientation(3)",f)
        self.assertIn("apply_screen_orientation(s_game_prior_orientation)",f)

if __name__ == "__main__": unittest.main(verbosity=2)
