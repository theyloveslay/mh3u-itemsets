"""Run real native transform code against the v3 hardware snapshot.
GPU/root upload is observed but not rendered. argv: original code, v3 capture.
"""
from pathlib import Path
import importlib.util,sys,struct,json,math,os
from unicorn import UC_HOOK_CODE,UC_HOOK_INTR,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u
installed=os.environ.get('MH3U_INSTALLED_BUILD_DIR')
if installed:
 sys.path.insert(0,str(ROOT/'tools'))
 from inspect_inputs import apply_bps
 from elftools.elf.elffile import ELFFile
 directory=ROOT/installed
 u.mem_write(0x100000,apply_bps(Path(sys.argv[1]).read_bytes(),(directory/'code.bps').read_bytes()))
 with (directory/'work/loadouts-arm.elf').open('rb') as elf:
  n.symbols.update({sym.name:sym['st_value'] for sym in ELFFile(elf).get_section_by_name('.symtab').iter_symbols()})
 # Enter the installed native branch, not just its payload handler.
 n.symbols['item_animation_step']=0x3e4a44
u.mem_map(0x16000000,0x1000000)
u.reg_write(a.UC_ARM_REG_C1_C0_2,0xf<<20);u.reg_write(a.UC_ARM_REG_FPEXC,0x40000000)
b=Path(sys.argv[2]).read_bytes();assert b[:4]==b'M3DG';at=64;widget=None;instances={};fonts={};plates={};frames={};graphics={}
while at<len(b):
 tag,addr,aux,size=struct.unpack_from('<4I',b,at);at+=16;data=b[at:at+size];at+=size
 if tag in [2,3,4,5,7,8,10,11,12,13]:u.mem_write(addr,data)
 if tag==2:widget=addr
 if tag==7:instances[struct.unpack_from('<I',data,0x68)[0]]=addr
 if tag==8:graphics[addr]=data
 if tag==11:frames[aux]=addr
 if tag==12:plates[aux]=addr
 if tag==13:fonts[aux]=addr
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
def flt(p):return struct.unpack('<f',u.mem_read(p,4))[0]
def put(p,v):u.mem_write(p,struct.pack('<f',v))
assert widget and 574 in instances and 593 not in instances
parent=instances[574];divider=instances[450];body=instances[438];bottom=instances[431]
assert flt(parent+0xac)==8 and math.isclose(flt(parent+0x40),-32,abs_tol=1e-4)
# This mismatch is the v3 failure: the new source position did not reach the world matrix.
assert math.isclose(flt(parent+0x40),flt(word(parent+0x88)+0x40)+12,abs_tol=1e-4)
lineglyph=word(word(divider+0xf8)+0x7c)
assert (flt(lineglyph+0xcc),flt(lineglyph+0xd0))==(160,2)
bodyglyph=word(word(word(body+0xf8)+0x7c)+0x7c)
assert (flt(bodyglyph+0xcc),flt(bodyglyph+0xd0))==(170,146)
assert word(plates[6]+0x70)&8 and not word(plates[7]+0x70)&8
# A fresh launch starts with the original -12 property, as before v3 wrote 8.
put(parent+0xac,-12)
viewport=0x2520000;u.mem_write(viewport,struct.pack('<2i',400,240))
uploads=[];base_args=[]
def intr(uc,number,data):
 pc=u.reg_read(a.UC_ARM_REG_PC);assert word(pc-4)&0xffffff==2
 address=n.reg(2);region=next(((lo,hi-lo+1,perm) for lo,hi,perm in u.mem_regions() if lo<=address<=hi),None)
 base,size,perm=region or (address&~4095,4096,0)
 for i,value in enumerate([0,base,size,perm,5,0]):u.reg_write(getattr(a,f'UC_ARM_REG_R{i}'),value)
def cb(uc,address,size,data):
 if address==0x292418:base_args.append(tuple(n.reg(i) for i in range(4))) # execute, never stub
 elif address==0x236fd4:uploads.append((n.reg(0),n.reg(1)));n.ret(0) # GPU-facing root endpoint
u.hook_add(UC_HOOK_INTR,intr);u.hook_add(UC_HOOK_CODE,cb)
def call(name,*args):return n.call(n.symbols[name],list(args),budget=2000000)
def animate(inst):
 parent_matrix=word(inst+0x88)+0x10
 call('item_animation_step',inst,parent_matrix,viewport,0x12345678)
 assert base_args[-1]==(inst,parent_matrix,viewport,0x12345678)
