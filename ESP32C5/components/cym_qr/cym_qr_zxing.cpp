#include "cym_qr_zxing.h"
#include "ReadBarcode.h"
#include "qrcode/QRVersion.h"
#include "ReedSolomon.h"
#include <atomic>
#include <climits>
#include <cstring>
#include <new>
struct cym_zx { cym_zx_config_t config; };
namespace {
// Nonblocking engine serialization; retain standard toolchain ABI guards.
std::atomic_flag engine_busy=ATOMIC_FLAG_INIT;
struct Lock { bool held=!engine_busy.test_and_set(std::memory_order_acquire);
 ~Lock(){if(held)engine_busy.clear(std::memory_order_release);} };
bool valid_config(const cym_zx_config_t *c) {
 return c&&c->abi_version==1&&c->max_width>0&&c->max_height>0&&
 c->max_width<=1024&&c->max_height<=1024&&c->try_harder<=1&&c->try_rotate<=1&&c->try_invert<=1&&c->try_downscale<=1;
}
}
extern "C" const char *cym_zx_identity(void){return "ZXing-C++/3.1.1@287c85df QR-only zx1";}
extern "C" cym_zx_status_t cym_zx_create(const cym_zx_config_t *c,cym_zx_t **out) {
 if(!out)return CYM_ZX_ARGUMENT;*out=nullptr;if(!valid_config(c))return CYM_ZX_ARGUMENT;
 Lock lock;if(!lock.held)return CYM_ZX_BUSY;
 try {
  // Warm exception TLS before DMA pressure; this is not an OOM guarantee.
  try {throw 1;} catch(int) {}
  ZXing::QRCode::Version::Model2(1);ZXing::QRCode::Version::Model1(1);
  ZXing::QRCode::Version::Micro(1);ZXing::QRCode::Version::rMQR(1);
  uint8_t warm[3]={0,0,0};
  ZXing::ReedSolomonDecode(ZXing::RSField::QRCode, std::span<uint8_t>(warm), 2);
  *out=new cym_zx{*c};return CYM_ZX_OK;
 } catch(const std::bad_alloc&) {return CYM_ZX_NO_MEMORY;}catch(...) {return CYM_ZX_EXCEPTION;}
}
extern "C" cym_zx_status_t cym_zx_destroy(cym_zx_t *q) {
 if(!q)return CYM_ZX_OK;Lock lock;if(!lock.held)return CYM_ZX_BUSY;
 try {delete q;return CYM_ZX_OK;}catch(...) {return CYM_ZX_EXCEPTION;}
}
extern "C" cym_zx_status_t cym_zx_decode(cym_zx_t *q,const uint8_t *gray,size_t bytes,
 int w,int h,size_t stride,uint8_t *out,size_t cap,cym_zx_result_t *r) {
 if(!r)return CYM_ZX_ARGUMENT;*r={CYM_ZX_ARGUMENT,0,0,0};
 if(!q||!gray||!out||w<1||h<1||w>q->config.max_width||h>q->config.max_height||
 stride<static_cast<size_t>(w)||stride>INT_MAX||
 (h>1&&stride>(SIZE_MAX-static_cast<size_t>(w))/static_cast<size_t>(h-1))||
 bytes<static_cast<size_t>(h-1)*stride+static_cast<size_t>(w))return r->status;
 Lock lock;if(!lock.held)return r->status=CYM_ZX_BUSY;
 try {
  const auto &c=q->config;
  auto opts=ZXing::ReaderOptions().setFormats(ZXing::BarcodeFormat::QRCode)
   .setTryHarder(c.try_harder).setTryRotate(c.try_rotate).setTryInvert(c.try_invert)
   .setTryDownscale(c.try_downscale).setMaxNumberOfSymbols(8).setReturnErrors(false);
  const auto codes=ZXing::ReadBarcodes(ZXing::ImageView(gray,w,h,ZXing::ImageFormat::Lum,static_cast<int>(stride)),opts);
  r->candidates=static_cast<uint32_t>(codes.size());
  const ZXing::Barcode *best=nullptr;int64_t distance=INT64_MAX;
  for(const auto &code:codes) {
   if(!code.isValid()||code.format()!=ZXing::BarcodeFormat::QRCode)continue;
   int64_t x=0,y=0;for(const auto &p:code.position()){x+=p.x;y+=p.y;}
   x=x/4-w/2;y=y/4-h/2;int64_t d=x*x+y*y;
   if(d<distance){distance=d;best=&code;}
  }
  if(!best)return r->status=CYM_ZX_NOT_FOUND;
  const auto &payload=best->bytes();r->length=payload.size();
  if(payload.size()>cap)return r->status=CYM_ZX_OUTPUT_SMALL;
  if(!payload.empty())std::memcpy(out,payload.data(),payload.size());
  r->valid=1;return r->status=CYM_ZX_OK;
 } catch(const std::bad_alloc&) {return r->status=CYM_ZX_NO_MEMORY;}catch(...) {return r->status=CYM_ZX_EXCEPTION;}
}
