#!/usr/bin/env python3
"""Compile the complete production NTP translation unit against deterministic fakes."""
from pathlib import Path
import re, subprocess, os, resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
root=Path(__file__).resolve().parents[1]
evidence=Path('/home/dev/projects/cym-ntp-memory-evidence')
os.environ['TMPDIR']=str(evidence)
src=(root/'ESP32C5/components/cym_timekeeper/cym_ntp_server.c').read_text()
hdr=(root/'ESP32C5/components/cym_timekeeper/include/cym_ntp_server.h').read_text()
def strip(s): return re.sub(r'^\s*#(?:include|pragma)[^\n]*', '', s, flags=re.M)
code=(root/'tests/ntp_lifecycle_host.c').read_text().replace('__PRODUCTION__',strip(hdr)+'\n'+strip(src))
p=evidence/'ntp_lifecycle_host_generated.c';p.write_text(code)
bin=evidence/'ntp_lifecycle_host'
subprocess.run(['cc','-std=c11','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable','-DCYM_NTP_HOST_TEST',str(p),'-o',str(bin)],check=True)
cases=['socket','bind','option','allocation','internal','psram','debug','timeout','delayed','serialize','malformed','sendfail']+[f'packet{i}' for i in range(7)]
for c in cases: subprocess.run([str(bin),c],check=True)
print(f'PASS {len(cases)} production NTP cases')
