#!/usr/bin/env python3
"""Fail-closed pinned mDNS source overlay; never edits managed_components."""
from pathlib import Path
import sys,json,hashlib,subprocess
upstream,out=map(Path,sys.argv[1:]);patches=Path(__file__).resolve().parents[1]/'patches/mdns'
for name,digest in json.loads((patches/'upstream.json').read_text()).items():
    source=upstream/name
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
        raise SystemExit('mDNS upstream changed; review lifecycle patch before building')
out.mkdir(parents=True,exist_ok=True)
(out/'mdns_service.c').write_bytes((upstream/'mdns_service.c').read_bytes())
subprocess.run(['patch','--batch','--fuzz=0','-d',str(out),'-p0','-i',str(patches/'service-lifecycle.patch')],check=True)
