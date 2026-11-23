"""Exercise native list activation code from the supplied RPX.

Usage: python tests/test_list_visibility.py RPX INVESTIGATION_DIRECTORY
GUI geometry/animation work is intercepted; this checks native unit activation,
not pixels. No game bytes are embedded or distributed.
"""
from test_ui import UI
from game_harness import *
sys.path.insert(0,sys.argv[2])
from inspect_rpx import sections
text=next(s for s in sections(sys.argv[1]) if s['name']=='.text')
for action in range(4):
    g=UI();g.enter_action(action)
    # uIDLobbyMaki::vf+1D4 and its base-class open operation, taken from the RPX.
    for address,size in [(0x026a3d3c,0x48),(0x0228d2a0,0x64)]:
        g.u.mem_write(address,text['data'][address-text['addr']:address-text['addr']+size])
    g.write32(0x11132000+0x1d4,0x026a3d3c)
    g.u.mem_write(g.maki+0x260,b'\x01') # GUI already loaded by the owning menu.
    opened=[]
    def native(uc,address,size,data):
        if address==0x026a3d3c:opened.append(g.reg(3))
        if address==0x02a70d34:g.return_(0) # Animation coordinates need real GUI assets.
    g.u.hook_add(UC_HOOK_CODE,native)
    g.render()
    assert opened==[g.maki],('Native activation skipped',action)
    assert g.number(g.maki+0xc)&0x130000==0x130000
    assert g.u.mem_read(g.maki+0x260,1)==b'\0'
    assert all(t in g.texts for t in g.row_texts)
    g.exit_list();g.render()
    assert g.number(g.maki+0xc)&0x30000==0
result={'status':'passed','checks':['All four actions reach native Maki activation code','Native activation clears deferred-hide flag','List receives update/draw scheduling bits','Eight labels populate while list is active','Exit releases borrowed scheduling bits'],
        'limitations':['GUI animation/geometry intercepted; Cemu visual confirmation required']}
(ROOT/'build/list-visibility-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
