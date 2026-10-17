import subprocess,sys
from pathlib import Path
ar,objcopy,stdlib,obj,out=sys.argv[1:]
Path(obj).write_bytes(subprocess.check_output([ar,"p",stdlib,"eh_alloc.o"]))
# Only allocation requests in this member change; its pools, locks, exception
# headers, dependent exceptions, free paths and unwind protocol are unchanged.
subprocess.run([objcopy,"--redefine-sym","malloc=cym_zx_eh_malloc",obj],check=True)
subprocess.run([ar,"rcs",out,obj],check=True)
