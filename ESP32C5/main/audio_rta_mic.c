/* Original CYM microphone artwork, 14x21 monochrome. U+E100 only.
 * No existing glyph/font is replaced. Authored for this feature. */
#include "lvgl.h"
static const uint8_t bitmap[]={0x0,0x0,0x1e,0x0,0xfc,0x3,0xf0,0xf,0xc0,0x3f,0x0,0xfc,0x13,0xf2,0x4f,0xc9,0x3f,0x24,0xfc,0x91,0xe2,0x40,0x8,0x80,0x41,0xfe,0x0,0xc0,0x3,0x0,0xc,0x0,0x30,0x0,0xc0,0x1f,0xe0};
static bool glyph(const lv_font_t*f,lv_font_glyph_dsc_t*d,uint32_t c,uint32_t next){
 (void)f;(void)next;if(c!=0xe100)return false;
 d->adv_w=18;d->box_w=14;d->box_h=21;d->ofs_x=0;d->ofs_y=0;d->bpp=1;return true;
}
static const uint8_t*image(const lv_font_t*f,uint32_t c){(void)f;return c==0xe100?bitmap:NULL;}
const lv_font_t audio_rta_mic_font={.get_glyph_dsc=glyph,.get_glyph_bitmap=image,.line_height=21,.base_line=0};
