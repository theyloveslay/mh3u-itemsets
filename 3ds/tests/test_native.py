"""Run native US 3DS inventory and menu helpers from the owned executable.
Usage: python tests/test_native.py DECOMPRESSED_CODE
External input/audio/weapon metadata and item parameter contents are fixtures.
"""
from pathlib import Path
import json,struct,sys,hashlib
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn import arm_const as a
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
code=Path(sys.argv[1]).read_bytes()
assert hashlib.sha256(code).hexdigest() in ('80db9caa329faacfaa580e435fce99614029a4bc201b5a898f56ff8a9a2b9006','fb60817c7dbc0c246f14c4525bfc5ff7fc14698b99781e3d9f77fdeec0e83b6d')
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x100000,0xd00000);u.mem_write(0x100000,code)
u.mem_map(0x1800000,0x100000);u.mem_map(0x2000000,0x600000);u.mem_map(0x2f00000,0x100000)
with open(ROOT/'build/loadouts-arm.elf','rb') as f:
 elf=ELFFile(f)
 for s in elf.iter_sections():
  if s['sh_flags']&2 and s['sh_size']:u.mem_write(s['sh_addr'],s.data())
 symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
UD,HUNTER,LOBBY,UI,TABLE,STACK,STOP=0x2000000,0x2000018,0x2200000,0x2300000,0x2400000,0x2ffe000,0x2fff000
state=LOBBY+0x67d0
buttons=dirs=weapon=0;events=[]
def reg(i):return u.reg_read(getattr(a,f'UC_ARM_REG_R{i}'))
def word(addr,value):u.mem_write(addr,struct.pack('<I',value))
def half(addr,value=None):
 if value is not None:u.mem_write(addr,struct.pack('<H',value))
 return struct.unpack('<H',u.mem_read(addr,2))[0]
def ret(value):u.reg_write(a.UC_ARM_REG_R0,value);u.reg_write(a.UC_ARM_REG_PC,u.reg_read(a.UC_ARM_REG_LR))
def callback(uc,addr,size,data):
 if addr==0x5ca6d4:ret(bool(buttons&reg(1)))
 elif addr==0x5cff40:ret(dirs)
 elif addr in (0x2d44c8,0x5faadc,0x257440):events.append(addr);ret(0)
 elif addr==0x892dc4:ret(weapon)
u.hook_add(UC_HOOK_CODE,callback)
word(0xc43360,UD);word(0xc406a0,UI);word(0xcb9954,TABLE)
def call(address,args,budget=100000):
 u.reg_write(a.UC_ARM_REG_SP,STACK);u.reg_write(a.UC_ARM_REG_LR,STOP)
 preserved={i:0x98760000+i for i in range(4,12)}
 for i,v in preserved.items():u.reg_write(getattr(a,f'UC_ARM_REG_R{i}'),v)
 for i,v in enumerate(args):
  if i<4:u.reg_write(getattr(a,f'UC_ARM_REG_R{i}'),v)
  else:word(STACK+(i-4)*4,v)
 u.emu_start(address,STOP,count=budget)
 assert u.reg_read(a.UC_ARM_REG_PC)==STOP,(hex(address),'budget')
 assert u.reg_read(a.UC_ARM_REG_SP)==STACK
 assert all(reg(i)==v for i,v in preserved.items()),'Nonvolatile register clobber'
 return reg(0)
checks=[]
for kind,count,offset in [(0,24,0xa8),(1,32,0x108)]:
 assert call(0x99a0f8,[UD,kind])==count
 assert call(0x99a108,[UD,HUNTER,kind])==HUNTER+offset
checks.append('Native pouch selectors and counts confirm Blade 24, Gunner 32 and offsets A8/108 from hunter')
for weapon in range(16):assert call(0x9987ac,[UD,HUNTER])==int(weapon in [4,5,6,10,13])
checks.append('Native gunner classification matches its weapon-type switch')
for item in [0,1,41,94,0x5fc,0x5fd,0x1000]:
 expected=item if item<0x5fd else 0
 assert call(0x57ab4c,[item])==TABLE+20*expected
# Native donor capacity lookup reads carry limit at offset 3, same as Wii U.
u.mem_write(TABLE+41*20,bytes([0,0,0,1])+bytes(16))
u.mem_write(HUNTER+0xa8,struct.pack('<HH',41,1))
assert call(0x99b810,[UD,41,HUNTER+0xa8,24])==0
half(HUNTER+0xaa,0);assert call(0x99b810,[UD,41,HUNTER+0xa8,24])==1
checks.append('Native item accessor verifies 20-byte records, 0x5FD bound and carry-limit byte at offset 3')

def step(btn=0,direction=0):
 global buttons,dirs
 buttons,dirs=btn,direction
 result=call(symbols['probe_box_menu'],[LOBBY]);buttons=dirs=0
 return result

def reset(mode):
 u.mem_write(state,bytes(0x100));u.mem_write(state,b'\x02\0'+bytes([mode])+b'\0')
 half(state+12,3 if mode else 6)
reset(0)
assert step()==0 and half(state+12)==7
half(state+6,2);step(direction=2);assert half(state+6)==6
step(direction=2);assert half(state+6)==3
for action in range(4):
 reset(0);half(state+6,6);step(0x10);assert half(state+14)==4
 half(state+8,action);assert step(0x10)==0x100+action
checks.append('Compiled probe plus actual native room menu reaches seventh row and all four submenu actions')
reset(1);assert step()==0 and half(state+12)==4
half(state+6,2);step(direction=2);assert half(state+6)==3
step(direction=2);assert half(state+6)==0
for action in range(4):
 reset(1);half(state+6,3);step(0x10);assert half(state+14)==4
 half(state+8,action);assert step(0x10)==0x100+action
assert half(0xb9b696)==5 and half(0xb9b6a4)==424 and half(0xb9b6b2)==169
checks.append('Native Tavern menu accepts fourth row/four actions; borrowed room tables restore afterwards')
reset(0);step(0x40);assert u.mem_read(state+3,1)==b'\x01'
assert 0x257440 in events
checks.append('Native 3DS View Mode action enters mode through its own camera call')
result={'status':'passed','checks':checks,'limitations':['Input, sound, rotation callback, camera and weapon lookup callbacks are fixtures','Item metadata contents are fixtures; accessor instructions are real game code','Probe is not installed; menu rendering, persistence and renaming are not connected to a live game']}
(ROOT/'build/native-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
