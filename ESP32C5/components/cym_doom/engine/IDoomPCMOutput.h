#pragma once

#include <stdint.h>
#include <stddef.h>

// Minimal audio output contract for the examples: raw PCM, no MP3
// player layered on top (that's IAudio in the Ultravice project,
// meant for its own music player -- you don't need it to run Doom).
//
// 'write' receives MONO 16-bit samples. If your DAC/I2S is stereo,
// duplicate L=R in your implementation; that's simpler than forcing
// everyone to think in stereo for a game that's mono to begin with.
//
// If your board has no audio, define DOOM_NO_AUDIO in hw_conf.h: the
// glue leaves DG_PCM as nullptr and the game runs silent, without
// touching this file.
class IDoomPCMOutput
{
public:
    virtual bool begin(uint32_t sampleRate) = 0;

    virtual void write(const int16_t *samples, size_t count) = 0;

    virtual void end() = 0;

    virtual ~IDoomPCMOutput() {}
};
