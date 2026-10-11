/* CYM game integration; GPL-2.0-or-later. See LICENSE.engine and NOTICE.md. */
/* One bounded, versioned intent. No NVS repair, partition selection or OTA. */
#include "game_mode.h"
#define INTENT_MAGIC UINT32_C(0x43594d47)
#define INTENT_V1_DOOM UINT32_C(0x00010001)
#define INTENT_SALT UINT32_C(0xa5a55a5a)
_Static_assert(sizeof(game_intent)==12, "intent is bounded to 12 bytes");
bool game_mode_record(const game_mode_io *io,game_mode mode)
{
 if (!io || !io->set || !io->erase || !io->commit || mode!=GAME_DOOM) return false;
 game_intent v={INTENT_MAGIC,INTENT_V1_DOOM,INTENT_MAGIC^INTENT_V1_DOOM^INTENT_SALT};
 if (!io->set(io->ctx,&v)) return false;
 if (io->commit(io->ctx)) return true;
 /* Never reboot after a failed commit. Best-effort invalidate the pending key. */
 if (io->erase(io->ctx)) (void)io->commit(io->ctx);
 return false;
}
game_mode game_mode_consume(const game_mode_io *io,bool supported,bool software_reset,bool boot_held)
{
 if (!io || !io->read || !io->erase || !io->commit) return GAME_NORMAL;
 game_intent v={0};game_read r=io->read(io->ctx,&v);
 if (r==GAME_ABSENT) return GAME_NORMAL;
 /* Consume corrupt, wrongly typed, stale and unreadable keys too. Fail closed. */
 if (!io->erase(io->ctx) || !io->commit(io->ctx)) return GAME_NORMAL;
 if (r!=GAME_FOUND || !supported || !software_reset || boot_held) return GAME_NORMAL;
 if (v.magic!=INTENT_MAGIC || v.version_mode!=INTENT_V1_DOOM ||
     v.check!=(v.magic^v.version_mode^INTENT_SALT)) return GAME_NORMAL;
 return GAME_DOOM;
}
