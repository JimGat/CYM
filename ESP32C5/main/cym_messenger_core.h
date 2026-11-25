#ifndef CYM_MESSENGER_CORE_H
#define CYM_MESSENGER_CORE_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
/* Wire v1 is explicitly serialized, never a C structure. See the protocol plan. */
enum {CM_TEXT_MAX=160,CM_FRAME_MAX=234,CM_INBOX=4,CM_HEADER=42,CM_TAG=32};
typedef bool (*cm_auth_fn)(const uint8_t key[16],const uint8_t *data,size_t len,uint8_t out[32]);
typedef struct {uint8_t bytes[CM_FRAME_MAX];size_t len;} cm_frame;
typedef struct {char text[CM_TEXT_MAX+1];uint16_t len;uint32_t id;} cm_message;
typedef enum {CM_IDLE,CM_PENDING,CM_CONFIRMED,CM_UNCONFIRMED} cm_delivery;
typedef enum {CM_REJECTED,CM_HANDSHAKE,CM_ACCEPTED,CM_DUPLICATE,CM_DELIVERED,CM_OVERFLOW} cm_result;
typedef struct {
 uint8_t key[16],own_mac[6],peer_mac[6],local[16],remote[16],candidate[16],last_tag[32];
 bool ready,candidate_set;cm_auth_fn auth;uint32_t next_id,last_rx,pending_id,sent_at;
 unsigned attempts,in_head,in_count;cm_delivery delivery;cm_frame pending;
 cm_message inbox[CM_INBOX];
} cm_core;
bool cm_text_valid(const uint8_t *text,size_t len);
void cm_init(cm_core *c,const uint8_t key[16],const uint8_t own[6],const uint8_t peer[6],const uint8_t nonce[16],cm_auth_fn auth);
bool cm_hello(cm_core *c,cm_frame *out);
bool cm_submit(cm_core *c,const uint8_t *text,size_t len,uint32_t now,cm_frame *out);
bool cm_retry(cm_core *c,uint32_t now,cm_frame *out);
cm_result cm_receive(cm_core *c,const uint8_t source[6],const uint8_t *wire,size_t len,cm_frame *reply);
bool cm_pop(cm_core *c,cm_message *out);
#endif
