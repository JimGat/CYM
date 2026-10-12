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
 src='#include <stdint.h>\nextern uint32_t cym_ui_diag_clock(void);\nextern void cym_ui_diag_record(unsigned,uint32_t);\nextern void cym_ui_diag_work_record(unsigned,uint32_t);\n'+src
 once('    lv_obj_t * top_act_scr = NULL;', '    uint32_t cym_render_start = cym_ui_diag_clock();\n    lv_obj_t * top_act_scr = NULL;')
 once('    draw_buf_flush(disp_refr);\n}', '    cym_ui_diag_record(0, cym_render_start);\n    draw_buf_flush(disp_refr);\n}')
 # Bounded RAM-only work counters. IDs match ui_diagnostics.h; no logs here.
 once('    /*Save only if this area is not in one of the saved areas*/',
      '    cym_ui_diag_work_record(0, lv_area_get_size('+chr(38)+'com_area));\n    /*Save only if this area is not in one of the saved areas*/')
 once('    disp->inv_p++;', '    cym_ui_diag_work_record(1, lv_area_get_size('+chr(38)+'disp->inv_areas[disp->inv_p]));\n    disp->inv_p++;')
 once('            refr_area('+chr(38)+'disp_refr->inv_areas[i]);',
      '            cym_ui_diag_work_record(2, lv_area_get_size('+chr(38)+'disp_refr->inv_areas[i]));\n            refr_area('+chr(38)+'disp_refr->inv_areas[i]);')
 once('    uint32_t cym_render_start = cym_ui_diag_clock();',
      '    cym_ui_diag_work_record(3, lv_area_get_size(draw_ctx->buf_area));\n    uint32_t cym_render_start = cym_ui_diag_clock();')
 once('    lv_obj_t * found_p = NULL;', '    cym_ui_diag_work_record(4, 1);\n    lv_obj_t * found_p = NULL;')
 once('    lv_layer_type_t layer_type = _lv_obj_get_layer_type(obj);',
      '    cym_ui_diag_work_record(5, 1);\n    lv_layer_type_t layer_type = _lv_obj_get_layer_type(obj);')
 once('    /*Do nothing if there is no active screen*/',
      '    cym_ui_diag_record(6, cym_layout_start);\n    /*Do nothing if there is no active screen*/')
 once('    /*Refresh the screen\'s layout if required*/', '    uint32_t cym_layout_start = cym_ui_diag_clock();\n    /*Refresh the screen\'s layout if required*/')
 once('    lv_refr_join_area();', '    uint32_t cym_refresh_start = cym_ui_diag_clock();\n    lv_refr_join_area();')
 once('    refr_invalid_areas();', '    refr_invalid_areas();\n    cym_ui_diag_record(7, cym_refresh_start);')
 # Rotation functions are static; bracket ONLY pixel permutation, not wait/flush.
 for call in ['draw_buf_rotate_180(drv, area, color_p);','draw_buf_rotate_90_sqr(drv->rotated == LV_DISP_ROT_270, area_w, color_p);','draw_buf_rotate_90(drv->rotated == LV_DISP_ROT_270, area_w, height, color_p, rot_buf);']:
  once(call,'{ uint32_t cym_rotate_start = cym_ui_diag_clock(); '+call+' cym_ui_diag_record(1, cym_rotate_start); }')
 return src
if __name__=='__main__':
 src=Path(sys.argv[1]);out=Path(sys.argv[2]);data=instrument(src.read_text());out.parent.mkdir(parents=True,exist_ok=True)
 if not out.exists() or out.read_text()!=data:out.write_text(data)
