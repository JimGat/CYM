#include "hat_tx.h"
#ifdef HAT_TX_HOST
#include <pthread.h>
static pthread_mutex_t s_lock = PTHREAD_MUTEX_INITIALIZER;
#define LOCK() pthread_mutex_lock(&s_lock)
#define UNLOCK() pthread_mutex_unlock(&s_lock)
#else
#include "freertos/FreeRTOS.h"
static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
#define LOCK() portENTER_CRITICAL(&s_lock)
#define UNLOCK() portEXIT_CRITICAL(&s_lock)
#endif
// @birolt29: owner/ack design origin; checked synchronization and integration: JimGat.
typedef struct { uint32_t generation; unsigned requests; bool owned, cancel, stopping, error; } owner_t;
static owner_t s_owner[HAT_TX_COUNT];
static bool s_inhibit;
static bool matches(hat_tx_ticket_t t) {
    return (unsigned)t.id < HAT_TX_COUNT && s_owner[t.id].owned && s_owner[t.id].generation == t.generation;
}
bool hat_tx_begin(hat_tx_id_t id, hat_tx_ticket_t *t) {
    if ((unsigned)id >= HAT_TX_COUNT || !t) return false;
    LOCK(); owner_t *o=&s_owner[id];
    bool ok=!s_inhibit && !o->owned;
    if (ok) { o->generation++; if (!o->generation) o->generation++;
        o->owned=true; o->cancel=o->stopping=o->error=false; o->requests=0;
        *t=(hat_tx_ticket_t){id,o->generation}; }
    UNLOCK(); return ok;
}
bool hat_tx_valid(hat_tx_ticket_t t) {
    LOCK(); bool ok=matches(t) && !s_owner[t.id].cancel && !s_owner[t.id].error;
    UNLOCK(); return ok;
}
bool hat_tx_enter(hat_tx_ticket_t t) {
    LOCK(); bool ok=matches(t) && !s_owner[t.id].cancel && !s_owner[t.id].stopping && !s_owner[t.id].error;
    if (ok) s_owner[t.id].requests++;
    UNLOCK(); return ok;
}
void hat_tx_leave(hat_tx_ticket_t t) {
    LOCK(); if (matches(t) && s_owner[t.id].requests) s_owner[t.id].requests--; UNLOCK();
}
void hat_tx_cancel(hat_tx_id_t id) {
    if ((unsigned)id >= HAT_TX_COUNT) return;
    LOCK(); if (s_owner[id].owned) s_owner[id].cancel=true; UNLOCK();
}
void hat_tx_inhibit(bool requested) {
    LOCK(); s_inhibit=requested;
    if (requested) for (int i=0;i<HAT_TX_COUNT;i++) if (s_owner[i].owned) s_owner[i].cancel=true;
    UNLOCK();
}
void hat_tx_finish(hat_tx_ticket_t t, bool checked_stopped) {
    LOCK(); if (matches(t) && !s_owner[t.id].requests) {
        owner_t *o=&s_owner[t.id]; o->stopping=false;
        if (checked_stopped) { o->owned=false; o->error=false; }
        else { o->error=true; o->cancel=true; }
    } UNLOCK();
}
bool hat_tx_claim_stop(hat_tx_id_t id, hat_tx_ticket_t *t) {
    if ((unsigned)id >= HAT_TX_COUNT || !t) return false;
    LOCK(); owner_t *o=&s_owner[id];
    bool ok=o->owned && o->cancel && !o->requests && !o->stopping;
    if (ok) { o->stopping=true; *t=(hat_tx_ticket_t){id,o->generation}; }
    UNLOCK(); return ok;
}
bool hat_tx_owned(hat_tx_id_t id) {
    if ((unsigned)id >= HAT_TX_COUNT) return false;
    LOCK(); bool owned=s_owner[id].owned; UNLOCK(); return owned;
}
hat_tx_snapshot_t hat_tx_snapshot(void) {
    LOCK(); hat_tx_snapshot_t s={.inhibit=s_inhibit};
    for (int i=0;i<HAT_TX_COUNT;i++) { owner_t *o=&s_owner[i];
        s.state[i]=o->error?HAT_TX_ERROR:o->owned?(o->cancel?HAT_TX_QUIESCING:HAT_TX_ACTIVE):(s_inhibit?HAT_TX_STOPPED:HAT_TX_READY);
    } UNLOCK(); return s;
}
