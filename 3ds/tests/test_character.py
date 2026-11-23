"""Execute native character-apply callback with copying/FS endpoints simulated."""
from pathlib import Path
import importlib.util,json,struct,sys
from unicorn import UC_HOOK_CODE,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u;SAVE,DATA,IO=0x2500000,0x2510000,0x2520000
READ,WRITE=0x180f100,0x180f110
copied=[];reads=[]
def callback(uc,address,size,data):
 r=n.reg
 if address==0x99dd00:
  assert [r(i) for i in range(3)]==[n.UD,DATA+4,0x7a00];copied.append('hunter');n.ret(0)
 elif address==0x999eec:
  assert r(0)==n.UD and r(1)==DATA+0x7a04
  copied.append(r(2));n.ret(0)
 elif address==READ:reads.append((r(1),r(2)));n.ret(0)
 elif address==WRITE:raise AssertionError('Character loading wrote a bank')
u.hook_add(UC_HOOK_CODE,callback)
def call(fn,*args):return n.call(n.symbols[fn],list(args),budget=2000000)
u.mem_write(IO,struct.pack('<3I',0,READ,WRITE));call('item_ui_set_io',IO)
for slot in [0,1,2,0x101,3]:
 n.word(SAVE+0x138,DATA);n.word(SAVE+0x260,slot)
 copied.clear();reads.clear()
 assert call('item_character_applied',SAVE)==1 and copied==['hunter',slot&255]
 assert not reads,'Filesystem access occurred during native character load'
 n.reset(0);call('item_ui_box_step',n.LOBBY)
 expected=slot&255
 assert reads==([(expected,0),(expected,1)] if expected<3 else [])
 store=n.symbols['item_store']
 assert struct.unpack('<I',u.mem_read(store,4))[0]==(expected if expected<3 else 3)
 n.word(SAVE+0x138,0);reads.clear()
 assert call('item_character_applied',SAVE)==0
 n.reset(0);call('item_ui_box_step',n.LOBBY);assert not reads
result={'status':'passed','checks':['Actual native 0x2A2374 function runs before tracking','Slot matches the low-byte argument passed by native secondary copy','Slots 1/2/3 select their own banks; invalid/failed loads unbind storage','No bank access during load callback; first Item Box update performs reads'],'limitations':['Hunter/secondary copying and file I/O endpoints are fixtures','No live character-selection or creation test']}
(ROOT/'build/character-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
