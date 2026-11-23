"""PPC controller/render integration; external game/OS APIs are mocked."""
from game_harness import *

class UI(Game):
    def __init__(self,files=None,rebase=0):
        self.buttons=0;self.gui=[];self.texts={};self.themes=[];self.y_values={};self.native_strings={}
        self.keyboard_ready=False;self.keyboard_accepted=True;self.keyboard_name='Gathering'
        self.maki=0x11120000;self.preview=0x11130000;self.selector=0x11070040
        self.native_calls={0x02688c68:'pouch_title',0x0221a1c8:'pressed',0x0221a4a4:'buttons',0x02043308:'confirm',0x020bfc74:'sound',
            0x021421f4:'dialog',0x021433c4:'dialog_setup',0x02143abc:'maki',0x0214380c:'preview',0x0214218c:'selector',0x026a5020:'frame',0x026a5668:'page',
            0x0228d438:'theme',0x02af349c:'show_text',0x02aff91c:'text_set',0x0203787c:'anim_prepare',
            0x02037600:'anim_open',0x0265e308:'preview_reset',0x0265f010:'preview_frame',0x0265fae4:'preview_rows',
            0x026611b8:'preview_items',0x02145c7c:'choice',0x02144ca8:'help',0x0228d1b4:'show_plate',
            0x02a72ce8:'child',0x02adef64:'set_y',0x02141030:'keyboard_hide',0x02141da4:'keyboard_restore',
            0x0211b8b8:'keyboard_open',0x0211db4c:'keyboard_ready',0x0211db48:'keyboard_result',0x02144574:'legend',
            0x020bfc84:'equip_sound',0x021f0cb8:'rotate',0x021f0bf4:'view_enter',0x021f0d44:'view_step'}
        super().__init__(files,rebase)
        self.write32(0x10314578,0x11070000)
        self.write32(0x101fdb9c,0x11090000)
        for name in ['original_root_draw','original_draw_options','original_draw_menu','original_animation']:
            self.callbacks[SYMS[name]+rebase]=name
        self.write32(self.maki,0x11132000)
        self.write32(0x11132000+0x1d4,0x01980110);self.native_calls[0x01980110]='list_open'
        self.write32(0x11132000+0x1dc,0x01980120);self.native_calls[0x01980120]='list_close'
        self.write32(self.maki+0xf8,0x11121000);self.row_texts=[]
        for i in range(8):
            self.half(0x1005f6e4+2*i,30+i)
            row=0x11122000+i*0x100;group=0x11124000+i*0x20;text=0x11125000+i*0x100
            self.write32(0x11121000+(30+i)*4,row);self.write32(row+0xf8,group);self.write32(group+8,text);self.row_texts.append(text)
        self.dialog=0x11135000;self.dialog_state=0x11136000
        self.write32(0x10314980,self.dialog_state)
        self.write32(0x11070000,0x11137000);self.write32(0x11137000+0x134,SYMS['original_text']+rebase)
        self.u.mem_write(0x11138000,b'Item Pouch\0');self.native_strings[3,0]=0x11138000
        self.write32(self.dialog,0x11139000);self.write32(0x11139000+0xe4,0x01980130)
        self.native_calls[0x01980130]='dialog_visible'
        self.write32(self.dialog+0x14c,0x123400)
        self.preview_title=0x11134000;self.write32(self.preview+0x570,self.preview_title)
        self.write32(self.preview,0x11131000);self.write32(0x11131000+0xe4,0x01980100);self.native_calls[0x01980100]='preview_visible'
        templates={175:'Register your current equipment and switch between equipment sets.',176:'Choose the equipment set you wish to use.',177:'Register your current equipment.',178:'Reorder your equipment sets.',179:'Unregister an equipment set.',
            0x114:'Select an equipment set.',0x115:'Use this equipment set?',0x116:'Choose where to register your equipment.',0x117:'Register the current equipment here?',
            0x118:'Choose an equipment set to reorder.',0x119:'Choose the equipment set to swap.',0x11a:'Choose an equipment set to unregister.',0x11b:'Unregister this equipment set?'}
        for i,(key,text) in enumerate(templates.items()):
            addr=0x11180000+i*0x100;self.u.mem_write(addr,text.encode()+b'\0');self.native_strings[0x2f,key]=addr
        self.u.mem_write(self.state(),b'\x02')
    def addr(self,name):return LOC['item_ui:'+name]+self.rebase
    def get(self,name):return self.number(self.addr(name))
    def hook(self,uc,address,size,data):
        callback=self.callbacks.get(address)
        if callback=='menu_next':self.half(self.state()+6,(self.half(self.state()+6)+1)%7);self.return_(0);return
        if callback in ['original_root_draw','original_draw_options','original_draw_menu','original_animation']:
            self.gui.append((callback,self.reg(3),self.reg(4)))
            if callback=='original_draw_options':
                frames=self.number(self.reg(3)+0x2ac)
                if frames:self.draw_frame_map=[self.number(frames+4*i) for i in range(8)]
            self.return_(0);return
        if callback=='text':self.return_(self.native_strings.get((self.reg(4),self.reg(5)),0));return
        name=self.native_calls.get(address)
        if name:
            args=[self.reg(i) for i in range(3,11)];self.gui.append((name,*args[:4]));result=0
            if name=='view_enter':self.u.mem_write(self.state()+3,b'\x01')
            elif name=='view_step':
                if self.buttons&(0x20|0x40):self.u.mem_write(self.state()+3,b'\0')
            elif name=='pressed':result=bool(self.buttons&args[1])
            elif name=='buttons':result=self.buttons
            elif name=='confirm':result=2 if self.buttons&0x20 else (1 if self.number(args[0])==0 else 2) if self.buttons&0x10 else 0
            elif name=='dialog':result=self.dialog
            elif name=='dialog_visible':self.write32(self.dialog+0x148,args[1])
            elif name=='dialog_setup':
                self.write32(self.dialog_state+0x2fc,args[1])
                self.u.mem_write(self.dialog_state+0x300,bytes([47 if args[2]==1 else 48]))
                self.write32(self.dialog+0x14c,args[3])
            elif name=='maki':result=self.maki
            elif name=='preview':result=self.preview
            elif name=='selector':result=self.selector
            elif name=='pouch_title':self.title_pouch=self.u.mem_read(args[1]+5,1)[0];assert args[2]==0
            elif name=='theme':self.themes.append((args[1],args[2]))
            elif name=='text_set':self.texts[args[0]]=self.cstring(args[1])
            elif name=='help':self.last_help=args[1]
            elif name=='preview_items':
                self.last_preview=bytes(self.u.mem_read(args[1],128));self.preview_page=args[3];self.preview_pages=args[4]
                self.preview_indices=[self.half(args[2]+i*0x18+4) for i in range(8)]
                assert self.number(self.reg(1)+8)==8,'Native ninth argument ABI mismatch'
            elif name=='child':result=0x11161000+(args[1]%16)*0x100
            elif name=='set_y':self.y_values[args[0]]=struct.unpack('>d',struct.pack('>Q',self.u.reg_read(p.UC_PPC_REG_FPR1)))[0]
            elif name=='keyboard_ready':result=self.keyboard_ready
            elif name=='keyboard_open':self.keyboard_initial=self.cstring(args[2]);assert args[1]==6
            elif name=='keyboard_result':
                assert args[2:]==[19,1,0,0xffffffff,0xffffffff,0xffffffff]
                value=self.keyboard_name.encode()[:19];self.u.mem_write(args[1],value+b'\0'+bytes(19-len(value)))
                result=self.keyboard_accepted
            self.return_(int(result));return
        super().hook(uc,address,size,data)
    def enter_action(self,action):
        assert not self.get('ui_list_open');s=self.state();self.u.mem_write(s,b'\x02')
        for offset,value in [(6,6),(8,action),(10,1),(12,6)]:self.half(s+offset,value)
        self.result=1;self.call('box_step',[LOBBY]);self.result=0
        assert self.get('ui_list_open')==1 and self.get('ui_action')==action
    def input(self,buttons=0,dirs=0):
        self.buttons=buttons;self.directions=dirs;self.call('box_step',[LOBBY]);self.buttons=self.directions=0
    def select(self,index):self.write32(SYMS['selected']+self.rebase,index);self.input()
    def exit_list(self):
        if self.get('ui_phase')==2:self.input(0x20)
        if self.get('ui_anchor')<24:self.input(0x20)
        self.input(0x20);assert self.get('ui_list_open')==0
    def register(self,index,gunner,items):
        self.enter_action(1);self.select(index);self.is_gunner=int(gunner);self.inventory(gunner,items)
        files=dict(self.files);self.input(0x10);assert self.get('ui_phase')==1 and self.files==files
        self.input(0x10);assert 'registered' in self.message();self.exit_list()
    def message(self):return self.cstring(self.number(SYMS['message']+self.rebase))
    def render(self):self.call('root_draw',[0x11150000,self.state()])

