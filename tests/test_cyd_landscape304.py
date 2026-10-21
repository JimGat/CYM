"""Patch #10 board gates and extracted-production native rotation contracts.
These tests do not qualify a physical LCD, touch panel or heap under RF load.
"""
from pathlib import Path
import hashlib, re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'ESP32C5/main/main.c').read_text()

def function(name):
    matches=list(re.finditer(r'^(?:static )?(?:void|bool) '+name+r'\([^;]*?\)\s*\{',SRC,re.M))
    assert len(matches)==1, name
    start=matches[0].start(); a=SRC.index('{',start); b=a+1; depth=1
    while depth:
        depth+=(SRC[b]=='{')-(SRC[b]=='}'); b+=1
    return SRC[start:b]

def gate(marker, start=0):
    pos=SRC.index(marker,start)
    return SRC[SRC.rfind('#if ',0,pos):].splitlines()[0]

def enabled(expr,boards):
    text=expr+'\nYES\n#endif\n'
    p=subprocess.run(['cc','-E','-P','-x','c',*['-D'+b+'=1' for b in boards],'-'],input=text,text=True,capture_output=True,check=True)
    return 'YES' in p.stdout

def native(code):
    with tempfile.TemporaryDirectory(prefix='cyd-landscape-') as d:
        c=Path(d)/'case.c'; exe=Path(d)/'case'; c.write_text(code)
        p=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],text=True,capture_output=True)
        assert p.returncode==0, p.stderr
        subprocess.run([str(exe)],check=True,capture_output=True)

