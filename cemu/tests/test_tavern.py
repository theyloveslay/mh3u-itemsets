"""Tavern item-only box integration, including native menu input from RPX.
Usage: python tests/test_tavern.py RPX TOOLS_DIRECTORY
External GUI/OS callbacks are fixtures; no game bytes are redistributed.
"""
from test_ui import UI
from game_harness import *
sys.path.insert(0,sys.argv[2])
from inspect_rpx import sections
mapped=sections(sys.argv[1])
text=next(s for s in mapped if s['name']=='.text')
class Tavern(UI):
    def __init__(self):
        super().__init__()
        self.u.mem_write(self.state()+2,b'\x01');self.half(self.state()+12,3)
        for s in mapped:
            if s['addr']<=0x10170f30<s['addr']+len(s['data']):
                at=0x10170f30-s['addr'];self.u.mem_write(0x10170f30,s['data'][at:at+80])
        self.tables=bytes(self.u.mem_read(0x10170f30,48))
    def enter_action(self,action):
        s=self.state();self.u.mem_write(s,b'\x02')
        for offset,value in [(6,3),(8,action),(10,1),(12,3)]:self.half(s+offset,value)
        self.result=1;self.input();self.result=0
        assert self.get('ui_list_open')==1 and self.get('ui_action')==action
        assert self.half(s+12)==4 and bytes(self.u.mem_read(0x10170f30,48))==self.tables

checks=[]
g=Tavern();g.register(2,False,[(9,10),(41,1)])
g.inventory(False,[]);g.inventory(True,[(41,1)]);g.u.mem_write(UD+0x1c0,struct.pack('>HH',9,9))
g.enter_action(0);g.select(2);g.input(0x10);g.input(0x10);assert g.number(SYMS['load_missing_units'])==1
g.render();assert list(struct.iter_unpack('>HH',g.last_preview))[:2]==[(9,9),(41,1)]
assert 'insufficient or missing' in g.cstring(g.call('text_hook',[0,0x2f,0x114]))
g.input(0x10);g.input(0x200);g.render();g.exit_list()
g.enter_action(2);g.select(2);g.input(0x10);g.select(10);g.input(0x10);g.exit_list()
assert g.u.mem_read(SYMS['sets']+10*132,1)==b'\x01'
g.enter_action(3);g.select(10);g.input(0x10);g.input(0x10);g.exit_list()
assert g.u.mem_read(SYMS['sets']+10*132,1)==b'\0'
checks.append('All four Tavern actions use the shared 24 sets, including direct transfer and partial loading')
# Main label, help, popup tables and fourth row are scoped to Tavern mode.
g.input();assert g.cstring(g.call('text_hook',[0,0x2e,392]))=='Item Sets'
g.enter_action(1);assert g.cstring(g.call('text_hook',[0,0x2f,182]))=='Register your item pouch as a new set.'
g.render();assert bytes(g.u.mem_read(0x10170f30,48))==g.tables
g.exit_list();g.half(g.state()+10,1);g.write32(g.maki+0x2e4,0x11168000)
g.call('draw_menu',[g.maki,g.state()]);assert any(e[:4]==('frame',0x11168000,0x4a,4) for e in g.gui)
assert bytes(g.u.mem_read(0x10170f30,48))==g.tables
frames,texts,plates=0x11140000,0x11141000,0x11142000
for off,arr in [(0x2ac,frames),(0x2b8,texts),(0x2b0,plates)]:g.write32(g.maki+off,arr)
for i in range(8):
 for arr in (frames,texts,plates):g.write32(arr+i*4,0x11150000+(arr-frames)+i*0x100)
before=bytes(g.u.mem_read(frames,32));g.call('draw_options',[g.maki,g.state()])
assert g.draw_frame_map[4]==g.number(frames+12) and bytes(g.u.mem_read(frames,32))==before
assert g.get('shift_count')==0
checks.append('Visible fourth row, Item Sets label, correct help and four-row Tavern frame; temporary tables restore')
# The Tavern's stock three-row scroll must gain the same native row height
# as the room box. Use the existing runtime geometry hook, not a new graphic.
layout=Tavern();layout.input();st=layout.state()
scroll,scroll_root=0x111b0000,0x111b1000
layout.write32(layout.maki+0xf4,scroll);layout.write32(scroll+4,428)
layout.write32(scroll+0xfc,scroll_root)
children=[0x111b2000+i*0x200 for i in range(5)]
layout.write32(scroll_root+0x68,children[0])
for i,node in enumerate(children):
 layout.write32(node,0x100a7cb0 if i==4 else 0x100a7f30)
 layout.u.mem_write(node+0x84,struct.pack('>f',100.0))
 if i<4:layout.write32(node+0x6c,children[i+1])
