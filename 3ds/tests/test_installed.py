"""Execute bootstrap, installed entry branches and displaced prologues.
Game GPU/FS/copy services remain fixtures. No live emulator test is claimed.
"""
from pathlib import Path
import importlib.util,json,struct,sys,tempfile,os
from unicorn import UC_HOOK_CODE,UC_HOOK_INTR,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC,arm_const as a
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from inspect_inputs import apply_bps
from build_install import branch_target
from exheader import REQUIRED_SVCS
from installer import merge_current
from arc import read_arc
from gmd import Gmd
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u;directory=ROOT/os.environ.get('MH3U_INSTALLED_BUILD_DIR','install-build');manifest=json.loads((directory/'manifest.json').read_text())
code=Path(sys.argv[1]).read_bytes();target=apply_bps(code,(directory/'code.bps').read_bytes())
baseline=apply_bps(code,Path(sys.argv[2]).read_bytes()) if sys.argv[2]!='-' else code
u.mem_write(0x100000,target)
n.word(0xc406a0,n.UI);n.word(0xc43360,n.UD);n.word(0xcb9954,n.TABLE)
base=int(manifest['payload_base'],16);size=manifest['payload_bytes'];old_entry=int(manifest['existing_entry'],16)
with open(directory/'work/loadouts-arm.elf','rb') as f:
 e=ELFFile(f);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
svcs=[];fs_reads=[];labels=[];root_phases=[];animation_args=[];menu_args=[]
def interrupt(uc,number,data):
 pc=u.reg_read(a.UC_ARM_REG_PC);svc=struct.unpack('<I',u.mem_read(pc-4,4))[0]&0xffffff;svcs.append(svc)
 if svc==0x35:assert n.reg(1)==0xffff8001;u.reg_write(a.UC_ARM_REG_R1,42)
 elif svc==0x33:assert n.reg(1)==42;u.reg_write(a.UC_ARM_REG_R1,0x123)
 elif svc==0x70:
  assert [n.reg(i) for i in range(6)]==[0x123,base,base,size,6,7]
  u.mem_protect(base,size,UC_PROT_READ|UC_PROT_WRITE|UC_PROT_EXEC)
 elif svc==0x23:assert n.reg(0)==0x123
 else:raise AssertionError(f'Unexpected startup SVC {svc:x}')
 u.reg_write(a.UC_ARM_REG_R0,0)
u.hook_add(UC_HOOK_INTR,interrupt)
u.mem_protect(base,size,UC_PROT_READ|UC_PROT_WRITE)
saved=[0x12340000+i for i in range(13)]
for i,v in enumerate(saved):u.reg_write(getattr(a,f'UC_ARM_REG_R{i}'),v)
u.reg_write(a.UC_ARM_REG_SP,n.STACK);u.reg_write(a.UC_ARM_REG_LR,n.STOP)
u.emu_start(0x100000,old_entry,count=1000)
assert u.reg_read(a.UC_ARM_REG_PC)==old_entry
assert [n.reg(i) for i in range(13)]==saved and u.reg_read(a.UC_ARM_REG_SP)==n.STACK
assert svcs==[0x35,0x33,0x70,0x23]
if manifest.get('existing_patch_sha256') is None:
 assert u.reg_read(a.UC_ARM_REG_LR)==0x100004
 bss_start,bss_end=struct.unpack_from('<2I',code,0x40)
 assert bss_end<=base
 assert not any(target[bss_start-0x100000:bss_end-0x100000])
 before=bytes(u.mem_read(base,32));n.word(bss_start,0xdeadbeef);n.word(bss_end-4,0xdeadbeef)
 n.call(old_entry,[],budget=2000000)
 assert bytes(u.mem_read(bss_start,4))==bytes(4) and bytes(u.mem_read(bss_end-4,4))==bytes(4)
 assert bytes(u.mem_read(base,32))==before


