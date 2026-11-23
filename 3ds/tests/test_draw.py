"""Execute native 3DS eight-row preview router and compiled GUI bindings.
GUI primitives and GPU/text services are fixtures. No framebuffer is rendered.
"""
from pathlib import Path
import importlib.util,json,struct,sys,os
from unicorn import UC_HOOK_CODE,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u
installed=os.environ.get('MH3U_INSTALLED_BUILD_DIR')
original_root=0x3be3b0
if installed:
 sys.path.insert(0,str(ROOT/'tools'))
 from inspect_inputs import apply_bps
 from elftools.elf.elffile import ELFFile
 directory=ROOT/installed
 u.mem_write(0x100000,apply_bps(Path(sys.argv[1]).read_bytes(),(directory/'code.bps').read_bytes()))
 with (directory/'work/loadouts-arm.elf').open('rb') as f:
  n.symbols.update({sym.name:sym['st_value'] for sym in ELFFile(f).get_section_by_name('.symtab').iter_symbols()})
 original_root=n.symbols['original_root_screen']
 n.symbols['item_root_draw']=0x3be3b0
 n.word(0xc406a0,n.UI);n.word(0xc43360,n.UD);n.word(0xcb9954,n.TABLE)
UI=n.symbols['item_ui'];STORE=n.symbols['item_store']
SID_GROUP,MAKI,PREVIEW,VTABLE,SELECTOR,ARRAYS,TITLE,ROOT_OBJECT=0x2500000,0x2510000,0x2520000,0x2530000,0x2540000,0x2550000,0x2560000,0x2570000
VIRTUAL=0x180f200
TEXT_LOOKUP=0x180f240
BANNER=TITLE+0x400;NATIVE_TITLE=TITLE+0x600;THEME=0x25a0000
POUCH_TITLE=TITLE+0x800;POUCH_GROUP=TITLE+0xa00
pouch_layers={};pouch_lookups=[]
colors=[];banner_calls=[]
rows=[];labels=[];paging=[];legends=[];help_ids=[];help_texts=[];root_phases=[];layouts=[];activations=[]
def word(at):return struct.unpack('<I',u.mem_read(at,4))[0]
def string(address):
 b=bytearray()
 for i in range(100):
  v=u.mem_read(address+i,1)[0]
  if not v:return b.decode()
  b.append(v)
 raise AssertionError('Missing terminator')