def ys():return [struct.unpack('>f',layout.u.mem_read(n+0x84,4))[0] for n in children]
for _ in range(3):
 layout.call('draw_options',[layout.maki,st]);layout.call('animation_hook',[scroll,0x111bf000])
 assert layout.get('shift_count')==3 and ys()==[100,154,154,100,154]
# Room/Tavern reuse the same widget; one extra row must not become two.
layout.u.mem_write(st+2,b'\0');layout.half(st+12,7)
layout.call('draw_options',[layout.maki,st]);layout.call('animation_hook',[scroll,0x111bf000])
assert ys()==[100,154,154,100,154]
layout.u.mem_write(st+2,b'\1');layout.half(st+12,4)
layout.call('draw_options',[layout.maki,st]);layout.call('animation_hook',[scroll,0x111bf000])
assert ys()==[100,154,154,100,154]
# No animation-count timeout: an idle open menu must keep its size.
for _ in range(32):layout.call('animation_hook',[scroll,0x111bf000])
assert ys()==[100,154,154,100,154]
# A page transition restores the shared frame before the new page draws.
layout.u.mem_write(st,b'\x14');layout.call('root_draw',[0x11150000,st])
assert ys()==[100]*5 and layout.get('shift_count')==0
checks.append('Tavern footer/fill move down exactly one 54px row; repeat draws and Room/Tavern transitions do not accumulate; exit restores geometry')
# Execute the native row renderer, including text lookup through our hook.
g.callbacks.pop(SYMS['original_draw_options'])
address=0x026a6b80;g.u.mem_write(address,text['data'][address-text['addr']:address-text['addr']+0x1b4])
g.write32(0x11070000,0x11169000);g.write32(0x11169000+0x134,SYMS['text_hook'])
for i,label in enumerate(['Take Items','Store Items','Combine and Manage Items']):
 at=0x111a8000+i*0x100;g.u.mem_write(at,label.encode()+b'\0');g.native_strings[0x2e,389+i]=at
def row_callbacks(uc,address,size,data):
 if address==0x0223b39c:g.return_(0xffffffff)
 elif address==0x026a3430:g.return_(len(g.cstring(g.reg(3))))
 elif address==0x02aff804:g.return_(0)
g.u.hook_add(UC_HOOK_CODE,row_callbacks)

g.call('draw_options',[g.maki,g.state()])
assert g.texts[g.number(texts+12)]=='Item Sets'
assert [g.texts[g.number(texts+i*4)] for i in range(3)]==['Take Items','Store Items','Combine and Manage Items']
checks.append('Actual native row renderer displays Item Sets as the fourth label and preserves the first three labels')

# Execute the real menu input function and real cursor wrap helper.
n=Tavern();s=n.state();n.callbacks.pop(SYMS['original_box_step'])
for address,size in [(0x021f0e7c,0x230),(0x020431f8,0xdc)]:
 n.u.mem_write(address,text['data'][address-text['addr']:address-text['addr']+size])
n.half(s+6,2);n.half(s+10,0);n.input(dirs=2);assert n.half(s+6)==3
n.input(dirs=2);assert n.half(s+6)==0
n.input(dirs=1);assert n.half(s+6)==3
n.input(0x10);assert n.half(s+10)==1 and n.half(s+14)==4
n.input(0x10);assert n.get('ui_list_open')==1 and n.get('ui_action')==0
n.input(0x20);assert n.get('ui_list_open')==0
assert bytes(n.u.mem_read(0x10170f30,48))==n.tables
checks.append('Actual native Tavern cursor wraps four rows, opens four-action submenu and returns from Current Sets')
# Return to the full box retains existing room order and native equipment table.
n.u.mem_write(s+2,b'\0');n.half(s+6,2);n.half(s+10,0);n.half(s+12,6)
n.input(dirs=2);assert n.half(s+6)==6 and n.half(s+12)==7
assert n.get('ui_tavern')==0 and bytes(n.u.mem_read(0x10170f30,48))==n.tables
checks.append('Returning to the full box preserves room navigation and equipment submenu tables')
result={'status':'passed','checks':checks,'limitations':['Native input executed with GUI/OS callbacks mocked; Cemu visual confirmation required']}
(ROOT/'build/tavern-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
