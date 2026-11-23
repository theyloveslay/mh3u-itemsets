"""Conservation and failure tests for host C and the exact compiled PPC core."""
from pathlib import Path
import collections, ctypes as C, json, random, struct, sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as p

ROOT=Path(__file__).resolve().parents[1]
class Slot(C.Structure): _fields_=[('id',C.c_uint16),('count',C.c_uint16)]
class Loadout(C.Structure): _fields_=[('valid',C.c_uint8),('gunner',C.c_uint8),('reserved',C.c_uint16),('slots',Slot*32)]
class Rule(C.Structure): _fields_=[('limit',C.c_uint8),('category',C.c_uint8),('allowed',C.c_uint8),('reserved',C.c_uint8)]
class Tx(C.Structure): _fields_=[('target',Slot*32),('donor',Slot*32),('box',Slot*1000),('remaining',Slot*32),('direct',C.c_uint32),('box_units',C.c_uint32),('missing',C.c_uint32)]

def totals(*arrays):
    out=collections.Counter()
    for arr in arrays:
        for item,n in arr:
            if item:out[item]+=n
    return +out
def pairs(array):return [(s.id,s.count) for s in array]
def packed(array):return b''.join(struct.pack('>HH',i,n) for i,n in array)
def padded(array,n):return list(array)+[(0,0)]*(n-len(array))

class Host:
    def __init__(self):
        self.lib=C.CDLL(str(ROOT/'build/loadouts-host.so'))
        self.lib.plan_loadout.argtypes=[C.POINTER(Slot),C.c_uint32,C.POINTER(Slot),C.c_uint32,C.POINTER(Slot),C.c_uint32,C.POINTER(Loadout),C.POINTER(Rule),C.POINTER(Tx)]
    def run(self,target,donor,box,want,rules,kind):
        t=(Slot*len(target))(*(Slot(*s) for s in target));d=(Slot*len(donor))(*(Slot(*s) for s in donor));b=(Slot*len(box))(*(Slot(*s) for s in box))
        w=Loadout(1,kind,0,(Slot*32)(*(Slot(*s) for s in padded(want,32))))
        r=(Rule*0x5fd)(*(Rule(*s) for s in rules));tx=Tx()
        status=self.lib.plan_loadout(t,len(t),d,len(d),b,len(b),C.byref(w),r,C.byref(tx))
        assert pairs(t)==target and pairs(d)==donor and pairs(b)==box,'Planner wrote authoritative inputs'
        if status in (0,3):self.lib.commit_loadout(t,len(t),d,len(d),b,len(b),C.byref(tx))
        return status,pairs(t),pairs(d),pairs(b),(tx.direct,tx.box_units,tx.missing)

class PPC:
    def __init__(self):
        self.u=Uc(UC_ARCH_PPC,UC_MODE_PPC32|UC_MODE_BIG_ENDIAN)
        self.u.mem_map(0x01800000,0x100000);self.u.mem_map(0x11000000,0x20000);self.u.mem_map(0x12000000,0x20000)
        with open(ROOT/'build/loadouts-ppc.elf','rb') as f:
            elf=ELFFile(f)
            for section in elf.iter_sections():
                if section['sh_flags']&2 and section['sh_size']:
                    self.u.mem_write(section['sh_addr'],section.data())
            self.symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    def call(self,fn,args):
        # Ninth argument follows the PPC32 caller linkage/argument save area.
        stack=0x1201f000
        self.u.reg_write(p.UC_PPC_REG_1,stack);self.u.reg_write(p.UC_PPC_REG_LR,0x018ff000)
        for i,v in enumerate(args):
            if i<8:self.u.reg_write(getattr(p,f'UC_PPC_REG_{3+i}'),v)
            else:self.u.mem_write(stack+8+4*(i-8),struct.pack('>I',v))
        self.u.emu_start(self.symbols[fn],0x018ff000,count=2000000)
        assert self.u.reg_read(p.UC_PPC_REG_PC)==0x018ff000
        return self.u.reg_read(p.UC_PPC_REG_3)
    def run(self,target,donor,box,want,rules,kind):
        t,d,b,w,r,tx=0x11000000,0x11000100,0x11000200,0x11002000,0x11003000,0x11005000
        inputs=[(t,packed(target)),(d,packed(donor)),(b,packed(box))]
        for a,data in inputs:self.u.mem_write(a,data)
        self.u.mem_write(w,bytes([1,kind,0,0])+packed(padded(want,32)))
        self.u.mem_write(r,b''.join(bytes(v) for v in rules))
        status=self.call('plan_loadout',[t,len(target),d,len(donor),b,len(box),w,r,tx])
        for a,data in inputs:assert bytes(self.u.mem_read(a,len(data)))==data
        counts=struct.unpack('>III',self.u.mem_read(tx+4384,12))
        if status in (0,3):self.call('commit_loadout',[t,len(target),d,len(donor),b,len(box),tx])
        def read(a,n):return [struct.unpack('>HH',self.u.mem_read(a+4*i,4)) for i in range(n)]
        return status,read(t,len(target)),read(d,len(donor)),read(b,len(box)),counts

