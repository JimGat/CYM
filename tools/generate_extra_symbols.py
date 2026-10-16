#!/usr/bin/env python3
"""Reproduce the existing 20px/4bpp FontAwesome bitmap with lv_font_conv 1.5.3.
TTFs are owner-provided Font Awesome Free sources (SIL OFL 1.1); keep source
provenance and their license. No font version refresh is performed here.
Usage: python tools/generate_extra_symbols.py --converter /path/lv_font_conv.js
       --fonts /home/dev/projects/fonts [--output /path/lv_extra_symbols.c]
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
def glyphs(text):
 """Resolve the production sparse cmap to actual 4bpp bitmap and metrics."""
 def block(name):return re.search(r'\b'+name+r'\[\]\s*=\s*\{(.*?)\n\};',text,re.S)[1]
 bitmap=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]+)',re.sub(r'/\*.*?\*/','',block('glyph_bitmap'),flags=re.S)))
 desc=[{k:int(v) for k,v in re.findall(r'\.(\w+)\s*=\s*(-?\d+)',row)} for row in re.findall(r'\{([^{}]*)\}',block('glyph_dsc'))]
 offsets=[int(x,16) for x in re.findall(r'0x([0-9a-fA-F]+)',block('unicode_list_0'))]
 cmap=block('cmaps');start=int(re.search(r'\.range_start\s*=\s*(\d+)',cmap)[1]);first=int(re.search(r'\.glyph_id_start\s*=\s*(\d+)',cmap)[1]);count=int(re.search(r'\.list_length\s*=\s*(\d+)',cmap)[1])
 assert count==len(offsets) and offsets==sorted(set(offsets))
 result={}
 for i,off in enumerate(offsets):
  d=desc[first+i].copy();idx=d.pop('bitmap_index');n=(d['box_w']*d['box_h']+1)//2;pixels=bitmap[idx:idx+n]
  assert len(pixels)==n and any(pixels),(off,'empty bitmap')
  result[str(start+off)]=dict(metrics=d,sha256=hashlib.sha256(pixels).hexdigest())
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--converter',required=True);p.add_argument('--fonts',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'ESP32C5/main/lv_extra_symbols.c');a=p.parse_args()
 recipe=json.loads((ROOT/'tools/extra_symbols_recipe.json').read_text())
 v=subprocess.check_output(['node',a.converter,'--version'],text=True).strip();assert v=='1.5.3',v
 for name,digest in recipe['font_sha256'].items():assert hashlib.sha256((a.fonts/name).read_bytes()).hexdigest()==digest,name
 cmd=['node',a.converter,'--bpp','4','--size','20','--no-compress','--lv-include','lvgl.h']
 for name,key in [('fa-solid-900.ttf','solid'),('fa-brands-400.ttf','brands')]:cmd+=['--font',str(a.fonts/name),'--range',','.join(map(str,sorted(recipe[key])))]
 cmd+=['--format','lvgl','--lv-font-name','lv_extra_symbols','-o',str(a.output)]
 subprocess.run(cmd,check=True)
 actual=glyphs(a.output.read_text());assert set(map(int,actual))==set(recipe['solid']+recipe['brands'])
 print('Generated',len(actual),'mapped, nonempty glyphs:',a.output)
