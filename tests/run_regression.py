#!/usr/bin/env python3
"""Fail-fast, output-isolated CYM gates. No serial/RF/flash operations.
Exit 0: nonempty selected gates passed (optional skips allowed).
Exit 1: test failed. Exit 2: dependency/configuration/not-run gate.
Exit 3: zero executed checks (an all-skip suite is not green).
"""
from pathlib import Path
import argparse
import collections
import hashlib
import importlib
import json
import os
import resource
import re
import shutil
import signal
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def unit_worker(module, output, method=None):
    sys.path.insert(0, str(ROOT/'tests'))
    loaded = importlib.import_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromName(method, loaded) if method else unittest.defaultTestLoader.loadTestsFromModule(loaded)
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    summary = dict(discovered=count, tests=result.testsRun,
                   passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
                   failures=len(result.failures), errors=len(result.errors),
                   skips=[dict(test=t.id(), reason=why) for t, why in result.skipped],
                   not_run=count-result.testsRun, success=result.wasSuccessful())
    write_json(output/'unittest.json', summary)
    return (0 if summary['passed'] else 3) if result.wasSuccessful() else 1


def missing(requirement):
    if requirement == 'generated-tick-configs':
        builds = ['ESP32C5/build_' + n for n in ('nm-cyd-c5', 'ws-c5-28', 'ws-c5-35', 'pancake-c5')]
        builds += ['ESP32/build_cyd2usb', 'ESP32/build_hackerbox-cyd', 'ESP32S3/build_hosyond-s3-35', 'ESP32S3/build_ws-s3-5b']
        for build in builds:
            if not (ROOT/build/'config/sdkconfig.h').is_file():
                return 'required generated board config absent: ' + build + '/config/sdkconfig.h'
        return None
    if requirement == 'cc':
        return None if shutil.which('cc') and shutil.which(os.environ.get('CC','cc')) else 'host C compiler missing (cc / CC)'
    if requirement == 'lvgl':
        p=ROOT/'ESP32C5/managed_components/lvgl__lvgl'
        if not (p/'src/core/lv_obj.c').is_file():return 'required managed LVGL absent; see tests/README.md'
        if 'version: 8.4.0' not in (p/'idf_component.yml').read_text():return 'required managed LVGL version is 8.4.0'
        return None
    if requirement == 'codec':
        p=ROOT/'ESP32C5/managed_components/espressif__esp_codec_dev'
        return None if (p/'device/es8311/es8311.c').is_file() else 'required managed esp_codec_dev absent'
    if requirement.startswith('idf-'):
        if not os.environ.get('IDF_PATH'):return 'required IDF_PATH not configured; see tests/README.md'
        p=Path(os.environ['IDF_PATH'])
        suffix = {'idf-nimble':'components/bt/host/nimble/nimble/nimble/host/src/ble_gap.c', 'idf-i2c':'components/esp_driver_i2c/i2c_master.c', 'idf-i2s':'components/esp_driver_i2s/i2s_common.c', 'idf-common':'components/esp_common/include/esp_err.h', 'idf-http-parser':'components/http_parser/http_parser.h'}.get(requirement)
        if suffix is None:return 'unknown SDK prerequisite: '+requirement
        return None if (p/suffix).is_file() else 'required installed SDK source absent: '+suffix
    if requirement=='git-gatt-history':
        p=subprocess.run(['git','cat-file','-e','4c699a66acaac50731529aea773a411eb8b4b68c:ESP32C5/main/gatt_walker.c'],cwd=ROOT,capture_output=True)
        return None if p.returncode==0 else 'private GATT test requires historical source object; full git history needed'
    return 'unknown prerequisite: '+requirement


def run_process(command, output, env, timeout):
    """Bound duration and log size; reap the entire process group on failure."""
    log=output/'run.log'
    with log.open('wb') as stream:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        start=time.monotonic();reason=None
        while process.poll() is None:
            if time.monotonic()-start>timeout:reason='per-gate timeout';break
            if log.stat().st_size>8*1024*1024:reason='log exceeded 8 MiB limit';break
            time.sleep(.1)
        if reason:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
        code=process.wait()
        if log.stat().st_size>8*1024*1024:
            reason=reason or 'log exceeded 8 MiB limit'
            stream.flush()
            stream.truncate(8*1024*1024)
        # Also drain a child that accidentally outlived its harness parent.
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    return code,reason


