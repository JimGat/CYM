#!/usr/bin/env python3
"""Package G (PN532 preexisting handle-loss ownership): production-extracted native proof
that pn532_driver_init()/deinit() retain still-owned I2C handles when a release call fails,
never reacquire a bus over a live resource, and fully release on success.

Extracts pn532_driver_init and pn532_driver_deinit VERBATIM from the component source
(sha256 in provenance.json) and drives them with instrumented I2C mocks that inject
add-device / bus-delete / device-remove failures. Compiled with ASan+UBSan.

This is a driver-lifecycle logic proof, NOT RF / card-detection / on-device proof.
"""
from pathlib import Path
import os, re, subprocess, hashlib, json

R = Path(__file__).resolve().parents[1]
SRC = R / 'ESP32C5/components/rfid/src/hf/pn532_driver.c'
D = Path(os.environ['CYM_TEST_OUT']) / 'pn532-ownership'
D.mkdir(parents=True, exist_ok=True)
s = SRC.read_text(encoding='utf-8', errors='replace')

def extract(sig):
    i = s.index(sig)
    j = s.index('{', i)
    depth = 1; k = j + 1
    while depth:
        depth += (s[k] == '{') - (s[k] == '}'); k += 1
    return s[i:k]

init_fn   = extract('rfid_err_t pn532_driver_init(void)')
deinit_fn = '\n'.join(extract(x) for x in ['bool pn532_driver_release(void)', 'void pn532_driver_deinit(void)', 'bool pn532_driver_is_init(void)', 'bool pn532_driver_is_owned(void)', 'rfid_err_t pn532_send_command(', 'rfid_err_t pn532_rf_field_off(void)'])

pre = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>

typedef int esp_err_t;
#define ESP_OK 0
typedef int rfid_err_t;
#define RFID_OK 0
#define RFID_ERR_HW (-1)
typedef int gpio_num_t;
typedef void* i2c_master_bus_handle_t;
typedef void* i2c_master_dev_handle_t;
typedef struct { int i2c_port, sda_io_num, scl_io_num, clk_source, glitch_ignore_cnt;
                 struct { int enable_internal_pullup; } flags; } i2c_master_bus_config_t;
typedef struct { int dev_addr_length, device_address, scl_speed_hz; } i2c_device_config_t;

#define RF_HAT_PN532_SCL_GPIO 8
#define RF_HAT_PN532_SDA_GPIO 9
#define PN532_I2C_PORT        0
#define PN532_I2C_ADDR        0x24
#define PN532_I2C_FREQ_HZ     100000
#define I2C_CLK_SRC_DEFAULT   0
#define I2C_ADDR_BIT_LEN_7    0
#define TAG "T"
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
static const char* esp_err_to_name(esp_err_t e){ (void)e; return ""; }
static void gpio_reset_pin(gpio_num_t g){ (void)g; }
static void vTaskDelay(int t){ (void)t; }
static rfid_err_t pn532_rf_field_off(void);

/* forward decl: pn532_driver_init() calls deinit(), which is defined after it */
void pn532_driver_deinit(void);
bool pn532_driver_release(void);

/* driver file-statics (extracted functions reference these) */
static i2c_master_bus_handle_t s_bus = NULL;
static i2c_master_dev_handle_t s_dev = NULL;
static bool s_init = false;

#define RFID_ERR_NOT_INIT (-2)
#define RFID_ERR_NOT_SUPPORTED (-3)
#include <stdint.h>
static int chip_io;
static rfid_err_t s_write_frame(const uint8_t*c,uint8_t n){(void)c;(void)n;assert(s_bus&&s_dev&&s_init);chip_io++;return RFID_OK;}
static rfid_err_t s_read_ack(void){return RFID_OK;}
static rfid_err_t pn532_read_response(uint8_t c,uint8_t*b,uint8_t*n,uint8_t m,uint32_t t){(void)c;(void)b;(void)n;(void)m;(void)t;assert(s_bus&&s_dev&&s_init);return RFID_OK;}
#define PN532_CMD_RF_CONFIGURATION 0x32

