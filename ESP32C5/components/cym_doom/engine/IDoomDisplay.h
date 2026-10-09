#pragma once

#include <stdint.h>

// Minimal contract between the doomgeneric glue and the display.
//
// Designed row by row (not "give me the whole framebuffer") on
// purpose: it's the only contract that works both for a display with
// an intermediate framebuffer (Arduino_Canvas: begin/endFrame
// accumulate, the actual flush happens in endFrame) and for one
// without it (direct SPI push row by row, no double buffer).
//
// That second form is cheaper on RAM -- it's the first step toward
// PSRAM-less targets -- but today it still doesn't solve Doom's 6 MB
// zone, so on its own it doesn't run on an ESP32 classic. See the
// Roadmap in the README.
class IDoomDisplay
{
public:
    virtual bool begin() = 0;

    // Called once per Doom frame, before the first writeRow.
    // Canvas implementation: no-op. Without canvas: opens the address
    // window (setAddrWindow) for the panel area.
    virtual void beginFrame() = 0;

    // Draw 'count' pixels (already palette-converted to RGB565 by the
    // glue) starting at panel-absolute column 'x', on panel-absolute
    // row 'y'.
    //
    // This is intentionally dumb: an implementation never needs to
    // know about rescaling, panning, or cropping. DoomGlue.cpp works
    // all of that out (see its "Rescale / fill / crop" section and the
    // README's "Display scaling" section) and always hands you exact,
    // final panel coordinates and an exact pixel count -- just draw
    // it, starting there.
    virtual void writeRow(int x, int y, const uint16_t* rgb565, int count) = 0;

    // With canvas: the real flush() happens here. Without canvas:
    // no-op, everything was already written in writeRow.
    virtual void endFrame() = 0;

    virtual int width() const = 0;
    virtual int height() const = 0;

    virtual ~IDoomDisplay() {}
};
