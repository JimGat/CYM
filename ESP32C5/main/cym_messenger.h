#ifndef CYM_MESSENGER_H
#define CYM_MESSENGER_H
#include "cym_messenger_core.h"
/* Thin transport contract: only ESP-NOW currently implemented. Session-only keys. */
typedef struct {const char *name;bool implemented;unsigned max_bytes;} cym_message_backend;
extern const cym_message_backend cym_message_backends[5];
typedef struct {uint8_t peer[6],key[16],channel;} cym_messenger_config;
typedef enum {MSG_STOPPED,MSG_STARTING,MSG_WAITING,MSG_READY,MSG_BUSY,MSG_FAILED,MSG_STOPPING,MSG_RETAINED} cym_messenger_state;
typedef struct {cym_messenger_state state;cm_delivery delivery;bool can_send;uint8_t own_mac[6];uint32_t rx_dropped;int error;} cym_messenger_status;
bool cym_messenger_start(const cym_messenger_config *config);
void cym_messenger_stop(void);
bool cym_messenger_busy(void);
bool cym_messenger_send(const char *text,size_t len);
void cym_messenger_snapshot(cym_messenger_status *out);
bool cym_messenger_take(cm_message *out);
/* Key generation is a separate off-UI task, never logs or transmits the key. */
bool cym_messenger_key_request(void);
bool cym_messenger_info_request(void);
bool cym_messenger_key_take(char out[33]);
bool cym_messenger_parse_mac(const char *text,uint8_t out[6]);
bool cym_messenger_parse_key(const char *text,uint8_t out[16]);
#endif
