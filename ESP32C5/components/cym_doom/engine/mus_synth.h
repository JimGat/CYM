// Music synthesizer for ESP32-S3.
//
//  Reads MUS lumps from the WAD directly (MUS is simpler than MIDI, so
//  mus2mid.c isn't needed on this path) and synthesizes them with
//  pulse + noise oscillators.
//
//  Why chiptune instead of OPL emulation: a small speaker typically
//  starts rolling off around 1 kHz, and Doom's bass lives in the
//  82-165 Hz range. A square wave at 165 Hz puts harmonics at
//  495/825/1155/1485 Hz, and the ones that survive the filter are
//  enough for the ear to reconstruct the missing fundamental. The
//  fine FM timbres of an OPL chip would be lost through the same
//  filter.

#pragma once

#include <stdint.h>
#include <stddef.h>

bool MusSynth_Init(uint32_t sampleRate);

void MusSynth_Shutdown();

// data/len = raw MUS lump, exactly as S_ChangeMusic hands it over.
bool MusSynth_Register(const void* data, int len);

void MusSynth_Play(bool looping);

void MusSynth_Stop();

void MusSynth_Pause();

void MusSynth_Resume();

bool MusSynth_IsPlaying();

// volume 0-127, as sent by I_SetMusicVolume.
void MusSynth_SetVolume(int volume);

// Adds into acc (stereo interleaved, int32). Called from the mixer
// task, before the EQ: the music comes out through the same speaker.
void MusSynth_Render(int32_t* acc, size_t frames);

void MusSynth_Stats(int* peakVoices, uint32_t* steals);
