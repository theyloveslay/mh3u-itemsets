"""Execute ARM double-bank storage and all set-edit operations with fault I/O."""
from pathlib import Path
import importlib.util,json,struct
from unicorn import UC_HOOK_CODE,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transaction',ROOT/'tests/test_transaction.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
arm=m.ARM();u=arm.u
STORE,IO,POUCH,NAME=0x11000000,0x11002000,0x11003000,0x11004000
READ,WRITE=0x18ff100,0x18ff110
files={};fault=None;events=[]
u.mem_write(IO,struct.pack('<3I',0,READ,WRITE))
def reg(i):return u.reg_read(getattr(a,f'UC_ARM_REG_R{i}'))
def word(at):return struct.unpack('<I',u.mem_read(at,4))[0]
def callback(uc,address,size,data):
 global fault
 key=(reg(1),reg(2));events.append((address,key));value=0xffffffff
 if address==READ:
  capacity_pointer=word(u.reg_read(a.UC_ARM_REG_SP));capacity=word(capacity_pointer)
  if key==fault:value=0xffffffff
  elif key not in files:value=0
  else:
   b=files[key];u.mem_write(reg(3),b[:capacity]);u.mem_write(capacity_pointer,struct.pack('<I',len(b)));value=1
 elif address==WRITE:
  length=word(u.reg_read(a.UC_ARM_REG_SP));assert length==3712
  b=bytes(u.mem_read(reg(3),length))
  if fault=='write':files[key]=b[:100];value=0
  else:files[key]=b;value=1
 u.reg_write(a.UC_ARM_REG_R0,value);u.reg_write(a.UC_ARM_REG_PC,u.reg_read(a.UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,callback,begin=READ,end=WRITE)
def call(fn,*args):return arm.call(fn,list(args))
def load(character=0):return call('store_load',STORE,IO,character)
def saved_state():return bytes(u.mem_read(STORE,3664))
def names(index):return bytes(u.mem_read(STORE+8+3168+index*20,20)).split(b'\0')[0]
def setbytes(index):return bytes(u.mem_read(STORE+8+index*132,132))
def rename(index,name):u.mem_write(NAME,name+b'\0');return call('set_rename',STORE,IO,index,NAME)

assert load()==1
for i in range(24):assert names(i)==f'Set {i+1}'.encode()
for i in range(24):
 u.mem_write(POUCH,bytes([1,i%2,0,0])+struct.pack('<HH',41+i,1)+bytes(124))
 assert call('set_register',STORE,IO,i,POUCH)==0
 assert rename(i,f'Custom {i+1}'.encode())==0
before=saved_state()
assert load()==1 and saved_state()==before
assert len(files)==2 and all(len(b)==3712 for b in files.values())

a0,a23=setbytes(0),setbytes(23)
assert call('set_reorder',STORE,IO,0,23)==0
assert setbytes(0)==a23 and setbytes(23)==a0
assert names(0)==b'Custom 24' and names(23)==b'Custom 1'
assert call('set_unregister',STORE,IO,23)==0
assert setbytes(23)==bytes(132) and names(23)==b'Set 24'
assert rename(23,b'Empty')==2
assert rename(0,b'x'*19)==0
for bad in [b'',b'x'*20,b'Line\nBreak']:
 before=saved_state();assert rename(0,bad)==1;assert saved_state()==before

# A failed/partial write may spoil only the alternate disk bank. Every editor
# restores the collection, selected bank and sequence, then reload recovers.
fault='write'
for fn,args in [('set_register',[STORE,IO,23,POUCH]),('set_reorder',[STORE,IO,0,22]),('set_unregister',[STORE,IO,0])]:
 before=saved_state();assert call(fn,*args)==3;assert saved_state()==before
before=saved_state();assert rename(0,b'Failed rename')==3;assert saved_state()==before
fault=None;assert load()==1 and saved_state()==before

# Independent character slots. Character mismatch cannot be treated as empty.
for character in [1,2]:
 assert load(character)==1
 assert all(setbytes(i)==bytes(132) for i in range(24))
 assert call('set_register',STORE,IO,character,POUCH)==0
assert load(0)==1 and names(0)==b'x'*19
files[1,0]=files[0,word(STORE+3656)];files.pop((1,1),None)
assert load(1)==0 and word(STORE+3660)==0
before=dict(files);assert call('store_save',STORE,IO)==0 and files==before

# No valid bank + a read error is blocked, rather than creating an empty file.
files.clear();fault=(0,0);assert load()==0
before=dict(files);assert call('set_register',STORE,IO,0,POUCH)==1 and files==before
fault=None
result={'status':'passed','checks':['Register and rename all 24 sets across alternating banks','Reload preserves contents and names','Reorder carries names and can move into empty slots','Unregister resets only the selected set and its default name','Partial-write rollback for register, rename, reorder and unregister','Recovery from one damaged bank','Three independent character slots','Mismatched/corrupt/unreadable banks block writes','19-byte name limit and control-character rejection'],'limitations':['Read/write/flush services are simulated; native 3DS FS not connected']}
(ROOT/'build/store-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
