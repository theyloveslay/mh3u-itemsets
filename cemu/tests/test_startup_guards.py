"""Execute inactive/active UI entry stubs and check native argument handoff."""
from test_ui import UI
from game_harness import *
expected={0x02141de0:'text_entry',0x026a6b80:'options_entry',0x02687d38:'menu_entry',0x0270a738:'root_entry',0x02ae1e40:'animation_entry'}
for address,entry in expected.items():assert MANIFEST['hooks'][hex(address)]==entry,('Guard not installed',hex(address))
g=UI();seen=[]
wrappers={SYMS[n]:n for n in ['draw_options','draw_menu_entry','root_draw','animation_hook']}
def observe(uc,address,size,data):
    if address in wrappers:
        seen.append(wrappers[address])
        # The paired-single save stub is checked by test_cafe_abi; Unicorn
        # cannot execute its Gekko-only instructions. Check this guard's
        # destination here and leave the target stub to that dedicated test.
        if wrappers[address]=='draw_menu_entry':g.return_(0)
g.u.hook_add(UC_HOOK_CODE,observe)
fprs={i:0x3ff1234500000000+i for i in range(32)}
for i,v in fprs.items():g.u.reg_write(getattr(p,f'UC_PPC_REG_FPR{i}'),v)
cases=[('text_entry',[0,0x2e,395]),('options_entry',[0x11150000,g.state()]),
       ('menu_entry',[0x11150000,g.state()]),('root_entry',[0x11150000,g.state()]),
       ('animation_entry',[0x11190000,0x11191000])]
for name,args in cases:
    g.call(name,args)
    assert g.reg(1)==0x1201f000
assert not seen,'Startup unexpectedly entered injected C UI'
assert all(g.u.reg_read(getattr(p,f'UC_PPC_REG_FPR{i}'))==v for i,v in fprs.items())
assert ('original_animation',0x11190000,0x11191000) in g.gui
assert any(e[:3]==('original_root_draw',0x11150000,g.state()) for e in g.gui)
g.write32(g.addr('ui_box_enabled'),1)
for name,args in cases[:-1]:g.call(name,args)
assert g.cstring(g.call('text_entry',[0,0x2e,395]))=='Item Sets'
assert set(seen)==set(['draw_options','draw_menu_entry','root_draw'])
g.write32(g.addr('shift_count'),1);g.call('animation_entry',[0x11190000,0x11191000])
assert seen[-1]=='animation_hook'
result={'status':'passed','checks':['Startup text and UI guards retain their native paths',
    'Native arguments, stack and all FPR primary values survive inactive handoff',
    'Stackless text serves labels; active UI and animation guards reach the intended wrappers'],
    'limitations':['External native callbacks are fixtures; not a Cemu startup test']}
(ROOT/'build/startup-guards-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
