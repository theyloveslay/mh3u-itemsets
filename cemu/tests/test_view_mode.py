"""Execute MH3U's actual View Mode entry/exit and model rotation helpers.

Usage: python tests/test_view_mode.py RPX INVESTIGATION_DIRECTORY
Game input/OS/GUI callbacks remain fixtures. No proprietary bytes embedded.
"""
from test_ui import UI
from game_harness import *
sys.path.insert(0,sys.argv[2])
from inspect_rpx import sections
text=next(s for s in sections(sys.argv[1]) if s['name']=='.text')
class NativeView(UI):
    def __init__(self):
        self.held=0;self.camera=[]
        super().__init__()
        for address in (0x021f0bf4,0x021f0cb8,0x021f0d44):self.native_calls.pop(address)
        start,end=0x021f0bf4,0x021f0e34
        self.u.mem_write(start,text['data'][start-text['addr']:end-text['addr']])
        self.write32(self.state()+0x10,0x111a0000)
        self.write32(0x111a0000+0xe30,0x111a1000)
        self.write32(0x111a1000+0x180,0x10000)
    def hook(self,uc,address,size,data):
        if address==0x0221a368:self.return_(bool(self.held&self.reg(4)));return
        if address==0x02120ed4:self.camera.append(self.reg(4));self.return_(0);return
        if address==0x021b77a4:self.return_(0);return
        super().hook(uc,address,size,data)
g=NativeView();g.enter_action(0);g.select(7);g.input(0x200);g.render()
snapshot=g.snapshot();selected=g.number(SYMS['selected']);page=g.get('ui_preview_page')
# Native rotation works with the menu open, then also within View Mode.
g.held=0x08000000;g.input()
assert g.number(0x111a1000+0x180)==0xfc00
g.held=0;g.input(0x40);assert g.u.mem_read(g.state()+3,1)==b'\x01' and g.camera==[1]
g.render();assert g.number(g.maki+0xc)&0x30000==0
assert g.number(g.preview+0xc)&0x30000==0
g.held=0x04000000;g.input();assert g.number(0x111a1000+0x180)==0x10000
g.held=0;g.input(0x20)
assert g.u.mem_read(g.state()+3,1)==b'\0' and g.camera==[1,0]
g.render();assert g.number(g.maki+0xc)&0x30000==0x30000
assert g.number(SYMS['selected'])==selected and g.get('ui_preview_page')==page
assert g.snapshot()==snapshot
# + also exits native View Mode without turning pouch pages.
g.input(0x40);g.input(0x40);assert g.u.mem_read(g.state()+3,1)==b'\0'
assert g.get('ui_preview_page')==page
result={'status':'passed','checks':['Actual native rotation helpers change model yaw in both directions','Native + View Mode enters and B or + exits','Camera mode toggles through the native entry/exit routines','List and preview hide in View Mode and restore afterwards','Selected set, pouch page and inventory remain intact'],
        'limitations':['Input/camera/GUI external callbacks are fixtures; Cemu visual confirmation required']}
(ROOT/'build/view-mode-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
