#pragma once

#include <IDoomPCMOutput.h>

// DG_sound_module and DG_music_module are mandatory: the library ships
// with FEATURE_SOUND on, so if you don't define them in SOME .cpp of
// the project, the link fails.
//
// By default this is the "afternoon project" version: 8 SFX channels
// mixed with no EQ, no limiter, music silent (nothing emulates OPL
// here).
//
// If you want real music -- a synthesized MUS score, EQ tuned for a
// small speaker, a limiter -- define DOOM_MUSIC_SYNTH in your
// hw_conf.h. That flips this file over to use mus_synth.cpp/.h, which
// is a separate, self-contained module already proven in the
// Ultravice project. See mus_synth.h for what it does on its own.
//
// DG_PCM can be nullptr (DOOM_NO_AUDIO in hw_conf.h): in that case
// DoomSound_Init doesn't create the task and everything else is a
// no-op.
extern IDoomPCMOutput* DG_PCM;

void DoomSound_Init();
