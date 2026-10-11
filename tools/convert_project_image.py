#!/usr/bin/env python3
"""Convert transparent project artwork to 16-bit LVGL color plus alpha."""
from pathlib import Path
import argparse
import re
from PIL import Image, ImageOps


def rgb565_alpha(image, byte_swap=False):
    data=bytearray()
    for r,g,b,a in image.convert('RGBA').get_flattened_data():
        color=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        data.extend((color>>8,color&255,a) if byte_swap else (color&255,color>>8,a))
    return bytes(data)


def generate(source, destination, symbol='deedee_img', width=120, height=180):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',symbol):
        raise ValueError('Invalid C symbol')
    if min(width,height)<=4:
        raise ValueError('Image dimensions must allow a two-pixel border')
    with Image.open(source) as original:
        fitted=ImageOps.contain(original.convert('RGBA'),(width-4,height-4),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(width,height))
    canvas.paste(fitted,((width-fitted.width)//2,(height-fitted.height)//2))
    payload=rgb565_alpha(canvas)
    pixels=[]
    for i in range(0,len(payload),3):
        color=payload[i]|(payload[i+1]<<8)
        pixels.append(f'IMAGE_PIXEL(0x{color:04x}, 0x{payload[i+2]:02x})')
    rows=['    '+', '.join(pixels[i:i+4])+',' for i in range(0,len(pixels),4)]
    text="""#include "lvgl.h"

/* Match the selected LVGL 16-bit pixel byte order without changing artwork. */
#if LV_COLOR_16_SWAP
#define IMAGE_PIXEL(color, alpha) ((color) >> 8), ((color) & 0xff), (alpha)
#else
#define IMAGE_PIXEL(color, alpha) ((color) & 0xff), ((color) >> 8), (alpha)
#endif

"""
    text+=f'static const uint8_t {symbol}_data[{len(payload)}] = {{\n'
    text+='\n'.join(rows)+'\n};\n\n#undef IMAGE_PIXEL\n\n'
    text+=f"""const lv_img_dsc_t {symbol} = {{
    .header = {{
        .cf = LV_IMG_CF_TRUE_COLOR_ALPHA,
        .always_zero = 0,
        .reserved = 0,
        .w = {width},
        .h = {height},
    }},
    .data_size = {len(payload)},
    .data = {symbol}_data,
}};
"""
    Path(destination).write_text(text)
    return canvas


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source');parser.add_argument('destination')
    parser.add_argument('--symbol',default='deedee_img')
    args=parser.parse_args()
    generate(args.source,args.destination,args.symbol)
