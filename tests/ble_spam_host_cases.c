
static unsigned random_value;
static unsigned esp_random(void){return random_value;}
static void windows(unsigned value){
 enum {BLE_SPAM_MODE_AIRTAG=1};int cur_mode=0;
 /* PRODUCTION_FIELDS */
 uint8_t win_mfg[32],win_name[12];random_value=value;
 /* PRODUCTION_WINDOWS */
 struct os_mbuf m={0};
 CHECK(serialize(&fields,&m)==0);
 /* Inspect actual AD bytes, independent literal wire types and company prefix. */
 CHECK(m.len<=31);
 int n=5+(value%5);
 CHECK(fields.name_len==n && m.len==(unsigned)(12+2*n));
 CHECK(m.data[0]==2 && m.data[1]==1 && m.data[2]==6);
 CHECK(m.data[3]==n+1 && m.data[4]==9);
 for(int i=0;i<n;i++) CHECK(m.data[5+i]=='A'+value%26);
 int off=5+n;uint8_t prefix[]={6,0,3,0,0x80};
 CHECK(m.data[off]==n+6 && m.data[off+1]==0xff);
 CHECK(!memcmp(m.data+off+2,prefix,sizeof(prefix)));
 CHECK(!memcmp(m.data+off+7,m.data+5,n));
 int before=free_calls;
 CHECK(ble_gap_ext_adv_set_data(0,&m)==0 && m.freed && free_calls==before+1);
}
static int address(const uint8_t*k){
 /* PRODUCTION_ADDRESS */
 return ble_gap_ext_adv_set_addr(0,&at_addr);
}
static void data_case(unsigned length,int instance,int want){
 struct os_mbuf m={.len=length};int before=free_calls;
 CHECK(ble_gap_ext_adv_set_data(instance,&m)==want);
 CHECK(m.freed && free_calls==before+1);
}

/* Production caller serialization/set_data tail. No actual allocator/controller. */
#define ESP_LOGW(...) ((void)0)
#define CYM_DEBUG_LOGD(...) ((void)0)
#define BLE_SPAM_ADV_INSTANCE 0
static struct os_mbuf caller_mbuf;
static int alloc_fail,aborts,reached_start;
static struct os_mbuf *os_msys_get_pkthdr(unsigned n,int reserve){(void)n;(void)reserve;if(alloc_fail)return NULL;caller_mbuf=(struct os_mbuf){0};return &caller_mbuf;}
static int ble_hs_adv_set_fields_mbuf(const struct ble_hs_adv_fields*f,struct os_mbuf*m){return serialize(f,m);}
static void ble_spam_abort(const char*why){(void)why;aborts++;}
static void production_caller(unsigned length){
 uint8_t bytes[40]={0};struct ble_hs_adv_fields fields={.mfg_data=bytes,.mfg_data_len=length};
 /* PRODUCTION_CALLER */
 reached_start++;
}
static void caller_case(unsigned length,int error,int want_free){
 int before=free_calls,prior_aborts=aborts,prior_start=reached_start;
 production_caller(length);
 CHECK(free_calls==before+want_free);
 CHECK(aborts==prior_aborts+(error!=0));
 CHECK(reached_start==prior_start+(error==0));
}
int main(void){
 ble_gap_slave[0].configured=true;ble_gap_slave[0].legacy_pdu=true;
 for(unsigned i=0;i<30;i++)windows(i);
 data_case(31,0,0); data_case(32,0,BLE_HS_EINVAL);
 hci_rc=17;data_case(30,0,17);hci_rc=0;
 enabled=0;data_case(30,0,BLE_HS_EDISABLED);enabled=1;
 data_case(30,99,BLE_HS_EINVAL);
 ble_gap_slave[0].configured=false;data_case(30,0,BLE_HS_EINVAL);ble_gap_slave[0].configured=true;
 ble_gap_slave[0].directed=true;data_case(30,0,BLE_HS_EINVAL);ble_gap_slave[0].directed=false;
 uint8_t k[6]={1,2,3,4,5,6},expected[6]={6,5,4,3,2,0xc1};
 CHECK(address(k)==0);CHECK(addr_calls==1 && !memcmp(last_addr,expected,6));
 ble_addr_t invalid={.type=0,.val={1,2,3,4,5,0xc1}};
 CHECK(ble_gap_ext_adv_set_addr(0,&invalid)==BLE_HS_EINVAL && addr_calls==1);
 CHECK(ble_gap_ext_adv_set_addr(0,NULL)==BLE_HS_EINVAL);
 invalid.type=BLE_ADDR_RANDOM;CHECK(ble_gap_ext_adv_set_addr(BLE_ADV_INSTANCES,&invalid)==BLE_HS_EINVAL);
 hci_rc=19;CHECK(address(k)==19 && addr_calls==2);hci_rc=0;
 uint8_t zeros[6]={0},ones[6]={255,255,255,255,255,255};
 CHECK(address(zeros)==BLE_HS_EINVAL && addr_calls==2);
 CHECK(address(ones)==BLE_HS_EINVAL && addr_calls==2);
 enabled=0;CHECK(address(k)==BLE_HS_EDISABLED && addr_calls==2);enabled=1;
 struct ble_hs_adv_fields f={.flags=6};struct os_mbuf m={0};append_fail=1;
 CHECK(serialize(&f,&m)==12);CHECK(!m.freed);append_fail=0;
 os_mbuf_free_chain(&m);CHECK(m.freed);
 caller_case(2,0,1);
 alloc_fail=1;caller_case(2,1,0);alloc_fail=0;
 append_fail=1;caller_case(2,1,1);append_fail=0;
 caller_case(30,1,1); /* Manufacturer AD adds two bytes: exceeds legacy max. */
 enabled=0;caller_case(2,1,1);enabled=1;
 hci_rc=17;caller_case(2,1,1);hci_rc=0;
 printf("RESULT checks=%d failures=0\n",checks);return 0;
}
