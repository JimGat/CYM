"""Production C metadata/legacy/export host regression, no RF or IDF build.
Private captures are optional, external, never copied into this checkout.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "ESP32C5/main"


def chr_(uuid="0x2a00", raw=b"Example", ok=True, props=2):
    return dict(uuid=uuid, read_data=raw.hex() if ok else None,
                read_ok=ok, properties=props)


def sample(name="Advertising", chars=None, service="0x1800"):
    return dict(name=name, services=[dict(uuid=service,
                characteristics=chars if chars is not None else [chr_()])])


class GattMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gatt23-host-")
        t = Path(cls.tmp.name)
        (t / "freertos").mkdir()
        (t / "freertos/FreeRTOS.h").write_text("#pragma once\n#include <stddef.h>\n")
        (t / "freertos/semphr.h").write_text("#pragma once\ntypedef void *SemaphoreHandle_t;\n")
        (t / "psa").mkdir()
        # Real OpenSSL host SHA, plus injected PSA failure paths. Not target linkage proof.
        (t / "psa/crypto.h").write_text(r"""
#pragma once
#include <stddef.h>
#include <openssl/evp.h>
typedef int psa_status_t;
typedef struct {EVP_MD_CTX *p;} psa_hash_operation_t;
#define PSA_HASH_OPERATION_INIT {NULL}
#define PSA_SUCCESS 0
#define PSA_ALG_SHA_256 1
static int psa_test_fail,psa_test_live;
static psa_status_t psa_crypto_init(void){return psa_test_fail==1?-1:0;}
static psa_status_t psa_hash_setup(psa_hash_operation_t *c,int alg){
 if(psa_test_fail==2||alg!=PSA_ALG_SHA_256)return -1;
 c->p=EVP_MD_CTX_new();if(!c->p)return -1;psa_test_live++;
 return EVP_DigestInit_ex(c->p,EVP_sha256(),NULL)==1?0:-1;
}
static psa_status_t psa_hash_update(psa_hash_operation_t *c,const unsigned char *p,size_t n){
 return psa_test_fail==3||!c->p||EVP_DigestUpdate(c->p,p,n)!=1?-1:0;
}
static psa_status_t psa_hash_finish(psa_hash_operation_t *c,unsigned char *p,size_t cap,size_t *len){
 if(psa_test_fail==4||!c->p||cap<32)return -1;
 unsigned n=0;if(EVP_DigestFinal_ex(c->p,p,&n)!=1)return -1;
 *len=psa_test_fail==5?31:n;return 0;
}
static psa_status_t psa_hash_abort(psa_hash_operation_t *c){
 if(c->p){EVP_MD_CTX_free(c->p);c->p=NULL;psa_test_live--;}return 0;
}
""")
        source = (MAIN / "gatt_walker.c").read_text()
        # Extract verbatim production legacy, adapter, UUID table, JSON builder,
        # and full export body. This intentionally tests real C, not a clone.
        code = source[source.index("#define FNV_OFFSET"):source.index("/* ── Forward declarations")]
        original=subprocess.check_output(["git","show","4c699a66acaac50731529aea773a411eb8b4b68c:ESP32C5/main/gatt_walker.c"],cwd=ROOT).decode()
        old_json=original[original.index("typedef struct { char *buf;"):original.index("/* ── Forward declarations")]
        old_json=old_json.replace("jb_","old_jb_").replace("jb_t","old_jb_t").replace("s_write_json", "s_write_json_legacy")
        callback=source[source.index("static int s_read_cb"):source.index("static void s_read_next(void)\n{",source.index("static int s_read_cb"))]
        pre = r"""
