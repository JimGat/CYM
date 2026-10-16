#include "cym_camera.h"
#include "camera_backend.h"
#include <stdbool.h>
#include <stdlib.h>
struct cym_camera { void *backend; bool held; };
esp_err_t cym_camera_open(cym_camera_t **out,void *bus)
{
    if(!out || *out)return ESP_ERR_INVALID_ARG;
    cym_camera_t *c=calloc(1,sizeof(*c));if(!c)return ESP_ERR_NO_MEM;
    esp_err_t e=camera_backend_open(&c->backend,bus);
    /* Backend reports a retained handle if partial-init teardown cannot quiesce. */
    if(e && !c->backend){free(c);return e;}
    *out=c;return e;
}
esp_err_t cym_camera_acquire(cym_camera_t *c,cym_camera_frame_t *f,unsigned ms)
{
    if(!c||!f||ms>500)return ESP_ERR_INVALID_ARG;
    if(c->held)return ESP_ERR_INVALID_STATE;
    esp_err_t e=camera_backend_acquire(c->backend,f,ms);if(!e)c->held=true;return e;
}
void cym_camera_release(cym_camera_t *c)
{if(c&&c->held){camera_backend_release(c->backend);c->held=false;}}
esp_err_t cym_camera_close(cym_camera_t **c)
{
    if(!c || !*c)return ESP_OK;
    if((*c)->held)return ESP_ERR_INVALID_STATE;
    esp_err_t e=camera_backend_close((*c)->backend);
    if(!e){free(*c);*c=NULL;}return e;
}