def execute_entry(entry, output, timeout):
    if entry['kind']=='private' and not os.environ.get('CYM_GATT23_FIXTURES'):
        return dict(status='SKIP',reason='optional private captures not configured; no substitute data')
    for req in entry['requires']:
        reason=missing(req)
        if reason:return dict(status='NOT_RUN',reason=reason,exit_code=2)
    env=os.environ.copy()
    # Release-specific source overrides must never silently weaken a maintained gate.
    for key in list(env):
        if key.startswith(('CYM_','FSD_','RFHAT_')) or key in ('BASELINE','REVIEWED'):
            if key!='CYM_GATT23_FIXTURES':env.pop(key)
    for n in ('tmp','generated'): (output/n).mkdir()
    env.update(CYM_TEST_OUT=str(output/'generated'),CYM_REPO=str(ROOT),
               TMPDIR=str(output/'tmp'),TMP=str(output/'tmp'),TEMP=str(output/'tmp'),
               PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
    command=[sys.executable,'-B',str(ROOT/entry['path'])]
    if entry['kind'] in ('unittest','private'):
        command=[sys.executable,'-B',str(Path(__file__).resolve()),'--unit-worker',Path(entry['path']).stem,'--worker-output',str(output)]
        if entry['kind']=='private':command+=['--method','GattMetadata.test_actual_private_nine']
    elif entry['kind']=='ble':command+=['--output',str(output/'generated/ble-spam')]
    elif entry.get('id') in ('display_layout','wardrive_gps_prompt_lvgl'):command+=['--verify-mutations']
    code,reason=run_process(command,output,env,timeout)
    record=dict(status='PASS' if code==0 and not reason else 'FAIL',exit_code=code,command=command,log=str(output/'run.log'))
    if reason:record['reason']=reason
    if (output/'unittest.json').exists():
        record['unittest']=json.loads((output/'unittest.json').read_text())
        if code==3:record.update(status='NOT_RUN',reason='no executed passing cases (empty/all-skip gate)')
    if entry['kind']=='ble' and code==0:
        provenance=json.loads((output/'generated/ble-spam/provenance.json').read_text())
        record['counted_native_checks']=provenance['runs'][0]['checks']
        record['mutation_kills']=[x['name'] for x in provenance['runs'] if x['expected_failure'] and x['status']=='PASS']
    elif code==0 and entry.get('id')=='display_layout':
        verification=json.loads((output/'generated/layout-verification.json').read_text())
        record['counted_native_checks']=verification['runs'][0]['checks']
        record['mutation_kills']=[x['name'] for x in verification['runs'] if x['expected_failure'] and x['status']=='PASS']
    if code==0 and entry.get('id')=='pn532_ownership':
        provenance=json.loads((output/'generated/pn532-ownership/provenance.json').read_text())
        record['mutation_kills']=[x['name'] for x in provenance['runs'] if x['expected_failure'] and x['status']=='PASS']
        record['native_scenario_groups']=provenance['scenario_groups']
    return record


def dependency_provenance(suites):
    result=dict(python=sys.version, manifest_sha256=hashlib.sha256((ROOT/'tests/regression-manifest.json').read_bytes()).hexdigest())
    if shutil.which('cc'):
        result['cc']=subprocess.check_output(['cc','--version'],text=True).splitlines()[0]
    if 'sdk-native' not in suites:return result
    files=[]
    for component in ['lvgl__lvgl','espressif__esp_codec_dev']:
        base=ROOT/'ESP32C5/managed_components'/component
        files.extend(p for p in base.rglob('*') if p.is_file() and p.suffix in ('.c','.h','.yml'))
    result['managed_files']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    if os.environ.get('IDF_PATH'):
        sdk=Path(os.environ['IDF_PATH']).resolve()
        for key,path in [('idf',sdk),('nimble',sdk/'components/bt/host/nimble/nimble')]:
            if path.exists():
                run=subprocess.run(['git','rev-parse','HEAD'],cwd=path,text=True,capture_output=True)
                result[key+'_commit']=run.stdout.strip() if run.returncode==0 else 'not a git checkout; use file hashes'
        sources=[sdk/'components/esp_driver_i2s/i2s_common.c', sdk/'components/esp_driver_i2c/i2c_master.c', sdk/'components/esp_driver_i2c/include/driver/i2c_master.h']
        result['sdk_files']={str(p.relative_to(sdk)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',action='append',choices=['portable','sdk-native','private-optional','hardware'])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--only',action='append',help='select manifest ID(s) within requested suites; unknown/empty selections fail')
    parser.add_argument('--timeout',type=int,default=300,help='per entry seconds, 1..900')
    parser.add_argument('--unit-worker',help=argparse.SUPPRESS)
    parser.add_argument('--worker-output',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--method',help=argparse.SUPPRESS)
    args=parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    if args.unit_worker:return unit_worker(args.unit_worker,args.worker_output,args.method)
    if args.output is None:parser.error('--output is required and must be a new directory')
    if not 1<=args.timeout<=900:parser.error('--timeout must be 1..900')
    output=args.output.resolve()
    # Never move/overwrite any pre-existing outputs, .hermes state, or caches.
    if '.hermes' in output.parts or output==ROOT or output==ROOT/'tests' or ROOT/'tests/_out' in (output,*output.parents):
        parser.error('unsafe output location; choose a new dedicated directory')
    try:output.mkdir(parents=True,exist_ok=False)
    except FileExistsError:parser.error('output already exists; choose a new dedicated directory')
    manifest=json.loads((ROOT/'tests/regression-manifest.json').read_text())
    entries=manifest['entries'];ids=[x['id'] for x in entries]
    if len(set(ids))!=len(ids):parser.error('duplicate manifest IDs')
    suites=args.suite or ['portable']
    selected=[x for x in entries if x['suite'] in suites]
    if args.only:
        unknown=set(args.only)-{x['id'] for x in selected}
        if unknown:parser.error('IDs not in selected suites: '+', '.join(sorted(unknown)))
        selected=[x for x in selected if x['id'] in args.only]
    if 'hardware' in suites:
        selected.append(dict(id='hardware-qualification',suite='hardware',taxonomy='hardware',kind='hardware'))
    results=[dict(id=x['id'],suite=x['suite'],taxonomy=x['taxonomy'],status='NOT_RUN',reason='fail-fast: not admitted yet') for x in selected]
    write_json(output/'dependency-provenance.json',dependency_provenance(suites))
    report=dict(schema_version=1,suites=suites,root=str(ROOT),source_sha256=hashlib.sha256((ROOT/'ESP32C5/main/main.c').read_bytes()).hexdigest(),results=results)
    # Record private optional status even when not requested; never claim it passed.
    if 'private-optional' not in suites:
        report['optional']=[dict(id='private_gatt23_captures',status='SKIP',reason='private-optional suite not requested')]
    exit_code=0
    def checkpoint():
        counts=collections.Counter(x['status'] for x in results)
        report['counts']={k:counts[k] for k in ('PASS','FAIL','SKIP','NOT_RUN')}
        report['unittest_totals']={k:sum(x.get('unittest',{}).get(k,0) for x in results) for k in ('tests','passed','failures','errors','not_run')}
        report['unittest_totals']['skips']=sum(len(x.get('unittest',{}).get('skips',[])) for x in results)
        report['successful_harness_invocations']=sum(x['status']=='PASS' and 'unittest' not in x for x in results)
        report['counted_native_checks']=sum(x.get('counted_native_checks',0) for x in results)
        report['mutation_kills']=sum(len(x.get('mutation_kills',[])) for x in results)
        report['exit_code']=exit_code
        write_json(output/'results.json',report)
    checkpoint()
    for entry,record in zip(selected,results):
        start=time.monotonic();directory=output/entry['id'];directory.mkdir()
        if entry['kind']=='hardware':
            result=dict(status='NOT_RUN',reason='Hardware requires scoped owner authorization, exact board/artifact matrix and real serial access; no hardware executed',exit_code=2)
        else:
            try:result=execute_entry(entry,directory,args.timeout)
            except Exception as error:result=dict(status='FAIL',reason=str(error),exit_code=1)
        record.pop('reason',None);record.update(result);record['seconds']=round(time.monotonic()-start,3)
        if record['status'] in ('FAIL','NOT_RUN'):exit_code=2 if record['status']=='NOT_RUN' else 1
        checkpoint()
        print(record['id']+': '+record['status']+(' — '+record['reason'] if 'reason' in record else ''),flush=True)
        if exit_code:break
    if not exit_code and not any(x['status']=='PASS' for x in results):exit_code=3
    checkpoint()
    print(json.dumps(dict(counts=report['counts'],unittest_totals=report['unittest_totals'],successful_harness_invocations=report['successful_harness_invocations'],exit_code=exit_code)),flush=True)
    return exit_code


if __name__=='__main__':
    sys.exit(main())