# Every installed branch targets the linked function, and every trampoline
# contains the original four instructions followed by a jump back to +16.
for site,record in manifest['hooks'].items():
 site=int(site,16);trampoline=int(record['original'],16)
 assert branch_target(site,struct.unpack_from('<I',target,site-0x100000)[0])==int(record['address'],16)
 if site==0x3e4a44:
  # BL is relocated through r12, not copied at a different PC.
  assert bytes(u.mem_read(trampoline,8))==code[site-0x100000:site-0x100000+8]
  assert struct.unpack('<I',u.mem_read(trampoline+12,4))[0]==0xe12fff3c
  assert struct.unpack('<I',u.mem_read(trampoline+16,4))[0]==struct.unpack_from('<I',code,site-0x100000+12)[0]
  assert struct.unpack('<2I',u.mem_read(trampoline+20,8))==(0xe51ff004,site+16)
 else:
  assert bytes(u.mem_read(trampoline,16))==code[site-0x100000:site-0x100000+16]
  assert struct.unpack('<2I',u.mem_read(trampoline+16,8))==(0xe51ff004,site+16)

SAVE,DATA,IO,READ,WRITE=0x2500000,0x2510000,0x2520000,0x180f100,0x180f110
LOOKUP,VTABLE,STRINGS=0x180f200,0x2580000,0x25a0000
def string(address):
 out=bytearray()
 while True:
  value=u.mem_read(address,1)[0]
  if not value:return out.decode()
  out.append(value);address+=1
def callback(uc,address,length,data):
 r=n.reg
 if address==0x292418:animation_args.append(tuple(r(i) for i in range(4)));n.ret(0)
 elif address==0x974fd0:
  menu_args.append((r(7),r(6)))
  sp=u.reg_read(a.UC_ARM_REG_SP);saved=struct.unpack('<9I',u.mem_read(sp,36))
  for i,value in enumerate(saved[:8]):u.reg_write(getattr(a,f'UC_ARM_REG_R{i+4}'),value)
  u.reg_write(a.UC_ARM_REG_SP,sp+36);u.reg_write(a.UC_ARM_REG_LR,saved[8]);n.ret(0)
 elif address in [0x99dd00,0x999eec]:n.ret(0)
 elif address==READ:fs_reads.append((r(1),r(2)));n.ret(0)
 elif address==WRITE:raise AssertionError('Unexpected startup/box write')
 elif address==0x3be3c0:
  root_phases.append(u.mem_read(r(5),1)[0]);u.reg_write(a.UC_ARM_REG_PC,0x3be75c)
 elif address==LOOKUP:assert r(1)==0x2e;n.ret(STRINGS+128*r(2))
 elif address==0x105564:n.ret(len(string(r(0))))
 elif address==0x323098:labels.append(string(r(1)));n.ret(0)
 elif address==0x5991d4:n.ret(0xff82d6f0)
 elif address in [0x292e44,0x292e68,0x535d70,0x324680,0x13fbd4]:n.ret(0)
u.hook_add(UC_HOOK_CODE,callback)
u.mem_write(IO,struct.pack('<3I',0,READ,WRITE))
n.call(symbols['item_ui_set_io'],[IO]);n.word(SAVE+0x138,DATA);n.word(SAVE+0x260,1)
# Call the patched game address, not the handler symbol.
assert n.call(0x2a2374,[SAVE],budget=2000000)==1 and not fs_reads
n.reset(0);assert n.call(0x5e8d30,[n.LOBBY],budget=2000000)==0
assert fs_reads==[(1,0),(1,1)] and n.half(n.state+12)==7
n.half(n.state+6,6);n.half(n.state+10,1);n.half(n.state+8,1)
n.buttons=0x10;n.call(0x5e8d30,[n.LOBBY],budget=2000000);n.buttons=0
assert struct.unpack('<3I',u.mem_read(symbols['item_ui'],12))==(1,1,0)

# Exercise the remaining two installed prologues. GPU primitives are fixtures;
# the native option-loop body executes and obtains its new label from the ARC.
arc_source=Path(sys.argv[4]).read_bytes()
arc_target=apply_bps(arc_source,(directory/'ID_lb_eng.arc.bps').read_bytes())
with tempfile.TemporaryDirectory() as tmp:
 path=Path(tmp)/'ID_lb_eng.arc';path.write_bytes(arc_target)
 gmd=Gmd(next(data for name,typ,data in read_arc(path) if name=='GUI\\font\\lobby\\Shop_eng'))
 for i in range(389,396):u.mem_write(STRINGS+128*i,gmd.strings[i].encode()+b'\0')
