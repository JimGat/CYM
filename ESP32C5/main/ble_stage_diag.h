/* Bounded numeric BLE lifecycle breadcrumbs. No heap, NVS, SD or payload data.
 * RTC retention is best-effort, never evidence of survival across every reset.
 * Adapters are supplied by main.c; host tests execute these exact functions. */
#ifndef CYM_BLE_STAGE_DIAG_H
#define CYM_BLE_STAGE_DIAG_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
typedef enum {
    BT_ST_UI_ENTER=1, BT_ST_HEAP_ENTER, BT_ST_HEAP_QUERY, BT_ST_HEAP_EXIT,
    BT_ST_WIFI_STOP, BT_ST_WIFI_STOP_RETURN, BT_ST_WIFI_DEINIT, BT_ST_WIFI_DEINIT_RETURN,
    BT_ST_PORT_INIT, BT_ST_PORT_INIT_RETURN, BT_ST_HOST_CREATE, BT_ST_HOST_CREATE_RETURN,
    BT_ST_SYNC, BT_ST_SYNC_TIMEOUT, BT_ST_SCAN_CREATE, BT_ST_SCAN_CREATE_RETURN,
    BT_ST_WORKER_ENTER, BT_ST_WORKER_PUBLISHED, BT_ST_GAP_START, BT_ST_GAP_RETURN,
    BT_ST_CANCEL, BT_ST_CANCEL_RETURN, BT_ST_HOST_STOP, BT_ST_HOST_EXIT,
    BT_ST_PORT_DEINIT, BT_ST_PORT_DEINIT_RETURN, BT_ST_UI_RETURN, BT_ST_END
} bt_stage_t;
/* A versioned record, plus eight independent checksummed slots. Interrupted
 * writes fail validation; no attempt is made to reconstruct corrupt history. */
#define BT_STAGE_TAG UINT32_C(0xB1E3031A)
#define BT_STAGE_SLOTS 8u
typedef struct { uint32_t seq, stage; int32_t rc; uint32_t check; } bt_stage_slot_t;
typedef struct { uint32_t tag, generation, check; bt_stage_slot_t slot[BT_STAGE_SLOTS]; } bt_stage_record_t;
static RTC_NOINIT_ATTR volatile bt_stage_record_t s_bt_stage_record;
static uint32_t s_bt_stage_seq, s_bt_stage_debug_generation;
// Reporter cache is main-task-only; producers never reset it concurrently.
static uint32_t s_bt_stage_reported, s_bt_stage_report_generation;
static int64_t s_bt_stage_last_report;
static uint32_t bt_stage_check(bt_stage_slot_t v)
{ return BT_STAGE_TAG ^ v.seq ^ (v.stage * UINT32_C(0x9e3779b1)) ^ (uint32_t)v.rc; }
static bool bt_stage_valid(bt_stage_slot_t v)
{ return v.seq && v.stage > 0 && v.stage < BT_ST_END && v.check == bt_stage_check(v); }
static void bt_stage_reset(uint32_t generation)
{
    s_bt_stage_record.tag=0;
    for (unsigned i=0;i<BT_STAGE_SLOTS;i++) s_bt_stage_record.slot[i]=(bt_stage_slot_t){0};
    s_bt_stage_record.generation = generation ? generation : 1;
    s_bt_stage_record.check = BT_STAGE_TAG ^ s_bt_stage_record.generation;
    s_bt_stage_record.tag = BT_STAGE_TAG;
    s_bt_stage_seq = 0;
}
/* Boot is single-threaded, before other BLE producers. 'valid' only means
 * same format/checksum and a potentially retaining reset, not a crash cause. */
static void bt_stage_boot(int reset, bool may_retain)
{
    bool format = s_bt_stage_record.tag == BT_STAGE_TAG;
    bool header = format && s_bt_stage_record.generation &&
        s_bt_stage_record.check == (BT_STAGE_TAG ^ s_bt_stage_record.generation);
    uint32_t generation = header ? s_bt_stage_record.generation + 1u : 1u;
    if (BT_STAGE_ENABLED()) {
        unsigned valid=0, corrupt=0;
        if (header && may_retain) for (unsigned i=0;i<BT_STAGE_SLOTS;i++) {
            bt_stage_slot_t v=s_bt_stage_record.slot[i];
            if (!v.seq) continue;
            if (bt_stage_valid(v)) { ++valid; BT_STAGE_PREVIOUS(s_bt_stage_record.generation,v.seq,v.stage,v.rc); }
            else ++corrupt;
        }
        BT_STAGE_BOOT_STATUS(!may_retain ? "unavailable" : !format ? "stale-or-unavailable" :
            !header || corrupt ? "corrupt" : valid ? "valid" : "unavailable", reset);
    }
    bt_stage_reset(generation);
    s_bt_stage_reported=s_bt_stage_report_generation=0;
    s_bt_stage_last_report=0;
    s_bt_stage_debug_generation = BT_STAGE_GENERATION();
}
/* Called at boundaries only, never per advertisement. No printing while locked. */
static void bt_stage(bt_stage_t stage, int rc)
{
    uint32_t debug_generation=BT_STAGE_GENERATION();
    BT_STAGE_LOCK();
    if (debug_generation != s_bt_stage_debug_generation) {
        bt_stage_reset(s_bt_stage_record.generation + 1u);
        s_bt_stage_debug_generation=debug_generation;
    }
    if (BT_STAGE_ENABLED() && stage > 0 && stage < BT_ST_END) {
        if (++s_bt_stage_seq == 0) bt_stage_reset(s_bt_stage_record.generation + 1u), ++s_bt_stage_seq;
        bt_stage_slot_t v={s_bt_stage_seq,(uint32_t)stage,rc,0};v.check=bt_stage_check(v);
        volatile bt_stage_slot_t *out=&s_bt_stage_record.slot[(v.seq-1u)%BT_STAGE_SLOTS];
        out->check=0;out->seq=v.seq;out->stage=v.stage;out->rc=v.rc;out->check=v.check;
    }
    BT_STAGE_UNLOCK();
}
/* At most two bounded snapshots/second from the existing main loop. Ring
 * entries survive a nonreturning call even when no console line is emitted. */
static void bt_stage_report(int64_t now)
{
    bt_stage_slot_t copy[BT_STAGE_SLOTS];uint32_t generation,seq;
    bt_stage((bt_stage_t)0,0); // apply debug transitions even without BLE activity
    if (!BT_STAGE_ENABLED() || now-s_bt_stage_last_report < 500000) return;
    BT_STAGE_LOCK();
    seq=s_bt_stage_seq;generation=s_bt_stage_record.generation;
    for (unsigned i=0;i<BT_STAGE_SLOTS;i++) copy[i]=s_bt_stage_record.slot[i];
    BT_STAGE_UNLOCK();
    uint32_t reported=generation==s_bt_stage_report_generation ? s_bt_stage_reported : 0;
    if (seq==reported) return;
    uint32_t first=seq>BT_STAGE_SLOTS ? seq-BT_STAGE_SLOTS+1u : 1u;
    for (uint32_t n=first;n && n<=seq;n++) {
        bt_stage_slot_t v=copy[(n-1u)%BT_STAGE_SLOTS];
        if (v.seq==n && v.seq>reported && bt_stage_valid(v) && BT_STAGE_ENABLED())
            BT_STAGE_CURRENT(generation,v.seq,v.stage,v.rc);
    }
    s_bt_stage_reported=seq;s_bt_stage_report_generation=generation;s_bt_stage_last_report=now;
}
#endif
