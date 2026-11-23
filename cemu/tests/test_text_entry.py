"""Exercise stackless text interception with MH3U's native text accessor.
Usage: python tests/test_text_entry.py US_RPX TOOLS_DIRECTORY
Resource methods and translation-index helper are fixtures, not a Cemu run.
"""
from test_ui import UI
from game_harness import *
sys.path.insert(0,sys.argv[2])
from inspect_rpx import sections
text=next(s for s in sections(sys.argv[1]) if s['name']=='.text')
g=UI();g.callbacks.pop(SYMS['original_text'])
start=0x02141de0;end=start+0xcc
g.u.mem_write(start,text['data'][start-text['addr']:end-text['addr']])
# For the text groups used here, the native regional index translator returns
# the requested index directly. Execute that real code rather than a stub.
translate=0x0213db30
g.u.mem_write(translate,text['data'][translate-text['addr']:translate-text['addr']+0x180])
resource_groups={}
for group in [0x2e,0x2f,0x30]:
 resource=0x111b0000+group*0x100;vtable=0x111b4000+group*0x100
 resource_groups[resource]=group
 g.write32(0x11070000+0x78+group*4,resource);g.write32(resource,vtable)
 g.write32(vtable+0x4c,0x01990200);g.write32(vtable+0x54,0x01990210)
for group,index,value in [(0x2e,389,'Take Items'),(0x2e,392,'Change Equipment'),(0x30,9,'Native item text')]:
 at=0x111c0000+len(g.native_strings)*0x100
 g.u.mem_write(at,value.encode()+b'\0');g.native_strings[group,index]=at
native_calls=[];in_lookup=False;unexpected=[]
def native(uc,address,size,data):
 if in_lookup and address==SYMS['box_step']:unexpected.append(address)
 if address==0x01990200:g.return_(resource_groups[g.reg(3)])
 elif address==0x01990210:
  group,index=resource_groups[g.reg(3)],g.reg(4)
  native_calls.append((group,index));g.return_(g.native_strings.get((group,index),0))

g.u.hook_add(UC_HOOK_CODE,native)
def lookup(group,index):
 global in_lookup
 # Arguments, stack, LR, nonvolatile GPRs and all floating registers survive.
 for i in range(6,11):g.u.reg_write(getattr(p,f'UC_PPC_REG_{i}'),0x12340000+i)
 floats={i:0x3ff0000000000000+i for i in range(32)}
 for i,v in floats.items():g.u.reg_write(getattr(p,f'UC_PPC_REG_FPR{i}'),v)
 in_lookup=True
 ptr=g.call('text_entry',[0x11070000,group,index]);in_lookup=False
 assert g.reg(1)==0x1201f000
 assert all(g.u.reg_read(getattr(p,f'UC_PPC_REG_FPR{i}'))==v for i,v in floats.items())
 return g.cstring(ptr) if ptr else None
# Before a box session, even the game's fourth row delegates unchanged.
assert lookup(0x2e,392)=='Change Equipment'
g.enter_action(0)
assert g.get('ui_text_ready')==1
# Base wording was fetched using the real native accessor, outside the hook.
assert (0x2f,175) in native_calls and (0x2f,0x11b) in native_calls
for group,index,expected in [(0x2e,395,'Item Sets'),(0x2e,433,'Current Sets'),(0x2e,434,'Register Set'),(0x2e,435,'Reorder Sets'),(0x2e,436,'Unregister Sets'),(0x2f,182,'Register your item pouch as a new set.')]:
 before=len(native_calls);assert lookup(group,index)==expected;assert len(native_calls)==before
assert lookup(0x2e,389)=='Take Items'
assert lookup(0x30,9)=='Native item text'
assert lookup(0x2f,0x114)=='Select an item set.'
assert not unexpected
# No C function is reachable from the lookup entry: inspect executed addresses.
c_only={SYMS[n] for n in ['box_step','root_draw','draw_options','prepare_item_text','refresh_item_text'] if n in SYMS}
executed=[]
g.u.hook_add(UC_HOOK_CODE,lambda uc,a,size,data:executed.append(a) if a in c_only else None)
for _ in range(100):
 assert lookup(0x2e,395)=='Item Sets';assert lookup(0x30,9)=='Native item text'
assert not executed
result={'status':'passed','checks':['Real native text accessor and native regional index translator fetch base help outside interception','All custom labels and requested Register Set wording return directly','Unrelated text delegates through the native accessor unchanged','Repeated lookups never enter C UI functions or allocate a wrapper stack frame','All floating and nonvolatile registers survive text lookup'], 'limitations':['Resource virtual methods are fixtures; Linux/Cemu confirmation required']}
(ROOT/'build/text-entry-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
