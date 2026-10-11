#pragma once
/* Header-only to keep every existing shared-board source list unchanged.
 * Pure bounded selection + canonical streaming ABI; no BLE, heap or crypto API.
 * See docs/gatt23-metadata.md before changing this versioned byte schema. */
#include "gatt_walker.h"
#include <stddef.h>
#include <string.h>

#define GW_METADATA_ALGORITHM "cym-gatt-metadata-v1"
/* The legacy walker cannot prove completion, even after read_ok. */
enum { GM_ABSENT, GM_UNREADABLE, GM_EMPTY, GM_OBSERVED, GM_CAP_UNCERTAIN };
enum { GM_NONE, GM_GATT, GM_ADVERTISED };
typedef struct {
    const uint8_t *data;
    uint16_t len;
    uint8_t source, state;
} gm_field_t;
typedef struct {
    gm_field_t fields[3]; /* DeviceName, ManufacturerName, ModelNumber */
    uint8_t name_gatt_state, mask;
} gm_selection_t;
typedef int (*gm_sink_t)(void *, const uint8_t *, size_t);

/* Match only actual NimBLE 16-bit strings or standardized Bluetooth-base
 * 128-bit strings. Reject vendor UUIDs with similar prefixes and extra text. */
static inline bool gm_uuid_is(const char *s, uint16_t uuid)
{
    size_t n = 0;
    while (n < 37 && s[n]) ++n;
    char short_u[7], long_u[37];
    /* No locale-sensitive folding: UUID hex alone is case-insensitive. */
    static const char hex[] = "0123456789abcdef";
    short_u[0]='0'; short_u[1]='x';
    for (int i=0;i<4;++i) short_u[2+i]=hex[(uuid >> (12-4*i)) & 15];
    short_u[6]=0;
    memcpy(long_u, "00000000-0000-1000-8000-00805f9b34fb", 37);
    memcpy(long_u+4, short_u+2, 4);
    const char *expected = n==6 ? short_u : n==36 ? long_u : NULL;
    if (!expected) return false;
    for (size_t i=0;i<n;++i) {
        unsigned char c=(unsigned char)s[i];
        if(c>='A' && c<='Z') c=(unsigned char)(c+'a'-'A');
        if(c!=(unsigned char)expected[i]) return false;
    }
    return true;
}

/* Count raw bytes, remove only trailing 0x00 padding; retain embedded NUL,
 * whitespace, case, UTF8 and all other bytes exactly. */
static inline gm_field_t gm_observe(const gw_chr_t *c)
{
    gm_field_t f={0}; f.source=GM_GATT;
    if (!c->read_ok) { f.state=GM_UNREADABLE; return f; }
    f.len=c->read_len > GW_READ_MAX ? GW_READ_MAX : c->read_len;
    f.data=c->read_data;
    f.state=c->read_len >= GW_READ_MAX ? GM_CAP_UNCERTAIN : GM_OBSERVED;
    while(f.len && f.data[f.len-1]==0) --f.len;
    if(!f.len && f.state!=GM_CAP_UNCERTAIN) f.state=GM_EMPTY;
    return f;
}

/* Duplicate choice is independent of enumeration/handle order: prefer nonempty,
 * then bytewise lexical minimum (shorter prefix first), then smaller state.
 * No nonempty: prefer empty evidence to unreadable, absent last. */
static inline bool gm_prefer(gm_field_t a, gm_field_t b)
{
    if (!!a.len != !!b.len) return a.len!=0;
    if(a.len) {
        size_t n=a.len<b.len ? a.len : b.len;
        int cmp=memcmp(a.data,b.data,n);
        if(cmp) return cmp<0;
        if(a.len!=b.len) return a.len<b.len;
        return a.state<b.state;
    }
    return a.state>b.state;
}

static inline gm_selection_t gm_select(const gw_result_t *r)
{
    gm_selection_t out={0};
    int ns=r->svc_count<0 ? 0 : r->svc_count>GW_MAX_SVCS ? GW_MAX_SVCS : r->svc_count;
    for(int si=0;si<ns;++si) {
        const gw_svc_t *s=&r->svcs[si];
        bool gap=gm_uuid_is(s->uuid_str,0x1800), dis=gm_uuid_is(s->uuid_str,0x180a);
        if(!gap && !dis) continue;
        int nc=s->chr_count<0 ? 0 : s->chr_count>GW_MAX_CHRS ? GW_MAX_CHRS : s->chr_count;
        for(int ci=0;ci<nc;++ci) {
            const gw_chr_t *c=&s->chrs[ci];
            int k=gap && gm_uuid_is(c->uuid_str,0x2a00) ? 0 :
                  dis && gm_uuid_is(c->uuid_str,0x2a29) ? 1 :
                  dis && gm_uuid_is(c->uuid_str,0x2a24) ? 2 : -1;
            if(k<0) continue;
            gm_field_t f=gm_observe(c);
            if(gm_prefer(f,out.fields[k])) out.fields[k]=f;
        }
    }
    out.name_gatt_state=out.fields[0].state;
    if(!out.fields[0].len) {
        size_t n=0;
        /* gw_walk stores at most 31 bytes of advertised name; completion of
         * the over-the-air name cannot be proved from this result struct. */
        while(n<sizeof(r->name)-1 && r->name[n]) ++n;
        if(n) out.fields[0]=(gm_field_t){(const uint8_t *)r->name,(uint16_t)n,
            GM_ADVERTISED,n==sizeof(r->name)-1 ? GM_CAP_UNCERTAIN : GM_OBSERVED};
    }
    for(int i=0;i<3;++i) if(out.fields[i].len) out.mask|=(uint8_t)(1u<<i);
    return out;
}

/* TLV tag:u8, length:u16 big endian. Domain tag0; layout tag1 (u32 BE);
 * tags2..4 body = source:u8,state:u8,name_gatt_state:u8,raw bytes.
 * name_gatt_state is zero for tags3,4. Missing fields still serialize markers.
 * Returns 1 for unavailable, 0 success, -1 sink error. Never hash layout only. */
static inline int gm_tlv(gm_sink_t sink, void *ctx, uint8_t tag, const uint8_t *p, uint16_t n)
{
    uint8_t head[3]={tag,(uint8_t)(n>>8),(uint8_t)n};
    if(sink(ctx,head,3)!=0 || (n && sink(ctx,p,n)!=0)) return -1;
    return 0;
}
static inline int gm_canonical(const gm_selection_t *s, uint32_t layout, gm_sink_t sink, void *ctx)
{
    if(!s->mask) return 1;
    const uint8_t domain[]=GW_METADATA_ALGORITHM;
    uint8_t be[4]={(uint8_t)(layout>>24),(uint8_t)(layout>>16),(uint8_t)(layout>>8),(uint8_t)layout};
    if(gm_tlv(sink,ctx,0,domain,sizeof(domain)-1) || gm_tlv(sink,ctx,1,be,4)) return -1;
    for(int i=0;i<3;++i) {
        const gm_field_t *f=&s->fields[i];
        /* Selections come from gm_select; bound again at the serializer ABI. */
        if(f->len>GW_READ_MAX || (f->len && !f->data)) return -1;
        uint16_t n=(uint16_t)(3+f->len);
        uint8_t head[6]={(uint8_t)(2+i),(uint8_t)(n>>8),(uint8_t)n,
            f->source,f->state,i==0 ? s->name_gatt_state : 0};
        if(sink(ctx,head,sizeof(head)) || (f->len && sink(ctx,f->data,f->len))) return -1;
    }
    return 0;
}
