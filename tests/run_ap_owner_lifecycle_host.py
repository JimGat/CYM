#!/usr/bin/env python3
"""Package B softAP attack-owner lifecycle: production-extracted, ASan/UBSan, no RF hardware.

Extracts the pure ownership core verbatim from the production source
(ESP32C5/components/wifi_attacks/wifi_attacks.c) and asserts the Package B
design-review invariants, with semantic mutants that must be DETECTED (nonzero
exit) to prove the test is mutation-sensitive (the Package A lesson)."""
import os, subprocess, json, hashlib
from pathlib import Path

# Boundary: pure extracted C only; no ESP-IDF / FreeRTOS / esp_wifi and no mocks
# (the functions take no SDK types). Proves the decision logic, NOT concurrency or
# physical/hardware RF behaviour - this is not an on-device test.
R = Path(__file__).resolve().parents[1]
OUT = Path(os.environ['CYM_TEST_OUT']) / 'ap-owner'
OUT.mkdir(parents=True, exist_ok=True)

core = R / 'ESP32C5/components/wifi_attacks/wifi_attacks.c'
assert core.exists(), 'wifi_attacks.c production source missing'
src = core.read_text()

TB = '/* >>> CYM_AP_OWNER_TYPES_BEGIN'
TE = 'CYM_AP_OWNER_TYPES_END */'
types = src[src.index(TB):src.index(TE) + len(TE)]


def extract(s, sig):
    a = s.index(sig)
    b = s.index('{', a)
    depth = 1
    i = b + 1
    while depth:
        depth += (s[i] == '{') - (s[i] == '}')
        i += 1
    return s[a:i]


FUNS = ['int ap_snapshot_build(', 'ap_own_state_t ap_owner_begin(',
        'ap_own_state_t ap_owner_suspend_result(', 'ap_own_state_t ap_owner_resume_result(',
        'uint32_t ap_owner_invalidate(', 'int ap_owner_can_resume(']
funcs = '\n'.join(extract(src, s) for s in FUNS)

