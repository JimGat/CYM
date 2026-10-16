"""Run the authentic UI stop function with a deterministic worker completion boundary."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
def body(text,name):
 start=text.index('void '+name+'(');a=text.index('{',start);depth=1;i=a+1
 while depth:
  if text[i]=='{':depth+=1
  if text[i]=='}':depth-=1
  i+=1
 return text[start:i]
class UiStop(unittest.TestCase):
 def test_completed_delayed_and_unquiesced_workers(self):
  source=body((ROOT/'ESP32C5/main/qr_decoder_ui.c').read_text(),'qr_decoder_ui_stop')
  pre=r"""
#include <assert.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdlib.h>
typedef struct {atomic_bool cancel,done;void *camera;int image;} qr_session_t;
static qr_session_t *session;
static void *poll_timer,*status_label,*result_label,*preview,*retry_button;
static int ticks,complete_at,disposed,detached,timer_deleted,cache_invalidated;
#define pdMS_TO_TICKS(x) (x)
static void lv_timer_del(void *p){assert(p);timer_deleted++;}
static void lv_label_set_text_static(void *p,const char *s){assert(p);assert(!*s);detached++;}
static void lv_img_set_src(void *p,void *s){assert(p);assert(!s);detached++;}
static void lv_img_cache_invalidate_src(void *p){assert(p);cache_invalidated++;}
static void vTaskDelay(int n){assert(n==10);ticks++;if(ticks==complete_at)atomic_store(&session->done,true);}
static void dispose(qr_session_t *s){assert(!s->camera);assert(atomic_load(&s->done));disposed++;free(s);}
static void setup(bool done,bool camera,int at){session=calloc(1,sizeof(*session));atomic_store(&session->done,done);session->camera=camera?(void*)1:NULL;poll_timer=status_label=result_label=preview=retry_button=(void*)1;ticks=disposed=detached=timer_deleted=cache_invalidated=0;complete_at=at;}
"""
  post=r"""
int main(void){
 setup(true,false,0);qr_decoder_ui_stop();assert(!session&&disposed==1&&ticks==0&&detached==2&&timer_deleted==1&&cache_invalidated==1);assert(!status_label&&!result_label&&!preview&&!retry_button&&!poll_timer);
 setup(false,false,5);qr_decoder_ui_stop();assert(!session&&disposed==1&&ticks==5);
 setup(false,false,0);qr_decoder_ui_stop();assert(session&&atomic_load(&session->cancel)&&ticks==300&&!disposed);free(session);session=NULL;
 setup(true,true,0);qr_decoder_ui_stop();assert(session&&!disposed&&atomic_load(&session->cancel));free(session);session=NULL;
 qr_decoder_ui_stop();return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(pre+source+post)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