def legacy_bank():
    bank=bytearray(2688);struct.pack_into('>5I',bank,0,0x4d334c44,1,0,7,0)
    for i in range(20):
        at=48+132*i;bank[at]=1;bank[at+1]=i%2;struct.pack_into('>HH',bank,at+4,100+i,1)
    checksum=2166136261
    for byte in bank:checksum=((checksum^byte)*16777619)&0xffffffff
    struct.pack_into('>I',bank,16,checksum);return bytes(bank)

def main():
    checks=[];g=UI();charms=[(41,1),(42,1),(43,1),(44,1)]
    blade=charms+[(9,5)];ranged=charms+[(10,5)]+[(0,0)]*19+[(94,20)]
    g.register(0,False,blade);g.register(1,True,ranged);checks.append('Register Set confirms before saving both pouch types')
    g.inventory(False,blade);g.inventory(True,[(10,5)]+[(0,0)]*23+[(94,20)])
    g.enter_action(0);g.select(1);g.is_gunner=1;g.input(0x10);g.input(0x10)
    assert g.slots(True)==ranged+[(0,0)]*7 and all(x==(0,0) for x in g.slots(False)[:4]) and not g.box_writes
    g.input(0x20);g.select(0);g.is_gunner=0;g.input(0x10);g.input(0x10)
    assert g.slots(False)[:5]==blade and all(x==(0,0) for x in g.slots(True)[:4]);g.exit_list()
    checks.append('Current Sets retains direct cross-pouch transfers and slot order in both directions')
    g.enter_action(2);g.select(0);g.input(0x10);assert g.get('ui_anchor')==0
    g.select(23);g.input(0x10);assert g.get('ui_anchor')==0xffffffff
    sets=SYMS['sets'];assert g.u.mem_read(sets,1)==b'\x00' and g.u.mem_read(sets+23*132,1)==b'\x01';g.exit_list()
    checks.append('Reorder Sets moves a registration to an empty slot on another page')
    g.enter_action(3);g.select(23);g.input(0x10);files=dict(g.files)
    g.write32(g.addr('ui_choice'),1);g.input(0x10)
    assert g.u.mem_read(sets+23*132,1)==b'\x01' and g.files==files
    g.input(0x10);g.input(0x10);assert g.u.mem_read(sets+23*132,1)==b'\x00';g.exit_list()
    checks.append('Unregister Sets cancels on No and removes on Yes')
    g.enter_action(0);g.select(1);snapshot=g.snapshot();g.render()
    assert all(t in g.texts for t in g.row_texts) and g.texts[g.row_texts[1]]=='Set 2'
    assert any(e[0]=='list_open' for e in g.gui)
    assert g.number(g.maki+0xc)&0x130000==0x130000
    assert g.last_preview==b''.join(struct.pack('>HH',*x) for x in ranged+[(0,0)]*7)
    assert g.preview_indices==list(range(8)) and g.preview_pages==4 and g.snapshot()==snapshot
    g.input(dirs=8);assert g.number(SYMS['selected'])==9;g.render()
    assert any(e[0]=='page' and e[2:4]==(2,3) for e in g.gui)
    g.input(dirs=8);assert g.number(SYMS['selected'])==17;g.render()
    g.input(dirs=8);assert g.number(SYMS['selected'])==1
    g.input(0x200);g.render();assert g.preview_indices==list(range(8,16));g.exit_list()
    checks.append('Eight native rows, three set pages and independent item preview pages')
    g.enter_action(1);g.select(2);g.inventory(False,[(9,7)]);g.is_gunner=0;g.input(0x10);snapshot=g.snapshot();g.render()
    assert g.last_preview[:4]==struct.pack('>HH',9,7) and g.snapshot()==snapshot
    g.input(0x20);g.exit_list();checks.append('Register confirmation previews current pouch without editing inventory')
    many=UI()
    for i in range(24):many.register(i,bool(i%2),[(100+i,1)])
    reload=UI(dict(many.files));reload.enter_action(0)
    for i in range(24):assert bytes(reload.u.mem_read(SYMS['sets']+132*i,8))==bytes([1,i%2,0,0])+struct.pack('>HH',100+i,1)
    checks.append('All 24 registrations persist across injected-state restart')
    names=UI(dict(many.files));names.enter_action(0);names.select(0);names.render();names.write32(0x10167d20,0x400)
    unchanged=dict(names.files);names.input(0x80)
    assert names.get('ui_phase')==3 and names.keyboard_initial=='Set 1'
    assert names.number(0x10167d20)==0x404
    names.render();assert names.number(names.maki+0xc)&0x30000==0
    assert any(e[0]=='list_close' for e in names.gui)
    names.input();assert names.get('ui_phase')==3 and names.files==unchanged
    names.keyboard_ready=True;names.input();assert names.get('ui_phase')==0 and names.number(0x10167d20)==0x400
    assert any(e[0]=='keyboard_restore' for e in names.gui)
    names.render();assert names.texts[names.row_texts[0]]=='Gathering';names.exit_list()
    names.enter_action(2);names.select(0);names.input(0x10);names.select(1);names.input(0x10);names.exit_list()
    named_reload=UI(dict(names.files));named_reload.enter_action(0);named_reload.select(1);named_reload.render()
    assert named_reload.texts[named_reload.row_texts[1]]=='Gathering'
    named_reload.keyboard_ready=True;named_reload.keyboard_accepted=False;old=dict(named_reload.files)
    named_reload.input(0x80);named_reload.input();assert named_reload.files==old
    checks.append('Native keyboard renames persist, follow reordered sets, cancel cleanly and preserve unrelated UI flags')
    migration=UI({'mh3u_loadouts_user1_a.bin':legacy_bank()});migration.enter_action(0)
    for i in range(20):assert bytes(migration.u.mem_read(SYMS['sets']+132*i+4,4))==struct.pack('>HH',100+i,1)
    assert bytes(migration.u.mem_read(SYMS['sets']+20*132,4*132))==bytes(4*132)
    migration.exit_list();migration.register(23,False,[(130,1)])
    again=UI(dict(migration.files));again.enter_action(0);assert again.u.mem_read(SYMS['sets']+23*132,1)==b'\x01'
    checks.append('Old 20-set files migrate without loss and add four empty slots')
    failure=UI(dict(many.files));failure.enter_action(2);failure.select(0);failure.input(0x10);failure.select(1)
    before=bytes(failure.u.mem_read(SYMS['sets'],24*132));failure.fail_write=True;failure.input(0x10)
    assert bytes(failure.u.mem_read(SYMS['sets'],24*132))==before
    recovery=UI(dict(failure.files));recovery.enter_action(0);assert bytes(recovery.u.mem_read(SYMS['sets'],24*132))==before
    checks.append('Failed reorder rolls back and previous valid bank survives a truncated write')
    wording=UI();wording.enter_action(0)
    def text(group,index):
        ptr=wording.call('text_hook',[0,group,index]);return wording.cstring(ptr) if ptr else ''
    assert text(0x2e,395)=='Item Sets'
    assert [text(0x2e,i) for i in range(433,437)]==['Current Sets','Register Set','Reorder Sets','Unregister Sets']
    assert text(0x2f,180)=='Register your current items and switch between item sets.'
    assert text(0x2f,182)=='Register your item pouch as a new set.'
    assert 'equipment' not in text(0x2f,181).lower() and 'item set' in text(0x2f,181).lower()
    checks.append('Requested labels, native overview wording and equipment-to-item help conversion')
    wording.exit_list()
    native=wording.call('text_hook',[0,0x2f,0x114]);assert 'equipment' in wording.cstring(native)
    wording.gui.clear();wording.u.mem_write(wording.state(),b'\x10');wording.render()
    assert wording.gui[0][0]=='original_root_draw' and all(e[0]!='frame' for e in wording.gui)
    checks.append('Native Equipment Sets text and rendering delegate unchanged outside Item Sets')
    nav=UI();nav.enter_action(0);nav.exit_list();s=nav.state();nav.half(s+10,0);nav.half(s+6,2)
    nav.callbacks[SYMS['original_box_step']]='menu_next';nav.input();assert nav.half(s+6)==6
    checks.append('Main cursor order puts Item Sets directly after Combine/Manage Items')
    # Main visual rows: real pointer permutation, visibility calls, and an
    # animated scroll/separator object graph. Our PPC code executes the float
    # operations here; only the engine drawing functions are mocked.
    layout=UI();state=layout.state();layout.half(state+12,7)
    frames,plates,texts=0x11128000,0x11128100,0x11128200
    for offset,arr in [(0x2ac,frames),(0x2b0,plates),(0x2b8,texts)]:layout.write32(layout.maki+offset,arr)
    for i in range(8):
        for array,start in [(frames,0x11129000),(plates,0x1112a000),(texts,0x1112b000)]:layout.write32(array+4*i,start+i*0x100)
    scroll,line,scroll_root,line_root=0x11140000,0x11140100,0x11142000,0x11142100
    layout.write32(layout.maki+0xf4,scroll);layout.write32(scroll+4,428);layout.write32(scroll+0x64,line);layout.write32(line+4,593)
    layout.write32(scroll+0xfc,scroll_root);layout.write32(line+0xfc,line_root)
    children=[0x11143000+i*0x100 for i in range(5)]
    layout.write32(scroll_root+0x68,children[0])
    for i,obj in enumerate(children):
        layout.write32(obj,0x100a7cb0 if i==4 else 0x100a7f30)
        layout.u.mem_write(obj+0x84,struct.pack('>f',100.0))
        if i<4:layout.write32(obj+0x6c,children[i+1])
    separator=0x11144000;layout.write32(line_root+0x68,separator);layout.write32(separator,0x100a7f30)
    layout.u.mem_write(separator+0x84,struct.pack('>f',100.0))
    old=[layout.number(frames+4*i) for i in range(8)]
    layout.call('draw_options',[layout.maki,state])
    assert layout.draw_frame_map==[old[i] for i in (0,1,2,4,5,6,7,3)]
    assert [layout.number(frames+4*i) for i in range(8)]==old
    assert any(e[0]=='show_plate' and e[2]==0x1112a300 and e[3]==1 for e in layout.gui)
    assert any(e[0]=='show_plate' and e[2]==0x1112a400 and e[3]==0 for e in layout.gui)
    assert struct.unpack('>f',layout.u.mem_read(children[1]+0x84,4))[0]==154.0, 'Frame extension missed the first draw'
    layout.call('animation_hook',[scroll,0x11199000]);layout.call('animation_hook',[line,0x11199100])
    assert ('original_animation',scroll,0x11199000) in layout.gui
    assert ('original_animation',line,0x11199100) in layout.gui
    def y(obj):return struct.unpack('>f',layout.u.mem_read(obj+0x84,4))[0]
    assert y(children[1])==154.0 and y(separator)==154.0
    for _ in range(32):layout.call('animation_hook',[scroll]);layout.call('animation_hook',[line])
    assert y(children[1])==154.0, 'Idle menu resized after its old eight-frame timeout'
    layout.call('animation_hook',[scroll]);assert y(children[1])==154.0
    layout.u.mem_write(children[1]+0x84,struct.pack('>f',120.0));layout.call('animation_hook',[scroll]);assert y(children[1])==174.0
    layout.u.mem_write(state,b'\x14');layout.call('root_draw',[0x11150000,state])
    layout.u.mem_write(state,b'\x02')
    layout.call('animation_hook',[line]);layout.call('animation_hook',[scroll])
    assert y(separator)==100.0 and y(children[1])==120.0
    checks.append('Main row remapping, visible plates, animated separator shift and restoration without accumulation')
    # The four-action popup follows the new row, with hard-float Cafe f1 ABI.
    screen=0x11160000;layout.half(state+6,6);layout.half(state+10,1);layout.half(state+14,4)
    layout.write32(screen+0x418,100);layout.write32(screen+0x41c,120)
    for address,value in [(0x1005c520,54.0),(0x1005c524,20.0),(0x1005c530,0.0),(0x1005c534,900.0)]:layout.u.mem_write(address,struct.pack('>f',value))
    layout.call('draw_menu',[screen,state]);assert sorted(layout.y_values.values())==[262.0,282.0,282.0]
    checks.append('Four-action popup position follows Item Sets row using native float argument ABI')
    rebased=UI(dict(many.files),0x40000);rebased.enter_action(0);rebased.select(23);rebased.render()
    assert rebased.texts[rebased.row_texts[7]]=='Set 24';checks.append('Paged UI and previews work at another code-cave base')
    for action in range(4):
        visible=UI();visible.enter_action(action);visible.render()
        assert any(e[0]=='list_open' for e in visible.gui)
        assert visible.number(visible.maki+0xc)&0x130000==0x130000
        assert all(t in visible.texts for t in visible.row_texts)
        visible.exit_list();visible.render()
        assert any(e[0]=='list_close' for e in visible.gui)
        assert visible.number(visible.maki+0xc)&0x30000==0
    checks.append('All four set lists activate native draw submission and release it on exit or keyboard')
    paging=UI(dict(many.files));paging.enter_action(0);paging.select(0)
    paging.input(0x100);paging.render();assert paging.preview_page==3
    paging.input(0x200);paging.render();assert paging.preview_page==1
    paging.select(1);paging.input(0x100);paging.render();assert paging.preview_page==4
    paging.input(0x200);paging.render();assert paging.preview_page==1
    before=paging.snapshot();paging.input(0x40);paging.render()
    assert paging.u.mem_read(paging.state()+3,1)==b'\x01'
    assert paging.number(paging.maki+0xc)&0x30000==0
    assert paging.number(paging.preview+0xc)&0x30000==0
    assert paging.gui[-1][:3]==('original_root_draw',0x11150000,paging.state())
    assert paging.get('ui_list_open') and paging.number(SYMS['selected'])==1
    paging.input(0x20);paging.render()
    assert paging.u.mem_read(paging.state()+3,1)==b'\0'
    assert paging.number(paging.maki+0xc)&0x30000==0x30000 and paging.snapshot()==before
    assert any(e[0]=='rotate' for e in paging.gui)
    assert any(e[0]=='legend' and e[2]==0x14 for e in paging.gui)
    checks.append('L/R wrap three or four pouch pages; + opens native View Mode and returns to the same set')
    for action in range(4):
        rename=UI(dict(many.files));rename.enter_action(action);rename.select(0);rename.render()
        assert any(e[0]=='legend' and e[2]==0x14 for e in rename.gui)
        rename.input(0x80);assert rename.get('ui_phase')==3
        rename.keyboard_ready=True;rename.input();rename.render()
        assert rename.texts[rename.row_texts[0]]=='Gathering'
    checks.append('All four lists expose the native rename/view legend and Y renames registered sets')
    # Existing v0.2 default names migrate independently of their current slots.
    source={}
    for path,raw in many.files.items():
        bank=bytearray(raw)
        for index,label in [(0,'Item Set 24'),(1,'Gathering')]:
            at=48+24*132+20*index;bank[at:at+20]=label.encode()+bytes(20-len(label))
        struct.pack_into('>I',bank,16,0);checksum=2166136261
        for byte in bank:checksum=((checksum^byte)*16777619)&0xffffffff
        struct.pack_into('>I',bank,16,checksum);source[path]=bytes(bank)
    upgraded=UI(source);upgraded.enter_action(0);upgraded.render()
    assert upgraded.texts[upgraded.row_texts[0]]=='Set 24'
    assert upgraded.texts[upgraded.row_texts[1]]=='Gathering'
    assert upgraded.cstring(SYMS['set_names']+23*20)=='Set 24'
    checks.append('Short default names and automatic legacy-name migration preserve custom names')
    banner=UI(dict(many.files));banner.enter_action(0);banner.select(0);banner.render()
    assert banner.preview_title not in banner.texts
    banner.select(1);banner.render();assert banner.preview_title not in banner.texts
    banner.input(0x100);banner.render();assert banner.preview_title not in banner.texts
    banner.exit_list();banner.enter_action(1);banner.select(0);banner.is_gunner=1
    banner.input(0x10);banner.render();assert banner.preview_title not in banner.texts
    checks.append('Item List title is preserved across pouch types, paging and registration')
    audio=UI();audio.register(0,False,[(9,5)]);audio.enter_action(0)
    audio.gui.clear();audio.input(0x10);audio.input(0x10)
    assert not any(e[0]=='equip_sound' for e in audio.gui)
    assert sum(e[0]=='sound' and e[2]==5 for e in audio.gui)==1
    audio.exit_list();audio.inventory(False,[]);audio.inventory(True,[]);audio.enter_action(0)
    snapshot=audio.snapshot();audio.gui.clear();audio.input(0x10);audio.input(0x10)
    assert 'loaded' in audio.message() and audio.snapshot()==snapshot
    assert audio.number(SYMS['load_missing_units'])==5
    assert not any(e[0]=='equip_sound' for e in audio.gui)
    assert any(e[0]=='sound' and e[2]==5 for e in audio.gui)
    checks.append('Original menu load sound restored; Equipment Sets equip sound never plays')
    partial=UI();partial.register(0,False,[(9,10)]);partial.inventory(False,[]);partial.inventory(True,[])
    partial.u.mem_write(UD+0x1c0,struct.pack('>HH',9,9));partial.enter_action(0)
    old_registration=bytes(partial.u.mem_read(SYMS['sets'],132));old_files=dict(partial.files)
    partial.input(0x10);partial.input(0x10)
    assert bytes(partial.u.mem_read(HUNTER+0xa8,4))==struct.pack('>HH',9,9)
    assert bytes(partial.u.mem_read(UD+0x1c0,4))==bytes(4)
    assert partial.number(SYMS['load_missing_units'])==1
    def help_text():
        return partial.cstring(partial.call('text_hook',[0,0x2f,0x114]))
    warning='(Some items were insufficient or missing.)'
    assert help_text()=='Item set loaded.\r\n'+warning
    partial.input(0x20)
    assert help_text()=='Select an item set.\r\n'+warning
    assert bytes(partial.u.mem_read(SYMS['sets'],132))==old_registration and partial.files==old_files
    partial.u.mem_write(UD+0x1c0,struct.pack('>HH',9,1))
    partial.input(0x10);partial.input(0x10);assert partial.number(SYMS['load_missing_units'])==0
    assert warning not in help_text()
    assert bytes(partial.u.mem_read(HUNTER+0xa8,4))==struct.pack('>HH',9,10)
    checks.append('Partial load fills nine of ten, appends exact warning below help, and retains saved quantities')
    partial.exit_list();partial.inventory(False,[]);partial.enter_action(0)
    partial.input(0x10);partial.input(0x10);assert partial.number(SYMS['load_missing_units'])==10
    partial.input(0x20);partial.input(dirs=2);assert warning not in help_text()
    partial.exit_list();assert partial.number(SYMS['load_missing_units'])==0
    checks.append('Entirely missing items are skipped; warnings clear on selection change, exit or complete refill')
    result_view=UI();result_view.register(0,False,[(9,10),(10,5),(41,1)])
    result_view.inventory(False,[]);result_view.inventory(True,[])
    result_view.u.mem_write(UD+0x1c0,struct.pack('>HHHH',9,9,10,3))
    registration=bytes(result_view.u.mem_read(SYMS['sets'],132));files_before=dict(result_view.files)
    result_view.enter_action(0);result_view.input(0x10);result_view.input(0x10)
    inventory=result_view.snapshot();result_view.render()
    assert result_view.last_preview[:12]==struct.pack('>HHHHHH',9,9,10,3,0,0)
    assert result_view.preview_title not in result_view.texts
    result_view.input(0x200);result_view.render();assert result_view.preview_indices==list(range(8,16))
    result_view.input(0x10);result_view.render()
    assert result_view.get('ui_phase')==0
    assert result_view.last_preview[:12]==struct.pack('>HHHHHH',9,10,10,5,41,1)
    assert bytes(result_view.u.mem_read(SYMS['sets'],132))==registration
    assert result_view.files==files_before and result_view.snapshot()==inventory
    checks.append('Partial-result Blade preview shows actual counts and missing slots; A restores registered preview')
    ammo_view=UI();ammo_view.u.mem_write(TABLE+95*20,bytes([4,0,0,99])+bytes(16))
    registered=[(9,4)]+[(0,0)]*23+[(94,20),(95,30)]
    ammo_view.register(0,True,registered);ammo_view.inventory(True,[]);ammo_view.inventory(False,[(9,2)])
    ammo_view.u.mem_write(UD+0x1c0,struct.pack('>HH',94,7));ammo_view.enter_action(0)
    ammo_view.input(0x10);ammo_view.input(0x10);ammo_view.render()
    assert ammo_view.last_preview[:4]==struct.pack('>HH',9,2)
    for _ in range(3):ammo_view.input(0x200)
    ammo_view.render();assert ammo_view.preview_indices==list(range(24,32))
    assert ammo_view.last_preview[96:104]==struct.pack('>HHHH',94,7,0,0)
    assert ammo_view.preview_title not in ammo_view.texts
    ammo_view.input(0x10);ammo_view.render()
    assert ammo_view.preview_indices==list(range(24,32))
    assert ammo_view.last_preview[96:104]==struct.pack('>HHHH',94,20,95,30)
    checks.append('Partial-result Gunner preview includes actual ammo and returns to registered ammo on the same page')
    result={'status':'passed','count':len(checks),'checks':checks,
        'limitations':['External game/OS callbacks and GUI objects are mocked','Actual Cemu screenshot and input verification still required']}
    (ROOT/'build/adapter-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
