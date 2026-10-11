/* CYM game integration; GPL-2.0-or-later. See LICENSE.engine and NOTICE.md. */
/* WS-only linker admission wrappers. All /sdcard stdio/FD opens retain an
 * admission until AFTER real close. Transient mutators retain it until return.
 * Read handles also block reset (conservative), no live owner is stopped.
 * Special raw FAT format/mount paths are separately named/refused by main.
 * Bound table avoids allocator retention. No wrapping on other board profiles. */
#include "storage_gate.h"
#include "freertos/FreeRTOS.h"
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdarg.h>
#include <string.h>
#define HANDLES 32
static struct {bool used;FILE *file;int fd;} owners[HANDLES];
static portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;
static bool sd_path(const char *p){return p && !strncmp(p,"/sdcard",7) && (p[7]=='/' || p[7]=='\0');}
static int reserve(void)
{
 if(!storage_gate_enter()){errno=EBUSY;return -1;}
 int slot=-1;portENTER_CRITICAL(&mux);
 for(int i=0;i<HANDLES;i++)if(!owners[i].used){owners[i].used=true;owners[i].file=NULL;owners[i].fd=-1;slot=i;break;}
 portEXIT_CRITICAL(&mux);
 if(slot<0){storage_gate_leave();errno=EMFILE;}
 return slot;
}
static void retire(int slot)
{
 portENTER_CRITICAL(&mux);owners[slot].used=false;owners[slot].file=NULL;owners[slot].fd=-1;portEXIT_CRITICAL(&mux);
 storage_gate_leave();
}
FILE *__real_fopen(const char *,const char *);
int __real_fclose(FILE *);
int __real_open(const char *,int,...);
int __real_close(int);
int __real_mkdir(const char *,mode_t);
int __real_unlink(const char *);
int __real_remove(const char *);
int __real_rmdir(const char *);
int __real_rename(const char *,const char *);
FILE *__wrap_fopen(const char *path,const char *mode)
{
 if(!sd_path(path))return __real_fopen(path,mode);
 int slot=reserve();if(slot<0)return NULL;
 FILE *f=__real_fopen(path,mode);
 if(!f){retire(slot);return NULL;}
 portENTER_CRITICAL(&mux);owners[slot].file=f;portEXIT_CRITICAL(&mux);return f;
}
int __wrap_fclose(FILE *f)
{
 int slot=-1;portENTER_CRITICAL(&mux);
 for(int i=0;i<HANDLES;i++)if(owners[i].used && owners[i].file==f){slot=i;break;}
 portEXIT_CRITICAL(&mux);
 int rc=__real_fclose(f); /* libc flush/close is part of live admission */
 if(slot>=0 && rc==0)retire(slot);
 return rc;
}
int __wrap_open(const char *path,int flags,...)
{
 mode_t mode=0;if(flags&O_CREAT){va_list args;va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
 if(!sd_path(path))return __real_open(path,flags,mode);
 int slot=reserve();if(slot<0)return -1;
 int fd=__real_open(path,flags,mode);
 if(fd<0){retire(slot);return -1;}
 portENTER_CRITICAL(&mux);owners[slot].fd=fd;portEXIT_CRITICAL(&mux);return fd;
}
int __wrap_close(int fd)
{
 int slot=-1;portENTER_CRITICAL(&mux);
 for(int i=0;i<HANDLES;i++)if(owners[i].used && owners[i].fd==fd){slot=i;break;}
 portEXIT_CRITICAL(&mux);
 int rc=__real_close(fd);if(slot>=0 && rc==0)retire(slot);
 return rc;
}
#define MUTATOR(name,type) int __wrap_##name(const char *p,type mode){if(!sd_path(p))return __real_##name(p,mode);if(!storage_gate_enter()){errno=EBUSY;return -1;}int rc=__real_##name(p,mode);storage_gate_leave();return rc;}
MUTATOR(mkdir,mode_t)
#define ONE_PATH(name) int __wrap_##name(const char *p){if(!sd_path(p))return __real_##name(p);if(!storage_gate_enter()){errno=EBUSY;return -1;}int rc=__real_##name(p);storage_gate_leave();return rc;}
ONE_PATH(unlink)
ONE_PATH(remove)
ONE_PATH(rmdir)
int __wrap_rename(const char *a,const char *b)
{
 if(!sd_path(a)&&!sd_path(b))return __real_rename(a,b);
 if(!storage_gate_enter()){errno=EBUSY;return -1;}
 int rc=__real_rename(a,b);storage_gate_leave();return rc;
}
