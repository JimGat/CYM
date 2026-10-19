/* Original CYM radix-2 FFT / streaming multirate power analyzer.
 * Full4096/48000 hop2048; bass2048/3000 hop256, first9 bands.
 * FIR193 Kaiser beta8.6 cutoff1400Hz, unity DC. Analysis removes window mean.
 * Hann window-energy normalization: integrated mean-square, not SPL.
 */
#include "audio_rta_dsp.h"
#include <string.h>
#include <math.h>
#define PI 3.14159265358979323846
#define FIR_N 193
static const float taps[FIR_N]={
 -4.201840221897e-06f, -6.292171769060e-06f, -8.654091412529e-06f, -1.110871974677e-05f, -1.340450140318e-05f, -1.521918215996e-05f,
 -1.616816887436e-05f, -1.581996984000e-05f, -1.371901250504e-05f, -9.415645775848e-06f, -2.502576332063e-06f, 7.343608955037e-06f,
 2.031778410499e-05f, 3.644100399819e-05f, 5.551760515650e-05f, 7.709805262321e-05f, 1.004510967078e-04f, 1.245488003957e-04f,
 1.480677653969e-04f, 1.694094046194e-04f, 1.867413770979e-04f, 1.980613290408e-04f, 2.012828988359e-04f, 1.943425881773e-04f,
 1.753246351954e-04f, 1.425995216849e-04f, 9.497028935244e-05f, 3.181952082508e-05f, -4.675124599793e-05f, -1.397986652913e-04f,
 -2.454406440863e-04f, -3.607945483389e-04f, -4.819591391521e-04f, -6.040476233950e-04f, -7.212774500174e-04f, -8.271202099993e-04f,
 -9.145122678014e-04f, -9.761236605157e-04f, -1.004679471953e-03f, -9.933244721597e-04f, -9.360184773673e-04f, -8.279468123771e-04f,
 -6.659276319103e-04f, -4.487958587557e-04f, -1.777422883695e-04f, 1.434138698061e-04f, 5.080399910805e-04f, 9.066117050984e-04f,
 1.326757416865e-03f, 1.753437848158e-03f, 2.169267793955e-03f, 2.554981505673e-03f, 2.890036727542e-03f, 3.153345675764e-03f,
 3.324114449745e-03f, 3.382765813070e-03f, 3.311914302553e-03f, 3.097357536390e-03f, 2.729043697667e-03f, 2.201972732397e-03f,
 1.516988037249e-03f, 6.814164731660e-04f, -2.904824951994e-04f, -1.377292872391e-03f, -2.550471086868e-03f, -3.774647200206e-03f,
 -5.008208080855e-03f, -6.204161562593e-03f, -7.311269292989e-03f, -8.275424489123e-03f, -9.041239638632e-03f, -9.553798806155e-03f,
 -9.760520109093e-03f, -9.613066558787e-03f, -9.069238214977e-03f, -8.094775788550e-03f, -6.665005673684e-03f, -4.766259013476e-03f,
 -2.397002806019e-03f, 4.313708748029e-04f, 3.694140971194e-03f, 7.353269688101e-03f, 1.135784750797e-02f, 1.564497224056e-02f,
 2.014104749873e-02f, 2.476347021079e-02f, 2.942266173262e-02f, 3.402438342977e-02f, 3.847226583862e-02f, 4.267047119703e-02f,
 4.652640267480e-02f, 4.995337033981e-02f, 5.287312394597e-02f, 5.521816606882e-02f, 5.693376584849e-02f, 5.797960339695e-02f,
 5.833098742751e-02f, 5.797960339695e-02f, 5.693376584849e-02f, 5.521816606882e-02f, 5.287312394597e-02f, 4.995337033981e-02f,
 4.652640267480e-02f, 4.267047119703e-02f, 3.847226583862e-02f, 3.402438342977e-02f, 2.942266173262e-02f, 2.476347021079e-02f,
 2.014104749873e-02f, 1.564497224056e-02f, 1.135784750797e-02f, 7.353269688101e-03f, 3.694140971194e-03f, 4.313708748029e-04f,
 -2.397002806019e-03f, -4.766259013476e-03f, -6.665005673684e-03f, -8.094775788550e-03f, -9.069238214977e-03f, -9.613066558787e-03f,
 -9.760520109093e-03f, -9.553798806155e-03f, -9.041239638632e-03f, -8.275424489123e-03f, -7.311269292989e-03f, -6.204161562593e-03f,
 -5.008208080855e-03f, -3.774647200206e-03f, -2.550471086868e-03f, -1.377292872391e-03f, -2.904824951994e-04f, 6.814164731660e-04f,
 1.516988037249e-03f, 2.201972732397e-03f, 2.729043697667e-03f, 3.097357536390e-03f, 3.311914302553e-03f, 3.382765813070e-03f,
 3.324114449745e-03f, 3.153345675764e-03f, 2.890036727542e-03f, 2.554981505673e-03f, 2.169267793955e-03f, 1.753437848158e-03f,
 1.326757416865e-03f, 9.066117050984e-04f, 5.080399910805e-04f, 1.434138698061e-04f, -1.777422883695e-04f, -4.487958587557e-04f,
 -6.659276319103e-04f, -8.279468123771e-04f, -9.360184773673e-04f, -9.933244721597e-04f, -1.004679471953e-03f, -9.761236605157e-04f,
 -9.145122678014e-04f, -8.271202099993e-04f, -7.212774500174e-04f, -6.040476233950e-04f, -4.819591391521e-04f, -3.607945483389e-04f,
 -2.454406440863e-04f, -1.397986652913e-04f, -4.675124599793e-05f, 3.181952082508e-05f, 9.497028935244e-05f, 1.425995216849e-04f,
 1.753246351954e-04f, 1.943425881773e-04f, 2.012828988359e-04f, 1.980613290408e-04f, 1.867413770979e-04f, 1.694094046194e-04f,
 1.480677653969e-04f, 1.245488003957e-04f, 1.004510967078e-04f, 7.709805262321e-05f, 5.551760515650e-05f, 3.644100399819e-05f,
 2.031778410499e-05f, 7.343608955037e-06f, -2.502576332063e-06f, -9.415645775848e-06f, -1.371901250504e-05f, -1.581996984000e-05f,
 -1.616816887436e-05f, -1.521918215996e-05f, -1.340450140318e-05f, -1.110871974677e-05f, -8.654091412529e-06f, -6.292171769060e-06f,
 -4.201840221897e-06f
};

