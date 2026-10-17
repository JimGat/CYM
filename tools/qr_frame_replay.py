#!/usr/bin/env python3
"""Offline owner-controlled replay. Reports counts/length/hash, NEVER payload.
Requires Pillow and zxing-cpp; compiles this tree's production quirc with cc.
Images are read-only; generated code/library/results stay in --output-dir.
"""
import argparse, ctypes as C, hashlib, importlib.metadata, json, subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('images',nargs='+',type=Path)
    ap.add_argument('--rgb565',type=Path,help='matched native raw file, one PGM only')
    ap.add_argument('--output-dir',type=Path,required=True)
    a=ap.parse_args()
    if len(a.images)>8 or (a.rgb565 and len(a.images)!=1):ap.error('bounded replay: <=8 images; raw pairing requires one PGM')
    from PIL import Image
    import zxingcpp
    out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1];b=root/'ESP32C5/components/cym_qr'
    so=out/'production-quirc.so'
    subprocess.run(['cc','-shared','-fPIC','-O2','-I',str(b/'include'),'-I',str(b/'third_party/quirc'),str(b/'cym_qr.c'),*[str(b/'third_party/quirc'/n) for n in ['quirc.c','identify.c','decode.c','version_db.c']],'-o',str(so)],check=True)
    lib=C.CDLL(str(so));lib.cym_qr_create.argtypes=[C.c_int,C.c_int];lib.cym_qr_create.restype=C.c_void_p
    lib.cym_qr_destroy.argtypes=[C.c_void_p]
    class Stats(C.Structure):
        _fields_=[(x,C.c_uint32) for x in ['candidates','normal_attempts','mirror_attempts','valid','payload_length']]+[('errors',C.c_uint32*8)]
    lib.cym_qr_decode_gray_ex.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.POINTER(Stats)]
    def replay(im):
        w,h=im.size;data=im.tobytes();q=lib.cym_qr_create(w,h)
        if not q:raise RuntimeError('production decoder allocation failed')
        payload=C.create_string_buffer(8896);st=Stats()
        try:n=lib.cym_qr_decode_gray_ex(q,data,w,payload,8896,C.byref(st))
        finally:lib.cym_qr_destroy(q)
        native=dict(valid=bool(st.valid),candidates=st.candidates,normal=st.normal_attempts,mirror=st.mirror_attempts,errors=list(st.errors),length=n if st.valid else None,sha256=hashlib.sha256(payload.raw[:n]).hexdigest() if st.valid else None)
        independent=[]
        for result in zxingcpp.read_barcodes(im,formats=zxingcpp.BarcodeFormat.QRCode):
            valid=bool(result.valid);raw=bytes(result.bytes) if valid else b''
            independent.append(dict(valid=valid,length=len(raw) if valid else None,sha256=hashlib.sha256(raw).hexdigest() if valid else None))
        return dict(mean=sum(data)/len(data),dark=sum(x<64 for x in data),light=sum(x>191 for x in data),minimum=min(data),maximum=max(data),gray_sha256=hashlib.sha256(data).hexdigest(),quirc=native,zxing=independent)
    rows=[]
    for path in a.images:
        with Image.open(path) as source:im=source.convert('L')
        w,h=im.size
        if w<1 or h<1 or w>1024 or h>1024:raise ValueError('image outside bounded production dimensions')
        row=dict(file=path.name,file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width=w,height=h,native=replay(im))
        if a.rgb565:
            raw=a.rgb565.read_bytes()
            if len(raw)!=w*h*2:raise ValueError('raw file must be exactly width*height*2')
            row['raw_sha256']=hashlib.sha256(raw).hexdigest();row['interpretations']={}
            for order in ['little','big']:
                for swap in [False,True]:
                    gray=bytearray()
                    for i in range(0,len(raw),2):
                        v=int.from_bytes(raw[i:i+2],order);r=((v>>11)&31)*255//31;g=((v>>5)&63)*255//63;b=(v&31)*255//31
                        if swap:r,b=b,r
                        gray.append((77*r+150*g+29*b)>>8)
                    variant=Image.frombytes('L',(w,h),bytes(gray));result=replay(variant)
                    result['mismatched_native_gray_pixels']=sum(x!=y for x,y in zip(gray,im.tobytes()))
                    row['interpretations'][order+('_bgr' if swap else '_rgb')]=result
        rows.append(row)
    report=dict(zxing_version=importlib.metadata.version('zxing-cpp'),source_root=str(root),images=rows,limitations='PGM alone cannot establish original sensor byte order, row packing, exposure or optics. Raw-order variants are offline diagnostics, not register settings or a physical fix.')
    (out/'replay-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
