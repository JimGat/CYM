"""Production build-script and Back navigation regressions; host-only, no device/RF."""
import ast, unittest, pathlib, re, subprocess, tempfile, os, importlib.util
R=pathlib.Path(__file__).resolve().parents[1]
def function(s,name):
    m=re.search(r"(?:static )?void "+name+r"\([^)]*\)\s*\{",s); start=m.start(); i=m.end(); depth=1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[start:i]
class BuildNav(unittest.TestCase):
    def test_windows_literal(self):
        source=(R/'ESP32C5/tools/update_memory_map.py').read_text(); node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='replace_section'); ns={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'production replace_section','exec'),ns)
        self.assertEqual(ns['replace_section']('START\nold\nEND','START','END',r'C:\local-builds\1\new'), 'START\n'+r'C:\local-builds\1\new'+'\nEND')

    def test_native_archive_equivalence(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
            d=pathlib.Path(d); (d/'eh_alloc.c').write_text('extern void *malloc(unsigned long); void *probe(void){return malloc(7);}')
            subprocess.run(['cc','-c',str(d/'eh_alloc.c'),'-o',str(d/'eh_alloc.o')],check=True)
            subprocess.run(['ar','rcs',str(d/'lib.a'),str(d/'eh_alloc.o')],check=True)
            original=subprocess.check_output(['ar','p',str(d/'lib.a'),'eh_alloc.o'])
            subprocess.run(['python3',str(R/'ESP32C5/components/cym_qr/copy_eh_runtime.py'),'ar','objcopy',str(d/'lib.a'),str(d/'new.o'),str(d/'out.a')],check=True)
            (d/'expect.o').write_bytes(original);subprocess.run(['objcopy','--redefine-sym','malloc=cym_zx_eh_malloc',str(d/'expect.o')],check=True)
            self.assertEqual((d/'expect.o').read_bytes(),(d/'new.o').read_bytes())
            self.assertEqual(subprocess.check_output(['ar','p',str(d/'out.a'),'new.o']),(d/'expect.o').read_bytes())
    def test_real_nav_stack(self):
        s=(R/'ESP32C5/main/main.c').read_text()
        code='#include <assert.h>\n#include <stdbool.h>\n#define NAV_STACK_MAX 12\n#include <string.h>\n#include <stddef.h>\ntypedef void lv_event_t;\nstatic const char *nav_stack[12];static int nav_stack_depth,nav_to_menu_flag,stops,cancelled,layout;static void (*g_screen_back_fn)(void),(*nav_deferred_show_fn)(void);static void clock_cancel_radio_navigation(void){cancelled++;}\n'
        code+=function(s,'nav_stack_enter')+'\nstatic void parent(void){nav_stack_enter("Parent");} static void grand(void){nav_stack_enter("Grand");} static void (*nav_show_lookup(const char *n))(void){return !strcmp(n,"Parent")?parent:!strcmp(n,"Grand")?grand:NULL;}\n'+function(s,'nav_back_cb')
        code+='\nstatic void drain(void){if(nav_to_menu_flag){nav_to_menu_flag=0;stops++;nav_stack_depth=0;}if(nav_deferred_show_fn){void(*fn)(void)=nav_deferred_show_fn;nav_deferred_show_fn=NULL;stops++;fn();}}\nint main(void){for(layout=0;layout<2;layout++){\nnav_stack_depth=0;nav_stack_enter("Shortcut");g_screen_back_fn=parent;int old=stops;nav_back_cb(NULL);assert(stops==old);drain();assert(nav_stack_depth==1&&!strcmp(nav_stack[0],"Parent"));nav_back_cb(NULL);drain();assert(nav_stack_depth==0);\nnav_stack_enter("Grand");nav_stack_enter("Parent");nav_stack_enter("Leaf");g_screen_back_fn=parent;nav_back_cb(NULL);drain();assert(nav_stack_depth==2);nav_back_cb(NULL);drain();assert(nav_stack_depth==1);nav_back_cb(NULL);drain();assert(!nav_stack_depth);\nnav_stack_enter("Parent");nav_stack_enter("Leaf");nav_back_cb(NULL);drain();assert(nav_stack_depth==1);nav_back_cb(NULL);drain();nav_back_cb(NULL);drain();assert(!nav_stack_depth);assert(!g_screen_back_fn&&!nav_deferred_show_fn);\n}assert(cancelled>0&&stops==cancelled);return 0;}\n'
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
            p=pathlib.Path(d)/'nav.c';p.write_text(code);subprocess.run(['cc','-fsanitize=address,undefined','-g',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
    def test_fsd_dispatch_precedes_existing_transition_gate(self):
        s=(R/'ESP32C5/main/main.c').read_text()
        self.assertLess(s.index('cym_fsd_poll();'),s.index('if (doom_ui_active() && (nav_to_menu_flag || nav_deferred_show_fn))'))

    def test_actual_home_stop_dispatch_both_layouts(self):
        source=(R/'ESP32C5/main/main.c').read_text();home=function(source,'show_menu')
        variables=sorted(set(re.findall(r'\b(\w+)\s*=\s*(?:NULL|false|0);',home,re.M)))
        code='#include <assert.h>\n#include <stdbool.h>\n#include <stddef.h>\n#define LV_OBJ_FLAG_HIDDEN 1\n'
        code+='static void *'+',*'.join(variables+['title_bar'])+';\nstatic int g_home_layout_4cat,stops,radio,deleted,classic,modern,released;static void(*g_screen_stop_fn)(void);\n'
        code+='#define cym_fsd_input_epoch() ((void)0)\n'
        code+=function(source,'run_screen_stop_fn')
        code+=r"""
static void stop(void){assert(!g_screen_stop_fn);assert(!radio&&!deleted);stops++;}
static void clock_cancel_radio_navigation(void){}
static void radio_reset_to_idle(void){assert(stops==1);radio++;}
static void wifi_attacks_set_evil_twin_event_cb(void*p){assert(!p);}
static void portal_disable_log_capture(void){}
static void stop_arp_ban(void){}
static void lv_timer_del(void*p){assert(p);assert(stops==1);}
static void reset_function_page_children(void){run_screen_stop_fn();assert(stops==1);}
static void lv_obj_del(void*p){assert(p);assert(stops==1&&radio==1);deleted++;}
static void sniffer_session_leave(void){assert(deleted==1);released++;}
static void show_category_home(void){assert(released==1);modern++;}
static void show_main_tiles(void){assert(released==1);classic++;}
static void lv_obj_clear_flag(void*p,int f){(void)p;(void)f;}
"""+home+r"""
int main(void){for(g_home_layout_4cat=0;g_home_layout_4cat<2;g_home_layout_4cat++){
 stops=radio=deleted=released=0;g_screen_stop_fn=stop;function_page=(void*)1;show_menu();
 assert(stops==1&&!function_page&&deleted==1&&released==1);
 assert(g_home_layout_4cat?modern==1:classic==1);
 }return 0;}
"""
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
            p=pathlib.Path(d)/'home.c';p.write_text(code);subprocess.run(['cc','-fsanitize=address,undefined','-g',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
if __name__=='__main__':unittest.main()
