#!/usr/bin/env python3
"""Package D: TX power level NVS decode/migration, production-extracted, ASan/UBSan.

Extracts the pwr_decode() state machine verbatim from the production source
(ESP32C5/components/wifi_cli/wifi_common.c) together with its type block from the
production header, and asserts the full migration/input matrix required by Jim's
Package D review: a genuinely absent key is distinguished from a wrong-type or
unreadable one; legacy pwr_mode 0/1 migrate to Normal/Max; a legacy 2/unknown
value and an unsupported Low are flagged (PWR_SRC_ERROR) and run as Normal,
never a silent promotion to Max; and a settings namespace that will not open is
an error, not a fresh install. Each mutant (silent Max, bad-type-as-fresh, Low
accepted, namespace-fail-as-fresh) must be DETECTED (assertion failure)."""
import os, subprocess, json, hashlib
from pathlib import Path

# Boundary: pure extracted C only; no ESP-IDF / NVS and no mocks. Proves the
# decode/migration RULE, not live NVS behaviour or physical TX power - this is
# not an on-device test and is not RF-output evidence.
R = Path(__file__).resolve().parents[1]
OUT = Path(os.environ['CYM_TEST_OUT']) / 'pwr-decode'
OUT.mkdir(parents=True, exist_ok=True)

core = R / 'ESP32C5/components/wifi_cli/wifi_common.c'
hdr = R / 'ESP32C5/components/wifi_cli/include/wifi_common.h'
assert core.exists(), 'wifi_common.c production source missing'
assert hdr.exists(), 'wifi_common.h production header missing'
src = core.read_text()
htext = hdr.read_text()

# Types come verbatim from the production header's marker block.
tb = htext.index('/* >>> CYM_PWR_DECODE_TYPES_BEGIN')
te = htext.index('CYM_PWR_DECODE_TYPES_END */') + len('CYM_PWR_DECODE_TYPES_END */')
types = htext[tb:te]


def extract(s, sig):
    a = s.index(sig)
    b = s.index('{', a)
    depth = 1
    i = b + 1
    while depth:
        depth += (s[i] == '{') - (s[i] == '}')
        i += 1
    return s[a:i]


funcs = extract(src, 'pwr_decode_t pwr_decode(')

pre = r"""
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
"""

post = r"""
int main(void) {
    pwr_decode_t r;
    /* Fresh install: both keys genuinely absent -> Normal / FRESH. */
    r = pwr_decode(PWR_KEY_ABSENT, 0, PWR_KEY_ABSENT, 0, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_FRESH);
    /* Explicit new key Normal / Max. */
    r = pwr_decode(PWR_KEY_OK, 1, PWR_KEY_ABSENT, 0, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_EXPLICIT);
    r = pwr_decode(PWR_KEY_OK, 2, PWR_KEY_ABSENT, 0, 1);
    assert(r.level == PWR_LVL_MAX && r.src == PWR_SRC_EXPLICIT);
    /* Explicit Low persisted but unsupported this build -> Normal + flagged. */
    r = pwr_decode(PWR_KEY_OK, 0, PWR_KEY_ABSENT, 0, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_ERROR);
    /* Explicit out-of-range new key -> Normal + flagged. */
    r = pwr_decode(PWR_KEY_OK, 3, PWR_KEY_ABSENT, 0, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_ERROR);
    /* New key wrong type / unreadable is NOT fresh and does NOT fall to legacy. */
    r = pwr_decode(PWR_KEY_BADTYPE, 0, PWR_KEY_OK, 1, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_ERROR);
    r = pwr_decode(PWR_KEY_READERR, 0, PWR_KEY_ABSENT, 0, 1);
    assert(r.src == PWR_SRC_ERROR);
    /* Migration from legacy pwr_mode 0/1. */
    r = pwr_decode(PWR_KEY_ABSENT, 0, PWR_KEY_OK, 0, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_MIGRATED);
    r = pwr_decode(PWR_KEY_ABSENT, 0, PWR_KEY_OK, 1, 1);
    assert(r.level == PWR_LVL_MAX && r.src == PWR_SRC_MIGRATED);
    /* Legacy 2 / unknown: explicit error disposition, NEVER a silent Max. */
    r = pwr_decode(PWR_KEY_ABSENT, 0, PWR_KEY_OK, 2, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_ERROR);
    r = pwr_decode(PWR_KEY_ABSENT, 0, PWR_KEY_OK, 7, 1);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_ERROR);
    /* Legacy key wrong type -> error. */
    r = pwr_decode(PWR_KEY_ABSENT, 0, PWR_KEY_BADTYPE, 0, 1);
    assert(r.src == PWR_SRC_ERROR);
    /* Namespace will not open -> error regardless of any value read. */
    r = pwr_decode(PWR_KEY_OK, 2, PWR_KEY_OK, 1, 0);
    assert(r.level == PWR_LVL_NORMAL && r.src == PWR_SRC_ERROR);
    puts("PASS pwr_decode migration/input matrix");
    return 0;
}
"""

variants = [
    ('production', funcs, False),
    # Silent promotion of legacy 2 (and any >=1) to Max — the exact failure the
    # review forbids.
    ('migrate-legacy2-as-max', funcs.replace('if (leg_raw == 1)', 'if (leg_raw >= 1)'), True),
    # Treat a wrong-type / unreadable new key as a fresh install instead of an error.
    ('badtype-as-fresh',
     funcs.replace('    if (lvl_rd != PWR_KEY_ABSENT) { out.src = PWR_SRC_ERROR; return out; }', ''), True),
    # Accept an unsupported Low (or any <= Max) as an explicit valid level.
    ('low-as-explicit',
     funcs.replace('if (lvl_raw == PWR_LVL_NORMAL || lvl_raw == PWR_LVL_MAX)', 'if (lvl_raw <= PWR_LVL_MAX)'), True),
    # Treat an unopenable settings namespace as a fresh install.
    ('nsfail-as-fresh',
     funcs.replace('    if (!ns_open_ok) { out.src = PWR_SRC_ERROR; return out; }', ''), True),
]

results = []
for name, f, mutant in variants:
    assert f != funcs or not mutant, 'mutant %s did not alter the source (stale target)' % name
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
    ok = assertion if mutant else (run.returncode == 0 and 'PASS' in run.stdout)
    print(name, 'PASS' if ok else 'FAIL', '| exit', run.returncode, '|', run.stdout.strip()[:60])
    results.append(dict(name=name, exit=run.returncode, ok=ok, mutant=mutant))

(OUT / 'results.json').write_text(json.dumps(dict(
    results=results,
    source='ESP32C5/components/wifi_cli/wifi_common.c',
    header='ESP32C5/components/wifi_cli/include/wifi_common.h',
    core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
    header_sha256=hashlib.sha256(hdr.read_bytes()).hexdigest(),
    extracted_sha256=hashlib.sha256((types + funcs).encode()).hexdigest(),
), indent=2))
nm = sum(1 for x in results if x['mutant']); km = sum(1 for x in results if x['mutant'] and x['ok'])
print(f'mutation: {km}/{nm} mutants killed (each failed as expected)')
assert all(x['ok'] for x in results), 'a variant did not behave as required'
print('ALL OK')
