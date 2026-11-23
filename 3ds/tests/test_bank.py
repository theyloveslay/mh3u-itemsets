"""Cross-execute ARM codec and the existing Cemu PPC persistence code."""
from pathlib import Path
import importlib.util,json,struct,sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transaction',ROOT/'tests/test_transaction.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
arm=module.ARM();u=arm.u
WIRE,COLLECTION,OUTPUT=0x11000000,0x11002000,0x11004000
def checksum(data):
 value=2166136261
 for i,b in enumerate(data):value=((value^(0 if 16<=i<20 else b))*16777619)&0xffffffff
 return value
def seal(data):
 b=bytearray(data);struct.pack_into('>I',b,16,checksum(b));return bytes(b)
def fixture(version=2,character=0,sequence=0xfffffffe):
 count=20 if version==1 else 24;b=bytearray(2688 if version==1 else 3712)
 struct.pack_into('>5I',b,0,0x4d334c44,version,character,sequence,0)
 for i in range(count):
  off=48+132*i;b[off]=int(i%3!=0);b[off+1]=i%2
  for j in range(32 if i%2 else 24):struct.pack_into('>HH',b,off+4+4*j,2+(i*32+j)%1500,1+(i+j)%10)
  if version==2:
   name=(f'Custom {i+1}' if i%2 else f'Set {i+1}').encode();b[3216+i*20:3216+i*20+len(name)]=name
 return seal(b)
def decode(data,character=0):
 u.mem_write(WIRE,data);return arm.call('bank_decode',[WIRE,len(data),character,COLLECTION])
def encode():
 assert arm.call('bank_encode',[COLLECTION,OUTPUT])==1
 return bytes(u.mem_read(OUTPUT,3712))

original=fixture();assert decode(original)==1
# This must be byte-identical, not merely numerically equivalent.
assert encode()==original

# Run the deployed Cemu adapter (PPC), using the ARM-produced bank as its file.
sys.path.insert(0,str(ROOT.parent/'cemu/tests'))
from game_harness import Game
g=Game(files={'mh3u_loadouts_user1_a.bin':encode()})
assert g.call('ensure_loaded',[])==1
assert bytes(g.u.mem_read(g.local('sets'),24*132))==original[48:3216]
assert bytes(g.u.mem_read(g.local('set_names'),24*20))==original[3216:3696]
assert g.call('persist',[])==1
saved=g.files['mh3u_loadouts_user1_b.bin']
assert struct.unpack_from('>I',saved,12)[0]==0xffffffff
assert decode(saved)==1 and encode()==saved

# Both Cemu and ARM upgrade the legacy 20-set version in the same way.
v1=fixture(1);assert decode(v1)==1;upgraded=encode()
old=Game(files={'mh3u_loadouts_user1_a.bin':v1})
assert old.call('ensure_loaded',[])==1
assert bytes(old.u.mem_read(old.local('sets'),3168))==upgraded[48:3216]
assert bytes(old.u.mem_read(old.local('set_names'),480))==upgraded[3216:3696]

# Preserve arbitrary name bytes and Cemu's legacy default-name migration.
names=bytearray(fixture())
names[3216:3236]=b'Item Set 09'+bytes(9)
names[3236:3256]='Énergie'.encode().ljust(20,b'\0')
names=seal(names);assert decode(names)==1;migrated=encode()
assert migrated[3216:3236]==b'Set 9'+bytes(15)
assert migrated[3236:3256]==names[3236:3256]

bad=[]
for size in [0,1,47,2687,2689,3711,3713]:bad.append(fixture()[:size] if size<=3712 else fixture()+b'\0')
for index in [0,4,8,12,16,48,511,3216,3711]:
 b=bytearray(fixture());b[index]^=1;bad.append(bytes(b))
for index in [48,49,48+23*132,49+23*132]:
 b=bytearray(fixture());b[index]=2;bad.append(seal(b))
for data in bad:
 u.mem_write(COLLECTION,b'\xA5'*3656)
 assert decode(data)==0
 assert bytes(u.mem_read(COLLECTION,3656))==b'\xA5'*3656
assert decode(fixture(),1)==0
for candidate,baseline,want in [(0,0xffffffff,1),(1,0xfffffffe,1),(0xffffffff,0,0),(8,8,0),(9,8,1),(8,9,0),(0x80000000,0,0)]:
 assert arm.call('bank_newer',[candidate,baseline])==want
result={'status':'passed','wire_format':'Existing Cemu M3LD big-endian v2, 3712 bytes','engines':['Compiled ARM11 codec','Existing compiled Cemu PPC adapter'],'checks':['ARM output accepted by existing Cemu loader','Cemu output decoded and re-encoded byte-identically by ARM','All 24 sets, all 32 slots, custom names preserved','v1 20-set upgrade matches existing Cemu behavior','Legacy default-name migration and UTF-8 bytes','Reject malformed/corrupt/wrong-character banks without mutating output','Wraparound sequence comparison'],'limitations':['OS file I/O is simulated; 3DS storage path and UI are not integrated']}
(ROOT/'build/bank-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
