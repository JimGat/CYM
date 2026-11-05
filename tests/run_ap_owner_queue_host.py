#!/usr/bin/env python3
"""Package B slice 2: bounded request queue + off-UI dispatch, production-extracted, ASan/UBSan.

Extracts the queue/schedule/dispatch logic verbatim from the production source
and asserts: bounded enqueue (reject-when-full, no overwrite), FIFO pop, and
generation-honouring dispatch that reconciles a completion landing after a
replacement owner / invalidate (Package B review #4, #5). Mutants must be
DETECTED (nonzero exit)."""
import os, subprocess, json, hashlib
from pathlib import Path

# Boundary: pure extracted C only; no ESP-IDF / FreeRTOS / esp_wifi and no mocks.
# Proves the queue/dispatch decision logic, NOT concurrency or physical/hardware RF
# behaviour - this is not an on-device test.
R = Path(__file__).resolve().parents[1]
OUT = Path(os.environ['CYM_TEST_OUT']) / 'ap-owner-queue'
OUT.mkdir(parents=True, exist_ok=True)

core = R / 'ESP32C5/components/wifi_attacks/wifi_attacks.c'
assert core.exists(), 'wifi_attacks.c production source missing'
src = core.read_text()


def between(s, begin, end):
    return s[s.index(begin):s.index(end) + len(end)]


def extract(s, sig):
    a = s.index(sig)
    b = s.index('{', a)
    depth = 1
    i = b + 1
    while depth:
        depth += (s[i] == '{') - (s[i] == '}')
        i += 1
    return s[a:i]


types = (between(src, '/* >>> CYM_AP_OWNER_TYPES_BEGIN', 'CYM_AP_OWNER_TYPES_END */') + '\n' +
         between(src, '/* >>> CYM_AP_QUEUE_TYPES_BEGIN', 'CYM_AP_QUEUE_TYPES_END */'))

FUNS = ['ap_own_state_t ap_owner_begin(', 'ap_own_state_t ap_owner_suspend_result(',
        'ap_own_state_t ap_owner_resume_result(', 'uint32_t ap_owner_invalidate(',
        'int ap_reqq_push(', 'int ap_reqq_pop(', 'uint32_t ap_owner_schedule(',
        'ap_own_state_t ap_owner_dispatch(']
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
    /* ---- bounded queue: fill, reject when full, FIFO order ---- */
    ap_reqq_t q; memset(&q, 0, sizeof(q));
    assert(ap_reqq_push(&q, AP_OP_SUSPEND, 10));
    assert(ap_reqq_push(&q, AP_OP_RESUME, 11));
    assert(ap_reqq_push(&q, AP_OP_SUSPEND, 12));
    assert(ap_reqq_push(&q, AP_OP_RESUME, 13));
    assert(!ap_reqq_push(&q, AP_OP_SUSPEND, 99));   /* full: rejected, not overwritten */
    assert(q.count == AP_REQQ_CAP);
    ap_req_t r;
    assert(ap_reqq_pop(&q, &r) && r.op == AP_OP_SUSPEND && r.generation == 10);
    assert(ap_reqq_pop(&q, &r) && r.op == AP_OP_RESUME && r.generation == 11);
    assert(ap_reqq_pop(&q, &r) && r.generation == 12);
    assert(ap_reqq_pop(&q, &r) && r.generation == 13);
    assert(!ap_reqq_pop(&q, &r));                   /* empty */
    /* ring wraps correctly after drain */
    assert(ap_reqq_push(&q, AP_OP_RESUME, 20) && ap_reqq_pop(&q, &r) && r.generation == 20);

    ap_req_snapshot_t snap; memset(&snap, 0, sizeof(snap));
    ap_owner_t o; memset(&o, 0, sizeof(o));

    /* ---- schedule + dispatch happy path ---- */
    ap_owner_begin(&o, &snap);
    assert(o.state == AP_OWN_ACTIVE);
    uint32_t g = ap_owner_schedule(&o, AP_OP_SUSPEND);
    assert(o.state == AP_OWN_SUSPENDING);
    ap_req_t rs = { AP_OP_SUSPEND, g };
    assert(ap_owner_dispatch(&o, &rs, 1) == AP_OWN_HELD);
    uint32_t g2 = ap_owner_schedule(&o, AP_OP_RESUME);
    assert(o.state == AP_OWN_RESUMING);
    ap_req_t rr = { AP_OP_RESUME, g2 };
    assert(ap_owner_dispatch(&o, &rr, 1) == AP_OWN_ACTIVE);

    /* ---- failed primitive via dispatch -> live/uncertain ---- */
    uint32_t g3 = ap_owner_schedule(&o, AP_OP_SUSPEND);
    ap_req_t rf = { AP_OP_SUSPEND, g3 };
    assert(ap_owner_dispatch(&o, &rf, 0) == AP_OWN_LIVE_UNCERTAIN);

    /* ---- stale completion after a REPLACEMENT owner: must be reconciled away ----
     * old suspend scheduled under gen G1 completes AFTER a new owner begins (G2,
     * state ACTIVE again). A correct dispatch drops it; applying the current
     * generation instead would wrongly suspend the new owner. */
    memset(&o, 0, sizeof(o));
    ap_owner_begin(&o, &snap);                 /* owner A, gen -> 1, ACTIVE */
    uint32_t gA = ap_owner_schedule(&o, AP_OP_SUSPEND);
    ap_owner_begin(&o, &snap);                 /* owner B replaces, gen -> 2, ACTIVE */
    ap_req_t rstale = { AP_OP_SUSPEND, gA };
    assert(ap_owner_dispatch(&o, &rstale, 1) == AP_OWN_ACTIVE);  /* A's result dropped; B untouched */

    /* ---- invalidate drops an in-flight op ---- */
    memset(&o, 0, sizeof(o));
    ap_owner_begin(&o, &snap);
    uint32_t gi = ap_owner_schedule(&o, AP_OP_SUSPEND);
    ap_owner_invalidate(&o);
    ap_req_t ri = { AP_OP_SUSPEND, gi };
    assert(ap_owner_dispatch(&o, &ri, 1) == AP_OWN_IDLE);

    puts("PASS ap-owner bounded queue, FIFO, schedule, generation-honouring dispatch, stale/replacement reconcile");
    return 0;
}
"""

variants = [
    ('production', funcs, False),
    # queue ignores full -> count exceeds cap (assert count==CAP fails)
    ('push-no-full', funcs.replace('    if (q->count >= AP_REQQ_CAP) return 0;\n', ''), True),
    # pop does not advance head -> same slot re-popped (FIFO assert fails)
    ('pop-no-advance', funcs.replace('    q->head = (uint8_t)((q->head + 1) % AP_REQQ_CAP);\n', ''), True),
    # dispatch uses current generation instead of the captured one -> stale applied
    ('dispatch-current-gen', funcs.replace('r->generation', 'o->generation'), True),
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
