/* USB-console half of FSD (co-developer @birolt29, patch #15).
 * The parser validates complete arguments. Only the UI owner touches LVGL.
 * Raw crash/debug logs remain enabled; screenshot rows have explicit framing. */
#include "fsd.h"
#if !CONFIG_ESP_CONSOLE_NONE
#include "debug_console_stdio.h"
#include "esp_console.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
static bool fsd_integer(const char *s,int low,int high,int *out)
{
    if(!s||!*s)return false;
    /* Reject spaces, trailing bytes, decimal suffixes and integer overflow. */
    const char *p=s;if(*p=='-'||*p=='+')p++;
    if(!*p)return false;
    for(;*p;p++)if(*p<'0'||*p>'9')return false;
    errno=0;char *end;long v=strtol(s,&end,10);
    if(errno||*end||v<low||v>high)return false;
    *out=(int)v;return true;
}
static bool fsd_join(int argc,char **argv,int first,char text[96])
{
    size_t n=0;text[0]=0;
    for(int i=first;i<argc;i++){
        size_t k=strlen(argv[i]);if(n+k+(i>first?1:0)>=96)return false;
        if(i>first)text[n++]=' ';memcpy(text+n,argv[i],k);n+=k;text[n]=0;
    }
    return n!=0;
}
static int fsd_command(int argc,char **argv)
{
    FILE *out=cym_console_output();if(argc<1)return 1;
    const char *cmd=argv[0];int op=-1,id=0,a=0,b=0;char text[96]="";bool valid=false;
    if(!strcmp(cmd,"heap")){
        if(argc!=1)goto invalid;
        fprintf(out,"HEAP internal_free=%u internal_largest=%u internal_min=%u dma_free=%u dma_largest=%u psram_free=%u psram_largest=%u\n",
            (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),(unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
            (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA|MALLOC_CAP_8BIT),(unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),(unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM));return 0;
    }
    const char *simple[]={"back","where","tree","shot"};const int ops[]={FSD_BACK,FSD_WHERE,FSD_TREE,FSD_SHOT};
    for(size_t i=0;i<4;i++)if(!strcmp(cmd,simple[i])){op=ops[i];valid=argc==1;}
    if(!strcmp(cmd,"nav")||!strcmp(cmd,"tapt")){op=!strcmp(cmd,"nav")?FSD_NAV:FSD_TAPT;valid=argc>=2&&fsd_join(argc,argv,1,text);}
    if(!strcmp(cmd,"text")){op=FSD_TEXT;valid=argc>=3&&fsd_integer(argv[1],0,65535,&id)&&fsd_join(argc,argv,2,text);}
    if(!strcmp(cmd,"tap")){op=FSD_TAP;valid=argc==3&&fsd_integer(argv[1],0,799,&a)&&fsd_integer(argv[2],0,799,&b);}
    if(!strcmp(cmd,"tapid")){op=FSD_TAPID;valid=argc==2&&fsd_integer(argv[1],0,65535,&id);}
    if(!strcmp(cmd,"move")||!strcmp(cmd,"size")){
        op=!strcmp(cmd,"move")?FSD_MOVE:FSD_SIZE;int low=op==FSD_SIZE?1:-800;
        valid=argc==4&&fsd_integer(argv[1],0,65535,&id)&&fsd_integer(argv[2],low,800,&a)&&fsd_integer(argv[3],low,800,&b);
    }
    if(!strcmp(cmd,"rotate")){
        op=FSD_ROTATE;valid=argc==2;
        if(valid){if(!strcmp(argv[1],"portrait"))a=0;else if(!strcmp(argv[1],"landscape"))a=1;else valid=fsd_integer(argv[1],0,3,&a);}
    }
    /* swipe <x> <y> <dy>: scroll the scrollable container under (x,y) by dy pixels, like a finger
     * drag (positive dy reveals content above, negative reveals below). id carries dy. */
    if(!strcmp(cmd,"swipe")){op=FSD_SWIPE;valid=argc==4&&fsd_integer(argv[1],0,799,&a)&&fsd_integer(argv[2],0,799,&b)&&fsd_integer(argv[3],-800,800,&id);}
    if(!valid||op<0)goto invalid;
    cym_fsd_request_t *r=cym_fsd_submit(op,id,a,b,text);
    if(!r){fprintf(out,"%s error: busy or request allocation failed\n",cmd);return 1;}
    int64_t deadline=esp_timer_get_time()+5000000;
    while(!__atomic_load_n(&r->done,__ATOMIC_ACQUIRE)&&esp_timer_get_time()<deadline)vTaskDelay(pdMS_TO_TICKS(10));
    if(!__atomic_load_n(&r->done,__ATOMIC_ACQUIRE)){
        __atomic_store_n(&r->cancelled,1,__ATOMIC_RELEASE);
        fprintf(out,"%s error: timeout; outcome indeterminate if already running; wait then inspect where/tree before retry\n",cmd);
        cym_fsd_release(r);return 1;
    }
    int rc=r->status?0:1;
    if(!r->status){fprintf(out,"%s error: %s\n",cmd,r->desc[0]?r->desc:"operation failed");}
    else if(op==FSD_WHERE)fprintf(out,"where %s\n",r->desc);
    else if(op==FSD_TREE){fprintf(out,"<<<TREE>>>\n");fwrite(r->data,1,r->length,out);fprintf(out,"<<<ENDTREE>>>\n");}
    else if(op==FSD_SHOT){
        size_t cap=((size_t)r->w*3+2)/3*4+1;
        /* PSRAM board only: no internal fallback for image transport buffers. */
        unsigned char *row=heap_caps_malloc(cap,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if(!row){fprintf(out,"shot error: encoding allocation failed\n");rc=1;}
        else{
            fprintf(out,"<<<SHOT w=%u h=%u fmt=rgb888>>>\n",r->w,r->h);
            for(unsigned y=0;y<r->h;y++){
                size_t n=0;
                if(mbedtls_base64_encode(row,cap,&n,(const unsigned char*)r->data+(size_t)y*r->w*3,(size_t)r->w*3)){rc=1;break;}
                fprintf(out,"SHOTROW y=%u data=",y);fwrite(row,1,n,out);fputc('\n',out);
                if(ferror(out)){rc=1;break;}vTaskDelay(pdMS_TO_TICKS(1));
            }
            fprintf(out,rc?"<<<SHOTERR stream>>>\n":"<<<ENDSHOT>>>\n");heap_caps_free(row);
        }
    }else if(op==FSD_TAPT)fprintf(out,"tapt ok id=%d: %s\n",r->id,r->text);
    else fprintf(out,"%s ok\n",cmd);
    fflush(out);cym_fsd_release(r);return rc;
invalid:
    fprintf(out,"%s error: invalid arguments (no truncation permitted); see help\n",cmd);return 1;
}
static const esp_console_cmd_t fsd_commands[]={
#define FSD_CMD(name,description,args) {.command=name,.help=description,.hint=args,.func=fsd_command}
    FSD_CMD("heap","Internal/DMA/PSRAM free, largest and internal minimum",NULL),
    FSD_CMD("nav","Direct screen jump (manual use; can start radio tools)","<screen name>"),
    FSD_CMD("back","Top Back via normal deferred stop lifecycle",NULL),
    FSD_CMD("where","UI-owned nav stack snapshot",NULL),
    FSD_CMD("tree","UI-owned widget tree (labels abbreviated with ~)",NULL),
    FSD_CMD("shot","PSRAM logical screenshot, framed RGB888 rows",NULL),
    FSD_CMD("tap","Manual synthetic click; may transmit/change settings","<x> <y>"),
    FSD_CMD("tapid","Manual click at current tree id","<id>"),
    FSD_CMD("tapt","Manual visible enabled label click","<label>"),
    FSD_CMD("move","Volatile logical widget position","<id> <x> <y>"),
    FSD_CMD("size","Volatile widget dimensions","<id> <w> <h>"),
    FSD_CMD("text","Volatile label edit, maximum 95 bytes","<id> <text>"),
    FSD_CMD("rotate","Supported boards only; volatile orientation then Home","<0-3|portrait|landscape>"),
    FSD_CMD("swipe","Scroll the scrollable container at a point (finger drag; +dy reveals above)","<x> <y> <dy>")
#undef FSD_CMD
};
static size_t fsd_registered;
void cym_fsd_unregister(void)
{
    while(fsd_registered){--fsd_registered;(void)esp_console_cmd_deregister(fsd_commands[fsd_registered].command);}
}
void cym_fsd_register(void)
{
    if(fsd_registered)return;
    for(size_t i=0;i<sizeof(fsd_commands)/sizeof(fsd_commands[0]);i++){
        esp_err_t rc=esp_console_cmd_register(&fsd_commands[i]);
        if(rc!=ESP_OK){cym_fsd_unregister();ESP_LOGE("FSD","FSD unavailable: registration failed (%s); debug console preserved",esp_err_to_name(rc));return;}
        fsd_registered++;
    }
}
#endif
