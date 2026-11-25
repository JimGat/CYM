#include "cym_messenger_core.h"
#include <string.h>
_Static_assert(CM_HEADER+CM_TEXT_MAX+CM_TAG==CM_FRAME_MAX,"wire MTU accounting");
_Static_assert(CM_FRAME_MAX<=250,"ESP-NOW v1 common MTU");
enum {HELLO=1,CHALLENGE,READY,DATA,ACK};
/* Constant-time tag comparison: never disclose a matching-prefix timing oracle. */
static bool same(const uint8_t *a,const uint8_t *b,size_t n){uint8_t d=0;for(size_t i=0;i<n;i++)d|=a[i]^b[i];return d==0;}
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static void put32(uint8_t *p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
/* Strict UTF-8 scalars; reject controls, NUL, LVGL recolor delimiters, bidi and
 * invisible direction controls. Font glyph coverage is deliberately not implied. */
bool cm_text_valid(const uint8_t *p,size_t n){
 if(!p||!n||n>CM_TEXT_MAX)return false;
 for(size_t i=0;i<n;){uint32_t u=p[i++];unsigned more=0;uint32_t min=0;
  if(u<0x80){if(u<0x20||u==0x7f||u=='#')return false;continue;}
  if(u>=0xc2&&u<=0xdf){u&=31;more=1;min=0x80;}
  else if(u>=0xe0&&u<=0xef){u&=15;more=2;min=0x800;}
  else if(u>=0xf0&&u<=0xf4){u&=7;more=3;min=0x10000;}else return false;
  if(n-i<more)return false;
  while(more--){uint8_t x=p[i++];if((x&0xc0)!=0x80)return false;u=(u<<6)|(x&63);}
  if(u<min||u>0x10ffff||(u>=0xd800&&u<=0xdfff)||(u>=0x80&&u<=0x9f)||
     (u>=0x2028&&u<=0x202e)||(u>=0x2066&&u<=0x2069)||u==0xfeff)return false;
 }return true;
}
void cm_init(cm_core *c,const uint8_t k[16],const uint8_t own[6],const uint8_t peer[6],const uint8_t nonce[16],cm_auth_fn auth){
 memset(c,0,sizeof(*c));memcpy(c->key,k,16);memcpy(c->own_mac,own,6);memcpy(c->peer_mac,peer,6);memcpy(c->local,nonce,16);c->auth=auth;c->next_id=1;
}
/* Domain separation and both MACs prevent reflection, cross-peer and cross-app
 * tag reuse. The SDK encrypts unicast; HMAC additionally authenticates callbacks
 * that provide no trusted encryption indication. */
static bool tag(cm_core *c,bool tx,const uint8_t *p,size_t n,uint8_t out[32]){
 static const uint8_t domain[]="CYM-MSG-v1";uint8_t input[sizeof(domain)-1+12+CM_HEADER+CM_TEXT_MAX];size_t off=sizeof(domain)-1;
 memcpy(input,domain,off);memcpy(input+off,tx?c->own_mac:c->peer_mac,6);off+=6;
 memcpy(input+off,tx?c->peer_mac:c->own_mac,6);off+=6;memcpy(input+off,p,n);
 bool ok=c->auth&&c->auth(c->key,input,off+n,out);memset(input,0,sizeof(input));return ok;
}
static bool frame(cm_core *c,unsigned type,const uint8_t dest[16],uint32_t id,const uint8_t *body,size_t n,cm_frame *out){
 out->len=0;if(n>CM_TEXT_MAX)return false;uint8_t *p=out->bytes;
 p[0]='C';p[1]='M';p[2]=1;p[3]=type;memcpy(p+4,c->local,16);memcpy(p+20,dest,16);put32(p+36,id);p[40]=n>>8;p[41]=n;
 if(n)memcpy(p+CM_HEADER,body,n);
 if(!tag(c,true,p,CM_HEADER+n,p+CM_HEADER+n))return false;
 out->len=CM_HEADER+n+CM_TAG;return true;
}
bool cm_hello(cm_core *c,cm_frame *out){const uint8_t zero[16]={0};return frame(c,HELLO,zero,0,NULL,0,out);}
bool cm_submit(cm_core *c,const uint8_t *text,size_t n,uint32_t now,cm_frame *out){
 out->len=0;if(!c->ready||c->delivery==CM_PENDING||c->next_id==UINT32_MAX||!cm_text_valid(text,n))return false;
 if(!frame(c,DATA,c->remote,c->next_id,text,n,out))return false;
 c->pending=*out;c->pending_id=c->next_id++;c->sent_at=now;c->attempts=1;c->delivery=CM_PENDING;return true;
}
bool cm_retry(cm_core *c,uint32_t now,cm_frame *out){
 out->len=0;if(c->delivery!=CM_PENDING||(uint32_t)(now-c->sent_at)<800)return false;
 if(c->attempts>=3){c->delivery=CM_UNCONFIRMED;return false;}
 c->attempts++;c->sent_at=now;*out=c->pending;return true;
}
cm_result cm_receive(cm_core *c,const uint8_t source[6],const uint8_t *p,size_t len,cm_frame *reply){
 reply->len=0;if(!p||!source||len<CM_HEADER+CM_TAG||len>CM_FRAME_MAX||memcmp(source,c->peer_mac,6)||p[0]!='C'||p[1]!='M'||p[2]!=1)return CM_REJECTED;
 unsigned type=p[3];size_t n=((size_t)p[40]<<8)|p[41];uint32_t id=get32(p+36);uint8_t mac[32];
 if(n>CM_TEXT_MAX||len!=CM_HEADER+n+CM_TAG||!tag(c,false,p,CM_HEADER+n,mac)||!same(mac,p+CM_HEADER+n,32))return CM_REJECTED;
 const uint8_t zero[16]={0};if(same(p+4,zero,16))return CM_REJECTED;
 if(type==HELLO){
  if(n||id||!same(p+20,zero,16)||(c->ready&&!same(p+4,c->remote,16)))return CM_REJECTED;
  if(!c->ready){memcpy(c->candidate,p+4,16);c->candidate_set=true;}
  return frame(c,CHALLENGE,p+4,0,NULL,0,reply)?CM_HANDSHAKE:CM_REJECTED;
 }
 if(!same(p+20,c->local,16))return CM_REJECTED;
 if(type==CHALLENGE){
  if(n||id||(c->ready&&!same(p+4,c->remote,16)))return CM_REJECTED;
  memcpy(c->remote,p+4,16);c->ready=true;
  return frame(c,READY,c->remote,0,NULL,0,reply)?CM_HANDSHAKE:CM_REJECTED;
 }
 if(type==READY){
  if(n||id||(!c->ready&&(!c->candidate_set||!same(p+4,c->candidate,16)))||(c->ready&&!same(p+4,c->remote,16)))return CM_REJECTED;
  memcpy(c->remote,p+4,16);c->ready=true;return CM_HANDSHAKE;
 }
 if(!c->ready||!same(p+4,c->remote,16)||!id)return CM_REJECTED;
 if(type==ACK){
  if(n!=32||c->delivery!=CM_PENDING||id!=c->pending_id||!same(p+CM_HEADER,c->pending.bytes+c->pending.len-CM_TAG,CM_TAG))return CM_REJECTED;
  c->delivery=CM_CONFIRMED;return CM_DELIVERED;
 }
 if(type!=DATA||!cm_text_valid(p+CM_HEADER,n))return CM_REJECTED;
 if(id==c->last_rx){
  if(!same(p+CM_HEADER+n,c->last_tag,CM_TAG))return CM_REJECTED;
  return frame(c,ACK,c->remote,id,c->last_tag,32,reply)?CM_DUPLICATE:CM_REJECTED;
 }
 if(id<c->last_rx)return CM_REJECTED;
 if(c->in_count==CM_INBOX)return CM_OVERFLOW;
 /* Construct ACK before accepting, but only publish it once inbox owns text. */
 if(!frame(c,ACK,c->remote,id,p+CM_HEADER+n,32,reply))return CM_REJECTED;
 cm_message *m=&c->inbox[(c->in_head+c->in_count)%CM_INBOX];memcpy(m->text,p+CM_HEADER,n);m->text[n]=0;m->len=n;m->id=id;c->in_count++;
 c->last_rx=id;memcpy(c->last_tag,p+CM_HEADER+n,32);return CM_ACCEPTED;
}
bool cm_pop(cm_core *c,cm_message *out){if(!c->in_count)return false;*out=c->inbox[c->in_head];memset(&c->inbox[c->in_head],0,sizeof(*out));c->in_head=(c->in_head+1)%CM_INBOX;c->in_count--;return true;}