/* PCM histories are integer: full/FIR are signed PCM16 units, low is Q27.
 * FFT samples are Q27 with one /2 per radix-2 stage (FFT/N). Coefficients
 * are Q30. All products/sums use 64 bits; even mean-subtracted full-scale
 * input has 3 guard bits in int32. No floating arithmetic in FIR/FFT loops.
 * Floating point remains at immutable preparation and 24-band power/dB edges.
 */
typedef struct {unsigned first,last;double first_weight,last_weight;} band_bins_t;
typedef struct {
 /* A second window of history permits bounded copying while capture advances.
  * All this storage belongs to the existing PSRAM workspace, not a task/queue.
  * A copy that outlives its overwrite margin is explicitly abandoned. */
 int32_t full[8192],low[4096],fir[FIR_N];
 int32_t real[4096],imag[4096],wr[2048],wi[2048];
 int32_t win[4096],low_win[2048],fir_taps[FIR_N];
 band_bins_t bins[24];
 float smooth[24];
 double alpha[2][2]; /* full/low x Fast/Slow, fixed sample-hop time */
 uint64_t last[24],total,sum_squares;
 unsigned pos,low_pos,fir_pos,phase,full_count,low_count,full_hop,low_hop;
 bool slow;
 bool full_due,low_due,next_low,job_low;
 unsigned job_phase,job_n,job_pos,job_i,job_j,job_len,job_base,job_band,job_bin;
 uint64_t job_total,job_power;
 int64_t job_sum;
 int32_t job_mean;
 double job_bands[24];
 uint32_t work_slices,analysis_restarts;
 audio_rta_spectrum_t out;
} dsp_t;
size_t audio_rta_dsp_bytes(void){return sizeof(dsp_t);}
double audio_rta_dsp_edge(unsigned i){return 20.0*pow(1000.0,(double)i/24.0);}
double audio_rta_dsp_filter(double f){
 double re=0,im=0;
 /* Report the actual quantized FIR, not the original design coefficients. */
 for(unsigned i=0;i<FIR_N;i++){double t=round(taps[i]*1073741824.0)/1073741824.0,a=2*PI*f*i/48000;re+=t*cos(a);im-=t*sin(a);}
 return hypot(re,im);
}
void audio_rta_dsp_reset(void *memory){
 dsp_t*d=memory;
 memset(d->full,0,sizeof(d->full));memset(d->low,0,sizeof(d->low));memset(d->fir,0,sizeof(d->fir));
 memset(d->smooth,0,sizeof(d->smooth));memset(d->last,0,sizeof(d->last));memset(&d->out,0,sizeof(d->out));
 d->total=d->sum_squares=0;d->pos=d->low_pos=d->fir_pos=d->phase=0;
 d->full_count=d->low_count=d->full_hop=d->low_hop=0;d->slow=false;
 d->full_due=d->low_due=d->next_low=false;d->job_phase=0;
 d->work_slices=d->analysis_restarts=0;
 for(unsigned i=0;i<24;i++)d->out.band[i]=d->out.peak[i]=AUDIO_RTA_FLOOR;
 d->out.rms=d->out.sample_peak=AUDIO_RTA_FLOOR;
 /* Scratch is overwritten; prepared windows/twiddles/bins/FIR stay. */
}
bool audio_rta_dsp_prepare(void *memory,bool (*checkpoint)(void *),void *arg){
 dsp_t*d=memory;memset(d,0,sizeof(*d));
 for(unsigned i=0;i<2048;i++){
  if(checkpoint&&!(i%128)&&!checkpoint(arg))return false;
  d->wr[i]=(int32_t)llround(cos(2*PI*i/4096)*1073741824.0);
  d->wi[i]=(int32_t)llround(-sin(2*PI*i/4096)*1073741824.0);
 }
 for(unsigned i=0;i<4096;i++){
  if(checkpoint&&!(i%128)&&!checkpoint(arg))return false;
  d->win[i]=(int32_t)llround((.5-.5*cos(2*PI*i/4096))*1073741824.0);
 }
 for(unsigned i=0;i<2048;i++){
  if(checkpoint&&!(i%128)&&!checkpoint(arg))return false;
  d->low_win[i]=(int32_t)llround((.5-.5*cos(2*PI*i/2048))*1073741824.0);
 }
 for(unsigned i=0;i<FIR_N;i++)d->fir_taps[i]=(int32_t)llround(taps[i]*1073741824.0);
 for(unsigned b=0;b<24;b++){
  double df=b<9?3000.0/2048:48000.0/4096;
  double lo=audio_rta_dsp_edge(b)/df,hi=audio_rta_dsp_edge(b+1)/df;
  band_bins_t*q=&d->bins[b];q->first=(unsigned)floor(lo+.5);q->last=(unsigned)ceil(hi-.5);
  q->first_weight=fmin(hi,q->first+.5)-lo;
  q->last_weight=hi-fmax(lo,q->last-.5);
 }
 for(unsigned low=0;low<2;low++)for(unsigned slow=0;slow<2;slow++)
  d->alpha[low][slow]=-expm1(-(low?4096.0:2048.0)/48000/(slow?1.0:.125));
 audio_rta_dsp_reset(d);
 return !checkpoint||checkpoint(arg);
}
void audio_rta_dsp_init(void *memory){(void)audio_rta_dsp_prepare(memory,NULL,NULL);}
void audio_rta_dsp_slow(void *memory,bool slow){((dsp_t*)memory)->slow=slow;}
void audio_rta_dsp_reset_peaks(void *memory){dsp_t*d=memory;for(unsigned i=0;i<24;i++)d->out.peak[i]=AUDIO_RTA_FLOOR;}
static float db(double power){return (float)(10*log10(fmax(power,1e-12)));}
/* Symmetric rounding avoids signed shifts, negative left shifts and systematic
 * negative bias near the noise floor. Bounds leave ample int64 headroom. */
