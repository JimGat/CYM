#!/usr/bin/env python3
from pathlib import Path
import re,subprocess
r=Path(__file__).resolve().parents[1];d=Path('/home/dev/projects/cym-targeted-refactor-20261017/netif');d.mkdir(exist_ok=True)
s=(r/'ESP32C5/components/wifi_cli/include/cym_netif_lifecycle.h').read_text();s=re.sub(r'^#include .*$', '', s,flags=re.M)
stub=r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
typedef int esp_err_t;typedef int esp_netif_t;typedef int esp_netif_dhcp_status_t;
typedef struct {struct {uint32_t addr;} ip,gw,netmask;} esp_netif_ip_info_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_ESP_NETIF_DHCP_ALREADY_STOPPED 3
#define ESP_ERR_ESP_NETIF_DHCP_ALREADY_STARTED 4
#define ESP_NETIF_DHCP_INIT 0
#define ESP_NETIF_DHCP_STARTED 1
#define ESP_NETIF_DHCP_STOPPED 2
#define ESP_LOGI(...) ((void)0)
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
static unsigned heap_caps_get_free_size(unsigned c){return c;}
static unsigned heap_caps_get_largest_free_block(unsigned c){return c;}
static const char *esp_err_to_name(int n){(void)n;return "mock";}
static int state,fail,gets,stops,sets,starts;
static int esp_netif_dhcpc_get_status(void*n,int*s){assert(n);gets++;*s=state;return fail==1?-1:0;}
static int esp_netif_dhcps_get_status(void*n,int*s){return esp_netif_dhcpc_get_status(n,s);}
static int esp_netif_dhcpc_stop(void*n){assert(n);stops++;if(fail==2)return -1;state=2;return 0;}
static int esp_netif_dhcps_stop(void*n){return esp_netif_dhcpc_stop(n);}
static int esp_netif_set_ip_info(void*n,const esp_netif_ip_info_t*i){assert(n&&i);sets++;return fail==3?-1:0;}
static int esp_netif_dhcpc_start(void*n){assert(n);starts++;if(fail==4)return -1;state=1;return 0;}
static int esp_netif_dhcps_start(void*n){return esp_netif_dhcpc_start(n);}
"""
main=r"""
int main(void){int n=0;esp_netif_ip_info_t ip={.ip.addr=1};assert(cym_dhcp_client_prepare(NULL)!=0);assert(cym_dhcp_server_configure(NULL,&ip)!=0);
 for(int initial=0;initial<3;initial++)for(fail=0;fail<5;fail++){
 state=initial;gets=stops=sets=starts=0;int rc=cym_dhcp_client_prepare(&n);
 if(fail==1||(initial==2&&(fail==3||fail==4)))assert(rc!=0);else assert(rc==0);
 if(initial!=2)assert(!sets&&!starts);
 state=initial;gets=stops=sets=starts=0;rc=cym_dhcp_server_configure(&n,&ip);
 assert((rc==0)==(fail==0));if(fail==2)assert(!sets&&!starts);if(fail==3)assert(!starts);
 }
 puts("PASS DHCP INIT/STARTED/STOPPED, static residue, stop/set/start/status failures");}
"""
p=d/'netif.c';p.write_text(stub+s+main);exe=d/'netif'
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-parameter','-fsanitize=address,undefined','-no-pie',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
