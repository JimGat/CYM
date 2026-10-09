#!/usr/bin/env python3
"""Read-only eight-board package gate; never builds, flashes or downloads."""
from pathlib import Path
import argparse,hashlib,json,re,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
BOARDS=[
 ('nm-cyd-c5','ESP32C5','build_nm-cyd-c5','docs/manifest.json','NM_CYD_C5',16),
 ('ws-c5-28','ESP32C5','build_ws-c5-28','docs/manifest.ws-c5-28.json','WS_C5_28',32),
 ('cyd-2432s028','ESP32','build_cyd2usb','docs/manifest.cyd-2432s028.json','CYD2USB',4),
 ('hosyond-s3-35','ESP32S3','build_hosyond-s3-35','docs/manifest.hosyond-s3-35.json','HOSYOND_S3_35',16),
 ('ws-c5-35','ESP32C5','build_ws-c5-35','docs/manifest.ws-c5-35.json','WS_C5_35',32),
 ('pancake-c5','ESP32C5','build_pancake-c5','docs/manifest.pancake-c5.json','PANCAKE_C5',8),
 ('hackerbox-cyd','ESP32','build_hackerbox-cyd','docs/manifest.hackerbox-cyd.json','HACKERBOX_CYD',4),
 ('ws-s3-5b','ESP32S3','build_ws-s3-5b','docs/manifest.ws-s3-5b.json','WS_S3_5B',16)]
def sha(b):return hashlib.sha256(b).hexdigest()
def sections(path):
 b=path.read_bytes();assert b[:6]==b'\x7fELF\x01\x01'
 off=struct.unpack_from('<I',b,32)[0];ents,names_count,names_idx=struct.unpack_from('<HHH',b,46)
 rows=[struct.unpack_from('<IIIIIIIIII',b,off+i*ents) for i in range(names_count)]
 st=rows[names_idx];strings=b[st[4]:st[4]+st[5]]
 return [dict(name=strings[x[0]:].split(b'\0')[0].decode(),type=x[1],flags=x[2],addr=x[3],size=x[5]) for x in rows]
