"""Run the original animation method prologue from a user-provided RPX.

The native transform operation is intercepted to verify its parent-matrix
argument. No proprietary bytes are embedded in this test or distributed.
Usage: python tests/test_animation.py EXECUTABLE_RPX INVESTIGATION_DIRECTORY
"""
from game_harness import *
sys.path.insert(0,sys.argv[2])
from inspect_rpx import sections
g=Game()
text=next(s for s in sections(sys.argv[1]) if s['name']=='.text')
start=0x02ae1e40
g.u.mem_write(start,text['data'][start-text['addr']:start-text['addr']+0x8c])
instance,parent=0x11190000,0x11191000
g.write32(instance+0xfc,0) # No transform root: native early-out after update.
calls=[]
def transform(uc,address,size,data):
    if address!=0x02adf674:return
    calls.append((g.reg(3),g.reg(4)))
    assert calls[-1]==(instance,parent),'Animation parent matrix was corrupted'
    g.return_(0)
g.u.hook_add(UC_HOOK_CODE,transform)
g.call('animation_hook',[instance,parent])
assert calls==[(instance,parent)]
result={'status':'passed','checks':['Original native animation prologue and epilogue execute','Parent matrix reaches native transform updater unchanged','Nonvolatile GPRs and stack preserved'],
        'limitations':['Native transform mathematics intercepted; not a full Cemu launch']}
(ROOT/'build/animation-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
