/* CYM game integration; GPL-2.0-or-later. See LICENSE.engine and NOTICE.md. */
#ifndef CYM_GAME_MODE_H
#define CYM_GAME_MODE_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef enum { GAME_NORMAL=0, GAME_DOOM=1, GAME_ARDUBOY=2 } game_mode;
typedef struct { uint32_t magic, version_mode, check; } game_intent;
typedef enum { GAME_ABSENT, GAME_FOUND, GAME_READ_FAULT } game_read;
typedef struct {
 void *ctx;
 game_read (*read)(void *,game_intent *);
 bool (*set)(void *,const game_intent *);
 bool (*erase)(void *);
 bool (*commit)(void *);
} game_mode_io;
bool game_mode_record(const game_mode_io *,game_mode);
game_mode game_mode_consume(const game_mode_io *,bool supported,bool software_reset,bool boot_held);
#endif