#include "gatt_walker.h"
#include "gatt_metadata.h"
#include "psa/crypto.h"
#include <stdio.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
static gw_result_t result,*s_result=&result;
static void *s_sd_mutex=(void *)1;
#define MALLOC_CAP_SPIRAM 0
#define heap_caps_malloc(n,c) malloc(n)
#define pdMS_TO_TICKS(n) (n)
#define pdTRUE 1
#define xSemaphoreTake(m,t) 1
#define xSemaphoreGive(m) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define mkdir(p,m) 0
#define fopen(p,m) stdout
#define fclose(f) 0
static int oui_lookup_is_loaded(void){return 0;}
static const char *oui_lookup(const uint8_t p[3]){(void)p;return NULL;}
static int s_cur_svc=0,s_cur_chr=0,advances=0;static bool s_cancel_req=false;
struct ble_gatt_error {int status;};
struct os_mbuf {uint16_t len;uint8_t *data;};
struct ble_gatt_attr {struct os_mbuf *om;};
#define OS_MBUF_PKTLEN(m) ((m)->len)
#define BLE_HS_EDONE 14
static void s_fail(const char *m){(void)m;}
static void s_read_next(void){++advances;}
static int os_mbuf_copydata(struct os_mbuf *m,int off,int n,void *dest){memcpy(dest,m->data+off,n);return 0;}
char *gw_chr_props_str(uint8_t p,char *b,size_t n){snprintf(b,n,"%u",p);return b;}
"""
        post = r"""
