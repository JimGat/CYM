#!/usr/bin/env python3
"""Production + installed NimBLE extraction, with deterministic in-memory mutants.

Inspired by co-developer @birolt29's Package A. HCI and mbuf storage are
instrumented, NOT a full NimBLE/controller build or RF acceptance test.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import resource
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def function(text, name):
    match = re.search(r'(?m)^(?:static\s+)?(?:int|void)\s*\n?' + name + r'\([^;]*?\)\s*\{', text)
    if not match:
        raise ValueError('function extraction failed: ' + name)
    i, depth = match.end(), 1
    while depth:
        depth += (text[i] == '{') - (text[i] == '}')
        i += 1
    return text[match.start():i]


def header_contract(sdk):
    """Copy real object-like defines (and their dependencies), plus address typedef."""
    base = sdk / 'components/bt/host/nimble/nimble/nimble'
    paths = [base/'include/nimble/ble.h', base/'include/nimble/hci_common.h',
             *[base/'host/include/host'/n for n in ('ble_hs.h', 'ble_hs_adv.h', 'ble_gap.h')]]
    definitions, provenance = {}, {}
    for path in paths:
        text = path.read_text()
        provenance[str(path.relative_to(sdk))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name, value in re.findall(r'^#define\s+(\w+)\s+([^\n]+)', text, re.M):
            definitions[name] = value
    names = ('BLE_ADDR_RANDOM BLE_DEV_ADDR_LEN BLE_STATIC_RAND_ADDR_MASK BLE_NON_RPA_MASK BLE_HS_ADV_F_DISC_GEN BLE_HS_ADV_F_BREDR_UNSUP '
             'BLE_HS_EINVAL BLE_HS_EDISABLED BLE_HS_EMSGSIZE BLE_HS_ENOTSUP BLE_HS_EALREADY '
             'BLE_HS_ADV_MAX_SZ BLE_HCI_OCF_LE_SET_EXT_ADV_DATA BLE_HS_ADV_TYPE_FLAGS '
             'BLE_HS_ADV_TYPE_COMP_NAME BLE_HS_ADV_TYPE_INCOMP_NAME BLE_HS_ADV_TYPE_MFG_DATA').split()
    lines, seen = [], set()
    def add(name):
        if name in seen:
            return
        value = definitions[name]
        seen.add(name)
        expression = re.sub(r'/\*.*?\*/|//.*', '', value)
        for dependency in re.findall(r'\b[A-Z][A-Z0-9_]+\b', expression):
            add(dependency)
        lines.append('#define ' + name + ' ' + value)
    for name in names:
        add(name)
    text = paths[0].read_text()
    addr = re.search(r'typedef struct\s*\{[^{}]*\}\s*ble_addr_t;', text)
    if not addr:
        raise ValueError('installed ble_addr_t layout unavailable')
    return '#include <stdint.h>\n' + '\n'.join(lines) + '\n' + addr[0] + '\n', provenance


def generate(source, gap, adv, contract):
    names = ['ble_gap_ext_adv_set_addr', 'ble_gap_ext_adv_set_data_validate', 'ble_gap_ext_adv_set_data']
    functions = [function(gap, n) for n in names]
    functions += [function(adv, n) for n in ['ble_hs_adv_set_hdr', 'ble_hs_adv_set_flat_mbuf']]
    whole = function(adv, 'adv_set_fields')
    flags = whole[whole.index('    if (adv_fields->flags != 0)'):whole.index('    /*** 0x02,0x03')]
    name = whole[whole.index('    if (adv_fields->name != NULL'):whole.index('    /*** 0x0a')]
    mfg = whole[whole.index('    if ((adv_fields->mfg_data != NULL)'):whole.index('    if (dst_len)')]
    serializer = ('static int serialize(const struct ble_hs_adv_fields *adv_fields,struct os_mbuf *om)'
                  '{uint8_t type;int rc;uint8_t *dst=NULL;uint8_t dst_len_local=0,max_len=0;\n'
                  + flags + name + mfg + 'return 0;}\n')
    a = source.index('        ble_addr_t at_addr;')
    b = source.index('        if (ble_gap_ext_adv_set_addr', a)
    # Deterministic test-only poison makes a missing production assignment observable.
    # This is initialized invalid memory, NOT an uninitialized-read detector.
    address = source[a:b].replace('ble_addr_t at_addr;', 'ble_addr_t at_addr; memset(&at_addr,0xa5,sizeof(at_addr));')
    a = source.index('    case BLE_SPAM_MODE_WINDOWS: {', source.index('static void ble_spam_timer_cb(lv_timer_t *timer)\n{'))
    b = source.index('    default:', a)
    windows = source[a:b]
    windows = windows[windows.index('        win_mfg[0]'):windows.index('        st->windows_idx')]
    a = source.index('    struct ble_hs_adv_fields fields;', source.index('static void ble_spam_timer_cb(lv_timer_t *timer)\n{'))
    b = source.index('    bool use_svc = false;', a)
    initialization = source[a:b]
    a = source.index('    // Allocate fresh mbuf', b)
    b = source.index('    // Start advertising with fresh payload', a)
    caller = source[a:b]
    post = (ROOT/'tests/ble_spam_host_cases.c').read_text().replace('/* PRODUCTION_FIELDS */', initialization).replace('/* PRODUCTION_CALLER */', caller).replace('/* PRODUCTION_WINDOWS */', windows).replace('/* PRODUCTION_ADDRESS */', address)
    return contract + (ROOT/'tests/ble_spam_host_scaffold.h').read_text() + '\n'.join(functions) + serializer + post


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if not os.environ.get('IDF_PATH'):
        parser.error('required IDF_PATH: installed ESP-IDF SDK (see tests/README.md)')
    sdk = Path(os.environ['IDF_PATH']).resolve()
    host = sdk/'components/bt/host/nimble/nimble/nimble/host/src'
    main_path = ROOT/'ESP32C5/main/main.c'
    source = main_path.read_text()
    gap, adv = (host/'ble_gap.c').read_text(), (host/'ble_hs_adv.c').read_text()
    contract, headers = header_contract(sdk)
    flags = ['-std=gnu11', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-no-pie']
    cc = os.environ.get('CC', 'cc')
    provenance = dict(source_sha256=hashlib.sha256(main_path.read_bytes()).hexdigest(),
                      sdk_files={**headers, **{str(p.relative_to(sdk)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (host/'ble_gap.c', host/'ble_hs_adv.c')}},
                      compiler=subprocess.check_output([cc, '--version'], text=True).splitlines()[0],
                      limitations=['Only flags/name/manufacturer serialization branches extracted',
                                   'HCI, locks and mbuf storage stubbed; real SDK ownership/validation paths extracted',
                                   'MYNEWT feature switches disabled; BLE_ADV_INSTANCES=3 fixture',
                                   'Invalid initialized poison is not uninitialized memory; ASan does not detect all uninitialized reads',
                                   'No controller, RF, embedded heap, timer or board acceptance proof'], runs=[])
    # Semantics preserved as a source observation; not an end-to-end start test.
    (args.output/'nimble-start-source.txt').write_text(function(gap, 'ble_gap_ext_adv_start'))
    mutants = [('accepted', source, False),
               ('missing-address-type', re.sub(r'(?m)^\s*at_addr\.type = BLE_ADDR_RANDOM;[^\n]*\n', '', source, count=1), True),
               ('name-cap-modulo6', source.replace('int name_len = 5 + (esp_random() % 5);', 'int name_len = 5 + (esp_random() % 6);', 1), True)]
    for label, text, expected_failure in mutants:
        if expected_failure and text == source:
            raise ValueError('mutation did not change source: ' + label)
        directory = args.output/label
        directory.mkdir()
        cfile, binary = directory/'host.c', directory/'host'
        cfile.write_text(generate(text, gap, adv, contract))
        command = [cc, *flags, str(cfile), '-o', str(binary)]
        compile_run = subprocess.run(command, capture_output=True, text=True)
        (directory/'compile.log').write_text(compile_run.stdout + compile_run.stderr)
        if compile_run.returncode:
            raise RuntimeError('compile failure is NOT a killed mutation: ' + str(directory/'compile.log'))
        env = os.environ.copy()
        env.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        run = subprocess.run([str(binary)], capture_output=True, text=True, env=env, timeout=30)
        log = run.stdout + run.stderr
        (directory/'run.log').write_text(log)
        check_match = re.search(r'RESULT checks=(\d+) failures=0', log)
        # Require a semantic assertion, not a sanitizer startup error or a crash.
        ok = run.returncode == 1 and 'FAIL line ' in log if expected_failure else run.returncode == 0 and check_match is not None
        record = dict(name=label, command=command, exit_code=run.returncode, expected_failure=expected_failure,
                      source_input_sha256=hashlib.sha256(text.encode()).hexdigest(),
                      checks=int(check_match[1]) if check_match else None, status='PASS' if ok else 'FAIL')
        provenance['runs'].append(record)
        (args.output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
        print(label + ': ' + record['status'] + '\n' + log, flush=True)
        if not ok:
            return 1
    print('PASS: accepted production extraction and two semantic mutation kills under ASan+UBSan; not RF proof')
    return 0


if __name__ == '__main__':
    sys.exit(main())