/* ---- instrumented I2C mocks with injectable failures + ownership model ---- */
static int fail_new_bus, fail_add_dev, fail_del_bus, fail_rm_dev;
static int new_bus_calls, live_bus, live_dev;
static esp_err_t i2c_new_master_bus(const i2c_master_bus_config_t* c, i2c_master_bus_handle_t* out){
    (void)c; new_bus_calls++; assert(!live_bus); if(fail_new_bus)return -1; *out = malloc(8); live_bus = 1; return ESP_OK;
}
static esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t b, const i2c_device_config_t* c,
                                           i2c_master_dev_handle_t* out){
    (void)b; (void)c; if (fail_add_dev){ *out = NULL; return -1; }
    *out = malloc(8); live_dev = 1; return ESP_OK;
}
static esp_err_t i2c_del_master_bus(i2c_master_bus_handle_t b){
    assert(b && live_bus && !live_dev); if (fail_del_bus) return -1; free(b); live_bus = 0; return ESP_OK;
}
static esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t d){
    assert(d && live_dev && live_bus); if (fail_rm_dev) return -1; free(d); live_dev = 0; return ESP_OK;
}
static esp_err_t i2c_master_bus_reset(i2c_master_bus_handle_t b){ (void)b; return ESP_OK; }
static esp_err_t i2c_master_probe(i2c_master_bus_handle_t b, int a, int t){ (void)b;(void)a;(void)t; return ESP_OK; }