class Landscape304(unittest.TestCase):
    def test_all_ten_gates_board_matrix(self):
        markers=['static void nvs_settings_save_orientation(', 'uint8_t saved_orient = screen_orientation;',
                 'apply_screen_orientation(saved_orient);', 'apply_screen_orientation(saved_orient);',
                 'disp_drv.sw_rotate = 1;', 'apply_screen_orientation(screen_orientation);',
                 'static lv_obj_t *orient_dropdown', 'uint8_t new_orient = orient_dropdown',
                 'orient_dropdown       = NULL;', '/* ── Orientation section']
        gates=[]; last=0
        for i,m in enumerate(markers):
            start=last if i==3 else 0
            gates.append(gate(m,start)); last=SRC.index(m,start)+len(m)
        self.assertEqual(len(gates),10)
        for label,boards,want,wantcal in [
            ('classic',['CONFIG_BOARD_CYD2USB'],True,True),
            ('hackerbox',['CONFIG_BOARD_CYD2USB','CONFIG_BOARD_HACKERBOX_CYD'],True,True),
            ('nm',['CONFIG_BOARD_NM_CYD_C5'],True,True),
            ('ws28',['CONFIG_BOARD_WS_C5_28'],True,False),
            ('ws35',['CONFIG_BOARD_WS_C5_35'],True,False),
            ('hosyond',['CONFIG_BOARD_HOSYOND_S3_35'],False,False),
            ('pancake',['CONFIG_BOARD_PANCAKE_C5'],False,False),
            ('ws-s3',['CONFIG_BOARD_WS_S3_5B'],False,False)]:
            for i,g in enumerate(gates):
                with self.subTest(board=label,gate=i):
                    self.assertEqual(enabled(g,boards),wantcal if i in (1,2,3) else want)

    def test_actual_orientation_helper_four_cases_invalid_and_no_display(self):
        helper=function('apply_screen_orientation')
        code='#include <assert.h>\n#include <stdint.h>\n#include <stddef.h>\n'
        code+='typedef int lv_disp_t; typedef int lv_disp_rot_t; enum {LV_DISP_ROT_NONE,LV_DISP_ROT_90,LV_DISP_ROT_180,LV_DISP_ROT_270};\n'
        code+='static int present=1, rotation=-1, calls; static lv_disp_t display;\n'
        code+='static lv_disp_t *lv_disp_get_default(void){return present?&display:NULL;}\n'
        code+='static void lv_disp_set_rotation(lv_disp_t *d,int r){assert(d==&display);rotation=r;calls++;}\n#define ESP_LOGI(...) ((void)0)\n'
        code+=helper+'\nint main(void){for(int i=0;i<4;i++){apply_screen_orientation(i);assert(rotation==i);}apply_screen_orientation(255);assert(rotation==0);present=0;int n=calls;apply_screen_orientation(1);assert(calls==n);}\n'
        native(code)

    def test_calibration_portrait_restore_success_abort_native(self):
        cal=function('run_touch_calibration')
        self.assertTrue(enabled(gate('uint8_t saved_orient = screen_orientation;'), ['CONFIG_BOARD_CYD2USB']))
        entry=cal[cal.index('#if '):cal.index('#endif')+len('#endif')]
        a=cal.index('if (aborted) {'); b=cal.index('\n        }',a)+len('\n        }')
        abort=cal[a:b]
        a=cal.index('// Strip cal widgets'); tail=cal[a:cal.rfind('}')]
        self.assertLess(cal.index('apply_screen_orientation(0)'),cal.index('lv_obj_create(NULL)'))
        self.assertEqual(len(re.findall(r'\breturn;',cal)),1)
        for boards in [('CONFIG_BOARD_CYD2USB',),('CONFIG_BOARD_CYD2USB','CONFIG_BOARD_HACKERBOX_CYD')]:
            code='#include <assert.h>\n#include <stdint.h>\n#include <stdbool.h>\n#define ESP_LOGI(...) ((void)0)\n'
            code+=''.join('#define '+b+' 1\n' for b in boards)
            code+='static uint8_t screen_orientation; static int trace[2], count; static void apply_screen_orientation(int n){trace[count++]=n;} static void lv_obj_clean(int n){(void)n;}\n'
            code+='static void run(bool aborted){int scr=0;\n'+entry+'\n'+abort+'\n'+tail+'}\n'
            code+='int main(void){for(int o=0;o<4;o++)for(int a=0;a<2;a++){screen_orientation=o;count=0;run(a);assert(count==2);assert(trace[0]==0);assert(trace[1]==o);}}'
            native(code)

    def test_persist_then_reboot_and_boot_before_ui(self):
        save=function('screen_popup_save_cb')
        self.assertLess(save.index('nvs_settings_save_orientation(screen_orientation)'),save.index('esp_restart()'))
        boot=function('app_main')
        self.assertLess(boot.index('disp_drv.sw_rotate = 1'),boot.index('lv_disp_drv_register(&disp_drv)'))
        self.assertLess(boot.index('apply_screen_orientation(screen_orientation)'),boot.index('honeypair_init('))
        self.assertIn('nvs_set_u8(h, NVS_KEY_ORIENT, orient)',function('nvs_settings_save_orientation'))

    def test_native_mapping_unchanged(self):
        hashes={'lvgl_flush_cb': '043f1ce3355f95792d2ca57400d103b93446bea25b23f606c690d4cf2de8a7b6', 'lvgl_touch_read_cb': '03769dba0cc0f5a6c06bd7c4d3e616db89fac44614b92edaacd2ac223bee2184'}
        for name,digest in hashes.items():
            # Pin native callbacks/panel setup, independently of rotation gates.
            body=function(name); body=body[body.index(name+'('):]
            self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),digest,name)
        for name,digest in {'ESP32C5/main/xpt2046.c': 'e2c2a96aa39b4da4aa1b9657c3b122bf48062c65c6d3069e2cbc514f4dafd045', 'ESP32/sdkconfig.defaults.hackerbox-cyd': '62069b3aa5b9d7f7352fcca22948dda55bb450f2b8d37d3c52f9b5d5c29f8d95'}.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        # Existing native init/header contracts are now board-preprocessed in test_cyd_l_variant.
        self.assertIn('#define TOUCH_CAL_NVS_NS "touch_hb"',SRC)

    def test_installed_lvgl_indev_rotation_native_corners_center(self):
        src=(ROOT/'ESP32C5/managed_components/lvgl__lvgl/src/core/lv_indev.c').read_text()
        a=src.index('    if(disp->driver->rotated == LV_DISP_ROT_180')
        b=src.index('    /*Simple sanity check*/',a)
        code='#include <assert.h>\ntypedef int lv_coord_t; enum {LV_DISP_ROT_NONE,LV_DISP_ROT_90,LV_DISP_ROT_180,LV_DISP_ROT_270};\n'
        code+='struct drv{int rotated,hor_res,ver_res;}; struct display{struct drv *driver;}; struct data{struct {int x,y;}point;};\n'
        code+='int main(void){const int p[][2]={{0,0},{239,0},{0,319},{239,319},{120,160}}; for(int r=0;r<4;r++)for(int i=0;i<5;i++){struct drv dr={r,240,320};struct display ds={&dr},*disp=&ds;struct data dt={{p[i][0],p[i][1]}},*data=&dt;\n'
        code+=src[a:b]
        code+='int x=p[i][0],y=p[i][1],ex=x,ey=y;if(r==1){ex=319-y;ey=x;}if(r==2){ex=239-x;ey=319-y;}if(r==3){ex=y;ey=239-x;}assert(data->point.x==ex&&data->point.y==ey);assert(ex>=0&&ex<(r%2?320:240));assert(ey>=0&&ey<(r%2?240:320));}}'
        native(code)

    def test_lvgl_rotation_is_before_native_flush(self):
        src=(ROOT/'ESP32C5/managed_components/lvgl__lvgl/src/core/lv_refr.c').read_text()
        self.assertIn('draw_buf_rotate(draw_ctx->buf_area, draw_ctx->buf)',src)
        self.assertIn('call_flush_cb(drv, area, rot_buf == NULL ? color_p : rot_buf)',src)
        self.assertIn('lv_mem_buf_get(LV_DISP_ROT_MAX_BUF)',src)
        cb=function('lvgl_touch_read_cb')
        self.assertIn('touch_x = point.x;',cb); self.assertIn('data->point.x = touch_x;',cb)
        flush=function('lvgl_flush_cb')
        self.assertIn('cym_panel_transfer(panel, area->x1, area->y1,',flush)

    def test_both_menu_layout_routes(self):
        self.assertRegex(function('show_cat_tools'),r'"Settings".*main_tile_event_cb, "Settings"')
        self.assertIn('lv_timer_create(settings_nav_timer_cb, 800, NULL)',function('main_tile_event_cb'))
        self.assertIn('show_settings_screen();',function('settings_nav_timer_cb'))
        self.assertRegex(function('show_settings_screen_measured'),r'"Screen".*settings_tile_event_cb, "Screen"')
        self.assertRegex(function('settings_tile_event_cb_measured'),r'strcmp\(tile_name, "Screen"\) == 0\) \{\s*show_screen_popup\(\);')
        self.assertRegex(function('show_main_tiles'),r'"Settings".*main_tile_event_cb, "Settings"')

if __name__=='__main__': unittest.main()
