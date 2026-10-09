#pragma once

#include <Arduino.h>
#include <IDoomInput.h>

// 8 plain GPIO buttons with INPUT_PULLUP (active low). No shift
// register, no I2C, nothing to solder besides the buttons themselves.
// Pins come from hw_conf.h.
class SimpleButtons : public IDoomInput
{
public:

    SimpleButtons(
        uint8_t pinUp, uint8_t pinDown, uint8_t pinLeft, uint8_t pinRight,
        uint8_t pinA, uint8_t pinB, uint8_t pinStart, uint8_t pinSelect)
    :   _pins{pinUp, pinDown, pinLeft, pinRight, pinA, pinB, pinStart, pinSelect}
    {
    }

    void begin() override
    {
        for (uint8_t p : _pins)
            pinMode(p, INPUT_PULLUP);
    }

    void update() override
    {
        _previous = _current;

        for (int i = 0; i < 8; i++)
        {
            // INPUT_PULLUP: pressed = LOW.
            bool held = (digitalRead(_pins[i]) == LOW);

            if (held) _current |= (1 << i);
            else      _current &= ~(1 << i);
        }
    }

    bool down(DoomButton b) override
    {
        return (_current & maskFor(b)) != 0;
    }

    bool pressed(DoomButton b) override
    {
        return (_current & maskFor(b)) && !(_previous & maskFor(b));
    }

    bool released(DoomButton b) override
    {
        return !(_current & maskFor(b)) && (_previous & maskFor(b));
    }

private:

    // WARNING: NEVER name this helper 'bit'. Arduino.h defines
    // '#define bit(b) (1UL << (b))' as a preprocessor macro, so any
    // function with that name gets clobbered before the compiler even
    // sees C++ (same problem with 'byte'/'word').
    static int maskFor(DoomButton b) { return 1 << (int)b; }

    uint8_t _pins[8];
    uint8_t _current = 0;
    uint8_t _previous = 0;
};
