"""Check compiled native keyboard adapter ABI against traced 3DS call sites."""
from pathlib import Path
import importlib.util,json,struct,sys
from unicorn import UC_HOOK_CODE,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
# Resolve the original LDR literal, so the fixture cannot validate a guessed flag address.
raw=Path(sys.argv[1]).read_bytes();site=0x613cdc
instruction=struct.unpack_from('<I',raw,site-0x100000)[0]
literal=site+8+(instruction&0xfff)
assert struct.unpack_from('<I',raw,literal-0x100000)[0]==0xb916c0
u=n.u;SESSION,NAME,GAME=0x2500000,0x2500100,0x2510000
done=False;accepted=True;events=[]
n.word(0xc3b978,GAME);n.word(0xb916c0,0x200)
u.mem_write(NAME,b'Custom set\0')
def callback(uc,address,size,data):
 r=n.reg
 if address in [0x526268,0x525dbc]:
  assert r(0)==n.UI;events.append(address);n.ret(0)
 elif address==0x590540:
  assert [r(i) for i in range(3)]==[GAME,6,NAME];events.append(address);n.ret(0)
 elif address==0x58eb40:assert r(0)==GAME;n.ret(int(done))
 elif address==0x58dbe4:
  assert [r(i) for i in range(4)]==[GAME,SESSION+4,19,1]
  args=struct.unpack('<4I',u.mem_read(u.reg_read(a.UC_ARM_REG_SP),16))
  assert args==(0,0xffffffff,0xffffffff,0xffffffff),args
  u.mem_write(r(1),b'New set name\0');events.append(address);n.ret(int(accepted))
u.hook_add(UC_HOOK_CODE,callback)
def call(fn,*args):return n.call(n.symbols[fn],list(args))
assert call('native_rename_begin',SESSION,NAME)==1
assert struct.unpack('<I',u.mem_read(0xb916c0,4))[0]==0x204
assert call('native_rename_begin',SESSION,NAME)==0
assert call('native_rename_poll',SESSION)==0
done=True;assert call('native_rename_poll',SESSION)==1
assert bytes(u.mem_read(SESSION+4,20)).split(b'\0')[0]==b'New set name'
assert struct.unpack('<I',u.mem_read(0xb916c0,4))[0]==0x200
assert events==[0x526268,0x590540,0x58dbe4,0x525dbc]
accepted=False
assert call('native_rename_begin',SESSION,NAME)==1
assert call('native_rename_poll',SESSION)==0xffffffff
n.word(0xb916c0,0x204);assert call('native_rename_begin',SESSION,NAME)==0
n.word(0xb916c0,0x200)
assert call('native_rename_begin',SESSION,NAME)==1
n.word(0xc3b978,0);assert call('native_rename_poll',SESSION)==0xffffffff
assert struct.unpack('<I',u.mem_read(0xb916c0,4))[0]==0x200
result={'status':'passed','checks':['Native request kind 6 and initial-name pointer','Completion query and all eight result arguments match Equipment Sets ABI','19-byte result buffer and termination','Cancel, busy overlay and disappearing game context cleanup','Original overlay bits retained and native UI restore called'],'limitations':['Native keyboard services are simulated','Visual timing and actual keyboard appearance are not game-tested']}
(ROOT/'build/rename-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