old_y={p:flt(p+0x40) for p in [parent,divider,bottom,body,*[plates[i] for i in [4,5,6]],*[frames[i] for i in [4,5,6]]]}
call('item_layout_refresh',widget)
# Property assignment alone still leaves the old world matrix: catches v3's inadequate test.
assert flt(parent+0xac)==8 and math.isclose(flt(parent+0x40),old_y[parent],abs_tol=1e-4)
for p in [divider,bottom,body,*[plates[i] for i in [4,5,6]],*[frames[i] for i in [4,5,6]]]:animate(p)
for p in [parent,divider,bottom,*[plates[i] for i in [4,5,6]],*[frames[i] for i in [4,5,6]]]:
 assert math.isclose(flt(p+0x40),old_y[p]-20,abs_tol=1e-3),(hex(p),old_y[p],flt(p+0x40))
assert math.isclose(flt(body+0x40),old_y[body]-10,abs_tol=1e-3)
assert math.isclose(abs(flt(body+0x20))*146,166,abs_tol=1e-3)
assert all(any(root==word(p+0xf8) for root,m in uploads) for p in [divider,bottom,body,*[plates[i] for i in [4,5,6]]])
first={p:bytes(u.mem_read(p+0x10,64)) for p in [parent,divider,body,bottom,plates[4],plates[5],plates[6]]}
# Native animation can overwrite local properties before each matrix update.
for tick in range(20):
 for p,y in [(divider,90),(bottom,180),(body,90)]:put(p+0xac,y)
 put(body+0xbc,1);put(parent+0xac,-12)
 call('item_layout_refresh',widget)
 for p in [divider,bottom,body,plates[4],plates[5],plates[6]]:animate(p)
 assert all(bytes(u.mem_read(p+0x10,64))==v for p,v in first.items()),tick
call('item_layout_stop')
assert flt(parent+0xac)==-12 and math.isclose(flt(parent+0x40),old_y[parent],abs_tol=1e-3)
assert flt(divider+0xac)==90 and flt(bottom+0xac)==180 and flt(body+0xac)==90 and flt(body+0xbc)==1
for p in [divider,bottom,body,plates[4],plates[5],plates[6]]:
 animate(p);assert math.isclose(flt(p+0x40),old_y[p],abs_tol=1e-3)
# Tavern uses the same native frame at a smaller starting height.
put(body+0xbc,0.6)
for tick in range(45):
 call('item_layout_refresh_mode',widget,1)
 for p in (body,bottom):animate(p)
 assert math.isclose(flt(body+0xbc)*146,0.6*146+20,abs_tol=1e-3)
 assert flt(bottom+0xac)==200 and flt(body+0xac)==100
 assert flt(parent+0xac)==-12 and flt(divider+0xac)==90
call('item_layout_stop')
assert math.isclose(flt(body+0xbc),0.6,abs_tol=1e-6)
assert flt(bottom+0xac)==180 and flt(body+0xac)==90
put(body+0xbc,1)
call('item_layout_refresh_mode',widget,1)
call('item_layout_refresh',widget)
assert flt(parent+0xac)==8 and flt(divider+0xac)==110
call('item_layout_stop')
assert flt(parent+0xac)==-12 and flt(divider+0xac)==90 and flt(bottom+0xac)==180
report={'status':'passed','source':'Real v3 hardware snapshot, 34880 bytes','installed_build':installed,'checks':['Reproduces v3 property/matrix mismatch before applying correction','Identifies divider by actual 160x2 graphic and body by 170x146 graphic','Actual native base transform rebuilds Null parent before row transforms','All three equipment rows and their selection frames move 20px in world matrices','Divider and bottom move 20px; body moves 10px and expands 146 to 166px','Actual native animation reaches graphics root update with corrected world matrices','Twenty frames with animation overwrites do not drift','Exit restores source properties AND world matrices','All four native argument registers forwarded','Tavern scaled body grows exactly 20px and footer moves one row; section divider stays native','Forty-five Tavern draws remain stable and explicit exit/mode change restores geometry'],'limitations':['GPU endpoint is observed, not rendered; real hardware photo still needed']}
(ROOT/'build/layout-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
