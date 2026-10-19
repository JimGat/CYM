"""Fault boundary for the production RTA gain store (not alternate store logic)."""
def write_nvs_stub(directory):
 (directory/'nvs.h').write_text(r"""
#pragma once
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef unsigned nvs_handle_t;
#define NVS_READONLY 0
#define NVS_READWRITE 1
#define ESP_ERR_NVS_NOT_FOUND 101
static int nvs_open_error,nvs_read_error,nvs_set_error,nvs_commit_error;
static int nvs_value=24,nvs_present,nvs_pending,nvs_sets,nvs_commits,nvs_opens,nvs_closes;
static int nvs_open(const char*n,int mode,nvs_handle_t*h){assert(!strcmp(n,"audio_rta"));(void)mode;nvs_opens++;if(nvs_open_error)return nvs_open_error;*h=1;return 0;}
static int nvs_get_i32(nvs_handle_t h,const char*k,int32_t*v){assert(h==1&&!strcmp(k,"gain_db"));if(nvs_read_error)return nvs_read_error;if(!nvs_present)return ESP_ERR_NVS_NOT_FOUND;*v=nvs_value;return 0;}
static int nvs_set_i32(nvs_handle_t h,const char*k,int32_t v){assert(h==1&&!strcmp(k,"gain_db"));nvs_sets++;if(nvs_set_error)return nvs_set_error;nvs_pending=v;return 0;}
static int nvs_commit(nvs_handle_t h){assert(h==1);nvs_commits++;if(nvs_commit_error)return nvs_commit_error;nvs_value=nvs_pending;nvs_present=1;return 0;}
static void nvs_close(nvs_handle_t h){assert(h==1);nvs_closes++;}
""")
