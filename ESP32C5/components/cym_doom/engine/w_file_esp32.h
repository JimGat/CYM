#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include "w_file.h"

int DG_FileExists(const char *path);

void *DG_FileOpen(const char *path);

void DG_FileClose(void *handle);

size_t DG_FileRead(
    void *handle,
    void *buffer,
    size_t len);

int DG_FileSeek(
    void *handle,
    unsigned int offset);

unsigned int DG_FileSize(
    void *handle);

extern wad_file_class_t esp32_wad_file;

#ifdef __cplusplus
}
#endif