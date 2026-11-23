"""Execute ARM SD transport, including real SVC instructions, against fake FS.
The kernel/service side is simulated; no claim of live 3DS SD access.
"""
from pathlib import Path
import importlib.util,json,re,struct
from unicorn import UC_HOOK_INTR,arm_const as a
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transaction',ROOT/'tests/test_transaction.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
arm=m.ARM();u=arm.u
STORE,IO,SESSION,POUCH,TLS=0x11000000,0x11002000,0x11002100,0x11003000,0x11008000
CMD=TLS+0x80
u.reg_write(a.UC_ARM_REG_C13_C0_3,TLS)
files={};handles={};events=[];next_handle=0x200;fault=None
baseline=bytes((i*17+3)%256 for i in range(256));u.mem_write(CMD,baseline)
def reg(i):return u.reg_read(getattr(a,f'UC_ARM_REG_R{i}'))
def cstring(address):
 b=bytearray()
 for i in range(200):
  v=u.mem_read(address+i,1)[0]
  if not v:return b.decode()
  b.append(v)
 raise AssertionError('No terminator')
def interrupt(uc,number,data):
 global next_handle
 pc=u.reg_read(a.UC_ARM_REG_PC);instruction=struct.unpack('<I',u.mem_read(pc-4,4))[0];svc=instruction&0xffffff
 result=0
 if svc==0x2d:
  assert cstring(reg(1))=='srv:';handles[0x100]='srv';u.reg_write(a.UC_ARM_REG_R1,0x100)
 elif svc==0x23:
  assert reg(0) in handles;del handles[reg(0)]
 elif svc==0x32:
  handle=reg(0);assert handle in handles
  c=list(struct.unpack('<64I',u.mem_read(CMD,256)));command=c[0];kind=handles[handle];response=[0]*64
  events.append((kind if isinstance(kind,str) else 'file',hex(command)))
  if kind=='srv':
   if command==0x10002:assert c[1:3]==[0x20,0]
   elif command==0x50100:
    assert struct.pack('<2I',*c[1:3])==b'fs:USER\0' and c[3:5]==[7,0]
    handles[0x101]='fs';response[3]=0x101
   else:raise AssertionError(hex(command))
  elif kind=='fs':
   if command==0x8010002:assert c[1:3]==[0x20,0]
   elif command==0x8030204:
    assert c[1:6]==[0,9,1,1,3]
    assert c[9]==(1<<14)|(2<<10)|2 and bytes(u.mem_read(c[10],1))==b'\0'
    path=cstring(c[12]);assert re.fullmatch(r'/mh3u_loadouts_user[123]_[ab]\.bin',path) or path=='/mh3u_itemsets_layout.bin'
    assert c[6]==len(path)+1 and c[11]==((len(path)+1)<<14)|2 and c[8]==0
    if fault=='permission':response[1]=0xd9004676
    elif c[7]==1 and path not in files:response[1]=0xc8804478
    else:
     assert c[7] in [1,6]
     if c[7]==6:files.setdefault(path,b'')
     handles[next_handle]=(path,c[7]);response[3]=next_handle;next_handle+=1
   else:raise AssertionError(hex(command))
  else:
   path,flags=kind
   if command==0x8040000:response[2]=len(files[path]);response[3]=0
   elif command==0x8050080:
    assert flags==6 and (c[1] in [0,3712] or path=='/mh3u_itemsets_layout.bin' and 0<c[1]<=65536) and c[2]==0;files[path]=files[path][:c[1]].ljust(c[1],b'\0')
   elif command==0x80200c2:
    assert flags==1 and c[1:3]==[0,0] and c[4]==(c[3]<<4)|12
    data=files[path][:c[3]];u.mem_write(c[5],data);response[2]=len(data)
   elif command==0x8030102:
    size_requested=c[3]
    assert flags==6 and c[1:3]==[0,0] and c[4]==1 and c[5]==(size_requested<<4)|10
    assert size_requested==3712 or path=='/mh3u_itemsets_layout.bin' and 0<size_requested<=65536
    size=100 if fault=='shortwrite' else size_requested;data=bytes(u.mem_read(c[6],size));files[path]=data+files[path][size:];response[2]=size
   elif command==0x8090000:
    if fault=='flush':response[1]=0xd9004676
   elif command==0x8080000:
    if fault=='close':response[1]=0xd9004676
   else:raise AssertionError(hex(command))
  u.mem_write(CMD,struct.pack('<64I',*response))
 else:raise AssertionError(hex(svc))
 u.reg_write(a.UC_ARM_REG_R0,result)
u.hook_add(UC_HOOK_INTR,interrupt)
def call(name,*args):
 result=arm.call(name,list(args));assert bytes(u.mem_read(CMD,256))==baseline,'Caller TLS command buffer changed';return result
call('sd_bank_io',IO,SESSION)
assert call('store_load',STORE,IO,0)==1
assert handles=={0x101:'fs'},handles
u.mem_write(POUCH,b'\x01\0\0\0'+struct.pack('<HH',41,1)+bytes(124))
assert call('set_register',STORE,IO,0,POUCH)==0
assert call('set_register',STORE,IO,23,POUCH)==0
before=bytes(u.mem_read(STORE,3664))
assert call('store_load',STORE,IO,0)==1 and bytes(u.mem_read(STORE,3664))==before
assert sorted(files)==['/mh3u_loadouts_user1_a.bin','/mh3u_loadouts_user1_b.bin']
assert handles=={0x101:'fs'}

for fault_name in ['shortwrite','flush','close']:
 fault=fault_name;assert call('set_unregister',STORE,IO,0)==3
 assert bytes(u.mem_read(STORE,3664))==before
 assert handles=={0x101:'fs'}
fault=None
# The surviving committed bank must still reload after a partial alternate.
assert call('store_load',STORE,IO,0)==1 and bytes(u.mem_read(STORE,3664))==before
fault='permission';snapshot=dict(files)
assert call('store_load',STORE,IO,2)==0 and files==snapshot
fault=None
files['/mh3u_loadouts_user3_a.bin']=b'bad';files['/mh3u_loadouts_user3_b.bin']=b'bad'
assert call('store_load',STORE,IO,2)==0
# The diagnostic writer is restricted to its own literal path and preserves
# existing bank bytes and TLS, including partial-write/error handling.
prior_banks=dict(files);report_data=bytes((i*31+7)%256 for i in range(8192))
u.mem_write(POUCH+0x1000,report_data)
assert call('sd_write_layout_report',POUCH+0x1000,len(report_data))==1
assert files['/mh3u_itemsets_layout.bin']==report_data
assert all(files[k]==v for k,v in prior_banks.items())
for fault_name in ['permission','shortwrite','flush','close']:
 fault=fault_name;assert call('sd_write_layout_report',POUCH+0x1000,len(report_data))==0
 assert all(files[k]==v for k,v in prior_banks.items())
fault=None
assert call('sd_write_layout_report',POUCH+0x1000,65537)==0
result={'status':'passed','checks':['Actual ARM TLS read and SVC instructions execute','Own srv/fs session initialized; srv and file handles close','SD archive, ASCII file paths and IPC descriptors match reference','Exact length checks, read/write/flush/close handling','Original thread command buffer restored after every operation','End-to-end register and reload through store + SD callbacks','Partial writes and flush/close failures roll back edits','Permission errors and malformed files never become empty writable stores'],'limitations':['Kernel and fs:USER responses are fixtures','Live Azahar/3DS access permissions and SD execution remain unverified']}
(ROOT/'build/sd-io-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
