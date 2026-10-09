#ifdef ARDUINO
#include <esp_heap_caps.h>
#endif

#include <stdio.h>

#include "m_argv.h"

#include "doomgeneric.h"
#include "i_sound.h"
#include "s_sound.h"
#include "g_game.h"
#include "w_wad.h"
#include "z_zone.h"
#include "r_plane.h"
#include "r_data.h"
#include "r_things.h"
#include "r_draw.h"

pixel_t* DG_ScreenBuffer = NULL;

void M_FindResponseFile(void);
void D_DoomMain (void);


void doomgeneric_Create(int argc, char **argv)
{
	printf("DG_Create()\n");
	// save arguments
    myargc = argc;
    myargv = argv;

	M_FindResponseFile();

	#ifdef ARDUINO

	DG_ScreenBuffer =
		heap_caps_malloc(
			DOOMGENERIC_RESX *
			DOOMGENERIC_RESY *
			sizeof(pixel_t),
			MALLOC_CAP_SPIRAM);

	#else

	DG_ScreenBuffer =
		malloc(
			DOOMGENERIC_RESX *
			DOOMGENERIC_RESY *
			sizeof(pixel_t));

	#endif
			
	DG_Init();
	
	D_DoomMain ();
}


//
// doomgeneric_Shutdown
//
//  Returns ALL the PSRAM doomgeneric_Create grabbed: ~6.2 MB that,
//  until now, never got released.
//
//  THE ORDER IS NOT NEGOTIABLE. Half of Doom holds pointers into the
//  zone (lumpinfo[].cache, sfxinfo->driver_data, the synth's score).
//  If you free the zone first, all of that is left dangling and the
//  crash doesn't show up on exit: it shows up the SECOND time you open
//  Doom.
//
//  1. audio  : stops the mixer task (it reads samples FROM the zone)
//              and releases driver_data
//  2. wad    : closes the file and releases lumpinfo
//  3. render : visplanes / openings / drawsegs / vissprites
//  4. screen
//  5. zone   : last, once nothing points into it anymore
//
#ifdef ARDUINO
#define DG_PSRAM_FREE()  heap_caps_get_free_size(MALLOC_CAP_SPIRAM)
static size_t dg_mark;
#define DG_STEP(name) \
	do { \
		size_t now = DG_PSRAM_FREE(); \
		printf("[shutdown] %-18s freed %8d bytes\n", name, (int)(now - dg_mark)); \
		dg_mark = now; \
	} while (0)
#else
#define DG_STEP(name) do {} while (0)
#endif

void doomgeneric_Shutdown (void)
{
	#ifdef ARDUINO
	dg_mark = DG_PSRAM_FREE();
	#endif

	// S_Shutdown llama a I_ShutdownMusic + I_ShutdownSound y ademas
	// olvida mus_playing y S_music[], que sobreviven a la zone.
	S_Shutdown ();
	DG_STEP("audio");

	G_ShutdownDemo ();

	W_Shutdown ();
	DG_STEP("wad");

	R_ShutdownPlanes ();
	DG_STEP("visplanes+openings");

	R_ShutdownData ();
	DG_STEP("drawsegs");

	R_ShutdownThings ();
	DG_STEP("vissprites");

	R_ShutdownDraw ();

	if (DG_ScreenBuffer)
	{
		#ifdef ARDUINO
		heap_caps_free (DG_ScreenBuffer);
		#else
		free (DG_ScreenBuffer);
		#endif

		DG_ScreenBuffer = 0;
	}
	DG_STEP("screenbuffer");

	Z_Shutdown ();
	DG_STEP("zone");
}