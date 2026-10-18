import shutil,subprocess,sys,tempfile
from pathlib import Path
ar,objcopy,stdlib,obj,out=sys.argv[1:]
# Extract to a file, not via `ar p` stdout: Windows binutils write stdout in text
# mode and the LF->CRLF translation corrupts the object ("file format not recognized").
with tempfile.TemporaryDirectory() as d:
    subprocess.run([ar,"x",str(Path(stdlib).resolve()),"eh_alloc.o"],cwd=d,check=True)
    shutil.copyfile(Path(d)/"eh_alloc.o",obj)
# Only allocation requests in this member change; its pools, locks, exception
# headers, dependent exceptions, free paths and unwind protocol are unchanged.
subprocess.run([objcopy,"--redefine-sym","malloc=cym_zx_eh_malloc",obj],check=True)
subprocess.run([ar,"rcs",out,obj],check=True)
