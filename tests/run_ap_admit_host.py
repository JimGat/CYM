#!/usr/bin/env python3
"""Package B (#3): utility-AP admission, production-extracted, ASan/UBSan.

Extracts ap_admit() verbatim from the production source and asserts that an
attack AP bring-up is refused while a utility AP owns the interface, unless an
explicit handoff permits it, and that teardown-only ops are never refused. The
mutant (admission ignores the utility owner) must be DETECTED (nonzero exit)."""
import os, subprocess, json, hashlib
from pathlib import Path

# Boundary: pure extracted C only; no ESP-IDF / esp_wifi and no mocks. Proves the
# admission rule, NOT the live utility-AP signal or physical/hardware behaviour -
# this is not an on-device test.
R = Path(__file__).resolve().parents[1]
OUT = Path(os.environ['CYM_TEST_OUT']) / 'ap-admit'
OUT.mkdir(parents=True, exist_ok=True)

core = R / 'ESP32C5/components/wifi_attacks/wifi_attacks.c'
assert core.exists(), 'wifi_attacks.c production source missing'
src = core.read_text()
types = src[src.index('/* >>> CYM_AP_ADMIT_TYPES_BEGIN'):src.index('CYM_AP_ADMIT_TYPES_END */') + len('CYM_AP_ADMIT_TYPES_END */')]


def extract(s, sig):
    a = s.index(sig)
    b = s.index('{', a)
    depth = 1
    i = b + 1
    while depth:
        depth += (s[i] == '{') - (s[i] == '}')
        i += 1
    return s[a:i]


funcs = extract(src, 'ap_admit_t ap_admit(')

pre = r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
"""

post = r"""
int main(void) {
    assert(ap_admit(1, 1, 0) == AP_ADMIT_REFUSE_UTILITY);  /* bring-up over a utility AP: refused */
    assert(ap_admit(1, 1, 1) == AP_ADMIT_OK);              /* explicit handoff permits it */
    assert(ap_admit(1, 0, 0) == AP_ADMIT_OK);              /* no utility owner */
    assert(ap_admit(0, 1, 0) == AP_ADMIT_OK);              /* teardown-only does not bring up the AP */
    puts("PASS ap_admit utility-AP admission");
    return 0;
}
"""

variants = [
    ('production', funcs, False),
    ('admit-over-utility', funcs.replace('if (brings_up_ap && utility_ap_owned && !handoff) return AP_ADMIT_REFUSE_UTILITY;', ''), True),
]

results = []
for name, f, mutant in variants:
    d = OUT / name
    d.mkdir(exist_ok=True)
    (d / 'host.c').write_text(pre + types + '\n' + f + '\n' + post)
    cmd = [os.environ.get('CC', 'cc'), '-std=gnu11', '-g', '-O1', '-fsanitize=address,undefined',
           '-fno-sanitize-recover=all', str(d / 'host.c'), '-o', str(d / 'host')]
    b = subprocess.run(cmd, capture_output=True, text=True)
    (d / 'compile.log').write_text(b.stdout + b.stderr)
    if mutant and b.returncode != 0:
        print(name, 'PASS (rejected at compile)')
        results.append(dict(name=name, compiled=False, ok=True, mutant=mutant))
        continue
    assert b.returncode == 0, 'production must compile: ' + b.stderr
    run = subprocess.run([str(d / 'host')], capture_output=True, text=True)
    (d / 'run.log').write_text(run.stdout + run.stderr)
    ok = (run.returncode != 0) if mutant else (run.returncode == 0 and 'PASS' in run.stdout)
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
