"""Explicitly synthetic PC transport/screenshot fixtures; not hardware evidence."""
import unittest, importlib.util, tempfile, os, queue, time, base64, types
from pathlib import Path
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fsd',R/'tools/fsd.py');fsd=importlib.util.module_from_spec(spec);spec.loader.exec_module(fsd)
def frame(w=2,h=1,data=b'\x01\x02\x03\x04\x05\x06'):
 return f'<<<SHOT w={w} h={h} fmt=rgb888>>>\nSHOTROW y=0 data='+base64.b64encode(data).decode()+'\n<<<ENDSHOT>>>\n'
class Transport:
 def __init__(self):self.q=queue.Queue();self.sent=[];self.closed=False
 def read(self,n):
  try:return self.q.get(timeout=.01)
  except queue.Empty:return b''
 def write(self,b):self.sent.append(b);self.q.put(b'where depth=0 back_fn=none stack=[]\n')
 def close(self):self.closed=True
class SyntheticPC(unittest.TestCase):
 def test_strict_complete_frame(self):
  w,h,d=fsd.decode_shot(frame());self.assertEqual((w,h,len(d)),(2,1,6))
  self.assertEqual(fsd.decode_shot(frame().replace('SHOTROW','I (123) debug preserved\nSHOTROW'))[2],d)
 def test_invalid_incomplete_oversized(self):
  raw=frame()
  for broken in [raw.replace('<<<ENDSHOT>>>',''),frame(data=b'x'),frame(w=999999),frame(h=2),raw.replace('data=','data=!'),raw.replace('y=0','y=1'),raw+raw,raw.replace('<<<ENDSHOT>>>','SHOTROW y=0 data=AQIDBAUG\n<<<ENDSHOT>>>')]:
   with self.subTest(broken=broken),self.assertRaises(fsd.FsdError):fsd.decode_shot(broken)
 def test_routes_fail_before_serial(self):
  for suite,route in [('path','Jammer'),('menu','Attack'),('path','Settings>Format'),('menu','Settings>OK'),('path',''),('smoke','Settings')]:
   with self.subTest(route=route),self.assertRaises(fsd.FsdError):fsd.route_for(suite,route)
  self.assertEqual(fsd.route_for('path','Settings'),('Settings',))
 def test_continuous_raw_preserves_precommand_crash(self):
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
   t=Transport();c=fsd.Console('SYNTHETIC',d,t);t.q.put(b'prior boot evidence\nGuru Medi');t.q.put(b'tation synthetic\n')
   for _ in range(100):
    if c.crashes:break
    time.sleep(.005)
   with self.assertRaises(fsd.FsdError):c.where()
   c.close();self.assertEqual(t.sent,[]);self.assertIn(b'Guru Meditation', (Path(d)/'serial.raw').read_bytes())
 def test_mock_response_logged(self):
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
   t=Transport();c=fsd.Console('SYNTHETIC',d,t);self.assertEqual(c.where()['depth'],0);c.close();self.assertIn(b'stack=[]',(Path(d)/'serial.raw').read_bytes())
 def test_no_false_pass(self):
  class C:
   def where(self):return {'depth':0,'stack':''}
   def heap(self):raise fsd.FsdError('synthetic heap unavailable')
  r=fsd.Run.__new__(fsd.Run);r.steps=[];r.c=C();r.args=types.SimpleNamespace(settle=0);r.dir=Path('/unused')
  with self.assertRaises(fsd.FsdError):r.step('synthetic','')
  self.assertEqual(r.steps[0]['status'],'failed')
 def test_expected_destination_required(self):
  class C:
   def where(self):return {'depth':1,'stack':'Wrong'}
   def heap(self):return {'internal_free':1}
   def shot(self,p):return {'bytes':6}
  r=fsd.Run.__new__(fsd.Run);r.steps=[];r.c=C();r.args=types.SimpleNamespace(settle=0);r.dir=Path('/unused')
  with self.assertRaises(fsd.FsdError):r.step('synthetic','Settings')
  self.assertEqual(r.steps[0]['status'],'failed')
 def test_unavailable_and_cleanup_errors_have_reports(self):
  class BrokenClose:
   crashes=[];error=None
   def close(self):raise OSError('synthetic close failure')
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as d:
   r=fsd.Run.__new__(fsd.Run);r.dir=Path(d);r.board='SYNTHETIC';r.suite='smoke';r.steps=[{'action':'synthetic open','status':'unavailable'}];r.c=None
   self.assertEqual(r.report(),'unavailable');self.assertTrue((r.dir/'report.json').exists())
   r.c=BrokenClose();self.assertEqual(r.report(),'failed');self.assertIn('synthetic close failure',(r.dir/'report.txt').read_text())
 def test_forward_automation_uses_real_tiles_not_direct_nav(self):
  class C:
   def __init__(self):self.calls=[]
   def nav(self,name):raise AssertionError('direct jumps bypass tile lifecycle')
   def back(self):self.calls.append(('back',))
   def tree(self):pass
   def tapt(self,name):self.calls.append(('tapt',name))
  r=types.SimpleNamespace(c=C(),suite='path',steps=[],step=lambda *args:None)
  fsd.execute(r,(fsd.TOOLS,'Settings'))
  self.assertEqual(r.c.calls,[('tapt',fsd.TOOLS),('tapt','Settings'),('back',),('back',)])
if __name__=='__main__':unittest.main()
