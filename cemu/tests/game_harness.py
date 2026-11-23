"""Execute the built injected PPC code with simulated game input and Cafe FS.

These checks exercise our compiled hooks, persistence and transactions. The
external game/UI/OS callbacks are mocks; this is NOT a Cemu gameplay test.
"""
from pathlib import Path
import collections,json,struct,sys
from unicorn import Uc,UC_ARCH_PPC,UC_MODE_PPC32,UC_MODE_BIG_ENDIAN,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import ppc_const as p
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/'build/mod-manifest.json').read_text())
SYMS=MANIFEST['symbols'];LOC=MANIFEST['locals']
UD,HUNTER,LOBBY,TABLE,STOP=0x11010000,0x11010038,0x11100000,0x13000000,0x14000000

class Game:
    def __init__(self,files=None,rebase=0):
        self.u=Uc(UC_ARCH_PPC,UC_MODE_PPC32|UC_MODE_BIG_ENDIAN)
        self.u.mem_map(0x01800000,0x200000);self.u.mem_map(0x02000000,0x1200000)
        self.u.mem_map(0x10000000,0x500000);self.u.mem_map(0x11000000,0x200000)
        self.u.mem_map(0x12000000,0x20000);self.u.mem_map(TABLE,0x10000);self.u.mem_map(STOP,0x1000)
        image=bytearray((ROOT/'build/mod.bin').read_bytes());self.rebase=rebase
        for r in MANIFEST['relocations']:
            addr=MANIFEST['base']+rebase+r['target'];typ=r['type'];at=r['offset']
            if typ==1:struct.pack_into('>I',image,at,addr)
            elif typ in (4,5,6):struct.pack_into('>H',image,at,(addr if typ==4 else addr>>16 if typ==5 else (addr+0x8000)>>16)&65535)
        self.u.reg_write(p.UC_PPC_REG_MSR,0x2000)
        self.u.mem_write(MANIFEST['base']+rebase,bytes(image))
        self.files={} if files is None else files
        self.handles={};self.next_fd=1;self.events=[];self.fail_write=False
        self.result=0;self.directions=0;self.is_gunner=0;self.box_slots=1000
        self.cancel_submenu=False
        self.u.mem_write(0x10315f50,struct.pack('>I',UD))
        self.u.mem_write(0x10167e50,struct.pack('>I',TABLE))
        self.u.mem_write(0x102cebe0,struct.pack('>I',0x11080000))
        self.u.mem_write(0x110842bf,b'\x01')
        for i in range(0x5fd):
            self.u.mem_write(TABLE+20*i,bytes([1 if i==94 else 0,0,0,1 if i in (41,42,43,44) else 99])+bytes(16))
        self.services={}
        sites=[(0x02bdbf18,'add'),(0x02935b84,'initcmd'),(0x02bdcef8,'open'),(0x02bdc56c,'read'),(0x02bdcff8,'write'),(0x02bdce88,'close'),(0x02bdd1ec,'flush')]
        for i,(site,name) in enumerate(sites):
            addr=0x01980000+16*i;self.services[addr]=name
            self.u.mem_write(site,struct.pack('>I',0x48000001|((addr-site)&0x03fffffc)))
        self.callbacks={SYMS['original_box_step']+rebase:'menu',SYMS['original_character']+rebase:'character',SYMS['original_text']+rebase:'text',0x02199e48:'gunner',0x0219880c:'boxslots',0x0221a430:'directions'}
        self.box_writes=[]
        self.u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,address,size,value,data:self.box_writes.append(address),begin=UD+0x1c0,end=UD+0x1c0+3999)
        self.u.hook_add(UC_HOOK_CODE,self.hook)
        self.call('track_character',[0,0,0])

    def reg(self,i):return self.u.reg_read(getattr(p,f'UC_PPC_REG_{i}'))
    def number(self,addr):return struct.unpack('>I',self.u.mem_read(addr,4))[0]
    def write32(self,addr,n):self.u.mem_write(addr,struct.pack('>I',n&0xffffffff))
    def half(self,addr,n=None):
        if n is not None:self.u.mem_write(addr,struct.pack('>H',n))
        return struct.unpack('>H',self.u.mem_read(addr,2))[0]
    def cstring(self,addr):
        out=bytearray()
        for i in range(1024):
            b=self.u.mem_read(addr+i,1)[0]
            if not b:return out.decode()
            out.append(b)
        raise AssertionError('Unterminated string')
    def return_(self,result):
        self.u.reg_write(p.UC_PPC_REG_3,result&0xffffffff)
        self.u.reg_write(p.UC_PPC_REG_PC,self.u.reg_read(p.UC_PPC_REG_LR))
    def hook(self,uc,address,size,data):
        if address in self.callbacks:
            name=self.callbacks[address]
            if name=='menu' and self.cancel_submenu:self.half(self.state()+10,0)
            result={'menu':self.result,'character':1,'text':0,'gunner':self.is_gunner,'boxslots':self.box_slots,'directions':self.directions}[name]
            self.return_(result);return
        name=self.services.get(address)
        if not name:return
        args=[self.reg(i) for i in range(3,11)]
        result=0
        if name=='add':assert args[0]%64==0 and args[1]==0xffffffff
        elif name=='initcmd':assert args[0]%64==0
        elif name=='open':
            path,mode=self.cstring(args[3]),self.cstring(args[4]);self.events.append((name,path,mode))
            assert path.startswith('mh3u_loadouts_user') and path.endswith(('_a.bin','_b.bin'))
            assert args[2]==1 and args[6]==0xffffffff
            if mode=='r' and path not in self.files:result=-6
            else:
                fd=self.next_fd;self.next_fd+=1;self.handles[fd]=(path,mode)
                if mode=='w':self.files[path]=b''
                self.write32(args[5],fd)
        elif name in ('read','write'):
            assert args[2]%64==0 and args[3:5]==[1,3712] and args[6:8]==[0,0xffffffff]
            path,mode=self.handles[args[5]]
            if name=='read':
                content=self.files[path][:3712];self.u.mem_write(args[2],content);result=len(content)
            elif self.fail_write:
                self.files[path]=bytes(self.u.mem_read(args[2],100));result=100
            else:
                self.files[path]=bytes(self.u.mem_read(args[2],3712));result=3712
        elif name=='close':self.handles.pop(args[2])
        elif name=='flush':assert args[2:4]==[1,0xffffffff]
        self.return_(result)
    def call(self,name,args):
        self.u.reg_write(p.UC_PPC_REG_1,0x1201f000);self.u.reg_write(p.UC_PPC_REG_LR,STOP)
        preserved={i:0xabc00000+i for i in range(14,32)}
        for i,v in preserved.items():self.u.reg_write(getattr(p,f'UC_PPC_REG_{i}'),v)
        for i,v in enumerate(args,3):self.u.reg_write(getattr(p,f'UC_PPC_REG_{i}'),v)
        self.u.emu_start(SYMS[name]+self.rebase,STOP,count=3000000)
        assert self.u.reg_read(p.UC_PPC_REG_PC)==STOP,(name,'instruction budget')
        for i,v in preserved.items():assert self.reg(i)==v,(name,'clobbered nonvolatile register',i)
        return self.reg(3)
    def local(self,name):return LOC['adapter:'+name]+self.rebase
    def state(self):return LOBBY+0x6f10
    def enter(self):
        s=self.state();self.half(s+6,6);self.half(s+8,0);self.half(s+10,1);self.half(s+12,6)
        self.result=0;self.call('box_step',[LOBBY]);assert self.half(s+12)==7
    def choose(self,slot):
        current=self.number(self.local('selected'));steps=(slot-current)%20
        self.result=0;self.directions=8
        for i in range(steps):self.call('box_step',[LOBBY])
        self.directions=0
        assert self.number(self.local('selected'))==slot
    def action(self,row):
        self.half(self.state()+8,row);self.result=1
        assert self.call('box_step',[LOBBY])==0
        self.result=0
    def message(self):return self.cstring(self.number(self.local('message')))
    def inventory(self,gunner,values):
        n=32 if gunner else 24;address=HUNTER+(0x108 if gunner else 0xa8)
        self.u.mem_write(address,b''.join(struct.pack('>HH',*x) for x in (values+[(0,0)]*(n-len(values)))))
    def slots(self,gunner):
        a=HUNTER+(0x108 if gunner else 0xa8)
        return [struct.unpack('>HH',self.u.mem_read(a+4*i,4)) for i in range(32 if gunner else 24)]
    def snapshot(self):return bytes(self.u.mem_read(HUNTER+0xa8,0x188-0xa8+4000))