static int32_t q30(int64_t v){return (int32_t)((v+(v>=0?536870912:-536870912))/1073741824);}
static bool check(bool (*checkpoint)(void*),void*arg){return !checkpoint||checkpoint(arg);}
/* Exactly the original Q27/Q30 radix-2 operation; wide intermediates and
 * symmetric rounding are shared by synchronous and sliced execution. */
static void butterfly(dsp_t*d,unsigned a,unsigned b,unsigned k){
 int32_t re=q30((int64_t)d->wr[k]*d->real[b]-(int64_t)d->wi[k]*d->imag[b]);
 int32_t im=q30((int64_t)d->wr[k]*d->imag[b]+(int64_t)d->wi[k]*d->real[b]);
 int32_t ar=d->real[a],ai=d->imag[a];
 d->real[b]=(ar-re)/2;d->imag[b]=(ai-im)/2;d->real[a]=(ar+re)/2;d->imag[a]=(ai+im)/2;
}
/* One reusable FFT workspace. Check cancellation each stage, without forcing
 * a tick sleep per stage: the session callback blocks only on its time budget. */
static bool fft(dsp_t*d,unsigned n,bool (*checkpoint)(void*),void*arg){
 for(unsigned i=1,j=0;i<n;i++){
  unsigned bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;
  if(i<j){int32_t t=d->real[i];d->real[i]=d->real[j];d->real[j]=t;t=d->imag[i];d->imag[i]=d->imag[j];d->imag[j]=t;}
 }
 for(unsigned len=2;len<=n;len<<=1){unsigned step=4096/len;
  if(!check(checkpoint,arg))return false;
  for(unsigned base=0;base<n;base+=len)for(unsigned j=0;j<len/2;j++){
   unsigned k=j*step,a=base+j,b=a+len/2;
   butterfly(d,a,b,k);
  }
 }
 return true;
}
static uint64_t bin_power(dsp_t*d,unsigned k){return (uint64_t)((int64_t)d->real[k]*d->real[k])+(uint64_t)((int64_t)d->imag[k]*d->imag[k]);}
static bool analyze(dsp_t*d,bool low,bool (*checkpoint)(void*),void*arg){
 unsigned n=low?2048:4096,cap=2*n,pos=((low?d->low_pos:d->pos)+n)%cap;
 int32_t*ring=low?d->low:d->full,*w=low?d->low_win:d->win;
 int64_t sum=0;for(unsigned i=0;i<n;i++)sum+=ring[(pos+i)%cap];
 int32_t mean=(int32_t)(sum*(low?1:4096)/n);
 for(unsigned i=0;i<n;i++){
  if(!(i%256)&&!check(checkpoint,arg))return false;
  int32_t x=ring[(pos+i)%cap]*(low?1:4096)-mean;
  d->real[i]=q30((int64_t)x*w[i]);d->imag[i]=0;
 }
 if(!fft(d,n,checkpoint,arg))return false;
 /* Periodic Hann energy =3N/8; FFT/N and Q27 yield normalization
  * (8/3)/2^54. All bands exclude DC/Nyquist, so one-sided factor is 2. */
 const double norm=(16.0/3.0)/18014398509481984.0;
 for(unsigned b=low?0:9;b<(low?9:24);b++){
  band_bins_t*q=&d->bins[b];uint64_t interior=0;
  for(unsigned k=q->first+1;k<q->last;k++)interior+=bin_power(d,k);
  double p=(interior+bin_power(d,q->first)*q->first_weight+
   (q->last!=q->first?bin_power(d,q->last)*q->last_weight:0))*norm;
  uint32_t mask=1u<<b;
  if(!(d->out.valid&mask))d->smooth[b]=(float)p;
  else d->smooth[b]+=(float)(d->alpha[low][d->slow]*(p-d->smooth[b]));
  d->last[b]=d->total;d->out.valid|=mask;d->out.band[b]=db(d->smooth[b]);
  if(d->out.band[b]>d->out.peak[b])d->out.peak[b]=d->out.band[b];
 }
 d->out.frames++;return check(checkpoint,arg);
}
static bool push(void*memory,const int16_t*pcm,size_t count,bool (*checkpoint)(void*),void*arg,bool defer){
 dsp_t*d=memory;
 for(size_t i=0;i<count;i++){
  if(!(i%256)&&!check(checkpoint,arg))return false;
  int32_t x=pcm[i],old=d->full[(d->pos+4096)%8192];
  if(x>=32760||x<=-32760)d->out.clips++;
  d->sum_squares-=(uint64_t)((int64_t)old*old);d->sum_squares+=(uint64_t)((int64_t)x*x);
  d->total++;d->full[d->pos]=x;d->pos=(d->pos+1)%8192;
  d->fir[d->fir_pos]=x;d->fir_pos=(d->fir_pos+1)%FIR_N;
  if(d->full_count<4096)d->full_count++;
  if(++d->phase==16){
   d->phase=0;int64_t y=0;unsigned k=d->fir_pos;
   for(unsigned j=0;j<FIR_N;j++){k=k?k-1:FIR_N-1;y+=(int64_t)d->fir_taps[j]*d->fir[k];}
   /* Q30 taps x PCM16 -> Q27 (12 fractional PCM bits retained). */
   d->low[d->low_pos]=(int32_t)((y+(y>=0?131072:-131072))/262144);d->low_pos=(d->low_pos+1)%4096;
   if(d->low_count<2048)d->low_count++;
   if(++d->low_hop>=256&&d->low_count==2048){if(defer)d->low_due=true;else if(!analyze(d,true,checkpoint,arg))return false;d->low_hop=0;}
  }
  if(++d->full_hop>=2048&&d->full_count==4096){if(defer)d->full_due=true;else if(!analyze(d,false,checkpoint,arg))return false;d->full_hop=0;}
 }
 d->out.samples=d->total;return true;
}
bool audio_rta_dsp_push_checked(void*memory,const int16_t*pcm,size_t count,bool (*checkpoint)(void*),void*arg){return push(memory,pcm,count,checkpoint,arg,false);}
bool audio_rta_dsp_ingest(void*memory,const int16_t*pcm,size_t count,bool (*checkpoint)(void*),void*arg){return push(memory,pcm,count,checkpoint,arg,true);}
/* Single-owner coroutine. Each call executes at most 128 copy/window/bit-reverse/
 * butterfly/bin operations, or one band's scalar finish, or one atomic commit.
 * Input may advance between ANY calls. Pending hops coalesce, not PCM: every
 * contiguous input sample still enters FIR/history/RMS. Alternation prevents
 * bass starvation. The next job selects the newest complete window, never an
 * unbounded queue of obsolete analyses. No pointers escape this workspace. */
