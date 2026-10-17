import subprocess,sys,json
from pathlib import Path
objcopy,nm,mapping,archive=sys.argv[1:5]
before=subprocess.check_output([nm,"-u",archive],text=True)
pairs=[l.split() for l in Path(mapping).read_text().splitlines() if l.strip()]
found={l.split()[-1] for l in before.splitlines() if l.split()}
used=[]
for old,new in pairs:
 if old in found:
  subprocess.run([objcopy,"--redefine-sym",old+"="+new,archive],check=True);used.append([old,new])
after=subprocess.check_output([nm,"-u",archive],text=True)
remaining={l.split()[-1] for l in after.splitlines() if l.split()}
assert not remaining.intersection({a for a,b in pairs})
Path(archive+".audit.json").write_text(json.dumps(dict(rebound=used,undefined_before=before,undefined_after=after),indent=2))

# Give private template COMDATs a distinct namespace, including group signatures.
# Plain compatible pointers still required for imported stdlib implementation paths.
import re
private=set()
for raw in sys.argv[5:]:
 listing=subprocess.check_output([nm,"--defined-only",raw],text=True)
 private.update(l.split()[-1] for l in listing.splitlines() if len(l.split())>=3 and l.split()[-2] in ["W","V"] and l.split()[-1].startswith("_Z") and not l.split()[-1].startswith(("_ZTI","_ZTS","_ZTV")))
 groups=subprocess.check_output([str(Path(objcopy).with_name(Path(objcopy).name.replace("objcopy","readelf"))),"--section-groups",raw],text=True)
 private.update(re.findall(r"COMDAT group section .*?\[([^]]+)\] contains",groups))
private={s for s in private if s.startswith("_Z") and not s.startswith(("_ZTI","_ZTS","_ZTV"))}
if private:
 symbols=Path(archive+".private-map.txt");symbols.write_text("\n".join(s+" cym_private_"+s for s in sorted(private))+"\n")
 subprocess.run([objcopy,"--redefine-syms="+str(symbols),archive],check=True)
Path(archive+".isolation.json").write_text(json.dumps(dict(renamed=sorted(private)),indent=2))
