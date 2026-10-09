#pragma once

// Minimal input contract for the examples. Deliberately identical in
// shape to the Ultravice project's IInput (Button + begin/update/
// pressed/released/down), but without depending on a multiplexer: the
// example implementation (SimpleButtons) reads plain GPIO with
// INPUT_PULLUP. If your hardware uses an HC165 or something else,
// you only change SimpleButtons.*, never DoomGlue.

enum class DoomButton
{
    Up, Down, Left, Right,
    A, B, Start, Select
};

class IDoomInput
{
public:
    virtual void begin() = 0;

    // Call it once per poll: it computes edges against the previous
    // reading. DoomGlue already does this for you, no need to call it
    // separately.
    virtual void update() = 0;

    virtual bool down(DoomButton button) = 0;
    virtual bool pressed(DoomButton button) = 0;
    virtual bool released(DoomButton button) = 0;

    virtual ~IDoomInput() {}
};