def callback(uc,address,size,data):
 r=n.reg
 if address==0x52683c:raise AssertionError('Item Sets configured the resident dialog')
 if address==VIRTUAL:
  activations.append(r(0))
  if r(0)==BANNER:
   banner_calls.append(r(1));n.word(BANNER+0x158,r(1))
  n.ret(0)
 elif address==TEXT_LOOKUP:
  assert (r(1),r(2))==(3,0);n.ret(NATIVE_TITLE)
 elif address==0xa2dd50:
  assert (r(0),r(1),r(2))==(POUCH_TITLE,0x170,1);pouch_lookups.append(r(0));n.ret(POUCH_GROUP)
 elif address==0x3e522c:
  assert r(0)==POUCH_GROUP and r(1) in (0xbe,0xc0);n.ret(POUCH_GROUP+0x100+r(1)*4)
 elif address==0x13fbd4:
  if r(0) in (POUCH_GROUP+0x100+0xbe*4,POUCH_GROUP+0x100+0xc0*4):pouch_layers[(r(0)-POUCH_GROUP-0x100)//4]=r(1)
  n.ret(0)
 elif address==0x2b1918:
  assert [r(i) for i in range(3)]==[MAKI,0x20,8];layouts.append(r(1));n.word(MAKI+0x230,ARRAYS+0x200);n.ret(0)
 elif address==0x2b0c30:paging.append(('sets',r(1),r(2)));assert r(3)==5;n.ret(0)
 elif address==0x51e880:paging.append(('pouch',r(1),r(2)));n.ret(0)
 elif address in [0x535d70,0x13fbd4,0x36feb8,0x37bb98,0x37c790,0x51e434,0x51e294,0x375f3c]:n.ret(0)
 elif address==0x324680:colors.append((r(0),word(r(1))));n.ret(0)
 elif address in [0x323098,0x3ae1e0]:labels.append((r(0),string(r(1))));n.ret(0)
 elif address==0x37568c:
  assert r(0)==PREVIEW and r(2)==0
  sp=u.reg_read(a.UC_ARM_REG_SP);entry,flags,out=struct.unpack('<3I',u.mem_read(sp,12))
  index=struct.unpack('<H',u.mem_read(entry+4,2))[0]
  assert flags==0x800 and u.mem_read(entry+2,1)==b'\x01'
  rows.append((r(1),index,struct.unpack('<HH',u.mem_read(r(3),4))));n.ret(0)
 elif address==original_root:root_phases.append(u.mem_read(r(1),1)[0]);n.ret(0)
 elif address==0x5269f0:legends.append(r(1));n.ret(0)
 elif address==0x526a74:help_ids.append(r(1));n.ret(0)
 elif address==0x3686cc:help_texts.append(string(r(1)));n.ret(0)
 elif address==0x523bb8:assert r(1) in [0,1];n.ret(0)
u.hook_add(UC_HOOK_CODE,callback)
for off in [0x70,0xd4,0xd8]:n.word(VTABLE+off,VIRTUAL)
n.word(ROOT_OBJECT+0x2c8,POUCH_TITLE)
for obj in [MAKI,PREVIEW,POUCH_TITLE]:n.word(obj,VTABLE)
n.word(n.UI,VTABLE);n.word(VTABLE+0x8c,TEXT_LOOKUP)
n.word(n.UI+0x28,SID_GROUP+0x300);n.word(SID_GROUP+0x358,BANNER);n.word(BANNER,VTABLE)
n.word(BANNER+0x15c,0x123400);n.word(BANNER+0x158,0)
n.word(0xc40728,THEME);n.word(THEME+20+708,0x123456);u.mem_write(THEME+20+712,b"\x2c")
u.mem_write(NATIVE_TITLE,b"Item Pouch\0")
n.word(n.UI+0x3c,SID_GROUP);n.word(SID_GROUP+0x58,MAKI)
n.word(n.UI+0x2c,SID_GROUP+0x100);n.word(SID_GROUP+0x188,PREVIEW)
n.word(SID_GROUP+0x184,TITLE+0x200)
n.word(PREVIEW+0x228,SELECTOR);n.word(SELECTOR,0x12345678)
n.word(PREVIEW+0x4a0,TITLE+0x100);n.word(MAKI+0x21c,TITLE)
for off,arr in [(0x224,ARRAYS),(0x228,ARRAYS+0x100),(0x230,ARRAYS+0x200)]:
 n.word(MAKI+off,arr)
 for i in range(8):n.word(arr+4*i,0x2580000+off*16+i*256)
def call(name,*args):return n.call(n.symbols[name],list(args),budget=2000000)
call('bank_defaults',STORE,0)
for i in range(24):
 u.mem_write(STORE+8+i*132,bytes([1,i%2,0,0])+b''.join(struct.pack('<HH',100+i*32+j,j+1) for j in range(32)))
call('item_ui_open',0);n.word(UI+8,0) # storage not bound in this renderer test
n.reset(0);n.half(n.state+6,6)
frames=0
for selected in range(24):
 n.word(UI+12,selected)
 for page in range(4 if selected%2 else 3):
  n.word(UI+24,page);rows.clear();labels.clear();paging.clear();colors.clear()
  call('item_root_draw',ROOT_OBJECT,n.state);frames+=1
  assert rows==[(j,page*8+j,(100+selected*32+page*8+j,page*8+j+1)) for j in range(8)]
  assert ('sets',selected//8+1,3) in paging
  assert ('pouch',page+1,4 if selected%2 else 3) in paging
  names=[s for ptr,s in labels if ptr not in [TITLE,TITLE+0x100]]
  assert names==[f'Set {selected//8*8+j+1}' for j in range(8)],names
  assert (TITLE,'Current Sets') in labels
  assert not any(ptr==TITLE+0x100 for ptr,text in labels), 'Native Item List title overwritten'
  assert word(THEME+20+708)==0x123456 and u.mem_read(THEME+20+712,1)==b'\x2c'
  assert word(BANNER+0x15c)==0x123400 and not banner_calls
  assert [c for ptr,c in colors]==[0xfff0f0f0 if j==selected%8 else 0xffc3c3c3 for j in range(8)]
  assert pouch_layers=={0xbe:int(not selected%2),0xc0:selected%2}
  assert root_phases[-1]==20 and legends[-1]==15 and help_texts[-1].startswith("Change into one of your item sets.")
  assert word(SELECTOR)==6

# Empty slots always use numbered placeholders and the native disabled gray.
for i in range(24):
 if i%2:u.mem_write(STORE+8+i*132,b'\0')
for page in range(3):
 n.word(UI+12,page*8);rows.clear();labels.clear();colors.clear()
 call('item_root_draw',ROOT_OBJECT,n.state)
 assert [t for ptr,t in labels if ptr not in [TITLE,TITLE+0x100]]==[f'Set {page*8+j+1}' for j in range(8)]
 assert [c for ptr,c in colors]==[0xff646464 if j%2 else 0xfff0f0f0 if j==0 else 0xffc3c3c3 for j in range(8)]
# Even a selected empty slot is gray; inspect the generated list frame directly.
n.word(UI+12,1);rows.clear();labels.clear();colors.clear()
call('item_root_draw',ROOT_OBJECT,n.state)
assert [c for ptr,c in colors][1]==0xff646464

# Native View Mode/keyboard/closed-list rendering releases borrowed state.
for hidden in ['view','keyboard','closed']:
 if hidden=='view':u.mem_write(n.state+3,b'\x01')
 elif hidden=='keyboard':n.word(UI+8,3)
 else:n.word(UI,0)
 rows.clear();call('item_root_draw',ROOT_OBJECT,n.state)
 assert not rows and word(SELECTOR)==0x12345678 and root_phases[-1]==2
 assert word(BANNER+0x15c)==0x123400 and not banner_calls
 assert word(THEME+20+708)==0x123456 and u.mem_read(THEME+20+712,1)==b'\x2c'
 u.mem_write(n.state+3,b'\0');n.word(UI+8,0);n.word(UI,1)
 call('item_root_draw',ROOT_OBJECT,n.state);assert word(SELECTOR)==6
result={'status':'passed','installed_build':installed,'render_frames':frames,'native_item_rows_checked':frames*8,'checks':['Actual 0x371B44 router supplies exact eight item pointers for every Blade/Gunner page','All 24 set names and three page indicators emitted','Resident dialog configurator never executes; its text, secondary, style and activation stay untouched','Actual native 975F48 selects baked Blade/Gunner texture layers BE/C0 on the root-owned pouch title', 'Item List title remains untouched and paging separate','Native theme colors: registered white/normal; all empty slots numbered and gray, including selected','View Mode/keyboard/exit do not configure or activate the resident dialog','Native control legend and help IDs','Neutral root shadow does not change live menu phase','View Mode/keyboard/exit hide custom widgets and restore selector'],'limitations':['Native layout/text/GPU primitives are fixtures; screen geometry not rendered','Installed BPS entry exercised; no live visual test' if installed else 'No installed game hooks or live visual test']}
(ROOT/'build/draw-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
