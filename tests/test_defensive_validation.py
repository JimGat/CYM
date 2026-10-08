"""Native offline production-source replay and fail-closed regression contracts.
No RF stack: HAL calls are deterministic stubs; payload builder/classifier/churn
and installed NimBLE AD parser bodies are extracted verbatim each invocation.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'ESP32C5/main/main.c'
OUT=ROOT/'.hermes/defensive-validation'
NIMBLE=Path(os.environ.get('IDF_PATH','/home/dev/esp/esp-idf'))/'components/bt/host/nimble/nimble/nimble/host'

def function(s,name):
    m=re.search(r'^(?:static )?[A-Za-z_][\w *]*\s+\b'+name+r'\([^;]*?\)\s*\{',s,re.M)
    if not m: raise AssertionError('Missing function '+name)
    opening=s.index('{',m.start());depth=1;pos=opening+1
    while depth:
        depth+=(s[pos]=='{')-(s[pos]=='}');pos+=1
    return s[m.start():pos]

def native(source=None,tag='native',ext=1,mutation=None,startup=False):
    s=source or SRC.read_text();OUT.mkdir(parents=True,exist_ok=True)
    nim=(NIMBLE/'src/ble_hs_adv.c').read_text()
    hdr=(NIMBLE/'include/host/ble_hs_adv.h').read_text()
    hdr=hdr[hdr.index('#define BLE_HS_ADV_MAX_SZ'):hdr.index('int ble_hs_adv_set_fields_mbuf')]
    stubs=(ROOT/'tests/defensive_native_stubs.h').read_text()
    split=stubs.index('static struct ble_hs_adv_fields captured;')
    # Real parser functions; UUID conversion, clocks, locks and UI are HAL stubs.
    parser='\n'.join(function(nim,n) for n in ['ble_hs_adv_parse_uuids16','ble_hs_adv_parse_uuids32','ble_hs_adv_parse_uuids128','ble_hs_adv_parse_one_field','ble_hs_adv_parse_fields'])
    uuids='\n'.join(f'static ble_uuid{n}_t ble_hs_adv_uuids{n}[BLE_HS_ADV_MAX_FIELD_SZ / {n//8}];' for n in [16,32,128])
    tables=s[s.index('static const uint8_t s_apple_payloads'):s.index('// ── SAS proceed wrappers')]
    state=s[s.index('struct ble_spam_state_t {'):s.index('} g_ble_spam_state = {0};')+len('} g_ble_spam_state = {0};')]
    det=s[s.index('enum { BSF_NONE'):s.index('static uint8_t bspam_classify')]
    wp=function((ROOT/'ESP32C5/main/ble_whisperpair.c').read_text(),'wp_is_fast_pair_adv')
    tx='\n'.join(function(s,n) for n in ['ble_spam_abort','ble_spam_timer_cb','ble_spam_start_btn_cb'] if n!='ble_spam_abort' or 'static void ble_spam_abort' in s)
    rx='\n'.join(function(s,n) for n in ['bspam_classify','bspam_gap_cb','bspam_ui_timer_cb'])
    if mutation=='nearby':rx=rx.replace('fields->mfg_data_len == 15','fields->mfg_data_len == 14')
    if mutation=='threshold':det=det.replace('#define BSPAM_CHURN_MIN   14','#define BSPAM_CHURN_MIN   15') # expectations separately anchored below
    if mutation=='count':tx=tx.replace('ble_spam_count++;','ble_spam_count += 2;')
    cases=(ROOT/'tests/defensive_native_cases.c').read_text()
    if mutation=='threshold':cases=cases.replace('BSPAM_CHURN_MIN','14')
    if not ext:cases='''int main(void){ble_spam_start_btn_cb(NULL);assert(!ble_spam_active);assert(!g_ble_spam_state.timer);assert(ble_spam_count==0);assert(strstr(status_obj.text,"unavailable"));puts("OFFLINE unsupported transport: PASS; no RF backend");return 0;}'''
    if startup:
        rx+='\n'+(ROOT/'tests/defensive_startup_stubs.h').read_text()+'\n'+function(s,'blespam_detector_stop')+'\n'+function(s,'show_blespam_detector_screen')
        cases=r'''static void reset_startup(void){if(g_screen_stop_fn)g_screen_stop_fn();g_screen_stop_fn=NULL;s_bspam_callbacks=0;alloc_calls=fail_alloc_at=scan_rc=0;fail_init=fail_timer=false;current_radio_mode=RADIO_MODE_BLE;}
static void unavailable(void){bool found=false;for(int i=0;i<object_n;i++){assert(!strstr(objects[i].text,"No BLE spam"));if(strstr(objects[i].text,"Detection unavailable"))found=true;}assert(found);assert(!s_bspam_active);assert(!s_bspam_ui_timer);}
int main(void){
for(int n=1;n<=2;n++){reset_startup();fail_alloc_at=n;show_blespam_detector_screen();unavailable();assert(!s_bspam);assert(!s_bspam_snap);}
reset_startup();fail_init=true;show_blespam_detector_screen();unavailable();
reset_startup();fail_timer=true;show_blespam_detector_screen();unavailable();
reset_startup();scan_rc=7;show_blespam_detector_screen();unavailable();assert(!s_bspam);assert(!s_bspam_snap);
reset_startup();show_blespam_detector_screen();assert(s_bspam_active);assert(s_bspam_ui_timer);assert(strstr(s_bspam_alert->text,"Learning"));blespam_detector_stop();assert(!s_bspam);assert(!s_bspam_snap);assert(!s_bspam_status);assert(!s_bspam_alert);assert(!s_bspam_ui_timer);
reset_startup();s_bspam=calloc(BSPAM_TBL,sizeof(*s_bspam));s_bspam_snap=calloc(BSPAM_TBL,sizeof(*s_bspam_snap));bspam_adv_t *held=s_bspam;s_bspam_callbacks=1;show_blespam_detector_screen();unavailable();assert(s_bspam==held);s_bspam_callbacks=0;blespam_detector_stop();assert(!s_bspam);
puts("OFFLINE detector startup: allocation/init/scan/timer failures, busy callbacks, teardown PASS; no RF backend");return 0;}'''
    serializer='\n'.join(function(nim,n) for n in ['ble_hs_adv_set_hdr','ble_hs_adv_set_flat_mbuf','ble_hs_adv_set_array_uuid16','ble_hs_adv_set_array_uuid32','ble_hs_adv_set_array_uuid128','ble_hs_adv_set_array16','adv_set_fields','ble_hs_adv_set_fields'])
    c='\n'.join([stubs[:split],hdr,'static int adv_set_fields(const struct ble_hs_adv_fields *,uint8_t *,uint8_t *,uint8_t,struct os_mbuf *);',stubs[split:],serializer,uuids,parser,tables,state,tx,det,wp,rx,cases])
    cpath=OUT/(tag+'.c');cpath.write_text(c)
    exe=OUT/tag
    compile_cmd=['cc','-std=c11','-g','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',f'-DCFG_BLE_EXT_ADV={ext}',str(cpath),'-o',str(exe)]
    result=subprocess.run(compile_cmd,text=True,capture_output=True)
    (OUT/(tag+'-compile.log')).write_text(result.stdout+result.stderr)
    if result.returncode:raise AssertionError(result.stderr)
    result=subprocess.run([str(exe)],cwd=OUT,text=True,capture_output=True)
    (OUT/(tag+'.log')).write_text(result.stdout+result.stderr)
    return result

class DefensiveValidation(unittest.TestCase):
    def test_native_production_replay(self):
        r=native();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_unsupported_transport(self):
        r=native(tag='unsupported',ext=0);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_mutations_rejected(self):
        for mutation in ['nearby','count','threshold']:
            r=native(tag='mutation-'+mutation,mutation=mutation);self.assertNotEqual(r.returncode,0,mutation+' survived')
    def test_detector_startup_executable(self):
        r=native(tag='startup',startup=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_detector_startup_unavailable(self):
        s=SRC.read_text();body=function(s,'show_blespam_detector_screen')
        self.assertIn('Detection unavailable',body)
        self.assertIn('if (!s_bspam_ui_timer)',body)
        self.assertIn('s_bspam_callbacks, __ATOMIC_ACQUIRE) != 0',body)
        self.assertNotIn('No BLE spam',body)
        self.assertIn('blespam_detector_stop();',body)
        self.assertLess(body.index('if (!s_bspam_ui_timer)'),body.index('if (bspam_start_scan()'))
    def test_truthful_ui_and_lifetime(self):
        s=SRC.read_text();tx=function(s,'ble_spam_stop')
        self.assertIn('ble_spam_needs_ui_update = false',tx)
        self.assertIn('ble_spam_status_label = NULL',tx)
        self.assertNotIn('Packets: %d", ble_spam_count',s)
        self.assertNotIn('packet %d sent", ble_spam_count',s)
        ui=function(s,'bspam_ui_timer_cb')
        self.assertNotIn('tap to locate',ui)
        self.assertNotIn('No BLE spam',ui)
        self.assertIn('Learning',ui)
    def test_passive_scan_unchanged(self):
        s=SRC.read_text();scan=function(s,'bspam_start_scan')
        self.assertEqual(scan.count('.passive = 1'),3)
        self.assertNotIn('ble_gap_connect',function(s,'bspam_gap_cb'))

if __name__=='__main__': unittest.main(verbosity=2)
