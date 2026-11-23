"""Native v32 pouch initialization rejects supplied 44-instance UI.

Execute the actual US/EU initializer's eight row_extra cache reads. Put its
instance array immediately before an unmapped page so out-of-bounds reads
cannot accidentally return heap data that looks like an instance pointer.
Native visibility work is intercepted; the cache/index instructions are real.
"""
import argparse,sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from game_harness import *
from inspect_rpx import sections
from inspect_gui import Arc,Gui
from unicorn import UcError,UC_ERR_READ_UNMAPPED
parser=argparse.ArgumentParser();parser.add_argument('--region',choices=['US','EU'],required=True);parser.add_argument('--rpx',required=True);parser.add_argument('--arc',required=True);args=parser.parse_args()
ss=sections(args.rpx);text=next(s for s in ss if s['name']=='.text')
rodata=next(s for s in ss if s['name']=='.rodata');off=0x1005888c-rodata['addr'];cache=rodata['data'][off:off+16]
assert list(struct.unpack('>8H',cache))==list(range(45,53))
real_count=Gui(Arc(args.arc).get('GUI\\lobby\\com_m_menu_n')).w(0x40);assert real_count>=53
shift=0 if args.region=='US' else -0x88
results=[]
for count in [44,real_count]:
 g=Game();g.u.mem_write(text['addr'],text['data']);g.u.mem_map(0x15000000,0x1000)
 array=0x15001000-count*4;widget,sp=0x11190000,0x1201e000
 g.write32(widget+0xf8,array);g.u.mem_write(sp+0x30,cache)
 for i in range(count):g.write32(array+i*4,0x111a0000+i*0x200)
 def callback(uc,pc,size,data):
  if pc==0x0265e740+shift:uc.emu_stop()
  elif pc==0x0228f44c+shift:g.return_(0)
 g.u.hook_add(UC_HOOK_CODE,callback)
 for r,v in [(1,sp),(28,0),(30,widget),(27,0)]:g.u.reg_write(getattr(p,'UC_PPC_REG_'+str(r)),v)
 try:g.u.emu_start(0x0265e6d0+shift,STOP,count=1000)
 except UcError as error:
  assert count==44 and error.errno==UC_ERR_READ_UNMAPPED
  assert g.u.reg_read(p.UC_PPC_REG_PC)==0x0265e6f0+shift
  results.append({'instance_count':count,'result':'out-of-bounds read reproduced in native cache loop','requested_index':45})
 else:
  assert count==53 and g.u.reg_read(p.UC_PPC_REG_PC)==0x0265e740+shift
  for i,index in enumerate(range(45,53)):assert g.number(widget+0x664+i*4)==0x111a0000+index*0x200
  results.append({'instance_count':count,'result':'all eight native cache reads in bounds'})
report={'status':'passed','region':args.region,'checks':results,'log_correspondence':{'observed_row':5,'observed_index':50,'old_source_instance_count':44,'current_source_instance_count':real_count,'pointer_read_in_crash':'0x00000002'},'limitations':['Instance construction/visibility work is intercepted; tests execute real native cache reads using the current asset count','No live Cemu launch; visibility work intercepted']}
(ROOT/('build' if args.region=='US' else 'build-eu')/'pouch-startup-layout-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
