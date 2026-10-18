#!/usr/bin/env python3
"""Compile actual retained Clock-pressure owner declaration and its consumers."""
from pathlib import Path
import os
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("CYM_TEST_OUT", os.environ.get("TMPDIR", str(ROOT / ".hermes")))) / "clock-data-placement"
SOURCE = (ROOT / "ESP32C5/main/main.c").read_text()


def production_function(name):
    match = re.search(r"^static void " + name + r"\([^;]*?\)\s*\{", SOURCE, re.M)
    assert match, name
    end, depth = match.end(), 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    return SOURCE[match.start():end]


class ClockDataPlacement(unittest.TestCase):
    def compile_owner(self, psram, execute):
        OUT.mkdir(parents=True, exist_ok=True)
        # Both the board policy and storage declaration come from production.
        policy = SOURCE[SOURCE.index("#if CONFIG_BOARD_HAS_PSRAM"):SOURCE.index("#include \"driver/spi_master.h\"")]
        start = SOURCE.index("#if defined(CONFIG_BOARD_CYD2USB)\n#define DETECT_MAX_RECORDS")
        end = SOURCE.index("static void cham_detect_stop", start)
        declarations = SOURCE[start:end]
        prefix = r"""
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EXT_RAM_BSS_ATTR __attribute__((section(".ext_ram.bss")))
typedef int lv_timer_t;
typedef int lv_obj_t;
typedef int lv_event_t;
static int sends, cancelled, timers, labels, next_index, send_ok = 1;
static void lv_timer_del(void *p) { assert(p); timers++; }
static void lv_label_set_text(void *p, const char *s) { assert(p && s); labels++; }
static void cham_cancel_pending(void) { cancelled++; }
static bool cham_send_cmd(int cmd, const uint8_t *p, int len,
                         void (*cb)(bool,const uint8_t*,uint16_t)) {
 assert(cmd == 4006 && len == 4 && p && cb); sends++;
 next_index = ((int)p[0]<<24)|((int)p[1]<<16)|((int)p[2]<<8)|p[3];
 return send_ok;
}
static char exported[1024];
static FILE *test_open(const char *p, const char *m) {
 assert(!strcmp(p,"/sdcard/lab/rfid/hf/mfkey32_nonces.txt") && !strcmp(m,"w"));
 return tmpfile();
}
static int test_close(FILE *f) {
 fflush(f); rewind(f); size_t n=fread(exported,1,sizeof(exported)-1,f);
 exported[n]=0; return fclose(f);
}
#define fopen test_open
#define fclose test_close
"""

        body = r"""
int main(void) {
 uint8_t record[18] = {3,3,0,0,0,1,0,0,0,2,0,0,0,3,0,0,0,4};
 assert(sizeof(s_det_record_t)==20);
 assert(DETECT_MAX_RECORDS == (CONFIG_BOARD_HAS_PSRAM ? 256 : 32));
 assert(sizeof(s_det_records)==20*DETECT_MAX_RECORDS);
 for(int cycle=0;cycle<100;cycle++) {
  s_det_count=0; s_det_remote_count=0; s_det_query_busy=true;
  s_det_on_results(false,record,18); assert(!s_det_query_busy&&!s_det_count);
  s_det_query_busy=true; s_det_on_results(true,NULL,18); assert(!s_det_query_busy&&!s_det_count);
  s_det_query_busy=true; s_det_on_results(true,record,17); assert(!s_det_query_busy&&!s_det_count);
  s_det_query_busy=true; s_det_on_results(true,record,19); assert(!s_det_query_busy&&!s_det_count);
  s_det_on_results(true,record,18);
  assert(s_det_count==1 && s_det_records[0].uid==1 && s_det_records[0].nt==2);
  assert(s_det_records[0].nr==3 && s_det_records[0].ar==4);
  assert(s_det_records[0].block==3 && s_det_records[0].key_type==0x61 && s_det_records[0].is_nested);
  s_det_on_results(true,record,18); s_det_export_cb(NULL);
  assert(strstr(exported,"00000001 00000002 00000003 00000004 00000002 00000003 00000004"));
  while(s_det_count<DETECT_MAX_RECORDS) s_det_on_results(true,record,18);
  s_det_on_results(true,record,18); assert(s_det_count==DETECT_MAX_RECORDS);
  s_det_count=0; s_det_remote_count=3; s_det_query_busy=true; sends=0; send_ok=1;
  s_det_on_results(true,record,18); assert(sends==1 && next_index==1 && s_det_query_busy);
  send_ok=0; s_det_on_results(true,record,18); assert(!s_det_query_busy);
  s_det_tmr=(void*)1; s_det_status=s_det_count_lbl=s_det_enable_btn=(void*)1;
  cham_detect_stop(); cham_detect_stop();
  assert(!s_det_tmr&&!s_det_status&&!s_det_count_lbl&&!s_det_enable_btn&&!s_det_query_busy);
 }
 assert(cancelled==200&&timers==100);
 puts("production retained owner: 100 init/use/stop/retry cycles PASS");
}
"""

        text = prefix + policy + declarations
        if execute:
            text += "\n".join(production_function(n) for n in
                              ["cham_detect_stop", "s_det_on_results", "s_det_export_cb"]) + body
        else:
            text += "\nvoid *owner_address(void) { return s_det_records; }\n"
        tag = ("psram" if psram else "internal") + ("-run" if execute else "-section")
        source, binary = OUT / (tag + ".c"), OUT / tag
        source.write_text(text)
        flags = ["-std=c11", "-O0", "-g", "-DCONFIG_BOARD_HAS_PSRAM=" + str(int(psram))]
        if not psram:
            flags += ["-DCONFIG_BOARD_CYD2USB=1"]
        if execute:
            flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-no-pie"]
        else:
            flags += ["-c"]
        subprocess.run(["gcc", *flags, str(source), "-o", str(binary)], check=True)
        if execute:
            subprocess.run([str(binary)], check=True)
        else:
            symbols = subprocess.check_output(["objdump", "-t", str(binary)], text=True)
            row = next(line for line in symbols.splitlines() if line.split()[-1:] == ["s_det_records"])
            self.assertIn(".ext_ram.bss" if psram else ".bss", row)
            if not psram:
                self.assertNotIn(".ext_ram.bss", row)

    def test_psram_owner_is_external_not_internal_bss(self):
        self.compile_owner(True, False)

    def test_no_psram_owner_retains_bounded_internal_storage(self):
        self.compile_owner(False, False)

    def test_psram_production_consumers_and_lifetime(self):
        self.compile_owner(True, True)

    def test_no_psram_production_consumers_and_lifetime(self):
        self.compile_owner(False, True)


if __name__ == "__main__":
    unittest.main()
