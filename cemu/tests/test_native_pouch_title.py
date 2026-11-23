"""Execute stock title helper and root hide prologue with native asset IDs.
No game bytes embedded; accepts owner's US/EU RPX and original lobby ARC.
"""
import argparse,sys,struct,json
from pathlib import Path
from game_harness import *
sys.path.insert(0,str(ROOT/'tools'))
from inspect_rpx import sections
from inspect_gui import Arc,Gui
parser=argparse.ArgumentParser();parser.add_argument('--region',choices=['US','EU'],required=True);parser.add_argument('--rpx',required=True);parser.add_argument('--arc',required=True);args=parser.parse_args()
shift=0 if args.region=='US' else -0x88
raw=Arc(args.arc).get('GUI\\lobby\\myh_p_title_n');gui=Gui(raw)
assert gui.string(gui.obj(7)[4])=='ti'
assert gui.obj(10)[0]==0xbe and gui.obj(11)[0]==0xc0
assert gui.obj(7)[5]==gui.obj(10)[5]==gui.obj(11)[5]==0x1b6313a3 # baked textures, not font objects
ss=sections(args.rpx);t=next(s for s in ss if s['name']=='.text')
g=Game();g.u.mem_write(t['addr'],t['data'])
title,instance,tree,table=0x11190000,0x11191000,0x11192000,0x11195000
show,hide=0x019b0000,0x019b0010
g.write32(title,table);g.write32(title+0xf4,instance);g.write32(instance+4,0x170);g.write32(instance+0xfc,tree)
g.write32(table+0x1d4,show);g.write32(table+0x1dc,hide)
# Preserve the actual native title resource hierarchy and object IDs.
for i in range(gui.w(0x2c)):
 o=gui.obj(i);node=tree+i*0x200;g.write32(node,0x11196000);g.write32(0x11196000+0x8c,0x019b0020);g.write32(node+0x50,o[0])
 if o[2]!=0xffffffff:g.write32(node+0x6c,tree+o[2]*0x200)
 if o[3]!=0xffffffff:g.write32(node+0x68,tree+o[3]*0x200)
 g.write32(node+0x54,1)
calls=[]
def hooks(uc,pc,size,data):
 if pc in [show,hide]:calls.append((pc,g.reg(3)));g.return_(0)
 elif pc==0x019b0020:g.return_(0) # visibility notification
 elif pc==0x02af33b8+shift:g.return_(0) # root dirty notification only
 elif pc in [0x021421f4+shift,0x021433c4+shift,0x02aff91c+shift]:raise AssertionError('Dialog or font setter called')
 elif pc==0x0270a874+shift:uc.emu_stop()
g.u.hook_add(UC_HOOK_CODE,hooks)
def call_at(pc,argv):
 g.u.reg_write(p.UC_PPC_REG_1,0x1201e000);g.u.reg_write(p.UC_PPC_REG_LR,STOP)
 for n,value in enumerate(argv,3):g.u.reg_write(getattr(p,'UC_PPC_REG_'+str(n)),value)
 try:g.u.emu_start(pc,STOP,count=20000)
 except Exception:
  print('Fault',hex(g.u.reg_read(p.UC_PPC_REG_PC)),[(i,hex(g.reg(i))) for i in [3,4,5,30,31]]);raise
 assert g.u.reg_read(p.UC_PPC_REG_PC)==STOP
state=0x11198000
for gunner in [False,True,False,True]:
 g.u.mem_write(state,bytes([0,0,0,0,0,int(gunner),0,0]));call_at(0x02688c68+shift,[title,state,0])
 assert g.number(tree+10*0x200+0x54)&1==int(not gunner)
 assert g.number(tree+11*0x200+0x54)&1==int(gunner)
assert calls==[(show,title)]*4
# Stock root prologue hides this exact title before dispatching every page;
# the mod's neutral/native View Mode/exit paths retain that prologue.
root=0x111a0000;g.write32(root+0x350,title)
for n,value in [(1,0x1201e000),(3,root),(4,state)]:g.u.reg_write(getattr(p,'UC_PPC_REG_'+str(n)),value)
g.u.emu_start(0x0270a738+shift,STOP,count=20000)
assert g.u.reg_read(p.UC_PPC_REG_PC)==0x0270a874+shift
assert calls[-1]==(hide,title)
report={'status':'passed','region':args.region,'checks':['Actual native title helper selects original Blade/Gunner texture objects','Original Item Pouch lettering and parchment objects remain unchanged','Actual box prologue hides existing title widget before page dispatch','No dynamic font setter or resident dialog helper called'], 'limitations':['Allocation/render submission and root dirty notification intercepted','No live Cemu rendering']}
(ROOT/('build' if args.region=='US' else 'build-eu')/'native-pouch-title-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
