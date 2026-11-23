"""Execute diagnostic ARM code, QueryMemory bridge and bounded capture.
Kernel query responses and the final file sink are fixtures; IPC is tested separately.
"""
from pathlib import Path
import importlib.util,struct,sys,json
from unicorn import UC_HOOK_CODE,UC_HOOK_INTR,arm_const as a
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from read_layout_report import decode
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u
WIDGET,SCROLL,LINE,OBJECT_ROOT,OBJECT,ARRAYS,FONTS=0x2500000,0x2510000,0x2511000,0x2520000,0x2521000,0x2530000,0x2540000
BAD=0x0badf000
captured=[];queries=[]
def reg(i):return n.reg(i)
def intr(uc,number,data):
 pc=u.reg_read(a.UC_ARM_REG_PC);svc=struct.unpack('<I',u.mem_read(pc-4,4))[0]&0xffffff
 assert svc==2,hex(svc)
 address=reg(2);queries.append(address)
 found=None
 for lo,hi,perm in u.mem_regions():
  if lo<=address<=hi:found=(lo,hi-lo+1,perm);break
 base,size,perm=found or (address&~4095,4096,0)
 for i,value in enumerate([0,base,size,perm,5,0]):u.reg_write(getattr(a,f'UC_ARM_REG_R{i}'),value)
def cb(uc,address,length,data):
 if address==n.symbols['sd_write_layout_report']:
  captured.append(bytes(u.mem_read(reg(0),reg(1))));n.ret(1)
u.hook_add(UC_HOOK_INTR,intr);u.hook_add(UC_HOOK_CODE,cb)
def call(name,*args):return n.call(n.symbols[name],list(args),budget=2000000)
# Real wrapper must preserve AAPCS nonvolatile registers across kernel outputs.
assert call('item_memory_readable',WIDGET,0x240)==1
for p,size in [(BAD,0x120),(0x25ffffc,0x120),(0xfffffff0,0x100)]:assert call('item_memory_readable',p,size)==0
n.word(WIDGET+0xf4,SCROLL);n.word(SCROLL+0x68,428);n.word(SCROLL+0x80,LINE);n.word(LINE+0x68,593)
n.word(SCROLL+0xf8,OBJECT_ROOT);n.word(LINE+0xf8,BAD)
EXTRA=0x2512000
n.word(LINE+0x84,EXTRA);n.word(EXTRA+0x68,438);n.word(EXTRA,0xb5ea6c);n.word(EXTRA+0xf8,OBJECT_ROOT)
n.word(OBJECT_ROOT+0x7c,OBJECT);n.word(OBJECT,0xb551e4);n.word(OBJECT+0x80,BAD)
for j,off in enumerate([0x224,0x228,0x230]):
 n.word(WIDGET+off,ARRAYS+j*0x100)
 for i in range(8):n.word(ARRAYS+j*0x100+i*4,FONTS+(j*8+i)*0x200)
call('item_diag_targets',SCROLL,LINE,OBJECT_ROOT,0)
for frame in range(60):
 call('item_diag_animation',SCROLL);call('item_diag_animation',LINE)
 call('item_diag_menu',WIDGET,n.state)
 if frame<59:assert not captured
assert len(captured)==1
report=decode(captured[0]);assert report['menu_frames']==60 and report['scroll_calls']==59 and report['divider_calls']==59
assert report['scroll']==hex(SCROLL) and report['divider']==hex(LINE)
assert report['invalid_reads']>=2 and report['animation_sample_count']==2
assert any(r['kind']=='unreadable' and r['address']==hex(BAD) for r in report['data'])
assert any(r['kind']=='instance' and r['address']==hex(LINE) for r in report['data'])
assert any(r['kind']=='watched-instance' and r['aux']==438 for r in report['data'])
assert report['build']=='0x500d4'
assert len(captured[0])<=65536
for frame in range(90):call('item_diag_menu',WIDGET,n.state)
assert len(captured)==1
try:decode(captured[0][:-1])
except ValueError:pass
else:raise AssertionError('Truncated report accepted')
result={'status':'passed','checks':['QueryMemory ABI preserves nonvolatile registers','Unmapped, cross-region and overflowing reads rejected','Capture waits for 60 room-menu frames and writes once','Live watcher counts, UI arrays and nested tree captured','Unmapped GUI pointers recorded without dereference','Binary length/record counts validated by standalone reader'],'fixture_capture_bytes':len(captured[0]),'limitations':['Kernel memory map and file sink simulated; hardware capture still needs to be run']}
(ROOT/'build/diagnostics-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
