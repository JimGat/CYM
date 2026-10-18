/* Single bounded mailbox with two references: caller + UI owner.
 * A timed-out caller NEVER frees storage still reachable by the UI owner.
 * No persistent semaphore, task, queue allocation, or LVGL async timer.
 * Included by production UI and the native failure-injection harness. */
static cym_fsd_request_t *s_fsd_pending;
static unsigned s_fsd_busy;
static void *fsd_alloc(size_t bytes)
{
#if CONFIG_BOARD_HAS_PSRAM
    /* Do not consume scarce internal RAM when advertised PSRAM is exhausted. */
    return heap_caps_calloc(1,bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
#else
    return heap_caps_calloc(1,bytes,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
#endif
}
void cym_fsd_release(cym_fsd_request_t *r)
{
    if(__atomic_sub_fetch(&r->refs,1,__ATOMIC_ACQ_REL)==0){
        heap_caps_free(r->data);heap_caps_free(r);
        __atomic_store_n(&s_fsd_busy,0,__ATOMIC_RELEASE);
    }
}
cym_fsd_request_t *cym_fsd_submit(int op,int id,int a,int b,const char *text)
{
    if(text && strlen(text)>=sizeof(((cym_fsd_request_t*)0)->text))return NULL;
    unsigned expected=0;
    if(!__atomic_compare_exchange_n(&s_fsd_busy,&expected,1,false,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return NULL;
    cym_fsd_request_t *r=fsd_alloc(sizeof(*r));
    if(!r){__atomic_store_n(&s_fsd_busy,0,__ATOMIC_RELEASE);return NULL;}
    r->refs=2;r->op=op;r->id=id;r->a=a;r->b=b;
    if(text)memcpy(r->text,text,strlen(text)+1);
    cym_fsd_request_t *empty=NULL;
    if(!__atomic_compare_exchange_n(&s_fsd_pending,&empty,r,false,__ATOMIC_RELEASE,__ATOMIC_RELAXED)){
        /* Defensive queue-failure path: published requests are never overwritten. */
        r->refs=1;cym_fsd_release(r);return NULL;
    }
    return r;
}
static cym_fsd_request_t *fsd_take(void)
{ return __atomic_exchange_n(&s_fsd_pending,NULL,__ATOMIC_ACQ_REL); }
static void fsd_complete(cym_fsd_request_t *r)
{
    __atomic_store_n(&r->done,1,__ATOMIC_RELEASE);
    cym_fsd_release(r); /* owner reference, even after caller timeout */
}
