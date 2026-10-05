// Reusable logical viewport. No LVGL internal scaling or hardware dependency.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct { uint16_t width, height, scale; } cym_viewport_t;
static inline bool cym_viewport_valid(const cym_viewport_t *v) {
 return v && v->width && v->height && v->scale &&
        (uint32_t)v->width*v->scale <= UINT16_MAX &&
        (uint32_t)v->height*v->scale <= UINT16_MAX;
}
static inline bool cym_viewport_touch(const cym_viewport_t *v, uint16_t px,
 uint16_t py, uint16_t *x, uint16_t *y) {
 if(!cym_viewport_valid(v) || !x || !y || px >= (uint32_t)v->width*v->scale ||
    py >= (uint32_t)v->height*v->scale) return false;
 *x=px/v->scale; *y=py/v->scale; return true;
}
static inline bool cym_viewport_expand_rgb565(const cym_viewport_t *v,
 const uint16_t *src, uint16_t *dst) {
 if(!cym_viewport_valid(v) || !src || !dst) return false;
 size_t stride=(size_t)v->width*v->scale;
 for(size_t y=0;y<v->height;y++) {
  uint16_t *row=dst+y*v->scale*stride;
  for(size_t x=0;x<v->width;x++)
   for(size_t sx=0;sx<v->scale;sx++) row[x*v->scale+sx]=src[y*v->width+x];
  for(size_t sy=1;sy<v->scale;sy++) memcpy(row+sy*stride,row,stride*sizeof(*row));
 }
 return true;
}