def verify(version,commit=None):
 result=[];artifacts=[]
 for board,soc,build_name,mp,flag,mb in BOARDS:
  base=ROOT/soc;build=base/build_name;manifest_path=base/mp;m=json.loads(manifest_path.read_text())
  assert m['version']==m['build']==version,(board,'manifest version')
  d=json.loads((build/'project_description.json').read_text());assert d['project_version']==version
  cfg=(build/'config/sdkconfig.h').read_text()
  assert '#define CONFIG_BOARD_'+flag+' 1' in cfg,(board,'board flag',flag)
  ws=board in ('ws-c5-28','ws-c5-35')
  assert ('#define CONFIG_BOARD_WS_C5_28 1' in cfg or '#define CONFIG_BOARD_WS_C5_35 1' in cfg)==ws
  f=json.loads((build/'flasher_args.json').read_text());assert f['flash_settings']['flash_size']==str(mb)+'MB',(board,f['flash_settings'])
  parts=m.get('parts') or m['builds'][0]['parts'];assert len(parts)==3
  exported={};app=None;partition=None
  for part in parts:
   p=(manifest_path.parent/part['path']).resolve();assert p.is_relative_to(base.resolve())
   data=p.read_bytes();offset=part['offset'];original=build/f['flash_files'][hex(offset)]
   assert data==original.read_bytes(),(board,'package does not equal generated part',p)
   assert offset+len(data)<=mb*1024*1024
   rec=dict(board=board,path=str(p.relative_to(ROOT)),size=len(data),sha256=sha(data),offset=offset)
   if 'sha256' in part:assert part['sha256']==rec['sha256']
   if 'size' in part:assert part['size']==rec['size']
   artifacts.append(rec);exported[offset]=data
   if offset==int(f['app']['offset'],0):app=p
   if offset==int(f['partition-table']['offset'],0):partition=data
  assert app and partition
  ab=app.read_bytes();assert ab[0]==0xe9 and struct.unpack_from('<I',ab,32)[0]==0xabcd5432
  descriptor=ab[48:80].split(b'\0')[0].decode();assert descriptor==version,(board,descriptor)
  flash_mib=1<<(ab[3]>>4);assert flash_mib==mb,(board,flash_mib,mb)
  assert struct.unpack_from('<H',ab,12)[0]=={'esp32':0,'esp32s3':9,'esp32c5':23}[d['target']]
  partitions=[]
  for i in range(0,len(partition),32):
   if struct.unpack_from('<H',partition,i)[0]!=0x50aa:break
   magic,typ,sub,offset,size,label,flags=struct.unpack_from('<HBBII16sI',partition,i)
   assert offset+size<=mb*1024*1024
   partitions.append(dict(type=typ,subtype=sub,offset=offset,size=size,label=label.split(b'\0')[0].decode()))
  ap=next(x for x in partitions if x['type']==0 and x['offset']==65536)
  assert len(ab)<=ap['size'],(board,'app partition overflow')
  full=app.with_name(app.stem+'-full.bin');fb=full.read_bytes()
  for off,data in exported.items():
   actual=fb[off:off+len(data)]
   # esptool merge rewrites ONLY boot header SPI flash mode/frequency/size.
   if off==int(f['bootloader']['offset'],0):
    assert actual[:2]==data[:2] and actual[4:]==data[4:]
    assert (1<<(actual[3]>>4))==mb
   else:assert actual==data,(board,'merged part mismatch',off)
  assert len(fb)==65536+len(ab) and len(fb)<=mb*1024*1024
  artifacts.append(dict(board=board,path=str(full.relative_to(ROOT)),size=len(fb),sha256=sha(fb),offset=0))
  nm=d['c_compiler'].removesuffix('gcc')+'nm'
  sym=subprocess.check_output([nm,'-S','--defined-only',str(build/d['app_elf'])],text=True)
  names={l.split()[-1] for l in sym.splitlines() if l.split()}
  for name in ('D_DoomMain','doomgeneric_Tick','doom_ui_attach_footer','_doom_init_start','_doom_init_end','_doom_zero_start','_doom_zero_end'):
   assert (name in names)==ws,(board,'engine inclusion',name)
  sec=sections(build/d['app_elf'])
  addresses={l.split()[-1]:int(l.split()[0],16) for l in sym.splitlines() if l.split()}
  state_size=0;reset_ranges=[]
  if ws:
   for stem,external in [('doom_init',False),('doom_zero',True),('doom_common',True)]:
    lo=addresses['_'+stem+'_start'];hi=addresses['_'+stem+'_end'];assert hi>=lo
    if hi>lo:
     containing=next(x for x in sec if x['addr']<=lo and hi<=x['addr']+x['size'] and x['flags']&2)
     assert containing['type']==(8 if external else 1),(board,stem,'initialization contract',containing)
     assert (0x42000000<=lo<0x43000000) if external else (0x40800000<=lo<0x4084e5a0)
    state_size+=hi-lo;reset_ranges.append(dict(name=stem,start=lo,end=hi,size=hi-lo,external=external))
   assert reset_ranges[0]['size']>0 and reset_ranges[1]['size']>0
   for pointer in ['states','mobjinfo']:
    assert addresses['_doom_zero_start']<=addresses[pointer]<addresses['_doom_zero_end']
  else:
   assert not any(n.startswith('_doom_') for n in names)
  ram=[x for x in sec if x['flags']&2 and x['size'] and (0x40800000<=x['addr']<0x4084e5a0 if soc=='ESP32C5' else x['name'].startswith(('.dram','.iram')))]
  memory=dict(engine_state_bytes=state_size,reset_ranges=reset_ranges,linked_internal_allocated_bytes=sum(x['size'] for x in ram),sections=ram)
  if soc=='ESP32C5':memory['static_internal_upper_bound_free']=0x4084e5a0-max(x['addr']+x['size'] for x in ram)
  result.append(dict(board=board,manifest=str(manifest_path.relative_to(ROOT)),manifest_sha256=sha(manifest_path.read_bytes()),version=descriptor,flash_mib=mb,app_bytes=len(ab),app_partition_bytes=ap['size'],app_free_bytes=ap['size']-len(ab),full_bytes=len(fb),partitions=partitions,memory=memory,engine=ws,generated_config=str((build/'config/sdkconfig.h').relative_to(ROOT))))
  print(board,'PASS',descriptor,'app',len(ab),'state',memory['engine_state_bytes'],flush=True)
 assert len(result)==8 and len(artifacts)==32
 if commit:
  for a in artifacts:
   blob=subprocess.check_output(['git','show',commit+':'+a['path']],cwd=ROOT)
   assert len(blob)==a['size'] and sha(blob)==a['sha256'],('Git artifact differs or is LFS pointer',a['path'])
 return dict(version=version,boards=result,artifacts=artifacts,counts=dict(boards=8,artifacts=32),git_objects_verified=commit)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--version',required=True);p.add_argument('--output',required=True);p.add_argument('--commit');a=p.parse_args()
 r=verify(a.version,a.commit);Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print('VERIFIED eight boards, 32 artifacts',flush=True)
