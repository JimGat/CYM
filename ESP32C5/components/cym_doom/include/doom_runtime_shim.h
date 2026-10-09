/* Force-included ONLY for engine objects, never CYM, libc, LVGL or this adapter.
 * All engine-owned allocation and filesystem effects pass through this boundary.
 */
#ifndef CYM_DOOM_RUNTIME_SHIM_H
#define CYM_DOOM_RUNTIME_SHIM_H
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <sys/stat.h>
#include <esp_heap_caps.h>
_Noreturn void doom_engine_fail(const char *);
_Noreturn void doom_engine_exit(int);
void *doom_owned_malloc(size_t);
void *doom_owned_calloc(size_t,size_t);
void *doom_owned_realloc(void *,size_t);
void doom_owned_free(void *);
FILE *doom_owned_fopen(const char *,const char *);
int doom_owned_fclose(FILE *);
size_t doom_owned_fread(void *,size_t,size_t,FILE *);
int doom_owned_fseek(FILE *,long,int);
long doom_owned_ftell(FILE *);
int doom_owned_forbidden(const char *);
int doom_owned_rename(const char *,const char *);
char *doom_owned_getenv(const char *);
#define malloc doom_owned_malloc
#define calloc doom_owned_calloc
#define realloc doom_owned_realloc
#define free doom_owned_free
#define heap_caps_malloc(n,c) doom_owned_malloc(n)
#define heap_caps_calloc(n,s,c) doom_owned_calloc(n,s)
#define heap_caps_free doom_owned_free
#define fopen doom_owned_fopen
#define fclose doom_owned_fclose
#define fread doom_owned_fread
#define fseek doom_owned_fseek
#define ftell doom_owned_ftell
#define exit doom_engine_exit
#define abort() doom_engine_fail("Engine abort requested")
#define system doom_owned_forbidden
#define remove doom_owned_forbidden
#define unlink doom_owned_forbidden
#define rename doom_owned_rename
#define getenv doom_owned_getenv
/* Config/save directories are deliberately not created by this lab engine. */
#define mkdir(path,mode) (0)
#endif
