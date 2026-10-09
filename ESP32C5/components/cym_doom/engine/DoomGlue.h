#pragma once

#include <IDoomDisplay.h>
#include <IDoomInput.h>

// Connection point between doomgeneric.h and your hardware. Neither
// CanvasDisplay nor DirectDisplay touch this file: they just assign
// these pointers before doomgeneric_Create() and that's it.
extern IDoomDisplay* DG_Display;
extern IDoomInput*   DG_Input;

// Rebuilds the enter/exit cycle without rebooting the ESP32: calls
// doomgeneric_Create/doomgeneric_Tick/doomgeneric_Shutdown for you.
// See each example's .ino for the full usage pattern.
void DoomGlue_Begin(const char* wadPath);
void DoomGlue_Tick();
void DoomGlue_Shutdown();