static void take(void *p,size_t n){if(fread(p,1,n,stdin)!=n) exit(2);}
static unsigned u16(void){uint8_t p[2];take(p,2);return (unsigned)p[0]*256+p[1];}
static uint8_t canonical[2048];static size_t used;
static int capture(void *ctx,const uint8_t *p,size_t n){(void)ctx;if(n>sizeof(canonical)-used)return -1;memcpy(canonical+used,p,n);used+=n;return 0;}
static int fail_sink(void *c,const uint8_t *p,size_t n){(void)c;(void)p;(void)n;return -1;}
int main(int argc,char **argv){
    if(argc==2 && !strcmp(argv[1],"read")){
        gw_chr_t *c=&result.svcs[0].chrs[0];
        uint8_t raw[300];memset(raw,'X',sizeof(raw));
        struct os_mbuf mb={300,raw};struct ble_gatt_attr a={&mb};
        struct ble_gatt_error ok={0},done={BLE_HS_EDONE},err={7};
        s_read_cb(0,&ok,&a,NULL);if(!c->read_ok || c->read_len!=300 || advances)return 7;
        mb.len=11;s_read_cb(0,&ok,&a,NULL);
        s_read_cb(0,&done,NULL,NULL);if(c->read_len!=311 || advances!=1 || gm_observe(c).state!=GM_OBSERVED)return 7;
        memset(c,0,sizeof(*c));s_cur_chr=0;advances=0;mb.len=300;
        s_read_cb(0,&ok,&a,NULL);s_read_cb(0,&err,NULL,NULL);
        if(c->read_len!=300 || !c->read_ok || advances!=1 || gm_observe(c).state!=GM_OBSERVED)return 7;
        memset(c,0,sizeof(*c));s_cur_chr=0;advances=0;
        s_read_cb(0,&ok,&a,NULL);s_read_cb(0,&ok,&a,NULL);s_read_cb(0,&done,NULL,NULL);
        if(c->read_len!=512 || advances!=1 || gm_observe(c).state!=GM_CAP_UNCERTAIN)return 7;
        memset(c,0,sizeof(*c));s_cur_chr=0;advances=0;s_read_cb(0,&err,NULL,NULL);
        if(c->read_ok || gm_observe(c).state!=GM_UNREADABLE || advances!=1)return 7;
        puts("production read callback: chunked/done/error/cap/unreadable PASS; completion remains unknown");return 0;
    }
    if(argc==2 && !strcmp(argv[1],"sha")){
        psa_hash_operation_t c=PSA_HASH_OPERATION_INIT;uint8_t d[32];size_t n=0;
        if(psa_crypto_init()!=PSA_SUCCESS || psa_hash_setup(&c,PSA_ALG_SHA_256)!=PSA_SUCCESS ||
           s_metadata_sha_sink(&c,(const uint8_t *)"abc",3) ||
           psa_hash_finish(&c,d,sizeof(d),&n)!=PSA_SUCCESS || n!=32)return 3;
        psa_hash_abort(&c);for(int i=0;i<32;++i)printf("%02x",d[i]);puts("");return 0;
    }
    if(argc==2 && !strcmp(argv[1],"faults")){
        strcpy(result.name,"Synthetic");result.fingerprint=0x7A62B0DC;
        for(int fail=0;fail<=5;++fail){
            psa_test_fail=fail;s_compute_metadata(&result);
            if(psa_test_live || result.metadata_available!=(fail==0))return 8;
            if(fail && (result.metadata_fingerprint[0] || !result.metadata_fields))return 8;
        }
        puts("PSA init/setup/update/finish/length failure cleanup PASS");return 0;
    }
    unsigned n=u16();if(n>31)return 2;take(result.name,n);
    take(result.mac,6);take(&result.rssi,1);take(result.timestamp,19);
    result.svc_count=(int)u16();if(result.svc_count>GW_MAX_SVCS)return 2;
    for(int si=0;si<result.svc_count;++si){
        gw_svc_t *s=&result.svcs[si];take(s->uuid_str,36);s->chr_count=(int)u16();
        if(s->chr_count>GW_MAX_CHRS)return 2;
        for(int ci=0;ci<s->chr_count;++ci){gw_chr_t *c=&s->chrs[ci];take(c->uuid_str,36);take(&c->properties,1);uint8_t ok;take(&ok,1);c->read_ok=ok!=0;c->read_len=(uint16_t)u16();take(c->read_data,GW_READ_MAX);}
    }
    result.fingerprint=s_compute_fingerprint();
    gm_selection_t sel=gm_select(&result);
    int rc=gm_canonical(&sel,result.fingerprint,capture,NULL);
    if(sel.mask && (rc || gm_canonical(&sel,result.fingerprint,fail_sink,NULL)!=-1))return 4;
    if(!sel.mask && rc!=1)return 4;
    /* Public ABI rejects oversized fields/null data without an out-of-bounds read. */
    gm_selection_t bad=sel;bad.mask=1;bad.fields[0].len=513;
    if(gm_canonical(&bad,result.fingerprint,fail_sink,NULL)!=-1)return 4;
    /* Clamp invalid discovery counts safely in selection (not legacy hash). */
    int saved=result.svc_count; result.svc_count=-1;(void)gm_select(&result);
    result.svc_count=GW_MAX_SVCS+1;(void)gm_select(&result);result.svc_count=saved;
    gw_chr_t malformed={0};malformed.read_ok=true;malformed.read_len=65535;
    memset(malformed.read_data,'Q',GW_READ_MAX);
    gm_field_t bounded=gm_observe(&malformed);
    if(bounded.len!=512 || bounded.state!=GM_CAP_UNCERTAIN)return 6;
    malformed.read_ok=false;if(gm_observe(&malformed).len!=0)return 6;
    /* Max non-NUL UUID string must not over-read. */
    char uuid_boundary[37];memset(uuid_boundary,'X',sizeof(uuid_boundary));
    if(gm_uuid_is(uuid_boundary,0x1800))return 6;
    bad=sel;bad.mask=1;bad.fields[0].data=NULL;bad.fields[0].len=1;
    if(gm_canonical(&bad,result.fingerprint,capture,NULL)!=-1)return 6;
    /* Discard any prefix emitted during rejected ABI inputs. */
    used=0;if(gm_canonical(&sel,result.fingerprint,capture,NULL)!=rc)return 6;
    for(size_t i=0;i<used;++i)printf("%02x",canonical[i]);puts("");
    if(argc==2 && !strcmp(argv[1],"legacy")) { if(!s_write_json_legacy())return 5; }
    else if(!s_write_json())return 5;
    return 0;
}
"""
        c = t / "host.c"; c.write_text(pre + code + old_json + callback + post)
        cls.exe = t / "host"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-function", "-Wno-unused-value", "-Wno-misleading-indentation", "-Wno-unused-parameter",
                        "-g", "-O1", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
                        "-fsanitize=address,undefined", "-I"+str(t), "-I"+str(MAIN),
                        str(c), "-lcrypto", "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_c(self, d, legacy=False):
        def uuid(s):
            b=s.encode("ascii"); assert len(b)<=36
            return b.ljust(36,b"\0")
        name=d.get("name", "").encode()[:31]
        payload=struct.pack(">H",len(name))+name
        payload+=bytes.fromhex(d.get("mac", "00:00:00:00:00:00").replace(":", ""))
        payload+=struct.pack("b", d.get("rssi",0))
        payload+=d.get("timestamp", "").encode()[:19].ljust(19,b"\0")
        payload+=struct.pack(">H", len(d["services"]))
        for s in d["services"]:
            payload+=uuid(s["uuid"])+struct.pack(">H",len(s["characteristics"]))
            for c in s["characteristics"]:
                raw=bytes.fromhex(c["read_data"]) if c.get("read_data") else b""
                payload+=uuid(c["uuid"])+bytes([c["properties"],c.get("read_ok",c.get("read_data") is not None)])
                payload+=struct.pack(">H",c.get("read_len",len(raw)))+raw[:512].ljust(512,b"\0")
        proc=subprocess.run([str(self.exe)]+(["legacy"] if legacy else []),input=payload,capture_output=True,
                            env={**os.environ,"ASAN_OPTIONS":"detect_leaks=1:halt_on_error=1","UBSAN_OPTIONS":"halt_on_error=1"})
        # Never print payload/stdout on private failure. Sanitizer diagnostics
        # contain code locations, not names/MAC/GPS/fixture contents.
        self.assertEqual(proc.returncode,0,proc.stderr.decode(errors="replace"))
        canon,output=proc.stdout.split(b"\n",1)
        result=json.loads(output)
        if legacy: return result,bytes.fromhex(canon.decode())
        if result["metadata"]["available"]:
            self.assertEqual(result["metadata_fingerprint"],hashlib.sha256(bytes.fromhex(canon.decode())).hexdigest())
            self.assertEqual(len(result["metadata_fingerprint"]),64)
        else:
            self.assertIsNone(result["metadata_fingerprint"])
            self.assertEqual(canon,b"")
        return result,bytes.fromhex(canon.decode())

    def digest(self,d):
        return self.run_c(d)[0]["metadata_fingerprint"]

    def test_sdk_public_sha_api(self):
        src=(MAIN/'gatt_walker.c').read_text()
        self.assertIn('#include "psa/crypto.h"',src)
        self.assertNotIn('mbedtls/sha256.h',src)
        self.assertIn('psa_hash_abort(&ctx)',src)

    def test_psa_error_cleanup(self):
        p=subprocess.run([str(self.exe),'faults'],capture_output=True,check=True)
        self.assertIn(b'cleanup PASS',p.stdout)

    def test_sha_known_vector(self):
        p=subprocess.run([str(self.exe),"sha"],capture_output=True,check=True)
        self.assertEqual(p.stdout.strip().decode(),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_canonical_abi_and_legacy(self):
        out,canon=self.run_c(sample())
        domain=b"cym-gatt-metadata-v1"
        self.assertEqual(canon[:3+len(domain)],b"\0"+struct.pack(">H",len(domain))+domain)
        self.assertEqual(canon[3+len(domain):10+len(domain)],b"\1\0\4"+int(out["fingerprint"],16).to_bytes(4,"big"))
        self.assertTrue(canon.endswith(b"\3\0\3\0\0\0\4\0\3\0\0\0"))
        self.assertIn(b"Example",canon)
        self.assertEqual(out["version"],1)
        self.assertEqual(out["metadata"]["name_source"],"gatt")
        self.assertEqual(out["metadata"]["fields"],["device_name"])
        self.assertEqual(out["metadata_algorithm"],domain.decode())
        self.assertEqual(self.run_c(sample(chars=[chr_(raw=b"Other")]))[0]["fingerprint"],out["fingerprint"])

    def test_excluded_metadata_mutations(self):
        d=sample(); original=self.digest(d)
        d.update(mac="aa:bb:cc:dd:ee:ff",rssi=-92,timestamp="20261011_010203",
                 gps={"valid":True,"lat":12,"lon":23},manufacturer="Convenience vendor")
        d["services"][0]["characteristics"][0]["name"]="Display label ignored"
        self.assertEqual(self.digest(d),original)
        d["name"]="Another advertisement"
        self.assertEqual(self.digest(d),original)

    def test_relevant_fields_and_correct_service(self):
        d=sample(); orig=self.digest(d)
        d["services"][0]["characteristics"][0]["read_data"]=b"Different".hex()
        self.assertNotEqual(self.digest(d),orig)
        d["services"].append(dict(uuid="0x180a",characteristics=[chr_("0x2a29",b"Maker"),chr_("0x2a24",b"Model")]))
        base=self.digest(d)
        for i in range(2):
            altered=copy.deepcopy(d); altered["services"][1]["characteristics"][i]["read_data"]=b"Changed".hex()
            self.assertNotEqual(self.digest(altered),base)
        out,_=self.run_c(d)
        self.assertEqual(out["metadata"]["fields"],["device_name","manufacturer_name","model_number"])
        wrong=sample(name="", chars=[chr_("0x2a29",b"Maker"),chr_("0x2a24",b"Model")])
        self.assertIsNone(self.digest(wrong))

    def test_absent_unreadable_empty_fallback(self):
        states=[]; hashes=[]
        for chars in ([],[chr_(ok=False)],[chr_(raw=b"\0\0")]):
            out,_=self.run_c(sample(chars=chars))
            self.assertEqual(out["metadata"]["name_source"],"advertised")
            states.append(out["metadata"]["name_gatt_state"])
            hashes.append(out["metadata_fingerprint"])
        self.assertEqual(states,["absent","unreadable","empty"])
        self.assertEqual(len(set(hashes)),3)
        for chars in ([],[chr_(ok=False)],[chr_(raw=b"")],[chr_(raw=b"\0")]):
            out,_=self.run_c(sample(name="",chars=chars))
            self.assertFalse(out["metadata"]["available"])
            self.assertEqual(out["metadata"]["name_source"],"none")

    def test_duplicates_order_and_uuid_forms(self):
        chars=[chr_(raw=b"Zulu"),chr_(raw=b"Alpha"),chr_(ok=False),chr_(raw=b"")]
        a=self.run_c(sample(chars=chars))
        b=self.run_c(sample(chars=list(reversed(chars))))
        self.assertEqual(a[0]["metadata_fingerprint"],b[0]["metadata_fingerprint"])
        self.assertIn(b"Alpha",a[1]); self.assertNotIn(b"Zulu",a[1])
        # UUID representations affect legacy layout by design. Compare selected
        # metadata bodies, not enriched digest which embeds the original layout.
        d=sample(service="00001800-0000-1000-8000-00805F9B34FB",
                 chars=[chr_("00002A00-0000-1000-8000-00805F9B34FB",b"Example")])
        offset=3+len(b"cym-gatt-metadata-v1")+7
        self.assertEqual(self.run_c(d)[1][offset:],self.run_c(sample())[1][offset:])
        dis_short=sample(name="", service="0x180a", chars=[chr_("0x2a29",b"Maker"),chr_("0x2a24",b"Model")])
        dis_long=sample(name="", service="0000180A-0000-1000-8000-00805F9B34FB", chars=[chr_("00002A29-0000-1000-8000-00805F9B34FB",b"Maker"),chr_("00002A24-0000-1000-8000-00805F9B34FB",b"Model")])
        self.assertEqual(self.run_c(dis_short)[1][offset:],self.run_c(dis_long)[1][offset:])
        repeated=sample(chars=[chr_(raw=b"Zulu")])
        repeated["services"].append(dict(uuid="0x1800",characteristics=[chr_(raw=b"Alpha")]))
        original=self.digest(repeated)
        repeated["services"].reverse()
        self.assertEqual(self.digest(repeated),original)
        for svc,u in (("00001800-0004-1000-8000-00805f9b34fb","0x2a00"),
                      ("0x1800extra","0x2a00"),("0x1800","0x2a00extra")):
            self.assertIsNone(self.digest(sample(name="",service=svc,chars=[chr_(u)])))

    def test_lengths_normalization_utf8_escape(self):
        name=b'A"\\\x01\x00'+"é".encode()
        out,canon=self.run_c(sample(name='Ad"\\\n',chars=[chr_(raw=name)]))
        self.assertIn(name,canon)
        self.assertEqual(out["name"],'Ad"\\\n')
        self.assertEqual(out["services"][0]["characteristics"][0]["ascii"],'A"\\..'+'..')
        self.assertEqual(self.digest(sample(chars=[chr_(raw=name)])),self.digest(sample(chars=[chr_(raw=name+b"\0\0")])))
        for raw in (b"Example ",b"example",b"Example\x00X"):
            self.assertNotEqual(self.digest(sample(chars=[chr_(raw=raw)])),self.digest(sample()))
        advertised="café"
        out,canon=self.run_c(sample(name=advertised,chars=[]))
        self.assertEqual(out["name"],advertised)
        self.assertIn(advertised.encode(),canon)
        self.assertEqual(out["metadata"]["name_source"],"advertised")
        for n in (1,31,32,511,512):
            out,canon=self.run_c(sample(chars=[chr_(raw=b"X"*n)]))
            self.assertIn(b"X"*n,canon)
            self.assertEqual(out["metadata"]["device_name"],"cap_truncation_unknown" if n==512 else "observed_completion_unknown")
        # Malformed count is clamped by production selection. Avoid legacy export
        # overflow since existing JSON code expects valid <=512 read_len.

    def test_chunk_error_uncertainty(self):
        p=subprocess.run([str(self.exe),"read"],capture_output=True,check=True)
        self.assertIn(b"PASS",p.stdout)
        # Existing read_ok carries bytes after one chunk, successful multi-chunk
        # reads and later errors alike. Never fabricate completion information.
        d=sample(chars=[chr_(raw=b"first-second")])
        out,_=self.run_c(d)
        self.assertEqual(out["metadata"]["completeness"],"observed_bytes_only_read_completion_not_proven")
        self.assertEqual(out["metadata"]["device_name"],"observed_completion_unknown")
        self.assertNotEqual(self.digest(d),self.digest(sample(chars=[chr_(raw=b"first")])))

    def test_production_scope_contract(self):
        src=(MAIN/"gatt_walker.c").read_text()
        base=subprocess.check_output(["git","show","4c699a66acaac50731529aea773a411eb8b4b68c:ESP32C5/main/gatt_walker.c"],cwd=ROOT).decode()
        def section(text,start,end):return text[text.index(start):text.index(end,text.index(start))]
        self.assertEqual(section(src,"static uint32_t s_compute_fingerprint", "\n}\n"),section(base,"static uint32_t s_compute_fingerprint","\n}\n"))
        self.assertEqual(section(src,"static int s_read_cb", "static void s_read_next"),section(base,"static int s_read_cb","static void s_read_next"))
        self.assertIn('char     filepath[80]',(MAIN/"gatt_walker.h").read_text())
        self.assertEqual(section(src,'    snprintf(s_result->filepath','    s_set_state(GW_STATE_SAVING)'),section(base,'    snprintf(s_result->filepath','    s_set_state(GW_STATE_SAVING)'))
        self.assertIn('    s_write_json();           /* re-save with probe data */',src)

    @unittest.skipUnless(os.environ.get("CYM_GATT23_FIXTURES"),"external private captures not configured")
    def test_actual_private_nine(self):
        folder=Path(os.environ["CYM_GATT23_FIXTURES"])
        outputs=[]; names=[]
        for i in range(1,10):
            d=json.loads((folder/f"{i}.json").read_text())
            out,_=self.run_c(d)
            legacy,_=self.run_c(d,legacy=True)
            # Compare all pre-existing export fields; never include private
            # content in a failed assertion diagnostic.
            self.assertTrue(all(out[k]==v for k,v in legacy.items()))
            # Assertions avoid including private values in failure messages.
            self.assertTrue(out["fingerprint"]=="0x7A62B0DC")
            self.assertTrue(out["metadata"]["name_source"]=="gatt")
            outputs.append(out["metadata_fingerprint"])
            names.extend(bytes.fromhex(c["read_data"]) for s in d["services"] for c in s["characteristics"] if c["uuid"].lower()=="0x2a00" and c.get("read_data"))
        self.assertEqual(len(outputs),9)
        self.assertEqual(len(set(outputs)),9)
        self.assertEqual(len(set(names)),9)
        print("Private regression: 9 captures, 9 unchanged legacy values, 9 distinct metadata SHA256, 9 GATT name sources (values withheld).")
