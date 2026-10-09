#pragma once

#include <Arduino.h>

class Palette
{
public:

    bool load(const uint8_t *rgb);

    uint16_t color565(uint8_t index) const;

private:

    uint16_t colors[256];
};