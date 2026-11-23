"""Exercise actual native 3DS option drawing, with GUI/text services simulated.

No framebuffer is rendered. Confirms label requests, row destination, cursor
theme inputs, native ABI and restoration; geometry remains a live-game check.
Usage: python tests/test_ui.py DECOMPRESSED_CODE LOBBY_ARC COMMON_ARC START_ARC
"""
from pathlib import Path
import importlib.util,json,struct,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from arc import read_arc
from inspect_ui import inspect
from prepare_ui_text import prepare,SHOP,HELP
from gmd import Gmd

# Reuse the existing native execution harness and its ABI assertions.
spec=importlib.util.spec_from_file_location('native',ROOT/'tests/test_native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
u=n.u;a=n.a
u.reg_write(a.UC_ARM_REG_C1_C0_2,0xf<<20)
u.reg_write(a.UC_ARM_REG_FPEXC,0x40000000)
WIDGET,ARRAYS,LOOKUP,VTABLE,TEXT=0x2500000,0x2510000,0x180f000,0x2520000,0x2530000
requests=[];emitted=[];themes=[];visibility=[]
def str_at(address):
 result=bytearray()
 while True:
  b=bytes(u.mem_read(address,1))
  if b==b'\0':return result.decode()
  result.extend(b);address+=1
def callback(uc,address,size,data):
 r=n.reg
 if address==LOOKUP:
  requests.append((r(1),r(2)));n.ret(TEXT+128*r(2))
 elif address==0x105564:n.ret(len(str_at(r(0))))
 elif address==0x323098:emitted.append((r(0),str_at(r(1))));n.ret(0)
 elif address==0x5991d4:themes.append((r(1),r(2),r(3)));n.ret(0xffffffff)
 elif address==0x535d70:visibility.append((r(1),r(2)));n.ret(0)
 elif address in (0x292e44,0x292e68,0x324680,0x13fbd4):n.ret(0)
from unicorn import UC_HOOK_CODE
u.hook_add(UC_HOOK_CODE,callback)
n.word(n.UI,VTABLE);n.word(VTABLE+0x8c,LOOKUP)
for offset,base in [(0x224,ARRAYS),(0x228,ARRAYS+0x100),(0x230,ARRAYS+0x200)]:
 n.word(WIDGET+offset,base)
 for i in range(8):n.word(base+4*i,0x2540000+offset*256+i*256)
for i in range(389,396):u.mem_write(TEXT+128*i,('row'+str(i)).encode()+b'\0')
before=bytes(u.mem_read(ARRAYS,0x220))
for selected in range(7):
 n.reset(0);n.half(n.state+12,7);n.half(n.state+6,selected)
 requests.clear();emitted.clear();themes.clear();visibility.clear()
 n.call(n.symbols['probe_room_options'],[WIDGET,n.state])
 assert requests==[(0x2e,i) for i in range(389,396)],requests
 assert [s for ptr,s in emitted]==['row'+str(i) for i in range(389,396)]
 # Logical row 6 is drawn through native physical slot 3, right after items.
 expected=[0,1,2,4,5,6,3]
 assert [ptr for ptr,s in emitted]==[0x2540000+0x230*256+i*256 for i in expected]
 assert [i for i,x in enumerate(themes) if x[1]]==[selected]
 assert bytes(u.mem_read(ARRAYS,0x220))==before

paths=list(map(Path,sys.argv[2:]))
if len(paths)!=3:raise ValueError('Supply all three archives')
report=inspect(paths)
patched,bindings=prepare(paths[0])
with tempfile.TemporaryDirectory() as tmp:
 out=Path(tmp)/'ID_lb_eng.arc';out.write_bytes(patched)
 old={(name,t):b for name,t,b in read_arc(paths[0])}
 new={(name,t):b for name,t,b in read_arc(out)}
 changed=[name for name,t in old if old[name,t]!=new[name,t]]
 assert sorted(changed)==sorted([SHOP,HELP])
 g=Gmd(next(b for (name,t),b in new.items() if name==SHOP))
 assert g.strings[395]=='Item Sets'
 assert g.strings[433:437]==['Current Sets','Register Set','Reorder Sets','Unregister Sets']
 g=Gmd(next(b for (name,t),b in new.items() if name==HELP))
 assert g.strings[182]=='Register your item pouch as a new set.'
 assert g.strings[175].endswith('equipment.')
 assert g.strings[bindings['warning']]=='(Some items were insufficient or missing.)'
result={'status':'passed','native_room_rows':7,'cursor_positions_exercised':7,'widget_arrays_restored':True,'text_roundtrips':report['text_roundtrips'],'layout_validations':report['layout_validations'],'changed_resources':changed,'text_bindings':bindings,'limitations':['Drawing services and text lookup are fixtures; no real framebuffer','No installed hooks; no live visual positioning, rename, persistence or preview test']}
(ROOT/'build/ui-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
