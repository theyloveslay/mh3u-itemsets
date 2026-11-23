"""Exercise real compiled storage failures and retries; Cafe FS is a fixture."""
from game_harness import *
class FailureGame(Game):
    def __init__(self,files=None):
        self.failures={};super().__init__(files)
    def hook(self,uc,address,size,data):
        name=self.services.get(address)
        if name in self.failures:
            code=self.failures[name]
            if callable(code):code=code(self)
            if code is not None:self.return_(code);return
        super().hook(uc,address,size,data)
def error(g):return g.cstring(g.call('storage_error',[]))
def load(g):return g.call('ensure_loaded',[])
checks=[]
# Missing sidecars are normal for a first installation and must stay writable.
g=FailureGame();before=g.snapshot();assert load(g)==1 and g.files=={} and g.snapshot()==before
checks.append('Two missing sidecars still initialize an empty, writable collection')
# An unavailable account used to latch io_ready=0 until character reload.
g=FailureGame();g.u.mem_write(0x110842bf,b'\xff');assert load(g)==0
assert error(g)=='Storage: account (255)\r\nChar 0, account 255'
g.u.mem_write(0x110842bf,b'\x01');assert load(g)==1
checks.append('Account-not-ready diagnostic reports exact value; later request retries successfully')
g=FailureGame();g.write32(g.local('character'),3);assert load(g)==0
assert error(g)=='Storage: character (3)\r\nChar 3, account 1'
g.write32(g.local('character'),0);assert load(g)==1
checks.append('Unbound character is distinguished from an unavailable account')
g=FailureGame();site=0x02bdbf18;original=bytes(g.u.mem_read(site,4));g.write32(site,0)
assert load(g)==0 and 'fs_add import (0)' in error(g)
g.u.mem_write(site,original);assert load(g)==1
checks.append('Unrecognized import reports its identity; restored import can retry')
for service,label in [('add','FSAddClient'),('open','open B')]:
 g=FailureGame();g.failures[service]=-19;before=g.snapshot()
 assert load(g)==0 and error(g)==f'Storage: {label} (-19)\r\nChar 0, account 1'
 assert not g.files and g.snapshot()==before
 g.failures.clear();assert load(g)==1
 checks.append(f'{service} failure reports native return code and permits a later successful retry')
# Obtain a valid file from compiled registration; retain it in every failure case.
g=FailureGame();g.inventory(False,[(41,7)]);g.call('capture',[])
original_files=dict(g.files);assert original_files
for service,label,code in [('read','read A',-8),('read','read A',100),('close','close A',-19)]:
 g=FailureGame(dict(original_files));g.failures[service]=code;before=g.snapshot()
 assert load(g)==0,(service,error(g))
 assert f'Storage: {label} ({code})' in error(g),error(g)
 assert g.files==original_files and g.snapshot()==before
 g.failures.clear();assert load(g)==1 and g.files==original_files
 checks.append(f'{label} return {code} reported without changing banks or inventory; retry succeeds')
g=FailureGame({'mh3u_loadouts_user1_a.bin':bytes(3712)});before=g.snapshot();saved=dict(g.files)
assert load(g)==0 and 'invalid bank A (-1)' in error(g)
assert load(g)==0 and g.files==saved and g.snapshot()==before
checks.append('Malformed sidecar remains read-only across retries; not silently replaced with defaults')
result={'status':'passed','checks':checks,'limitations':['Filesystem results are injected; live EU diagnostic identifies the actual failing stage']}
(ROOT/'build/storage-diagnostics-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
