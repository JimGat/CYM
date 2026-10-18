#!/usr/bin/env python3
"""Failure injection against the production console, not a parallel model."""
from pathlib import Path
import subprocess, re, os
r=Path(__file__).resolve().parents[1]
d=Path(os.environ.get('CYM_TEST_OUT','/home/dev/projects/cym-targeted-refactor-20261017'))/'console';d.mkdir(parents=True,exist_ok=True)
s=(r/'ESP32C5/main/debug_console.c').read_text()
s=re.sub(r'^#include .*$', '', s, flags=re.M)
stub=r"""
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <assert.h>
#define CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED 1
#define CONFIG_ESP_CONSOLE_NONE 0
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_DMA 4
#define MALLOC_CAP_SPIRAM 8
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM 2
#define ESP_ERR_INVALID_STATE 3
#define ESP_ERR_INVALID_ARG 4
#define ESP_ERR_NOT_FOUND 5
#define ESP_ERR_NOT_SUPPORTED 6
#define pdPASS 1
#define pdMS_TO_TICKS(n) (n)
#define ESP_LINE_ENDINGS_CR 1
#define DRAM_ATTR
#define portMUX_TYPE int
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
typedef int esp_err_t;typedef unsigned char StackType_t;typedef struct {char bytes[96];} StaticTask_t;typedef void *TaskHandle_t;
typedef struct {int max_cmdline_length;} esp_console_config_t;
typedef struct {const char *command,*help,*hint;int (*func)(int,char**);} esp_console_cmd_t;
typedef struct {int dummy;} usb_serial_jtag_driver_config_t;
#define ESP_CONSOLE_CONFIG_DEFAULT() {0}
#define USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT() {0}
static int fail,borrowed,installed,uninstalled,opened,closed,parser,registered,dynamic_tasks,static_tasks,route;
static void logline(const char *tag,const char *fmt,...){(void)tag;va_list ap;va_start(ap,fmt);vprintf(fmt,ap);puts("");va_end(ap);}
#define ESP_LOGI logline
#define ESP_LOGW logline
#define ESP_LOGE logline
static bool cym_debug_enabled(void){return false;}
static unsigned cym_debug_generation(void){return 0;}
static int cym_debug_command(int n,char **a){(void)n;(void)a;return 0;}
static const char *esp_err_to_name(int e){return e?"INJECTED":"OK";}
static size_t heap_caps_get_free_size(unsigned c){return 1000+c;}
static size_t heap_caps_get_largest_free_block(unsigned c){return 500+c;}
static size_t heap_caps_get_minimum_free_size(unsigned c){return 100+c;}
static uint64_t esp_timer_get_time(void){return 0;}
static unsigned uxTaskGetStackHighWaterMark(void *h){(void)h;return 2048;}
static void vTaskDelay(unsigned n){(void)n;}
static bool usb_serial_jtag_is_driver_installed(void){return borrowed||installed;}
static int usb_serial_jtag_driver_install(void *c){assert(c);if(fail==1)return 2;installed++;return 0;}
static int usb_serial_jtag_driver_uninstall(void){assert(!borrowed);uninstalled++;installed--;return 0;}
static FILE *mock_fopen(const char *p,const char *mode){
#if CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG
 const char *registered_path="/dev/secondary";
#else
 const char *registered_path="/dev/usbserjtag";
#endif
 if(strcmp(p,registered_path)){errno=ENOENT;return NULL;}int stage=!strcmp(mode,"r")?2:3;if(fail==stage){errno=EMFILE;return NULL;}opened++;return (FILE*)(uintptr_t)stage;}
static int mock_fclose(FILE *f){assert(f);closed++;return 0;}
#define fopen mock_fopen
#define fclose mock_fclose
static int esp_console_init(esp_console_config_t *c){assert(c->max_cmdline_length==100);if(fail==4)return 2;parser++;return 0;}
static int esp_console_deinit(void){assert(parser);parser--;registered=0;return 0;}
static int esp_console_cmd_register(const esp_console_cmd_t *c){assert(!strcmp(c->command,"debug"));if(fail==5)return 2;registered++;return 0;}
static void linenoiseSetDumbMode(int n){assert(n==1);}
static void linenoiseSetMaxLineLen(int n){assert(n==100);}
static char *linenoise(const char *p){(void)p;return NULL;}
static void linenoiseFree(void *p){free(p);}
static int esp_console_run(char *l,int *r){(void)l;(void)r;return 0;}
static void usb_serial_jtag_vfs_set_rx_line_endings(int n){assert(n==1);}
static void usb_serial_jtag_vfs_use_driver(void){route=1;}
static void usb_serial_jtag_vfs_use_nonblocking(void){route=0;}
static int xTaskCreate(void (*f)(void*),const char*n,unsigned depth,void *a,int pri,void*h){(void)f;(void)n;(void)a;(void)h;assert(depth==4096&&pri==1);dynamic_tasks++;return fail==6?0:1;}
static TaskHandle_t xTaskCreateStatic(void (*f)(void*),const char*n,unsigned depth,void*a,int pri,StackType_t *stack,StaticTask_t *tcb){(void)f;(void)n;(void)a;assert(depth==4096&&pri==1&&stack&&tcb);static_tasks++;return fail==6?NULL:tcb;}
"""
main=r"""
int main(int argc,char **argv){assert(argc==3);fail=atoi(argv[1]);borrowed=atoi(argv[2]);int rc=cym_debug_console_start();
 if(fail){assert(rc!=0);assert(opened==closed&&!parser&&!registered);assert(uninstalled==(!borrowed&&fail!=1));if(borrowed&&static_tasks)assert(route==1);fail=0;rc=cym_debug_console_start();assert(rc==0);}
 assert(rc==0);assert(dynamic_tasks==0);assert(static_tasks>=1);int count=static_tasks;assert(cym_debug_console_start()==0&&static_tasks==count);assert(opened-closed==2&&parser==1&&registered==1);puts("PASS console boundary/retry/borrowed-driver/static-reservation");}
"""
p=d/'console.c';p.write_text(stub+s+main)
for secondary in [0,1]:
 exe=d/('console-secondary' if secondary else 'console-primary')
 print('USB route:', 'secondary' if secondary else 'primary', flush=True)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable','-fsanitize=address,undefined','-g',f'-DCONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG={secondary}',f'-DCONFIG_ESP_CONSOLE_USB_SERIAL_JTAG={1-secondary}',str(p),'-o',str(exe)],check=True)
 for borrowed in [0,1]:
  for stage in range(7):
   if borrowed and stage==1:continue
   subprocess.run([str(exe),str(stage),str(borrowed)],check=True)
