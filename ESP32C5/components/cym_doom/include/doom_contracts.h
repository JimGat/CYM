/* CYM private Doom prototype contracts. No IDF, LVGL, RF or card ownership.
 * New CYM adapter code; engine GPL notices and corresponding source accompany distribution.
 */
#ifndef CYM_DOOM_CONTRACTS_H
#define CYM_DOOM_CONTRACTS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Callback must perform a bounded positional read and RELEASE transport locks
 * before returning. This validator does not allocate or change card state.
 * Structural/resource validation is not a full hostile-map renderer audit.
 */
typedef bool (*doom_read_at)(void *,uint64_t,void *,size_t);
typedef enum {DOOM_WAD_OK,DOOM_WAD_BOUNDS,DOOM_WAD_UNSUPPORTED,DOOM_WAD_RESOURCES,DOOM_WAD_IO} doom_wad_result;
doom_wad_result doom_wad_validate(doom_read_at,void *,uint64_t);
typedef struct {uint32_t first_ms;unsigned count;bool down;} doom_trigger;
void doom_trigger_reset(doom_trigger *);
bool doom_trigger_update(doom_trigger *,uint32_t,bool,bool,bool);
typedef struct {int x,y,w,h;} doom_rect;
doom_rect doom_scale_fit(int,int);
bool doom_scale_point(doom_rect,int,int,int *,int *);
bool doom_rotate_point(int,int,unsigned,int,int,int *,int *);
enum {DOOM_KEY_LEFT=1u<<0,DOOM_KEY_FORWARD=1u<<1,DOOM_KEY_RIGHT=1u<<2,DOOM_KEY_BACK=1u<<3,DOOM_KEY_FIRE=1u<<4,DOOM_KEY_USE=1u<<5,DOOM_KEY_MENU=1u<<6,DOOM_KEY_CONFIRM=1u<<7,DOOM_KEY_EXIT=1u<<8};
typedef struct {unsigned desired,delivered;} doom_keys;
void doom_keys_set(doom_keys *,unsigned);
bool doom_keys_next(doom_keys *,unsigned *,bool *);
unsigned doom_touch_keys(int,int,int,int,bool);
/* Registry rollback is allowed ONLY after worker acknowledgement. The caller
 * serializes this structure; it is not an RTOS semaphore or a join substitute.
 */
#define DOOM_OWNERS_MAX 32
typedef void (*doom_cleanup_fn)(void *);
typedef enum {DOOM_IDLE,DOOM_STARTING,DOOM_RUNNING,DOOM_STOPPING,DOOM_FAILED} doom_phase;
typedef struct {doom_phase phase;uint32_t generation;bool worker_done;unsigned owned_count;struct {doom_cleanup_fn fn;void *ptr;} owned[DOOM_OWNERS_MAX];} doom_lifecycle;
bool doom_lifecycle_begin(doom_lifecycle *);
bool doom_lifecycle_own(doom_lifecycle *,doom_cleanup_fn,void *);
bool doom_lifecycle_running(doom_lifecycle *);
void doom_lifecycle_stop(doom_lifecycle *);
void doom_lifecycle_fail(doom_lifecycle *);
void doom_lifecycle_worker_done(doom_lifecycle *);
bool doom_lifecycle_joined(const doom_lifecycle *);
void doom_lifecycle_cleanup(doom_lifecycle *);
bool doom_lifecycle_callback_valid(const doom_lifecycle *,uint32_t);
typedef struct {bool supported,idle,sd_ready,licensed,assets_valid;size_t psram_free,psram_largest;} doom_gate;
bool doom_gate_ready(doom_gate);
/* Exact private prototype asset allowlist; structural validation alone is not
 * hostile-content safety. Only official Freedoom 0.13.0 Phase 1 is qualified
 * for the observed initial-level host gate. Arbitrary mods are refused. */
bool doom_wad_trusted_hash(const uint8_t[32]);
#endif
