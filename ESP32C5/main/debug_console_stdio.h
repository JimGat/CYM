/* Match installed IDF linenoise stdio ABI without private include paths.
 * Picolibc globals are not task-local, even in Newlib compatibility mode.
 * Newlib uses per-task reentrancy; pure Picolibc linenoise owns its TLS. */
#ifndef CYM_DEBUG_CONSOLE_STDIO_H
#define CYM_DEBUG_CONSOLE_STDIO_H
#include <stdio.h>
#ifdef ESP_PLATFORM
#include "sdkconfig.h"
#endif
#if CONFIG_LIBC_PICOLIBC
#if CONFIG_LIBC_PICOLIBC_NEWLIB_COMPATIBILITY
extern __thread FILE *tls_stdin;
extern __thread FILE *tls_stdout;
#define CYM_CONSOLE_IN tls_stdin
#define CYM_CONSOLE_OUT tls_stdout
#else
extern __thread FILE *linenoise_stdin;
extern __thread FILE *linenoise_stdout;
#define CYM_CONSOLE_IN linenoise_stdin
#define CYM_CONSOLE_OUT linenoise_stdout
#endif
#else
#define CYM_CONSOLE_IN stdin
#define CYM_CONSOLE_OUT stdout
#endif
static inline void cym_console_bind(FILE *in, FILE *out)
{
    CYM_CONSOLE_IN=in;
    CYM_CONSOLE_OUT=out;
}
static inline FILE *cym_console_output(void)
{
    return CYM_CONSOLE_OUT ? CYM_CONSOLE_OUT : stdout;
}
#endif