'''

post = r'''
int main(void){
    fail_new_bus=1;
    assert(pn532_driver_init()==RFID_ERR_HW);
    assert(!s_init && !s_bus && !s_dev && !live_bus && !live_dev);
    fail_new_bus=0;
    /* 1. Happy init + deinit: everything acquired then fully released. */
    fail_add_dev = fail_del_bus = fail_rm_dev = 0;
    assert(pn532_driver_init() == RFID_OK);
    assert(s_init && s_bus && s_dev && live_bus && live_dev);
    int original_calls=new_bus_calls;
    assert(pn532_driver_init()==RFID_OK && new_bus_calls==original_calls);
    uint8_t normal_cmd=0;
    assert(pn532_send_command(&normal_cmd,1)==RFID_OK && chip_io==1);
    pn532_driver_deinit();
    assert(!s_init && !s_bus && !s_dev && !live_bus && !live_dev);

    /* 2. add-device fails, bus delete succeeds: no handle left, bus released. */
    fail_add_dev = 1; fail_del_bus = 0; fail_rm_dev = 0;
    assert(pn532_driver_init() == RFID_ERR_HW);
    assert(!s_init && !s_dev && !s_bus && !live_bus && !live_dev);

    /* 3. add-device fails AND bus delete fails: bus handle RETAINED (not leaked/nulled);
          a re-init must NOT reacquire a new bus over the live one; later cleanup frees it. */
    fail_add_dev = 1; fail_del_bus = 1; fail_rm_dev = 0;
    int nb = new_bus_calls;
    assert(pn532_driver_init() == RFID_ERR_HW);
    assert(new_bus_calls == nb + 1);            /* one bus was created */
    assert(s_bus != NULL && live_bus);          /* RETAINED, still owned */
    assert(s_dev == NULL && !live_dev && !s_init);
    assert(pn532_driver_init() == RFID_ERR_HW); /* refuse while owned */
    assert(new_bus_calls == nb + 1);            /* NO reacquire over the live bus */
    assert(s_bus != NULL && live_bus);
    fail_del_bus = 0;
    pn532_driver_deinit();                       /* retry succeeds */
    assert(!s_bus && !live_bus && !s_init);

    /* 4. deinit: device-remove fails -> device RETAINED, bus NOT deleted yet. */
    fail_add_dev = fail_del_bus = fail_rm_dev = 0;
    assert(pn532_driver_init() == RFID_OK);
    nb=new_bus_calls;
    fail_rm_dev = 1; fail_del_bus = 1;
    pn532_driver_deinit();
    assert(s_dev != NULL && live_dev);           /* device retained */
    assert(s_bus != NULL && live_bus);           /* bus NOT deleted while device owned */
    assert(!pn532_driver_is_init() && pn532_driver_is_owned());
    uint8_t refused_cmd=0;int before_io=chip_io;
    assert(pn532_send_command(&refused_cmd,1)==RFID_ERR_NOT_INIT);
    assert(pn532_rf_field_off()==RFID_ERR_NOT_INIT && chip_io==before_io);
    for(int retry=0;retry<3;retry++){
        assert(pn532_driver_init()==RFID_ERR_HW);
        assert(s_dev&&s_bus&&!s_init&&new_bus_calls==nb);
    }
    fail_rm_dev = 0;
    assert(!pn532_driver_release()); /* now only bus deletion fails */
    assert(!s_dev && s_bus && !s_init && live_bus && !live_dev);
    assert(pn532_driver_init()==RFID_ERR_HW && new_bus_calls==nb);
    fail_del_bus = 0;
    pn532_driver_deinit();                        /* retry frees both */
    assert(!s_dev && !s_bus && !live_dev && !live_bus && !s_init);

    /* 5. deinit: bus-delete fails -> bus RETAINED; retry frees it. */
    assert(pn532_driver_init() == RFID_OK);
    fail_del_bus = 1;
    pn532_driver_deinit();
    assert(!s_dev && !live_dev);                  /* device released */
    assert(s_bus != NULL && live_bus);            /* bus retained */
    assert(!s_init); /* partial release must never remain ready */
    nb=new_bus_calls;
    for(int retry=0;retry<3;retry++){
        assert(pn532_driver_init()==RFID_ERR_HW);
        assert(new_bus_calls==nb && s_bus && !s_dev && !s_init);
        uint8_t c=0;int io=chip_io;
        assert(pn532_send_command(&c,1)==RFID_ERR_NOT_INIT);
        assert(pn532_rf_field_off()==RFID_ERR_NOT_INIT && chip_io==io);
        pn532_driver_deinit();
    }
    fail_del_bus = 0;
    assert(pn532_driver_init()==RFID_OK);
    assert(new_bus_calls==nb+1 && s_bus && s_dev && s_init);
    pn532_driver_deinit();
    assert(!s_bus && !live_bus && !s_init);

    puts("PASS PN532 Package G: handles retained on release failure, no reacquire over a "
         "live bus, full release on success (init+deinit extracted verbatim).");
    return 0;
}
'''

# Unsupported-board admission is exercised before reset/probe/bus calls.
unsupported_pre=pre.replace('static void gpio_reset_pin(gpio_num_t g){ (void)g; }','static void gpio_reset_pin(gpio_num_t g){ (void)g; abort(); }')
u=D/'unsupported';u.mkdir(exist_ok=True)
(u/'host.c').write_text('#define CONFIG_BOARD_WS_S3_5B 1\n'+unsupported_pre+init_fn+'\n'+deinit_fn+'\nint main(void){assert(pn532_driver_init()==RFID_ERR_NOT_SUPPORTED);assert(!new_bus_calls&&!s_bus&&!s_dev&&!s_init);return 0;}')
subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-fsanitize=address,undefined','-fno-pie','-no-pie',str(u/'host.c'),'-o',str(u/'host')],check=True)
subprocess.run([str(u/'host')],check=True)
print('unsupported-board no-GPIO admission PASS')
runs=[]
variants=[('production', init_fn + '\n' + deinit_fn, False)]
variants += [
 ('false-ready', (init_fn+'\n'+deinit_fn).replace('    s_init = false;', '    /* mutation: keep stale readiness */',1), True),
 ('lose-bus', (init_fn+'\n'+deinit_fn).replace('if (e == ESP_OK) s_bus = NULL;', 's_bus = NULL;',1), True),
 ('lose-device', (init_fn+'\n'+deinit_fn).replace('if (e == ESP_OK) s_dev = NULL;', 'if (true) s_dev = NULL;',1), True),
 ('skip-retained-guard', (init_fn+'\n'+deinit_fn).replace('if (s_bus || s_dev) {', 'if (false) {',1), True),
]
for name,code,expected_failure in variants:
    d=D/name;d.mkdir(exist_ok=True)
    # Keep syntax valid for the unconditional bus-handle-loss mutant.
    if name=='lose-bus': code=code.replace('s_bus = NULL;\n        else ESP_LOGE', 'if (true) s_bus = NULL;\n        else ESP_LOGE')
    (d/'host.c').write_text(pre+code+'\n'+post)
    cmd=[os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(d/'host.c'),'-o',str(d/'host')]
    built=subprocess.run(cmd,capture_output=True,text=True);(d/'compile.log').write_text(built.stdout+built.stderr)
    if built.returncode: raise RuntimeError(built.stderr)
    run=subprocess.run([str(d/'host')],capture_output=True,text=True);(d/'run.log').write_text(run.stdout+run.stderr)
    # Mutants must fail on a semantic assertion, not compilation/sanitizer setup.
    good=(run.returncode!=0 and 'Assertion' in run.stderr) if expected_failure else run.returncode==0
    runs.append(dict(name=name,expected_failure=expected_failure,exit_code=run.returncode,status='PASS' if good else 'FAIL',command=cmd))
    print(name, runs[-1]['status'],run.stdout.strip())
provenance={'source':str(SRC.relative_to(R)),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'extracted_sha256':hashlib.sha256((init_fn+deinit_fn).encode()).hexdigest(),'classification':'production-extracted lifecycle/public guards with I2C/task/protocol mocks; no installed SDK or hardware execution','runs':runs,'scenario_groups':6,'mutation_kills':sum(x['expected_failure'] and x['status']=='PASS' for x in runs)}
(D/'provenance.json').write_text(json.dumps(provenance,indent=2))
assert all(x['status']=='PASS' for x in runs),runs
