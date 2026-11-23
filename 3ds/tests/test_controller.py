"""Execute Item Sets controller with native input/inventory and fixture FS/UI."""
from pathlib import Path
import ctypes as C,importlib.util,json,struct,sys
from unicorn import UC_HOOK_CODE,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u;UI=n.symbols['item_ui'];STORE=n.symbols['item_store'];IO=0x2500000
READ,WRITE=0x180f100,0x180f110
files={};fail_write=False;keyboard_done=False;keyboard_text=b''
def string(address):
 out=bytearray()
 for i in range(500):
  v=u.mem_read(address+i,1)[0]
  if not v:return out.decode()
  out.append(v)
 raise AssertionError('Unterminated string')
def word(at):return struct.unpack('<I',u.mem_read(at,4))[0]
def callback(uc,address,size,data):
 r=n.reg
 if address==READ:
  key=r(1),r(2);length=word(u.reg_read(a.UC_ARM_REG_SP))
  if key not in files:n.ret(0)
  else:u.mem_write(r(3),files[key]);n.word(length,len(files[key]));n.ret(1)
 elif address==WRITE:
  assert word(u.reg_read(a.UC_ARM_REG_SP))==3712
  files[r(1),r(2)]=bytes(u.mem_read(r(3),100 if fail_write else 3712));n.ret(0 if fail_write else 1)
 elif address in [0x526268,0x525dbc]:n.ret(0)
 elif address==0x590540:assert r(1)==6;n.ret(0)
 elif address==0x58eb40:n.ret(int(keyboard_done))
 elif address==0x58dbe4:u.mem_write(r(1),keyboard_text+b'\0');n.ret(1)
u.hook_add(UC_HOOK_CODE,callback)
u.mem_write(IO,struct.pack('<3I',0,READ,WRITE))
n.word(0xc3b978,0x2510000);n.word(0xc3b9cc,0x2511000);n.word(0xb916c0,0)
for i in range(0x5fd):u.mem_write(n.TABLE+20*i,bytes([1,0,0,20])+bytes(16))
def call(name,*args):return n.call(n.symbols[name],list(args),budget=2000000)
def step(buttons=0,dirs=0):
 n.buttons,n.dirs=buttons,dirs
 result=call('item_ui_box_step',n.LOBBY);n.buttons=n.dirs=0;return result
def field(offset):return word(UI+offset)
def select(index):n.word(UI+12,index)
class Slot(C.Structure):_fields_=[('id',C.c_uint16),('count',C.c_uint16)]
class Frame(C.Structure):
 _fields_=[('title',C.c_uint32),('names',C.c_uint32*8)]+[(name,C.c_uint32) for name in ['valid','selected','anchor','page','help','choice','gunner','pouch_page','pouch_pages']]+[('pouch',Slot*32)]
def frame():return Frame.from_buffer_copy(bytes(u.mem_read(call('item_ui_frame'),C.sizeof(Frame))))
def open_action(action,tavern=False):
 n.reset(int(tavern));n.half(n.state+6,3 if tavern else 6);n.half(n.state+8,action);n.half(n.state+10,1)
 assert step(0x10)==0 and field(0)==1 and field(4)==action and field(8)==0
def clear_inventory():u.mem_write(n.HUNTER+0xa8,bytes(0x1080))
def put(address,item,count):u.mem_write(address,struct.pack('<HH',item,count))
def stored(index):return bytes(u.mem_read(STORE+8+index*132,132))
call('item_ui_set_io',IO);call('item_ui_bind',0)
open_action(1)
for index in range(24):
 select(index);f=frame()
 assert not f.valid and string(f.names[index%8])==f"Set {index+1}"
for index in range(24):
 select(index);clear_inventory();n.weapon=4 if index%2 else 0
 put(n.HUNTER+(0x108 if index%2 else 0xa8),41+index,2)
 step(0x10);assert field(8)==1
 f=frame();assert (f.pouch[0].id,f.pouch[0].count)==(41+index,2) and f.gunner==index%2
 step(0x10);assert field(8)==2 and frame().help==617
 step(0x10);assert field(8)==0
 f=frame();assert f.page==index//8+1 and string(f.names[index%8])==f'Set {index+1}'
 keyboard_done=False;step(0x80);assert field(8)==3
 step();assert field(8)==3
 keyboard_text=f'Custom {index+1}'.encode();keyboard_done=True;step();assert field(8)==0
 assert string(frame().names[index%8])==f'Custom {index+1}'

# Three-page and eight-row navigation; page changes reset pouch page/warning.
select(0);step(dirs=1);assert field(12)==7
step(dirs=2);assert field(12)==0
step(dirs=8);assert field(12)==8
step(dirs=8);assert field(12)==16
step(dirs=8);assert field(12)==0
step(dirs=4);assert field(12)==16
select(0);step(0x100);assert frame().pouch_page==2
step(0x200);assert frame().pouch_page==0
select(1);step(0x100);assert frame().pouch_page==3
step(0x200);assert frame().pouch_page==0

# Exit to submenu, then move a named registration across set pages.
step(0x20);assert field(0)==0 and n.half(n.state+10)==1
open_action(2);select(0);source=stored(0);step(0x10);assert field(16)==0
step(dirs=4);assert field(12)==16 and field(16)==0
select(23);step(0x10);assert field(16)==0xffffffff and stored(23)==source
assert string(frame().names[7])=='Custom 1'
step(0x20);open_action(3);select(23);step(0x10);step(0x10)
assert stored(23)==bytes(132)

# Partial result previews actual contents; acknowledgement restores registration.
step(0x20);open_action(1);select(0);n.weapon=0;clear_inventory();put(n.HUNTER+0xa8,41,10)
step(0x10);step(0x10);step(0x10);step(0x20)
clear_inventory();put(n.HUNTER+0x108,41,1);put(n.HUNTER+0x188,41,8)
open_action(0);select(0);before=stored(0);step(0x10);step(0x10)
f=frame();assert field(28)==1 and f.help==611 and (f.pouch[0].id,f.pouch[0].count)==(41,9)
assert stored(0)==before
step(0x10);f=frame();assert f.help==612 and f.pouch[0].count==10
step(dirs=2);assert field(28)==0 and frame().help==599

# View Mode uses the native entry/camera, and retains list selection.
old=field(12);step(0x40);assert bytes(u.mem_read(n.state+3,1))==b'\x01'
step();assert field(12)==old and field(0)==1
u.mem_write(n.state+3,b'\0');assert 0x257440 in n.events and 0x5faadc in n.events
step(0x20)

# Tavern's fourth entry and storage failure acknowledgement.
open_action(1,True);select(2);before=stored(2);fail_write=True
step(0x10);step(0x10);assert frame().help==620 and stored(2)==before
fail_write=False
call('item_ui_bind',3);call('item_ui_open',0);assert frame().help==619 and frame().valid==0
result={'status':'passed','checks':['Room and Tavern native submenu dispatch into all four actions','Register and native-keyboard rename all 24 sets','Three set pages and independent 3/4-page pouch navigation','Named reorder across pages and unregister','Best-effort load previews actual pouch only on shortage result','Original registration retained after apply','Native View Mode entry/selection retention and rotation callback','Write failure preserves prior registration; unbound character blocks storage'],'limitations':['Input, filesystem and keyboard services are fixtures','No installed hooks or actual framebuffer rendering']}
(ROOT/'build/controller-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
