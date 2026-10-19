"""Numerical tests exercise the production C, never a surrogate analyzer."""
import ctypes as C
import math, os, pathlib, subprocess, unittest
import numpy as np
R = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(os.environ.get("CYM_TEST_OUT", "/home/dev/projects/cym-audio-rta-beta")) / "rta-host"
class Snapshot(C.Structure):
    _fields_=[("band",C.c_float*24),("peak",C.c_float*24),("valid",C.c_uint32),("age",C.c_uint32*24),("rms",C.c_float),("sample_peak",C.c_float),("clips",C.c_uint32),("samples",C.c_uint64),("frames",C.c_uint32)]
class DSP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=R/"ESP32C5/main/audio_rta_dsp.c"
        assert p.exists(), "production audio_rta_dsp.c missing (expected initial RED)"
        OUT.mkdir(parents=True,exist_ok=True)
        subprocess.run(["gcc","-std=c11","-O2","-Wall","-Wextra","-Werror","-fsanitize=undefined","-fno-sanitize-recover=all","-shared","-fPIC",str(p),"-lm","-o",str(OUT/"dsp.so")],check=True)
        cls.lib=C.CDLL(str(OUT/"dsp.so")); cls.lib.audio_rta_dsp_bytes.restype=C.c_size_t
        cls.lib.audio_rta_dsp_init.argtypes=[C.c_void_p]
        cls.lib.audio_rta_dsp_reset.argtypes=[C.c_void_p]
        cls.lib.audio_rta_dsp_push.argtypes=[C.c_void_p,C.POINTER(C.c_int16),C.c_size_t]
        cls.lib.audio_rta_dsp_snapshot.argtypes=[C.c_void_p,C.POINTER(Snapshot)]
        cls.lib.audio_rta_dsp_slow.argtypes=[C.c_void_p,C.c_bool]
        cls.lib.audio_rta_dsp_reset_peaks.argtypes=[C.c_void_p]
        cls.lib.audio_rta_dsp_edge.argtypes=[C.c_uint];cls.lib.audio_rta_dsp_edge.restype=C.c_double
        cls.lib.audio_rta_dsp_filter.argtypes=[C.c_double];cls.lib.audio_rta_dsp_filter.restype=C.c_double
    def setUp(self):
        self.mem=C.create_string_buffer(self.lib.audio_rta_dsp_bytes());self.lib.audio_rta_dsp_init(self.mem)
    def feed(self,x,block=512):
        x=np.clip(np.rint(np.asarray(x)*32768),-32768,32767).astype(np.int16)
        for k in range(0,len(x),block):
            a=np.ascontiguousarray(x[k:k+block]);self.lib.audio_rta_dsp_push(self.mem,a.ctypes.data_as(C.POINTER(C.c_int16)),len(a))
        s=Snapshot();self.lib.audio_rta_dsp_snapshot(self.mem,C.byref(s));return s
    def tone(self,f,amp=.5,seconds=3):
        t=np.arange(int(48000*seconds))/48000;return amp*np.sin(2*np.pi*f*t)
    def test_incremental_overwrite_wrap_and_phase_reset(self):
        subprocess.run(['python3',str(R/'tests/run_audio_rta_incremental_host.py')],check=True)
    def incremental_api(self):
        self.lib.audio_rta_dsp_ingest.argtypes=[C.c_void_p,C.POINTER(C.c_int16),C.c_size_t,C.c_void_p,C.c_void_p]
        self.lib.audio_rta_dsp_ingest.restype=C.c_bool
        self.lib.audio_rta_dsp_work.argtypes=[C.c_void_p];self.lib.audio_rta_dsp_work.restype=C.c_bool
    def incremental_feed(self,x,slices=30):
        self.incremental_api()
        pcm=np.clip(np.rint(np.asarray(x)*32768),-32768,32767).astype(np.int16)
        for k in range(0,len(pcm),256):
            a=np.ascontiguousarray(pcm[k:k+256])
            self.assertTrue(self.lib.audio_rta_dsp_ingest(self.mem,a.ctypes.data_as(C.POINTER(C.c_int16)),len(a),None,None))
            for _ in range(slices):
                if not self.lib.audio_rta_dsp_work(self.mem):break
        out=Snapshot();self.lib.audio_rta_dsp_snapshot(self.mem,C.byref(out));return out
    def test_incremental_numeric_reference_all_centres_and_alias(self):
        # Exercise the runtime arithmetic, not just the synchronous reference API.
        for b in range(24):
            self.setUp();f=20*1000**((b+.5)/24)
            out=self.incremental_feed(self.tone(f,seconds=3))
            self.assertEqual(out.valid,0xffffff)
            self.assertAlmostEqual(out.band[b],10*np.log10(.125),delta=1.)
        for f in [2970,3030,12000+230,21000-40]:
            self.setUp();out=self.incremental_feed(self.tone(f,seconds=3))
            self.assertLess(max(out.band[:9]),-69)
    def test_incremental_window_matches_synchronous_and_commit_is_atomic(self):
        self.incremental_api()
        x=self.tone(1000,seconds=4096/48000)
        expected=self.feed(x);self.setUp()
        got=self.incremental_feed(x,slices=0)
        self.assertEqual(got.frames,0);self.assertEqual(got.valid,0)
        for _ in range(1000):
            more=self.lib.audio_rta_dsp_work(self.mem)
            self.lib.audio_rta_dsp_snapshot(self.mem,C.byref(got))
            self.assertIn(got.valid,[0,0xfffe00])
            if not more:break
        self.assertEqual(got.frames,1)
        np.testing.assert_array_equal(got.band,expected.band)
        self.assertEqual(list(got.age)[9:],list(expected.age)[9:])
        self.assertEqual(got.rms,expected.rms)
    def test_incremental_coalescing_smoothing_reset_and_floor(self):
        self.incremental_api()
        # 10 slices per256 samples intentionally coalesces many hops.
        for slow in [False,True]:
            self.setUp();self.lib.audio_rta_dsp_slow(self.mem,slow)
            a=self.incremental_feed(self.tone(70,seconds=3)+self.tone(1000,amp=.1,seconds=3),slices=10)
            self.assertEqual(a.valid,0xffffff)
            b=self.incremental_feed(np.zeros(48000),slices=10)
            if slow:slow_level=b.band[13]
            else:fast_level=b.band[13]
            self.lib.audio_rta_dsp_reset(self.mem)
            z=self.incremental_feed(np.zeros(48000),slices=10)
            self.assertEqual(z.valid,0xffffff);self.assertTrue(all(v<=-119 for v in z.band))
        self.assertGreater(slow_level,fast_level+10)
    def test_history_reset_matches_fresh_initialization(self):
        self.lib.audio_rta_dsp_slow(self.mem,True)
        self.feed(np.tile([1.,-1.],48000))
        self.lib.audio_rta_dsp_reset(self.mem)
        cleared=Snapshot();self.lib.audio_rta_dsp_snapshot(self.mem,C.byref(cleared))
        self.assertEqual(cleared.samples,0);self.assertEqual(cleared.valid,0)
        self.assertEqual(cleared.clips,0);self.assertTrue(all(v==-120 for v in cleared.peak))
        x=self.tone(70,seconds=2)+self.tone(3000,amp=.1,seconds=2)
        reset=self.feed(x);self.setUp();fresh=self.feed(x)
        self.assertEqual(bytes(reset),bytes(fresh))
    def test_exact_readiness_and_empty_reads(self):
        s=self.feed(np.zeros(4095));self.assertEqual(s.valid,0)
        s=self.feed([0]);self.assertEqual(s.valid,0xfffe00)
        s=self.feed(np.zeros(32767-4096));self.assertEqual(s.valid,0xfffe00)
        s=self.feed([0]);self.assertEqual(s.valid,0xffffff)
        before=bytes(s);s=self.feed([]);self.assertEqual(bytes(s),before)
        self.lib.audio_rta_dsp_reset(self.mem)
        s=self.feed(np.zeros(4095));self.assertEqual(s.valid,0)
    def test_low_level_fullscale_and_dc_numeric_reference(self):
        for amplitude in [1., .01, .0001, 1/32768]:
            for frequency in [70.,1000.,13000.]:
                self.setUp();x=self.tone(frequency,amp=amplitude,seconds=2)
                quant=np.clip(np.rint(x*32768),-32768,32767)/32768
                s=self.feed(x);b=int(np.log(frequency/20)/np.log(1000)*24)
                expected=10*np.log10(np.mean(quant**2))
                self.assertAlmostEqual(s.band[b],expected,delta=.5)
                latest=quant[-4096:]
                self.assertAlmostEqual(s.rms,10*np.log10(np.mean(latest**2)),delta=.001)
                self.assertAlmostEqual(s.sample_peak,20*np.log10(np.max(np.abs(latest))),delta=.001)
        for value in [-1.,1.,0.,1/32768]:
            self.setUp();s=self.feed(np.full(48000*6,value))
            self.assertTrue(all(v<=-119 for v in s.band))
    def test_processing_cancellation_and_reset(self):
        callback=C.CFUNCTYPE(C.c_bool,C.c_void_p)
        self.lib.audio_rta_dsp_push_checked.argtypes=[C.c_void_p,C.POINTER(C.c_int16),C.c_size_t,callback,C.c_void_p]
        self.lib.audio_rta_dsp_push_checked.restype=C.c_bool
        pcm=np.full(32768,32767,dtype=np.int16)
        # Includes startup, input chunks, window setup, early/mid/last FFT stage.
        for stop in [1,16,17,25,35,65,100,150,200]:
            self.setUp();calls=[]
            @callback
            def check(_):
                calls.append(1);return len(calls)<stop
            ok=self.lib.audio_rta_dsp_push_checked(self.mem,pcm.ctypes.data_as(C.POINTER(C.c_int16)),len(pcm),check,None)
            self.assertFalse(ok);self.assertEqual(len(calls),stop)
            self.lib.audio_rta_dsp_reset(self.mem)
            a=self.feed(self.tone(70,seconds=1));self.setUp();b=self.feed(self.tone(70,seconds=1))
            self.assertEqual(bytes(a),bytes(b))
    def test_budget_and_edges(self):
        self.assertLessEqual(self.lib.audio_rta_dsp_bytes(),256*1024)
        for i in range(25): self.assertAlmostEqual(self.lib.audio_rta_dsp_edge(i),20*1000**(i/24),places=7)
    def test_silence_dc_and_warmup(self):
        s=self.feed(np.zeros(1024));self.assertEqual(s.valid,0)
        s=self.feed(np.zeros(48000));self.assertEqual(s.valid,(1<<24)-1)
        self.assertTrue(all(math.isfinite(x) and x<=-119 for x in s.band))
        s=self.feed(np.full(96000,.3));self.assertTrue(all(x<-65 for x in s.band))
    def test_impulse_finite(self):
        x=np.zeros(96000);x[24000]=1;s=self.feed(x)
        self.assertTrue(all(math.isfinite(x) for x in s.band));self.assertGreater(s.clips,0)
    def test_centres_against_independent_long_reference(self):
        # A 3-second rectangular reference FFT resolves 1/3 Hz. Compare tone power
        # only away from exact edges; window leakage at those edges is characterized separately.
        for i in range(24):
            self.setUp();f=20*1000**((i+.5)/24);x=self.tone(f)
            s=self.feed(x);ref=np.mean(x*x);want=10*np.log10(ref)
            self.assertLess(abs(s.band[i]-want),1.0,(i,f,s.band[i],want))
            self.assertAlmostEqual(s.rms,10*np.log10(.125),delta=.6)
            self.assertAlmostEqual(s.sample_peak,20*np.log10(.5),delta=.1)
    def test_filter_passband_and_alias_rejection(self):
        pass_db=[20*np.log10(max(1e-15,self.lib.audio_rta_dsp_filter(float(f)))) for f in np.linspace(20,20*1000**(9/24),301)]
        alias=[self.lib.audio_rta_dsp_filter(float(f)) for f in np.linspace(3000-20*1000**(9/24),24000,6001)]
        self.assertLess(max(abs(x) for x in pass_db),.5)
        self.assertLess(20*np.log10(max(alias)),-60)
    def test_crossover_multitone_noise_clipping_and_reset(self):
        t=np.arange(144000)/48000
        x=.2*np.sin(2*np.pi*230*t)+.2*np.sin(2*np.pi*310*t)+.2*np.sin(2*np.pi*4000*t)
        s=self.feed(x)
        for f in [230,310,4000]:
            i=int(np.log(f/20)/np.log(1000)*24);self.assertAlmostEqual(s.band[i],10*np.log10(.02),delta=1)
        self.assertTrue(all(p>=b for p,b in zip(s.peak,s.band)))
        self.lib.audio_rta_dsp_reset_peaks(self.mem);s=self.feed(np.zeros(10000))
        self.assertTrue(all(math.isfinite(b) for b in s.band))
        self.setUp();s=self.feed(np.random.default_rng(191).normal(0,.2,144000))
        self.assertTrue(all(math.isfinite(b) and b<0 for b in s.band));self.assertEqual(s.clips,0)
        s=self.feed(np.tile([1.,-1.],24000));self.assertGreaterEqual(s.clips,48000)
    def test_slow_is_slower_and_reset_invalidates_gain_history(self):
        self.feed(self.tone(1000,seconds=2));s0=self.feed(np.zeros(4800))
        self.setUp();self.lib.audio_rta_dsp_slow(self.mem,True);self.feed(self.tone(1000,seconds=2));s1=self.feed(np.zeros(4800))
        self.assertGreater(s1.band[13],s0.band[13])
        self.lib.audio_rta_dsp_init(self.mem);s=self.feed(np.zeros(1024));self.assertEqual(s.valid,0)
    def test_exact_edge_sweep_and_crossover(self):
        # A steady edge sinusoid splits equally for a symmetric Hann spectrum.
        # Characterize transition bins by adjacent-band SUM, not fictitious
        # independent bass bins; full/low crossover is deliberately included.
        worst=0
        for edge in range(1,24):
            for offset in [-.01,0,.01]:
                self.setUp();f=20*1000**(edge/24)*(1+offset)
                s=self.feed(self.tone(f,seconds=4))
                power=10**(s.band[edge-1]/10)+10**(s.band[edge]/10)
                error=abs(10*np.log10(power/.125));worst=max(worst,error)
                # Unequal-resolution crossover has an explicitly characterized
                # +/-23.44Hz boundary (two full-rate bins). No <=1dB claim there.
                limit=2.0 if edge==9 else 1.0
                self.assertLess(error,limit,(edge,f,error))
        print("Measured worst adjacent-edge/crossover sum error dB:",worst)
    def test_alias_tones_actual_stream(self):
        for f in [2800,2970,3030,6000-140,12000+230,21000-40]:
            self.setUp();s=self.feed(self.tone(f,seconds=4))
            self.assertLess(max(s.band[:9]),-69,(f,list(s.band[:9])))
    def test_white_pink_noise_independent_high_resolution_reference(self):
        rng=np.random.default_rng(8761);n=48000*48
        for pink in [False,True]:
            self.setUp();x=rng.normal(size=n)
            if pink:
                spec=np.fft.rfft(x);f=np.fft.rfftfreq(n,1/48000)
                spec/=np.sqrt(np.maximum(f,1));x=np.fft.irfft(spec,n)
            x*=.08/np.std(x)
            # Reference is an independent 48-second FFT, not the production
            # FFT/decimator. Average actual output powers after warmup.
            powers=[]
            for k in range(0,n,4800):
                got=self.feed(x[k:k+4800])
                if k>=48000*4:powers.append(10**(np.array(got.band)/10))
            quant=np.clip(np.rint(x*32768),-32768,32767)/32768
            z=np.fft.rfft(quant);ps=abs(z)**2/n**2;ps[1:-1]*=2
            f=np.fft.rfftfreq(n,1/48000);actual=np.mean(powers,axis=0)
            errors=[]
            for b in range(24):
                lo,hi=20*1000**(b/24),20*1000**((b+1)/24)
                ref=ps[(f>=lo)&(f<hi)].sum()
                err=abs(10*np.log10(actual[b]/ref));errors.append(float(err))
                self.assertLess(err,1.0,(pink,b,err))
            print("Measured", "pink" if pink else "white", "48s reference max dB error",max(errors))
    def test_gain_scale_reset_peaks_and_stream_partition(self):
        x=self.tone(1000,seconds=2);a=self.feed(x,block=127)
        self.setUp();b=self.feed(x,block=1024)
        np.testing.assert_allclose(a.band,b.band,atol=.0001)
        self.lib.audio_rta_dsp_reset_peaks(self.mem)
        z=Snapshot();self.lib.audio_rta_dsp_snapshot(self.mem,C.byref(z))
        self.assertTrue(all(v==-120 for v in z.peak))
        self.setUp();c=self.feed(x/2)
        self.assertAlmostEqual(b.band[13]-c.band[13],20*np.log10(2),delta=.02)
        self.assertEqual(c.samples,len(x));self.assertTrue(all(age<=4096 for age in c.age))
if __name__=="__main__":unittest.main()

