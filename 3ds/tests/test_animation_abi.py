"""Reproduce the real ARM11 crash and compare fixed hooks with stock code.
Executes the actual 0x292418 transform, including the faulting VLDM at 29243C.
No native transform or GUI-method callback is mocked in this test.
"""
from pathlib import Path
import sys,struct,json,os
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,arm_const as a,UcError
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from inspect_inputs import apply_bps
source=Path(sys.argv[1]).read_bytes()
old_directory=os.environ.get('MH3U_OLD_DIAGNOSTIC_BUILD_DIR')
old=apply_bps(source,(ROOT/old_directory/'code.bps').read_bytes()) if old_directory else None
fixed=apply_bps(source,(ROOT/os.environ.get('MH3U_INSTALLED_BUILD_DIR','install-build')/'code.bps').read_bytes())
INST,PARENT,VIEW,STACK,STOP=0x2500000,0x2510000,0x2520000,0x2ffe000,0x2fff000
R=lambda i:getattr(a,f'UC_ARM_REG_R{i}')
D=lambda i:getattr(a,f'UC_ARM_REG_D{i}')
def engine(image):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x100000,0xd00000);u.mem_write(0x100000,image)
 u.mem_map(0x2000000,0x600000);u.mem_map(0x2f00000,0x100000)
 u.reg_write(a.UC_ARM_REG_C1_C0_2,0xf<<20);u.reg_write(a.UC_ARM_REG_FPEXC,0x40000000)
 return u
def call(u,address,args):
 u.reg_write(a.UC_ARM_REG_SP,STACK);u.reg_write(a.UC_ARM_REG_LR,STOP)
 gp={i:0x98760000+i for i in range(4,12)};fp={i:0x3ff0000000000000+i for i in range(8,16)}
 for i,v in gp.items():u.reg_write(R(i),v)
 for i,v in fp.items():u.reg_write(D(i),v)
 for i,v in enumerate(args):u.reg_write(R(i),v)
 u.emu_start(address,STOP,count=2000000)
 assert u.reg_read(a.UC_ARM_REG_PC)==STOP
 assert u.reg_read(a.UC_ARM_REG_SP)==STACK
 assert all(u.reg_read(R(i))==v for i,v in gp.items())
 assert all(u.reg_read(D(i))==v for i,v in fp.items())
def setup(u,width,height,offset):
 u.mem_write(INST,bytes(0x120));call(u,0x293b2c,[INST])
 flags=struct.unpack('<I',u.mem_read(INST+0x70,4))[0];u.mem_write(INST+0x70,struct.pack('<I',flags|0x10000))
 u.mem_write(INST+0xa8,struct.pack('<2f',5+offset,7+offset))
 matrix=[float(i%5==0) for i in range(16)];matrix[12]=float(offset)
 u.mem_write(PARENT,struct.pack('<16f',*matrix));u.mem_write(VIEW,struct.pack('<2i',width,height))
crash=None
if old is not None:
 # The previously shipped diagnostic reproduces the supplied screen exactly.
 u=engine(old);setup(u,400,240,0)
 try:call(u,0x3e4a44,[INST,PARENT,VIEW,0x12345678])
 except UcError:
  crash={'pc':hex(u.reg_read(a.UC_ARM_REG_PC)),'r2':hex(u.reg_read(R(2))),'lr':hex(u.reg_read(a.UC_ARM_REG_LR))}
  assert crash['pc']=='0x29243c' and crash['r2']=='0x1',crash
 else:raise AssertionError('Old hardware fault not reproduced')
stock=engine(source);patched=engine(fixed);entries=[];dirty=[]
def trace(uc,address,size,data):
 if address==0x292418:entries.append(tuple(uc.reg_read(R(i)) for i in range(4)))
 elif address==0x29243c:dirty.append(uc.reg_read(R(2)))
patched.hook_add(UC_HOOK_CODE,trace)
cases=[(400,240,0),(320,240,1),(800,480,2)]
for width,height,offset in cases:
 setup(stock,width,height,offset);setup(patched,width,height,offset)
 args=[INST,PARENT,VIEW,0x12345678+offset]
 call(stock,0x3e4a44,args);call(patched,0x3e4a44,args)
 assert entries[-1]==tuple(args),entries[-1]
 assert dirty[-1]==VIEW
 assert bytes(stock.mem_read(INST,0x120))==bytes(patched.mem_read(INST,0x120)),'Native transform differs'
report={'status':'passed','old_diagnostic_fault':crash,'fixed_cases':len(cases),'checks':(['Old diagnostic reproduces PC 29243C / R2=1'] if old is not None else [])+['All four incoming argument registers reach native base transform unchanged','Faulting VFP load executes against the real aligned viewport pair','Actual native transform results byte-match unpatched game','Stack, nonvolatile GPRs and VFP d8-d15 preserved'],'limitations':['This verifies the specific animation ABI/crash; live layout and SD capture remain unverified']}
(ROOT/'build/animation-abi-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
