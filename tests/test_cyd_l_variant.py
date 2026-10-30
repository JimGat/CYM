"""Isolated alternate mapping; contracts are not physical qualification."""
from pathlib import Path
import json, os, re, subprocess, tempfile, unittest
R=Path(__file__).resolve().parents[1]
MAIN=R/'ESP32C5/main/main.c'
FLAG='CONFIG_BOARD_CYD_2432S028_L'
def pp(text,flags):
 return subprocess.run(['cc','-E','-P','-x','c',*['-D'+f+'=1' for f in flags],'-'],input=text,text=True,capture_output=True,check=True).stdout
def function(text,name):
 a=text.index('static void '+name+'(void)\n{');b=text.index('{',a);depth=1;i=b+1
 while depth:depth+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[a:i]
def baseline(path):return subprocess.check_output(['git','show','31bfb4a1262c3f449232cff0691de5a91db21576:'+path],cwd=R,text=True)
class CydLVariant(unittest.TestCase):
 def test_identity_defaults_and_family(self):
  h=(R/'ESP32C5/components/board_hal/include/boards/cyd2usb.h').read_text()
  out=pp(h+'\nBOARD_NAME BOARD_LCD_WIDTH BOARD_LCD_HEIGHT BOARD_DEFAULT_ORIENTATION\n',['CONFIG_BOARD_CYD2USB',FLAG])
  self.assertIn('"CYD-2432S028-L" 240 320 1',out)
  d=(R/'ESP32/sdkconfig.defaults.cyd-2432s028-l').read_text()
  self.assertIn(FLAG+'=y',d);self.assertIn('# CONFIG_BOARD_HACKERBOX_CYD is not set',d)
  self.assertIn('CONFIG_BOARD_CYD2USB=y',(R/'ESP32/sdkconfig.defaults.cyd2usb').read_text())
 def test_existing_profiles_preprocessed_unchanged(self):
  src=MAIN.read_text();old=baseline('ESP32C5/main/main.c');h='ESP32C5/components/board_hal/include/boards/cyd2usb.h'
  for flags in [[],['CONFIG_BOARD_CYD2USB'],['CONFIG_BOARD_CYD2USB','CONFIG_BOARD_HACKERBOX_CYD']]:
   for extra in [[],['CONFIG_BOARD_HAS_PSRAM'],['CONFIG_SPIRAM']]:
    fs=flags+extra
    for name in ['init_display','run_touch_calibration']:
     self.assertEqual(pp(function(src,name),fs),pp(function(old,name),fs),(name,fs))
    # -dM is required: plain -E removes definitions and would compare two empty headers.
    def macros(text):
     return subprocess.run(['cc','-E','-dM','-x','c',*['-D'+f+'=1' for f in fs],'-'],input=text,text=True,capture_output=True,check=True).stdout
    self.assertEqual(macros((R/h).read_text()),macros(baseline(h)),fs)
 def test_variant_transform_and_color(self):
  out=pp(function(MAIN.read_text(),'init_display'),['CONFIG_BOARD_CYD2USB',FLAG])
  for s in ['esp_lcd_panel_swap_xy(panel_handle, false)','esp_lcd_panel_mirror(panel_handle, true, false)','LCD_RGB_ELEMENT_ORDER_RGB','esp_lcd_panel_invert_color(panel_handle, false)','esp_lcd_new_panel_ili9341']:
   self.assertIn(s,out)
 def test_variant_solver_and_namespace(self):
  src=MAIN.read_text();out=pp(function(src,'run_touch_calibration'),['CONFIG_BOARD_CYD2USB',FLAG])
  self.assertIn('bool swapped =',out);self.assertIn('abs(horizontal) < 500',out)
  a=src.index('// Touch calibration NVS');b=src.index('#endif',a)+len('#endif')
  for flag,ns in [(FLAG,'touch_cyd_l'),('CONFIG_BOARD_HACKERBOX_CYD','touch_hb'),(None,'touch_cal')]:
   fs=['CONFIG_BOARD_CYD2USB']+([flag] if flag else [])
   self.assertEqual(pp(src[a:b]+'\nTOUCH_CAL_NVS_NS\n',fs).strip(),'"'+ns+'"')
 def test_saved_orientation_wins(self):
  src=MAIN.read_text();a=src.index('uint8_t orient',src.index('static void nvs_settings_load(void)\n{'));b=src.index('\n',src.index('screen_orientation = orient;',a))+len('\n        }')
  block=src[a:b];self.assertIn('orient <= 3',block)
  code='#include <stdint.h>\n#include <assert.h>\n#define ESP_OK 0\nstatic int err;static uint8_t value,screen_orientation;\n#define nvs_get_u8(h,k,p) (*(p)=value,err)\nvoid load(void){'+block+'\n}\nint main(void){for(int fail=0;fail<2;fail++)for(int n=0;n<256;n++){err=fail;value=n;screen_orientation=1;load();assert(screen_orientation==(!fail&&n<=3?n:1));}}'
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.c').write_text(code);subprocess.run(['cc',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True);subprocess.run([str(p/'t')],check=True)
 def test_mutual_exclusion(self):
  k=(R/'ESP32C5/components/board_hal/Kconfig').read_text()
  self.assertRegex(k,r'config BOARD_CYD_2432S028_L\s+bool "CYD-2432S028-L[^\n]*\n\s+depends on BOARD_CYD2USB && !BOARD_HACKERBOX_CYD')
  h=(R/'ESP32C5/components/board_hal/include/boards/cyd2usb.h').read_text()
  p=subprocess.run(['cc','-E','-x','c','-DCONFIG_BOARD_CYD_2432S028_L=1','-DCONFIG_BOARD_HACKERBOX_CYD=1','-'],input=h,text=True,capture_output=True)
  self.assertNotEqual(p.returncode,0)
 def test_package_build_and_channel_identity(self):
  s=(R/'scripts/build.sh').read_text();self.assertIn('cyd-2432s028-l)',s);self.assertIn('sdkconfig.defaults.cyd2usb;sdkconfig.defaults.cyd-2432s028-l',s)
  cm=(R/'ESP32/CMakeLists.txt').read_text();self.assertIn('binaries-cyd-2432s028-l',cm);self.assertIn('CYM-CYD-2432S028-L',cm)
  m=json.loads((R/'ESP32/docs/manifest.cyd-2432s028-l.json').read_text());self.assertEqual(m['version'],'v3.0.41');self.assertEqual([p['offset'] for p in m['parts']],[4096,32768,65536])
  self.assertTrue(all('binaries-cyd-2432s028-l/' in p['path'] for p in m['parts']))
  page=(R/'ESP32C5/docs/index.html').read_text();board=page.split('"cyd-2432s028-l": {',1)[1].split('},',1)[0]
  self.assertIn('stableAvailable: true',board);self.assertIn('beta: false',board);self.assertIn('label: "CYD-2432S028-L"',board)
  self.assertIn('cyd-2432s028-l',(R/'.github/workflows/deploy-flasher.yml').read_text())

 def test_production_solver_and_xpt_mapping_eight_transforms(self):
  src=MAIN.read_text();a=src.index('        int dx_x =');b=src.index('\n#else',a)
  solver=src[a:b].replace('lv_label_set_text(lbl, "Invalid corner samples.\\nRelease and retry.");','return false;').replace('            for (int wait = 0; wait < 150; wait++) cal_tick();','').replace('            continue;','')
  xpt=(R/'ESP32C5/main/xpt2046.c').read_text()
  a=xpt.index('static uint16_t xpt2046_map(');b=xpt.index('\n}',a)+2;mapper=xpt[a:b]
  a=xpt.index('    // Apply axis swap / invert before mapping');b=xpt.index('    point->x',a);mapping=xpt[a:b]
  code='#include <assert.h>\n#include <stdint.h>\n#include <stdbool.h>\n#include <stdlib.h>\n'
  code+='typedef struct {int x_min,x_max,y_min,y_max,invert_x,invert_y,swap_xy,null_x,null_y,screen_w,screen_h;} touch_cal_t;\n'
  code+='bool solve(uint16_t raw_x[4],uint16_t raw_y[4],touch_cal_t *out){'+solver+'\n*out=cal;return true;}\n'+mapper
  code+='\nvoid map(touch_cal_t *handle,uint16_t raw_x,uint16_t raw_y,int *x,int *y){'+mapping+'*x=px;*y=py;}\n'
  code+=r"""
int main(void){
 for(int sw=0;sw<2;sw++)for(int ix=0;ix<2;ix++)for(int iy=0;iy<2;iy++){
  uint16_t rx[4],ry[4];
  for(int i=0;i<4;i++){int x=(i&1)^ix,y=((i>>1)&1)^iy;rx[i]=300+(sw?y:x)*3000;ry[i]=700+(sw?x:y)*2000;}
  touch_cal_t c;assert(solve(rx,ry,&c));assert(c.swap_xy==sw&&c.invert_x==ix&&c.invert_y==iy);
  assert(c.x_min==300&&c.x_max==3300&&c.y_min==700&&c.y_max==2700);c.screen_w=240;c.screen_h=320;
  for(int i=0;i<4;i++){int x,y;map(&c,rx[i],ry[i],&x,&y);assert(x==(i&1)*239&&y==((i>>1)&1)*319);}
  int x,y;map(&c,1800,1700,&x,&y);assert(abs(x-120)<=1&&abs(y-160)<=1);
 }
 touch_cal_t c;uint16_t z[4]={0,0,0,0};assert(!solve(z,z,&c));
 uint16_t a[4]={300,600,300,600},b[4]={700,700,1000,1000};assert(!solve(a,b,&c));
 uint16_t d[4]={0,2000,2000,4000};assert(!solve(d,d,&c));
}
"""
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=c11','-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)


 def test_real_flasher_channels_preserve_selection_and_ignore_stale(self):
  page=(R/'ESP32C5/docs/index.html').read_text()
  defs=page[page.index('const BOARDS ='):page.index('// Hidden opt-in:')]
  load=page[page.index('let manifestRequest ='):page.index('// ── Connection')]
  channel=page[page.index('const switchChannel ='):page.index('const updateBetaBoardWarning =')]
  code=defs+r"""
const assert=require('assert');let fetched=[],errors=[];
const state={board:'cyd-2432s028-l',channel:'dev',manifest:null};
const BRANCH={stable:'main',dev:'Jimgat_Dev'};
const raw=(b,s,p)=>b+'/'+s+'/'+p;
const element=()=>({style:{},querySelector:()=>element(),removeAttribute(){}});
const ui=new Proxy({},{get:(o,k)=>o[k]||(o[k]=element())});
const document={querySelectorAll:()=>[],title:''};
const updateBoardUI=()=>{};const setStatus=()=>{};const log=()=>{};
const PAGE_VERSION='test';const manifestError=e=>errors.push(e.message);
const normalizeManifest=m=>m;
let fetch=async url=>{fetched.push(url);return {ok:true,json:async()=>({name:'L',version:'v3.0.41',parts:[{}]})};};
"""+load+channel+r"""
(async()=>{
 const exact=ch=>BRANCH[ch]+'/ESP32/docs/manifest.cyd-2432s028-l.json';
 await loadManifest();assert.equal(fetched[0],exact('dev'));
 for(const ch of ['stable','dev','stable']){
  switchChannel(ch);await new Promise(setImmediate);
  assert.equal(state.board,'cyd-2432s028-l');assert.equal(state.channel,ch);assert(state.manifest);
  assert.equal(fetched.at(-1),exact(ch));
 }
 assert(fetched.every(url=>url===exact('stable')||url===exact('dev')));assert.equal(errors.length,0);
 // A delayed old channel must not replace the current channel's manifest.
 for(const ch of ['dev','stable']){
  const other=ch==='dev'?'stable':'dev';state.board='cyd-2432s028-l';state.channel=other;let finish;
  fetch=async url=>{fetched.push(url);return {ok:true,json:()=>new Promise(resolve=>finish=resolve)};};
  const old=loadManifest();await new Promise(setImmediate);
  fetch=async url=>{fetched.push(url);return {ok:true,json:async()=>({name:'current-'+ch,parts:[{}]})};};
  switchChannel(ch);await new Promise(setImmediate);
  assert.equal(fetched.at(-1),exact(ch));assert.equal(state.manifest.name,'current-'+ch);
  finish({name:'stale',parts:[{}]});await old;
  assert.equal(state.board,'cyd-2432s028-l');assert.equal(state.channel,ch);assert.equal(state.manifest.name,'current-'+ch);
 }
 // Preserve the preexisting exact generic/HackerBox identities too.
 for(const id of ['cyd-2432s028','hackerbox-cyd']){
  state.board=id;state.channel='dev';switchChannel('stable');await new Promise(setImmediate);
  assert.equal(state.board,id);assert.equal(fetched.at(-1),'main/ESP32/docs/manifest.'+id+'.json');
 }
 // Experimental targets must not gain Stable availability.
 for(const id of ['pancake-c5','ws-s3-5b']){
  state.board=id;state.channel='dev';switchChannel('stable');assert.equal(state.channel,'dev');
 }

})().catch(e=>{console.error(e);process.exitCode=1;});
"""
  p=subprocess.run(['node','-e',code],text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)


 def test_normal_root_direct_selection_starts_stable(self):
  page=(R/'ESP32C5/docs/index.html').read_text()
  defs=page[page.index('const BOARDS ='):page.index('// Hidden opt-in:')]
  initial=page[page.index('// Hidden opt-in:'):page.index('const PAGE_VERSION')]
  code=defs+"const window={location:{search:'?board=cyd-2432s028-l'}};\n"+initial+"\nconst assert=require('assert');assert.equal(betaUnlock,false);assert.equal(initialBoard,'cyd-2432s028-l');assert.equal(state.board,'cyd-2432s028-l');assert.equal(state.channel,'stable');assert.equal(DEFAULT_BOARD_IDS.length,7);"
  p=subprocess.run(['node','-e',code],text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':unittest.main()