bool audio_rta_dsp_work(void*memory){
 dsp_t*d=memory;d->work_slices++;
 if(!d->job_phase){
  if(!d->full_due&&!d->low_due)return false;
  d->job_low=d->low_due&&(!d->full_due||d->next_low);
  d->next_low=!d->job_low;
  if(d->job_low)d->low_due=false;else d->full_due=false;
  d->job_n=d->job_low?2048:4096;
  d->job_pos=((d->job_low?d->low_pos:d->pos)+d->job_n)%(2*d->job_n);
  d->job_total=d->total;d->job_sum=0;d->job_i=0;d->job_phase=1;
 }
 unsigned n=d->job_n;
 switch(d->job_phase){
 case 1: { /* Immutable window copy and mean; double-ring overwrite guard. */
  if(d->total-d->job_total>=(uint64_t)n*(d->job_low?16:1)){
   d->analysis_restarts++;d->job_phase=0;return true;
  }
  int32_t*ring=d->job_low?d->low:d->full;
  unsigned end=d->job_i+128;if(end>n)end=n;
  for(;d->job_i<end;d->job_i++){
   int32_t x=ring[(d->job_pos+d->job_i)%(2*n)];
   d->real[d->job_i]=x;d->job_sum+=x;
  }
  if(d->job_i==n){d->job_mean=(int32_t)(d->job_sum*(d->job_low?1:4096)/n);d->job_i=0;d->job_phase=2;}
  break;
 }
 case 2: {
  int32_t*w=d->job_low?d->low_win:d->win;
  unsigned end=d->job_i+128;if(end>n)end=n;
  for(;d->job_i<end;d->job_i++){
   unsigned i=d->job_i;int32_t x=d->real[i]*(d->job_low?1:4096)-d->job_mean;
   d->real[i]=q30((int64_t)x*w[i]);d->imag[i]=0;
  }
  if(d->job_i==n){d->job_i=1;d->job_j=0;d->job_phase=3;}
  break;
 }
 case 3: {
  unsigned end=d->job_i+128;if(end>n)end=n;
  for(;d->job_i<end;d->job_i++){
   unsigned bit=n>>1;for(;d->job_j&bit;bit>>=1)d->job_j^=bit;d->job_j^=bit;
   if(d->job_i<d->job_j){unsigned i=d->job_i,j=d->job_j;
    int32_t t=d->real[i];d->real[i]=d->real[j];d->real[j]=t;
    t=d->imag[i];d->imag[i]=d->imag[j];d->imag[j]=t;}
  }
  if(d->job_i==n){d->job_len=2;d->job_base=d->job_j=0;d->job_phase=4;}
  break;
 }
 case 4:
  for(unsigned work=0;work<128&&d->job_len<=n;work++){
   unsigned len=d->job_len,j=d->job_j,a=d->job_base+j;
   butterfly(d,a,a+len/2,j*(4096/len));
   if(++d->job_j==len/2){d->job_j=0;d->job_base+=len;
    if(d->job_base==n){d->job_base=0;d->job_len*=2;}}
  }
  if(d->job_len>n){d->job_band=d->job_low?0:9;d->job_power=0;d->job_bin=d->bins[d->job_band].first+1;d->job_phase=5;}
  break;
 case 5: {
  unsigned b=d->job_band;band_bins_t*q=&d->bins[b];
  unsigned end=d->job_bin+128;if(end>q->last)end=q->last;
  for(;d->job_bin<end;d->job_bin++)d->job_power+=bin_power(d,d->job_bin);
  if(d->job_bin>=q->last){
   const double norm=(16.0/3.0)/18014398509481984.0;
   d->job_bands[b]=(d->job_power+bin_power(d,q->first)*q->first_weight+
    (q->last!=q->first?bin_power(d,q->last)*q->last_weight:0))*norm;
   if(++d->job_band==(d->job_low?9:24))d->job_phase=6;
   else {d->job_power=0;d->job_bin=d->bins[d->job_band].first+1;}
  }
  break;
 }
 case 6: {
  /* Commit only a complete analysis. Smoothing uses actual window-to-window
   * sample time when hops coalesce, preserving 125ms/1s energy constants. */
  unsigned first=d->job_low?0:9,last=d->job_low?9:24;
  uint64_t elapsed=d->job_total-d->last[first];
  double hop=d->job_low?4096.0:2048.0;
  double alpha=1-pow(1-d->alpha[d->job_low][d->slow],elapsed/hop);
  for(unsigned b=first;b<last;b++){
   double p=d->job_bands[b];uint32_t mask=1u<<b;
   if(!(d->out.valid&mask))d->smooth[b]=(float)p;
   else d->smooth[b]+=(float)(alpha*(p-d->smooth[b]));
   d->last[b]=d->job_total;d->out.valid|=mask;d->out.band[b]=db(d->smooth[b]);
   if(d->out.band[b]>d->out.peak[b])d->out.peak[b]=d->out.band[b];
  }
  d->out.frames++;d->job_phase=0;break;
 }
 default:d->job_phase=0;break;
 }
 return true;
}
void audio_rta_dsp_work_status(void*memory,unsigned*phase,uint32_t*slices,uint32_t*restarts){
 dsp_t*d=memory;*phase=d->job_phase;*slices=d->work_slices;*restarts=d->analysis_restarts;
}
void audio_rta_dsp_push(void*memory,const int16_t*pcm,size_t count){(void)audio_rta_dsp_push_checked(memory,pcm,count,NULL,NULL);}
void audio_rta_dsp_snapshot(void*memory,audio_rta_spectrum_t*out){
 dsp_t*d=memory;*out=d->out;
 /* RMS uses an O(1) rolling exact PCM square sum; peak scans integers only,
  * no per-sample software float/double or full-history RMS rescan. */
 int32_t peak=0;
 for(unsigned i=0;i<d->full_count;i++){int32_t x=d->full[(d->pos+8192-d->full_count+i)%8192];if(x<0)x=-x;if(x>peak)peak=x;}
 if(d->full_count){out->rms=db((double)d->sum_squares/(d->full_count*1073741824.0));out->sample_peak=db((double)peak*peak/1073741824.0);}
 for(unsigned i=0;i<24;i++){
  uint64_t age=d->total-d->last[i];out->age[i]=age>UINT32_MAX?UINT32_MAX:(uint32_t)age;
  if(age>24000)out->valid&=~(1u<<i); /* never present an aged window as live */
 }
}
