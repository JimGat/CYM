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
typedef struct {
 float full[4096],low[2048],fir[FIR_N];
 float real[4096],imag[4096],wr[2048],wi[2048];
 float win[4096],low_win[2048],smooth[24];
 uint64_t last[24],total;
 unsigned pos,low_pos,fir_pos,phase,full_count,low_count,full_hop,low_hop;
 bool slow;
 audio_rta_spectrum_t out;
} dsp_t;
size_t audio_rta_dsp_bytes(void){return sizeof(dsp_t);}
double audio_rta_dsp_edge(unsigned i){return 20.0*pow(1000.0,(double)i/24.0);}
double audio_rta_dsp_filter(double f){
 double re=0,im=0;
 for(unsigned i=0;i<FIR_N;i++){double a=2*PI*f*i/48000;re+=taps[i]*cos(a);im-=taps[i]*sin(a);}
 return hypot(re,im);
}
void audio_rta_dsp_init(void *memory){
 dsp_t*d=memory;memset(d,0,sizeof(*d));
 for(unsigned i=0;i<2048;i++){d->wr[i]=(float)cos(2*PI*i/4096);d->wi[i]=(float)-sin(2*PI*i/4096);}
 for(unsigned i=0;i<4096;i++)d->win[i]=(float)(.5-.5*cos(2*PI*i/4096));
 for(unsigned i=0;i<2048;i++)d->low_win[i]=(float)(.5-.5*cos(2*PI*i/2048));
 for(unsigned i=0;i<24;i++)d->out.band[i]=d->out.peak[i]=AUDIO_RTA_FLOOR;
 d->out.rms=d->out.sample_peak=AUDIO_RTA_FLOOR;
}
void audio_rta_dsp_slow(void *memory,bool slow){((dsp_t*)memory)->slow=slow;}
void audio_rta_dsp_reset_peaks(void *memory){dsp_t*d=memory;for(unsigned i=0;i<24;i++)d->out.peak[i]=AUDIO_RTA_FLOOR;}
static float db(double power){return (float)(10*log10(fmax(power,1e-12)));}
/* One reusable FFT workspace, never borrowed by the UI. */
static void fft(dsp_t*d,unsigned n){
 for(unsigned i=1,j=0;i<n;i++){
  unsigned bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;
  if(i<j){float t=d->real[i];d->real[i]=d->real[j];d->real[j]=t;t=d->imag[i];d->imag[i]=d->imag[j];d->imag[j]=t;}
 }
 for(unsigned len=2;len<=n;len<<=1){unsigned step=4096/len;
  for(unsigned base=0;base<n;base+=len)for(unsigned j=0;j<len/2;j++){
   unsigned k=j*step,a=base+j,b=a+len/2;
   float re=d->wr[k]*d->real[b]-d->wi[k]*d->imag[b],im=d->wr[k]*d->imag[b]+d->wi[k]*d->real[b];
   d->real[b]=d->real[a]-re;d->imag[b]=d->imag[a]-im;d->real[a]+=re;d->imag[a]+=im;
  }
 }
}
static void analyze(dsp_t*d,bool low){
 unsigned n=low?2048:4096,pos=low?d->low_pos:d->pos;
 float*ring=low?d->low:d->full,*w=low?d->low_win:d->win;
 double mean=0,energy=0;for(unsigned i=0;i<n;i++)mean+=ring[i];mean/=n;
 for(unsigned i=0;i<n;i++){d->real[i]=(float)((ring[(pos+i)%n]-mean)*w[i]);d->imag[i]=0;energy+=(double)w[i]*w[i];}
 fft(d,n);
 double df=(low?3000.0:48000.0)/n,norm=1.0/(n*energy);
 for(unsigned b=low?0:9;b<(low?9:24);b++){
  double lo=audio_rta_dsp_edge(b),hi=audio_rta_dsp_edge(b+1),p=0;
  unsigned first=(unsigned)fmax(0,floor(lo/df-.5)),last=(unsigned)fmin(n/2,ceil(hi/df+.5));
  for(unsigned k=first;k<=last;k++){
   double cl=fmax(0,(k-.5)*df),ch=fmin(low?1500.0:24000.0,(k+.5)*df);
   double fraction=fmax(0,fmin(hi,ch)-fmax(lo,cl))/(ch-cl);
   double bin=((double)d->real[k]*d->real[k]+(double)d->imag[k]*d->imag[k])*norm;
   p+=bin*fraction*((k==0||k==n/2)?1:2);
  }
  uint32_t mask=1u<<b;
  if(!(d->out.valid&mask))d->smooth[b]=(float)p;
  else{double dt=(double)(d->total-d->last[b])/48000.0,alpha=-expm1(-dt/(d->slow?1.0:.125));d->smooth[b]+=(float)(alpha*(p-d->smooth[b]));}
  d->last[b]=d->total;d->out.valid|=mask;d->out.band[b]=db(d->smooth[b]);
  if(d->out.band[b]>d->out.peak[b])d->out.peak[b]=d->out.band[b];
 }
}
void audio_rta_dsp_push(void*memory,const int16_t*pcm,size_t count){
 dsp_t*d=memory;
 for(size_t i=0;i<count;i++){
  double x=(double)pcm[i]/32768.0;
  if(pcm[i]>=32760||pcm[i]<=-32760)d->out.clips++;
  d->total++;d->full[d->pos]=x;d->pos=(d->pos+1)%4096;
  d->fir[d->fir_pos]=x;d->fir_pos=(d->fir_pos+1)%FIR_N;
  if(d->full_count<4096)d->full_count++;
  if(++d->phase==16){
   d->phase=0;double y=0;unsigned k=d->fir_pos;
   for(unsigned j=0;j<FIR_N;j++){k=k?k-1:FIR_N-1;y+=taps[j]*d->fir[k];}
   d->low[d->low_pos]=y;d->low_pos=(d->low_pos+1)%2048;
   if(d->low_count<2048)d->low_count++;
   if(++d->low_hop>=256&&d->low_count==2048){analyze(d,true);d->low_hop=0;}
  }
  if(++d->full_hop>=2048&&d->full_count==4096){analyze(d,false);d->full_hop=0;}
 }
 d->out.samples=d->total;
}
void audio_rta_dsp_snapshot(void*memory,audio_rta_spectrum_t*out){
 dsp_t*d=memory;*out=d->out;
 /* Unwindowed latest85ms input, distinct from asynchronous band ages. */
 double sum=0,peak=0;
 for(unsigned i=0;i<d->full_count;i++){double x=d->full[i];sum+=x*x;if(fabs(x)>peak)peak=fabs(x);}
 if(d->full_count){out->rms=db(sum/d->full_count);out->sample_peak=db(peak*peak);}
 for(unsigned i=0;i<24;i++)out->age[i]=(uint32_t)(d->total-d->last[i]);
}