def main():
    host,ppc=Host(),PPC();rng=random.Random(0x3abc)
    rules=[(10,0,1,0)]*0x5fd
    rules[0]=rules[1]=(0,0,0,0)
    for item in (41,42,43,44):rules[item]=(1,0,1,0)
    rules[94]=(99,1,1,0)
    cases=[]
    def add(name,t,d,b,w,kind,expected=None):
        cases.append((name,padded(t,32 if kind else 24),padded(d,24 if kind else 32),b,padded(w,32),kind,expected))
    add('direct_singletons_full_box',[],[(41,1),(42,1),(43,1),(44,1)],[(500,99)]*1000,[(44,1),(43,1),(42,1),(41,1)],1,0)
    add('direct_reverse',[],[(41,1),(42,1),(43,1),(44,1)],[(500,99)]*1000,[(41,1),(42,1),(43,1),(44,1)],0,0)
    add('target_then_donor_then_box',[(9,2)],[(9,3)],[(9,7),(0,0)],[(9,10)],0,0)
    add('withdraw_frees_box_space',[(10,5)],[],[(9,8)],[(9,8)],0,0)
    add('capacity_failure',[(10,5)],[(9,8)],[(500,99)],[(9,8)],0,4)
    add('partial_across_three_sources',[(9,2)],[(9,3)],[(9,1)],[(9,10)],0,3)
    add('ammo_last_eight',[],[(94,90)],[(0,0)],[(0,0)]*24+[(94,90)],1,0)
    add('normal_item_in_ammo_rejected',[],[(9,1)],[(0,0)],[(0,0)]*24+[(9,1)],1,1)
    add('stack_limit_rejected',[],[(9,10)],[(9,99)],[(9,11)],0,1)
    add('empty_loadout',[(9,5)],[(10,6)],[(0,0)],[],0,0)
    add('same_item_multiple_saved_slots',[(9,3)],[(9,7)],[(0,0)],[(9,5),(9,5)],0,0)
    add('unrelated_donor_untouched',[],[(10,7),(9,5)],[(0,0)],[(9,3)],0,0)
    add('source_quantity_left_over',[],[(9,9)],[(0,0)],[(9,3)],0,0)
    add('zero_item_with_quantity_invalid',[],[],[(0,0)],[(0,1)],0,1)
    add('box_nine_of_ten',[],[],[(9,9)],[(9,10)],0,3)
    add('nine_box_one_donor',[],[(9,1)],[(9,9)],[(9,10)],0,0)
    add('missing_one_item_other_items_apply',[],[],[(10,5)],[(9,10),(10,5)],0,3)
    add('no_stock_at_all',[],[],[(0,0)],[(9,10)],0,3)
    add('partial_duplicate_slots',[(9,3)],[],[(9,4)],[(9,5),(9,5)],0,3)
    add('partial_ammo',[],[(94,7)],[(0,0)],[(0,0)]*24+[(94,20)],1,3)
    add('partial_but_box_full',[(10,5)],[],[(500,99)],[(9,10)],0,4)
    # Random conservation runs, including independent box capacity and shortages.
    for i in range(200):
        kind=rng.randrange(2)
        def inventory(n):return [(rng.randrange(2,15),rng.randrange(1,11)) if rng.randrange(3) else (0,0) for _ in range(n)]
        t=inventory(24);d=inventory(24);b=inventory(rng.randrange(1,21))
        w=inventory(rng.randrange(0,25))
        add(f'random_{i}',t,d,b,w,kind)
    passed=[]
    for name,t,d,b,w,kind,expected in cases:
        h=host.run(t,d,b,w,rules,kind);native=ppc.run(t,d,b,w,rules,kind)
        assert native==h,(name,'PPC/host mismatch',h[0],native[0],h[-1],native[-1])
        status,nt,nd,nb,counts=h
        if expected is not None:assert status==expected,(name,status,expected)
        if status in (0,3):
            supply=totals(t,d,b);expected_slots=[];missing=0
            for item,count in w[:len(t)]:
                actual=min(count,supply[item]) if item else 0
                expected_slots.append((item,actual) if actual else (0,0))
                supply[item]-=actual;missing+=count-actual
            assert nt==expected_slots,(name,nt,expected_slots)
            assert counts[2]==missing and (status==3)==bool(missing),name
            assert totals(t,d,b)==totals(nt,nd,nb),(name,'quantity loss/duplication')
            assert all(n<=99 for item,n in nb)
        else:assert (nt,nd,nb)==(t,d,b),(name,'failed operation modified inventory')
        if name=='target_then_donor_then_box':assert counts==(3,5,0)
        if name=='unrelated_donor_untouched':assert nd[0]==(10,7)
        if name=='source_quantity_left_over':assert nd[0]==(9,6)
        passed.append(name)
    result={'status':'passed','cases':len(passed),'engines':['host C','compiled PowerPC under Unicorn'],
            'coverage':['exact slot layout','conservation','direct both directions','full box','deficit sourcing order','partial stacks','missing item best-effort loads','rollback on invalid/capacity errors','ammo section','per-item limits','200 randomized cases'],
            'limitations':['Metadata fixtures supplied; not an actual Cemu gameplay test'], 'named_cases':passed[:21]}
    (ROOT/'build/transaction-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