pre = r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
"""

post = r"""
int main(void) {
    ap_req_snapshot_t s;
    /* ---- snapshot validation ---- */
    assert(ap_snapshot_build(&s, AP_REQ_EVIL_TWIN, "HomeNet", "secretpw", NULL, 0, 0, 0) == AP_SNAP_OK);
    assert(s.kind == AP_REQ_EVIL_TWIN && s.generation == 0);
    assert(ap_snapshot_build(&s, AP_REQ_ROGUE, "R", NULL, NULL, 6, 0, 0) == AP_SNAP_EPASS);   /* rogue needs pass */
    assert(ap_snapshot_build(&s, AP_REQ_EVIL_TWIN, NULL, "p", NULL, 0, 0, 0) == AP_SNAP_ENULL);
    assert(ap_snapshot_build(&s, AP_REQ_EVIL_TWIN, "x", "password", NULL, 200, 0, 0) == AP_SNAP_ECHAN); /* >177 invalid */
    char longssid[64]; memset(longssid, 'A', 63); longssid[63] = '\0';
    assert(ap_snapshot_build(&s, AP_REQ_EVIL_TWIN, longssid, "p", NULL, 0, 0, 0) == AP_SNAP_ESSID); /* 33+ rejected */

    /* ---- overlap-safe copy: input aliases *out (resume feeds its own buffers) ---- */
    memset(&s, 0, sizeof(s));
    strcpy(s.ssid, "AliasMe");
    strcpy(s.pass, "pwpwpwpw");
    assert(ap_snapshot_build(&s, AP_REQ_PORTAL, s.ssid, s.pass, NULL, 1, 0, 7) == AP_SNAP_OK);
    assert(strcmp(s.ssid, "AliasMe") == 0 && strcmp(s.pass, "pwpwpwpw") == 0 && s.generation == 7);

    /* ---- rogue target copied by value ---- */
    uint8_t bssid[6] = {2, 2, 3, 4, 5, 6};
    assert(ap_snapshot_build(&s, AP_REQ_ROGUE, "RG", "rgpass12", bssid, 149, 1, 0) == AP_SNAP_OK); /* 5GHz ch accepted */
    assert(s.has_target && s.bssid[0] == 2 && s.bssid[5] == 6 && s.channel == 149);

    /* ---- happy lifecycle: begin -> suspend ok -> held -> resume ok -> active ---- */
    ap_owner_t o; memset(&o, 0, sizeof(o));
    ap_owner_begin(&o, &s);
    assert(o.state == AP_OWN_ACTIVE && o.req.kind == AP_REQ_ROGUE);
    assert(ap_owner_suspend_result(&o, o.generation, 1) == AP_OWN_HELD);
    assert(ap_owner_can_resume(&o, o.generation));
    assert(ap_owner_resume_result(&o, o.generation, 1) == AP_OWN_ACTIVE);

    /* ---- failed STOP -> live/uncertain, NOT held; request retained ---- */
    assert(ap_owner_suspend_result(&o, o.generation, 0) == AP_OWN_LIVE_UNCERTAIN);
    assert(o.req.kind == AP_REQ_ROGUE);

    /* ---- failed RESUME -> error, NOT broadcasting; request retained, not resumable ---- */
    o.state = AP_OWN_HELD;
    assert(ap_owner_resume_result(&o, o.generation, 0) == AP_OWN_ERROR);
    assert(o.req.kind == AP_REQ_ROGUE && !ap_owner_can_resume(&o, o.generation));

    /* ---- stale result dropped (generation moved on) ---- */
    o.state = AP_OWN_HELD;
    uint32_t stale = o.generation - 1;
    assert(ap_owner_resume_result(&o, stale, 1) == AP_OWN_HELD);   /* stale resume must NOT activate */
    o.state = AP_OWN_ACTIVE;
    assert(ap_owner_suspend_result(&o, stale, 1) == AP_OWN_ACTIVE); /* stale suspend must NOT hold */

    /* ---- invalidate (Back/Home/reset): resume eligibility destroyed, old gen dropped ---- */
    o.state = AP_OWN_ACTIVE;
    uint32_t g = o.generation;
    ap_owner_invalidate(&o);
    assert(o.state == AP_OWN_IDLE && o.req.kind == AP_REQ_NONE);
    assert(ap_owner_suspend_result(&o, g, 1) == AP_OWN_IDLE);  /* in-flight suspend from before invalidate dropped */
    assert(ap_owner_resume_result(&o, g, 1) == AP_OWN_IDLE);

    puts("PASS ap-owner snapshot validation, overlap-safe copy, held/live-uncertain/error, stale-drop, invalidate");
    return 0;
}
"""

# (name, mutated funcs text, is_mutant) -- mutants must be DETECTED (nonzero exit)
variants = [
    ('production', funcs, False),
    # failed stop reported as held (design: must be LIVE_UNCERTAIN)
    ('stop-fail-held', funcs.replace('stop_ok ? AP_OWN_HELD : AP_OWN_LIVE_UNCERTAIN', 'AP_OWN_HELD'), True),
    # failed resume reported as broadcasting (design: must be ERROR)
    ('resume-fail-active', funcs.replace('start_ok ? AP_OWN_ACTIVE : AP_OWN_ERROR', 'AP_OWN_ACTIVE'), True),
    # stale resume applied instead of dropped
    ('ignore-stale-resume', funcs.replace('if (captured_gen != o->generation) return o->state;   /* stale completion: drop */', ''), True),
    # stale suspend applied instead of dropped
    ('ignore-stale-suspend', funcs.replace('if (captured_gen != o->generation) return o->state;   /* stale suspend: drop */', ''), True),
    # unbounded ssid copy (overlaps/overflows fixed buffer -> ASan)
    ('unbounded-ssid', funcs.replace('size_t sn = ssid ? strnlen(ssid, sizeof(tssid)) : 0;\n    if (sn == 0 || sn >= sizeof(tssid)) return AP_SNAP_ESSID;',
                                     'size_t sn = ssid ? strlen(ssid) : 0;'), True),
]

results = []
for name, f, mutant in variants:
    d = OUT / name
    d.mkdir(exist_ok=True)
    (d / 'host.c').write_text(pre + types + '\n' + f + '\n' + post)
    cmd = [os.environ.get('CC', 'cc'), '-std=gnu11', '-g', '-O1', '-fsanitize=address,undefined',
           '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', str(d / 'host.c'), '-o', str(d / 'host')]
    b = subprocess.run(cmd, capture_output=True, text=True)
    (d / 'compile.log').write_text(b.stdout + b.stderr)
    assert b.returncode == 0, 'production must compile: ' + b.stderr
    run = subprocess.run([str(d / 'host')], capture_output=True, text=True)
    (d / 'run.log').write_text(run.stdout + run.stderr)
    assertion = 'Assertion' in run.stderr and 'failed' in run.stderr
    intended_memory_finding = (name == 'unbounded-ssid' and
        ('ERROR: AddressSanitizer: stack-buffer-overflow' in run.stderr or
         'runtime error: index' in run.stderr))
    ok = (assertion or intended_memory_finding) if mutant else (run.returncode == 0 and 'PASS' in run.stdout)
    print(name, 'PASS' if ok else 'FAIL', '| exit', run.returncode, '|', run.stdout.strip()[:60])
    results.append(dict(name=name, exit=run.returncode, ok=ok, mutant=mutant))

(OUT / 'results.json').write_text(json.dumps(dict(
    results=results,
    source='ESP32C5/components/wifi_attacks/wifi_attacks.c',
    core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
    extracted_sha256=hashlib.sha256((types + funcs).encode()).hexdigest(),
), indent=2))
nm = sum(1 for x in results if x['mutant']); km = sum(1 for x in results if x['mutant'] and x['ok'])
print(f'mutation: {km}/{nm} mutants killed (each failed as expected)')
assert all(x['ok'] for x in results), 'a variant did not behave as required'
print('ALL OK')
