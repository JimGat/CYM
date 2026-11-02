
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#define MYNEWT_VAL(x) 0
#define NIMBLE_BLE_CONNECT 0
#define BLE_ADV_INSTANCES 3
#define BLE_GAP_OP_NULL 0
#define BLE_GAP_OP_S_ADV 1
#define BLE_HS_LOG(...) ((void)0)
#define BLE_HS_DBG_ASSERT assert
#define min(a,b) ((a)<(b)?(a):(b))
/* ble_addr_t and numeric constants injected from installed headers. */
struct os_mbuf {unsigned len;uint8_t data[128];bool freed;};
static int enabled=1,addr_calls,hci_rc,free_calls,append_fail;
static uint8_t last_addr[6];
static int checks;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static bool ble_hs_is_enabled(void){return enabled;}
static void ble_hs_lock(void){}
static void ble_hs_unlock(void){}
static int ble_gap_ext_adv_set_addr_no_lock(uint8_t i,const uint8_t*a){(void)i;memcpy(last_addr,a,6);addr_calls++;return hci_rc;}
static int os_mbuf_append(struct os_mbuf*m,const void*p,int n){assert(!m->freed);if(append_fail)return 12;assert(m->len+n<=128);memcpy(m->data+m->len,p,n);m->len+=n;return 0;}
static void os_mbuf_free_chain(struct os_mbuf*m){if(m){assert(!m->freed);m->freed=true;free_calls++;}}
#define OS_MBUF_PKTLEN(m) ((m)->len)
static struct {bool configured,legacy_pdu,directed,connectable,scannable;int op;}ble_gap_slave[3];
static int ble_gap_ext_adv_set(uint8_t i,int code,struct os_mbuf**m){(void)i;(void)code;(void)m;return hci_rc;}
struct ble_hs_adv_fields {uint8_t flags;const uint8_t*name,*mfg_data;uint8_t name_len,mfg_data_len,name_is_complete;};
