#!/usr/bin/env python3
"""Pinned LVGL8 refresh hooks in build tree only; preserve vendor source/input."""
import hashlib,sys
from pathlib import Path
EXPECTED='6aca7ff57a634d5a220465feccee749dd22890c3f2d9748b6f690c4b6105eb70'
def instrument(src):
 if hashlib.sha256(src.encode()).hexdigest()!=EXPECTED:raise ValueError('LVGL refresh source differs from reviewed pinned input')
 def once(a,b):
  nonlocal src
  if src.count(a)!=1:raise ValueError('LVGL hook anchor differs: '+a)
  src=src.replace(a,b)
 # Include the original source directory in CMake for ../ and local headers.
 src='#include <stdint.h>\nextern uint32_t cym_ui_diag_clock(void);\nextern void cym_ui_diag_record(unsigned,uint32_t);\n'+src
 once('    lv_obj_t * top_act_scr = NULL;', '    uint32_t cym_render_start = cym_ui_diag_clock();\n    lv_obj_t * top_act_scr = NULL;')
 once('    draw_buf_flush(disp_refr);\n}', '    cym_ui_diag_record(0, cym_render_start);\n    draw_buf_flush(disp_refr);\n}')
 # Rotation functions are static; bracket ONLY pixel permutation, not wait/flush.
 for call in ['draw_buf_rotate_180(drv, area, color_p);','draw_buf_rotate_90_sqr(drv->rotated == LV_DISP_ROT_270, area_w, color_p);','draw_buf_rotate_90(drv->rotated == LV_DISP_ROT_270, area_w, height, color_p, rot_buf);']:
  once(call,'{ uint32_t cym_rotate_start = cym_ui_diag_clock(); '+call+' cym_ui_diag_record(1, cym_rotate_start); }')
 return src
if __name__=='__main__':
 src=Path(sys.argv[1]);out=Path(sys.argv[2]);data=instrument(src.read_text());out.parent.mkdir(parents=True,exist_ok=True)
 if not out.exists() or out.read_text()!=data:out.write_text(data)
