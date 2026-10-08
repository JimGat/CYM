static int checks=0,failures=0;
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);failures++;}}while(0)
static void reset_tx(void){memset(&g_ble_spam_state,0,sizeof(g_ble_spam_state));ble_spam_active=false;ble_spam_count=0;fail_timer=fail_init=fail_alloc=false;fail_config=fail_stop=fail_addr=fail_gen=fail_set=fail_data=fail_start=0;fail_addr_at=addr_calls=start_calls=stop_calls=0;status_obj.text[0]=button_obj.text[0]=0;}
static void begin_tx(void){ble_spam_start_btn_cb(NULL);}
static void failure_case(int *failure){reset_tx();*failure=7;begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(!ble_spam_active);CHECK(g_ble_spam_state.timer==NULL);CHECK(ble_spam_count==0);CHECK(strcmp(button_obj.text,"STOP")!=0);CHECK(strstr(status_obj.text,"failed")!=NULL);}
static uint8_t raw[96];static int rawlen;
/* This wrapper is test-only AD framing, not the NimBLE serializer. */
static void ad(uint8_t t,const uint8_t *p,int n){raw[rawlen++]=n+1;raw[rawlen++]=t;memcpy(raw+rawlen,p,n);rawlen+=n;}
static void wrap_fields(void){rawlen=0;if(captured.flags)ad(1,&captured.flags,1);if(captured.name)ad(9,captured.name,captured.name_len);if(captured.svc_data_uuid16)ad(0x16,captured.svc_data_uuid16,captured.svc_data_uuid16_len);if(captured.mfg_data)ad(0xff,captured.mfg_data,captured.mfg_data_len);}
static void reset_rx(void){static bspam_adv_t table[BSPAM_TBL],snapshot[BSPAM_TBL];memset(table,0,sizeof(table));s_bspam=table;s_bspam_snap=snapshot;s_bspam_n=0;s_bspam_active=true;s_bspam_open_ms=0;s_bspam_locate=false;s_bspam_was_flood=false;s_bspam_status=&status_obj;s_bspam_alert=&counter_obj;s_bspam_list=NULL;}
static void receive(int id,int ext){struct ble_gap_event e={0};e.type=ext?BLE_GAP_EVENT_EXT_DISC:BLE_GAP_EVENT_DISC;e.disc.data=raw;e.disc.length_data=rawlen;e.disc.addr.val[0]=id;e.disc.addr.val[1]=id>>8;e.disc.rssi=-50;e.ext_disc.data=raw;e.ext_disc.length_data=rawlen;e.ext_disc.addr=e.disc.addr;e.ext_disc.rssi=-50;bspam_gap_cb(&e,NULL);}
static void fixture(FILE *f,int mode,int idx,int expected){reset_tx();ble_spam_mode=mode;begin_tx();for(int i=0;i<=idx;i++)ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(ble_spam_active);CHECK(ble_spam_count==idx+1);CHECK(bspam_classify(&captured)==expected);wrap_fields();CHECK(rawlen==mbuf.n);CHECK(memcmp(raw,mbuf.data,rawlen)==0);uint8_t flat[96],flatlen=0;CHECK(ble_hs_adv_set_fields(&captured,flat,&flatlen,sizeof(flat))==0);CHECK(flatlen==rawlen);CHECK(memcmp(flat,raw,rawlen)==0);struct ble_hs_adv_fields decoded;CHECK(ble_hs_adv_parse_fields(&decoded,raw,rawlen)==0);CHECK(bspam_classify(&decoded)==expected);fprintf(f,"%d,%d,%d,%d,",mode,idx,expected,rawlen);for(int i=0;i<rawlen;i++)fprintf(f,"%02x",raw[i]);fprintf(f,"\n");}
int main(void){
/* Installed NimBLE sends disable, then returns EALREADY for an already-stopped instance.
 * This is a confirmed stop, unlike EALREADY from start (not a new start). */
reset_tx();fail_stop=BLE_HS_EALREADY;begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);
CHECK(ble_spam_active);CHECK(g_ble_spam_state.timer!=NULL);CHECK(ble_spam_count==1);
begin_tx();CHECK(!ble_spam_active);CHECK(g_ble_spam_state.timer==NULL);CHECK(strcmp(status_obj.text,"Stopped")==0);
reset_tx();fail_timer=true;begin_tx();CHECK(!ble_spam_active);CHECK(g_ble_spam_state.timer==NULL);CHECK(strcmp(button_obj.text,"STOP")!=0);
failure_case(&fail_config);failure_case(&fail_stop);failure_case(&fail_addr);failure_case(&fail_gen);failure_case(&fail_set);failure_case(&fail_data);failure_case(&fail_start);
reset_tx();fail_start=BLE_HS_EALREADY;begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(!ble_spam_active);CHECK(ble_spam_count==0);CHECK(g_ble_spam_state.timer==NULL);
reset_tx();fail_alloc=true;begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(!ble_spam_active);CHECK(g_ble_spam_state.timer==NULL);CHECK(ble_spam_count==0);
reset_tx();ble_spam_mode=BLE_SPAM_MODE_AIRTAG;fail_addr_at=2;begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(!ble_spam_active);CHECK(start_calls==0);CHECK(ble_spam_count==0);
reset_tx();ble_spam_mode=BLE_SPAM_MODE_SAMSUNG;fail_gen=7;begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(!ble_spam_active);CHECK(start_calls==0);
reset_tx();begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(ble_spam_count==1);begin_tx();CHECK(!ble_spam_active);CHECK(g_ble_spam_state.timer==NULL);
/* A failure after a prior accepted start stops once, latches failure, and never retries TX. */
reset_tx();ble_spam_mode=BLE_SPAM_MODE_SAMSUNG;begin_tx();for(int i=0;i<4;i++)ble_spam_timer_cb(g_ble_spam_state.timer);fail_gen=7;int stopped=stop_calls;ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(!ble_spam_active);CHECK(!g_ble_spam_state.timer);CHECK(stop_calls==stopped+1);int started=start_calls;begin_tx();CHECK(start_calls==started);CHECK(!ble_spam_active);
reset_tx();begin_tx();ble_spam_timer_cb(g_ble_spam_state.timer);fail_stop=7;stopped=stop_calls;ble_spam_timer_cb(g_ble_spam_state.timer);CHECK(stop_calls==stopped+1);CHECK(!ble_spam_active);CHECK(ble_spam_count==1);
reset_tx();fail_init=true;begin_tx();CHECK(!ble_spam_active);CHECK(!g_ble_spam_state.timer);CHECK(ble_spam_count==0);
FILE *f=fopen("fixtures.csv","w");assert(f);fprintf(f,"mode,index,expected_family,ad_length,test_wrapped_ad_hex\n");
for(int i=0;i<APPLE_PAYLOAD_COUNT*2;i++)fixture(f,BLE_SPAM_MODE_APPLE,i,BSF_APPLE);
for(int i=0;i<SAMSUNG_MODEL_COUNT;i++)fixture(f,BLE_SPAM_MODE_SAMSUNG,i,BSF_SAMSUNG);
for(int i=0;i<GOOGLE_PAYLOAD_COUNT;i++)fixture(f,BLE_SPAM_MODE_GOOGLE,i,BSF_GOOGLE);
for(int i=0;i<12;i++)fixture(f,BLE_SPAM_MODE_WINDOWS,i,BSF_MICROSOFT);
for(int i=0;i<11;i++)fixture(f,BLE_SPAM_MODE_SOUR_APPLE,i,BSF_APPLE);
for(int i=0;i<AIRTAG_KEY_COUNT;i++)fixture(f,BLE_SPAM_MODE_AIRTAG,i,BSF_NONE);
for(int i=0;i<SMARTTAG_PAYLOAD_COUNT;i++)fixture(f,BLE_SPAM_MODE_SMARTTAG,i,BSF_NONE);
fclose(f);
/* Same byte-exact Apple input, stable vs distinct addresses, both event paths. */
fixture(f=fopen("churn-fixture.csv","w"),BLE_SPAM_MODE_APPLE,0,BSF_APPLE);fclose(f);
for(int ext=0;ext<=CFG_BLE_EXT_ADV;ext++){
reset_rx();clock_ms=7000;for(int i=0;i<1000;i++)receive(1,ext);bspam_ui_timer_cb(NULL);CHECK(s_bspam_n==1);CHECK(!s_bspam_was_flood);
reset_rx();clock_ms=5000;for(int i=0;i<BSPAM_CHURN_MIN;i++)receive(i,ext);bspam_ui_timer_cb(NULL);CHECK(!s_bspam_was_flood);clock_ms=6000;bspam_ui_timer_cb(NULL);CHECK(s_bspam_was_flood);
reset_rx();clock_ms=7000;for(int i=0;i<BSPAM_CHURN_MIN-1;i++)receive(i,ext);bspam_ui_timer_cb(NULL);CHECK(!s_bspam_was_flood);receive(BSPAM_CHURN_MIN-1,ext);bspam_ui_timer_cb(NULL);CHECK(s_bspam_was_flood);clock_ms=10000;bspam_ui_timer_cb(NULL);CHECK(s_bspam_was_flood);clock_ms=10001;bspam_ui_timer_cb(NULL);CHECK(!s_bspam_was_flood);
reset_rx();clock_ms=7000;for(int i=0;i<BSPAM_TBL+100;i++)receive(i,ext);CHECK(s_bspam_n==BSPAM_TBL);bspam_ui_timer_cb(NULL);CHECK(s_bspam_was_flood);
}
/* Tracking source bytes must not populate the popup churn table. */
for(int mode=BLE_SPAM_MODE_AIRTAG;mode<=BLE_SPAM_MODE_SMARTTAG;mode++){fixture(f=fopen("tracking-fixture.csv","w"),mode,0,BSF_NONE);fclose(f);reset_rx();clock_ms=7000;for(int i=0;i<20;i++)receive(i,0);bspam_ui_timer_cb(NULL);CHECK(s_bspam_n==0);CHECK(!s_bspam_was_flood);}
fixture(f=fopen("churn-fixture.csv","w"),BLE_SPAM_MODE_APPLE,0,BSF_APPLE);fclose(f);
/* Oversize extended reports are not silently truncated to a matching prefix. */
reset_rx();struct ble_gap_event oversized={0};oversized.type=BLE_GAP_EVENT_EXT_DISC;oversized.ext_disc.data=raw;oversized.ext_disc.length_data=256+rawlen;bspam_gap_cb(&oversized,NULL);CHECK(s_bspam_n==0);
struct ble_hs_adv_fields d;for(int n=1;n<rawlen;n++){int rc=ble_hs_adv_parse_fields(&d,raw,n);if(rc==0)CHECK(bspam_classify(&d)==BSF_NONE);else CHECK(rc!=0);}
uint8_t benign[]={5,0xff,0x4c,0,0x10,0};CHECK(ble_hs_adv_parse_fields(&d,benign,sizeof(benign))==0);CHECK(bspam_classify(&d)==BSF_NONE);
uint8_t unrelated_nearby[]={5,0xff,0x4c,0,4,1};CHECK(ble_hs_adv_parse_fields(&d,unrelated_nearby,sizeof(unrelated_nearby))==0);CHECK(bspam_classify(&d)==BSF_NONE);
uint8_t malformed[]={7,0xff,0x4c};CHECK(ble_hs_adv_parse_fields(&d,malformed,sizeof(malformed))!=0);
uint8_t broad_samsung[]={4,0xff,0x75,0,0x99};CHECK(ble_hs_adv_parse_fields(&d,broad_samsung,sizeof(broad_samsung))==0);CHECK(bspam_classify(&d)==BSF_SAMSUNG); /* documented false-positive limit */
printf("OFFLINE native validation: %d checks, %d failures; no RF backend\n",checks,failures);return failures?1:0;
}
