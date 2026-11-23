"""Compare the compiled menu binding with actual native positioning/theme code.
Text/GPU services are fixtures; position setters and color calculation execute.
"""
from pathlib import Path
import importlib.util,struct,sys,json
from unicorn import UC_HOOK_CODE,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u
u.reg_write(a.UC_ARM_REG_C1_C0_2,0xf<<20);u.reg_write(a.UC_ARM_REG_FPEXC,0x40000000)
WIDGET,ARRAYS,NODES,FONTS,PARENT,VTABLE,TEXTS=0x2500000,0x2510000,0x2520000,0x2530000,0x2540000,0x2550000,0x2560000
LOOKUP=0x180f100
labels=[];colors=[];theme_args=[];visible=[]
def string(p):
 data=bytearray()
 for i in range(200):
  c=u.mem_read(p+i,1)[0]
  if not c:return data.decode()
  data.append(c)
 raise AssertionError('unterminated')
def cb(uc,addr,size,data):
 r=n.reg
 if addr==LOOKUP:assert r(1)==0x2e;n.ret(TEXTS+128*r(2))
 elif addr==0x105564:n.ret(len(string(r(0))))
 elif addr==0x323098:labels.append((r(0),string(r(1))));n.ret(0)
 elif addr==0x324680:colors.append((r(0),struct.unpack('<I',u.mem_read(r(1),4))[0]));n.ret(0)
 elif addr==0x13fbd4:visible.append((r(0),r(1)));n.ret(0)
 elif addr==0x5991d4:
  # Observe and execute the actual native theme routine, including its stack arg.
  theme_args.append(tuple(r(i) for i in range(1,4))+(struct.unpack('<I',u.mem_read(u.reg_read(a.UC_ARM_REG_SP),4))[0],))
u.hook_add(UC_HOOK_CODE,cb)
n.word(n.UI,VTABLE);n.word(VTABLE+0x8c,LOOKUP);n.word(WIDGET+0x190,PARENT)
for i in range(389,396):u.mem_write(TEXTS+128*i,('stock-'+str(i)).encode()+b'\0')
for j,off in enumerate([0x224,0x228,0x230]):
 arr=ARRAYS+j*0x100;n.word(WIDGET+off,arr)
 for i in range(8):
  ptr=FONTS+i*0x200 if j==2 else NODES+(j*8+i)*0x200
  n.word(arr+i*4,ptr)
  # Distinct positions: modifying any child's coordinates must be detected.
  u.mem_write(ptr+0xa8,struct.pack('<3f',70+j*5,20+i*20,0))
geometry=[bytes(u.mem_read(NODES+i*0x200+0xa8,12)) for i in range(16)]
geometry+= [bytes(u.mem_read(FONTS+i*0x200+0xa8,12)) for i in range(8)]
visual=[0,1,2,3,4,5,6];physical=[0,1,2,4,5,6,3]
expected=['Store Items','Remove Items','Combine/Manage Items','Manage Equipment','Change Appearance','Equipment Sets','Item Sets']
def clear():labels.clear();colors.clear();theme_args.clear();visible.clear();u.mem_write(PARENT+0xa8,struct.pack('<2f',200,120))
for level in [0,1]:
 for selected in range(7):
  n.reset(0);n.half(n.state+12,7);n.half(n.state+6,visual[selected]);n.half(n.state+10,level)
  clear();n.call(0x2b24e0,[WIDGET,n.state]);native_colors=list(colors);native_themes=list(theme_args)
  assert all(args[0]==1 for args in native_themes)
  assert struct.unpack('<2f',u.mem_read(PARENT+0xa8,8))==(100,20)
  n.half(n.state+6,selected);before=bytes(u.mem_read(n.state,32));clear()
  n.call(n.symbols['item_draw_options'],[WIDGET,n.state])
  assert bytes(u.mem_read(n.state,32))==before
  assert [v for p,v in colors]==[v for p,v in native_colors] and theme_args==native_themes
  assert struct.unpack('<2f',u.mem_read(PARENT+0xa8,8))==(100,20)
  assert labels[-7:]==[(FONTS+p*0x200,s) for p,s in zip(physical,expected)]
  assert visible[-1]==(FONTS+7*0x200,0)
  assert struct.unpack('<I',u.mem_read(NODES+(8+3)*0x200+0x70,4))[0]&3==3
  assert struct.unpack('<I',u.mem_read(NODES+(8+4)*0x200+0x70,4))[0]&3==3
  assert [bytes(u.mem_read(NODES+i*0x200+0xa8,12)) for i in range(16)]+[bytes(u.mem_read(FONTS+i*0x200+0xa8,12)) for i in range(8)]==geometry
  # White selected text and bright normal text, never the disabled 0x64 gray.
  assert colors[visual[selected]][1]!=0xff646464
# Tavern has four item rows and no equipment section. Its native fourth
# logical slot also skips 3, so temporarily route it to the reserved font.
n.reset(1);n.half(n.state+12,4);n.half(n.state+6,3);clear()
n.call(n.symbols['item_draw_options'],[WIDGET,n.state])
assert labels[-1]==(FONTS+3*0x200,'Item Sets')
assert (FONTS+4*0x200,0) in visible
assert struct.unpack('<I',u.mem_read(NODES+(8+3)*0x200+0x70,4))[0]&3==3
assert struct.unpack('<I',u.mem_read(NODES+(8+4)*0x200+0x70,4))[0]&3==0
report={'status':'passed','cases':14,'checks':['Actual native 0x292E44/0x292E68 restore parent position (100,20)','Actual native 0x5991D4 colors match baseline for all rows and submenu states','No child geometry changes','Logical-to-visual selection remap preserves live input state','Hardware-guided row mapping: Item Sets font 3 and original Equipment Sets font 6; dormant row 7 hidden'],'limitations':['Text/GPU endpoints are fixtures; seven-row layout still requires live visual verification']}
(ROOT/'build/main-menu-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
