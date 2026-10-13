#ifndef GPS_RX_WS35_H
#define GPS_RX_WS35_H
#include <stdbool.h>
#include <stddef.h>
/* Single owner; completed line valid until next byte. Overflow waits for a new $. */
typedef struct { char line[256]; size_t used; } gps_rx_ws35_t;
static inline bool gps_rx_ws35_push(gps_rx_ws35_t *f, unsigned char c){
 if(c=='$'){f->used=0;f->line[f->used++]='$';return false;}
 if(!f->used)return false;
 if(c=='\r')return false;
 if(c=='\n'){f->line[f->used]=0;f->used=0;return true;}
 if(f->used>=sizeof(f->line)-1){f->used=0;return false;}
 f->line[f->used++]=(char)c;return false;
}
#endif