widget,arrays=0x2530000,0x2540000
n.word(n.UI,VTABLE);n.word(VTABLE+0x8c,LOOKUP)
for offset,base_array in [(0x224,arrays),(0x228,arrays+0x100),(0x230,arrays+0x200)]:
 n.word(widget+offset,base_array)
 for i in range(8):n.word(base_array+4*i,0x2550000+offset*256+i*256)
u.reg_write(a.UC_ARM_REG_C1_C0_2,0xf<<20);u.reg_write(a.UC_ARM_REG_FPEXC,0x40000000)
n.call(0x2b24e0,[widget,n.state],budget=2000000)
assert labels[-7:]==['Store Items','Remove Items','Combine/Manage Items','Manage Equipment','Change Appearance','Equipment Sets','Item Sets']
n.word(symbols['item_ui'],0)
n.call(0x3be3b0,[0x2560000,n.state],budget=2000000);assert root_phases[-1]==2

# Exercise the globally installed animation hook with a startup-like empty
# instance. The displaced BL must reach the original base transform with the
# same four arguments; no layout records exist for this instance.
# test_animation_abi.py separately executes the actual transform without this fixture.
INSTANCE,PARENT_MATRIX,VIEWPORT=0x25d0000,0x25d1000,0x25d2000
u.mem_write(INSTANCE,bytes(0x200))
u.mem_write(VIEWPORT,struct.pack("<2i",400,240))
n.call(0x3e4a44,[INSTANCE,PARENT_MATRIX,VIEWPORT,0x12345678]);assert animation_args[-1]==(INSTANCE,PARENT_MATRIX,VIEWPORT,0x12345678)
n.half(n.state+12,6)
n.call(0x974fc0,[INSTANCE,n.state]);assert menu_args[-1]==(INSTANCE,n.state)

# Metadata grants only the required additions and expands the data image.
ex=apply_bps(Path(sys.argv[3]).read_bytes(),(directory/'exheader.bps').read_bytes())
for caps in [0x200,0x600]:
 assert int.from_bytes(ex[caps+0x48:caps+0x4f],'little')&0x8080==0x8080
 assert int.from_bytes(ex[caps+0x1f0:caps+0x1ff],'little')&(1<<9)
 allowed=set()
 for w in struct.unpack_from('<28I',ex,caps+0x170):
  if w>>27==0x1e:allowed.update(((w>>24)&7)*24+i for i in range(24) if w&(1<<i))
 assert REQUIRED_SVCS<=allowed
assert struct.unpack_from('<I',ex,0x30)[0]+struct.unpack_from('<I',ex,0x34)[0]*4096==0x100000+len(target)

# Current-patch merging preserves unrelated edits and refuses hook collisions.
current=bytearray(baseline);current[0x123456]^=1
merged=merge_current(code,baseline,current,target)
assert merged[0x123456]==current[0x123456]
for site in manifest['hooks']:assert merged[int(site,16)-0x100000:int(site,16)-0x100000+4]==target[int(site,16)-0x100000:int(site,16)-0x100000+4]
current[0x5e8d30-0x100000]^=1
try:merge_current(code,baseline,current,target)
except ValueError:pass
else:raise AssertionError('Hook conflict accepted')
result={'status':'passed','checks':['Entry bootstrap preserves registers/stack, enables payload execution and chains existing loader','Six installed entry branches verified; animation BL relocation checked','Patched native character-load entry tracks the correct slot','Patched Item Box entry loads that slot once and opens Register Set','Patched option loop emits seven regular rows with direct Item Sets text','Root trampoline returns through native epilogue; rendering services are fixtures','Data image and required FS/ARM9/SVC capabilities match payload','Non-conflicting existing patch edits preserved; hook collisions rejected'],'limitations':['Bootstrap kernel calls and game service endpoints are fixtures','Actual GPU rendering, startup in Azahar and real hardware remain unverified']}
(ROOT/'build/installed-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
