"""Run compiled inventory bridge + native capacity/classification + ARM core.
The game code is real; inventory contents and item-rule rows are fixtures.
"""
from pathlib import Path
import importlib.util,json,struct,sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u
WANT,MISSING=0x2500000,0x2500200
def slots(address,count):return [struct.unpack('<HH',u.mem_read(address+4*i,4)) for i in range(count)]
def put(address,index,item,count):u.mem_write(address+4*index,struct.pack('<HH',item,count))
def call(name,args):return n.call(n.symbols[name],args,budget=2000000)
def reset(gunner=False,flags=0):
 n.weapon=4 if gunner else 0
 u.mem_write(n.HUNTER+0xa8,bytes(0x1080))
 n.word(n.HUNTER+0x60b4,flags)
 u.mem_write(WANT,bytes(132))
def register(gunner,items):
 u.mem_write(WANT,bytes([1,gunner,0,0])+b''.join(struct.pack('<HH',i,c) for i,c in items)+bytes(4*(32-len(items))))
def apply():return call('apply_native_pouch',[WANT,MISSING])
for i in range(0x5fd):u.mem_write(n.TABLE+i*20,bytes([1,0,0,20])+bytes(16))
capacities=[]
for flags,expected in [(0,600),(0x80,800),(0x180,1000)]:
 reset(flags=flags);assert n.call(0x999ffc,[n.UD,n.HUNTER])==expected;capacities.append(expected)

# Every eligible ID in both directions. Pair source slots to demonstrate the
# bridge does not specialize charms, potions, ammunition or any one item ID.
eligible=[i for i in range(2,0x5fd) if not 0x4db<=i<=0x4de and i!=0x5f3]
for gunner in [0,1]:
 for start in range(0,len(eligible),12):
  reset(bool(gunner))
  group=eligible[start:start+12];target=n.HUNTER+(0x108 if gunner else 0xa8);donor=n.HUNTER+(0xa8 if gunner else 0x108);box=n.HUNTER+0x188
  for j,item in enumerate(group):put(donor,j,item,1);put(box,j,item,1)
  register(gunner,[(i,2) for i in group]);assert apply()==0
  assert slots(target,len(group))==[(i,2) for i in group]
  assert all(c==0 for i,c in slots(donor,32 if not gunner else 24))
  assert all(c==0 for i,c in slots(box,600))
  assert call('capture_native_pouch',[WANT])==0
  assert bytes(u.mem_read(WANT,4))==bytes([1,gunner,0,0])
  assert slots(WANT+4,len(group))==[(i,2) for i in group]

# All 32 Gunner slots, including the eight ammunition slots. Exercise both
# ammunition categories alongside ordinary items in the first 24 slots.
reset(True);box=n.HUNTER+0x188
items=[(100+i,2) for i in range(32)]
for j,(item,count) in enumerate(items):
 category=0 if j<24 else (1 if j%2 else 4)
 u.mem_write(n.TABLE+item*20,bytes([category,0,0,20])+bytes(16))
 put(box,j,item,count)
register(1,items);assert apply()==0
assert slots(n.HUNTER+0x108,32)==items
assert call('capture_native_pouch',[WANT])==0 and slots(WANT+4,32)==items

# Shortage commits available stock, and leaves the registration intact.
for gunner in [0,1]:
 reset(bool(gunner));target=n.HUNTER+(0x108 if gunner else 0xa8);donor=n.HUNTER+(0xa8 if gunner else 0x108);box=n.HUNTER+0x188
 register(gunner,[(41,10),(42,1)]);saved=bytes(u.mem_read(WANT,132))
 put(donor,0,41,1);put(box,0,41,8)
 assert apply()==3 and n.reg(0)==3
 assert struct.unpack('<I',u.mem_read(MISSING,4))[0]==2
 assert slots(target,2)==[(41,9),(0,0)]
 assert bytes(u.mem_read(WANT,132))==saved

# Full box rolls back all inventories; inaccessible pages cannot absorb surplus.
reset();target=n.HUNTER+0xa8;donor=n.HUNTER+0x108;box=n.HUNTER+0x188
for j in range(600):put(box,j,43,99)
put(target,0,44,1);register(0,[(41,1)])
before=bytes(u.mem_read(target,0x1080));assert apply()==4
assert bytes(u.mem_read(target,0x1080))==before

reset();register(1,[(41,1)]);assert apply()==2
for item in [0x4db,0x4dc,0x4dd,0x4de,0x5f3]:
 reset();register(0,[(item,1)]);assert apply()==1

result={'status':'passed','item_ids_exercised_each_direction':len(eligible),'directions':2,'native_unlocked_capacities':capacities,'checks':['Direct donor + box allocation and capture for every eligible ID','32-slot Gunner capture/load including both ammo categories in slots 24-31','Partial commit, missing slots and original registration retention','Full box rollback with unlocked capacity boundary','Wrong pouch and mask action rejection','AAPCS stack and preserved registers checked on every call'],'limitations':['Item metadata and inventory contents are fixtures','No installed hooks or game UI/storage integration']}
(ROOT/'build/inventory-bridge-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
