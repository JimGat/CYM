#include "cym_qr_zxing.h"
#include "cym_zx_alloc.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>
#include <climits>
#include <cstdlib>
#include <algorithm>
static std::string token(std::istream &f){std::string s;while(f>>s){if(s[0]=='#'){std::getline(f,s);continue;}return s;}return {};}
int main(int argc,char **argv) {
 cym_zx_config_t cfg={1,1024,1024,1,1,1,1};cym_zx_t *q=nullptr;
 if(argc==3&&std::string(argv[1])=="--coldfail") {
  cym_zx_test_fail_after(std::strtol(argv[2],nullptr,10),0);
  auto rc=cym_zx_create(&cfg,&q);assert(rc==CYM_ZX_NO_MEMORY||rc==CYM_ZX_OK);
  if(q)assert(cym_zx_destroy(q)==CYM_ZX_OK);
  cym_zx_test_fail_after(-1,0);assert(cym_zx_create(&cfg,&q)==CYM_ZX_OK);
  assert(cym_zx_destroy(q)==CYM_ZX_OK);return 0;
 }
 assert(argc==3);assert(cym_zx_create(nullptr,&q)==CYM_ZX_ARGUMENT&&!q);
 auto bad=cfg;bad.abi_version=2;assert(cym_zx_create(&bad,&q)==CYM_ZX_ARGUMENT);
 bad=cfg;bad.try_harder=2;assert(cym_zx_create(&bad,&q)==CYM_ZX_ARGUMENT);
 assert(cym_zx_create(&cfg,nullptr)==CYM_ZX_ARGUMENT);
 assert(cym_zx_destroy(nullptr)==CYM_ZX_OK);
 assert(cym_zx_create(&cfg,&q)==CYM_ZX_OK);
 std::vector<unsigned char> out(8896,0xa5),gray(32*32,255);cym_zx_result_t r;
 assert(cym_zx_decode(q,gray.data(),gray.size(),32,32,32,out.data(),out.size(),&r)==CYM_ZX_NOT_FOUND);
 assert(!r.valid&&!r.length&&out[0]==0xa5);
 assert(cym_zx_decode(q,gray.data(),0,32,32,32,out.data(),out.size(),&r)==CYM_ZX_ARGUMENT);
 assert(cym_zx_decode(q,gray.data(),gray.size(),0,32,32,out.data(),out.size(),&r)==CYM_ZX_ARGUMENT);
 assert(cym_zx_decode(q,gray.data(),gray.size(),32,32,31,out.data(),out.size(),&r)==CYM_ZX_ARGUMENT);
 assert(cym_zx_decode(q,gray.data(),SIZE_MAX,32,32,SIZE_MAX,out.data(),out.size(),&r)==CYM_ZX_ARGUMENT);
 assert(cym_zx_decode(nullptr,gray.data(),gray.size(),32,32,32,out.data(),out.size(),&r)==CYM_ZX_ARGUMENT);
 for(int f=0;f<2;f++) {
  std::ifstream in(argv[f+1],std::ios::binary);assert(in);assert(token(in)=="P5");
  int w=std::stoi(token(in)),h=std::stoi(token(in));assert(token(in)=="255");in.get();
  std::vector<uint8_t> img(w*h);in.read(reinterpret_cast<char*>(img.data()),img.size());assert(in.gcount()==static_cast<long>(img.size()));
  for(int repeat=0;repeat<2;repeat++) {
   auto rc=cym_zx_decode(q,img.data(),img.size(),w,h,w,out.data(),out.size(),&r);
   assert(rc==(f?CYM_ZX_OK:CYM_ZX_NOT_FOUND));assert(r.valid==static_cast<unsigned>(f));assert(r.length==static_cast<size_t>(f?29:0));
   std::printf("frame=%d pass=%d status=%d valid=%u length=%zu\n",f,repeat,rc,r.valid,r.length);
  }
  // Padded stride exercises the very same input interface, no repacked decoder.
  std::vector<uint8_t> padded((w+17)*h,0x5a);
  for(int y=0;y<h;y++)std::copy_n(img.data()+y*w,w,padded.data()+y*(w+17));
  assert(cym_zx_decode(q,padded.data(),padded.size(),w,h,w+17,out.data(),out.size(),&r)==(f?CYM_ZX_OK:CYM_ZX_NOT_FOUND));
  if(f) {
   std::fill(out.begin(),out.end(),0xa5);
   assert(cym_zx_decode(q,img.data(),img.size(),w,h,w,out.data(),28,&r)==CYM_ZX_OUTPUT_SMALL);
   assert(r.length==29&&!r.valid);for(auto x:out)assert(x==0xa5);
   assert(cym_zx_decode(q,img.data(),img.size(),w,h,w,out.data(),29,&r)==CYM_ZX_OK&&r.length==29);
   // Fail every imported allocation early in a real successful-frame decode.
   for(int i=0;i<120;i++) {
    cym_zx_test_fail_after(i,0);auto rc=cym_zx_decode(q,img.data(),img.size(),w,h,w,out.data(),out.size(),&r);
    assert(rc==CYM_ZX_NO_MEMORY||rc==CYM_ZX_OK||rc==CYM_ZX_NOT_FOUND);
   }
   cym_zx_test_fail_after(0,1);
   assert(cym_zx_decode(q,img.data(),img.size(),w,h,w,out.data(),out.size(),&r)==CYM_ZX_EXCEPTION);
   cym_zx_test_fail_after(-1,0);
   assert(cym_zx_decode(q,img.data(),img.size(),w,h,w,out.data(),out.size(),&r)==CYM_ZX_OK);
  }
 }
 assert(cym_zx_destroy(q)==CYM_ZX_OK);
 auto retained=cym_zx_alloc_stats().live;
 // Caller STL operations must not bind to decoder's private COMDAT allocator.
 auto before_caller=cym_zx_alloc_stats().calls;
 {std::vector<unsigned char> caller(65536,7);std::string text(512,'q');assert(caller[0]==7&&text.size()==512);}
 assert(cym_zx_alloc_stats().calls==before_caller);
 for(int i=0;i<20;i++){assert(cym_zx_create(&cfg,&q)==CYM_ZX_OK);assert(cym_zx_destroy(q)==CYM_ZX_OK);}
 assert(cym_zx_alloc_stats().live==retained);
 auto a=cym_zx_alloc_stats();std::printf("native-contract PASS failures=%zu live_process_tables=%zu peak=%zu calls=%zu foreign_frees=%zu\n",a.failures,a.live,a.peak,a.calls,a.foreign_frees);
}
