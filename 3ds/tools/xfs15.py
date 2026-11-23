"""Read self-described 3DS XFS v15.1 layouts; reject inconsistent sizes.

This reader is intentionally restricted to the property types observed in the
supplied MH3U UI archives. All offsets and object lengths are checked.
"""
import struct
from pathlib import Path

class Xfs15:
 def __init__(self,data):
  self.data=data;self.at=0;self.objects=[];self.schemas=[]
  magic,major,minor,classes,unused,definitions,bytes_=self.take('4sHH4I')
  if (magic,major,minor)!=(b'XFS\0',15,1):raise ValueError('Unsupported XFS')
  if definitions>128 or 24+bytes_>len(data):raise ValueError('Invalid schema bounds')
  self.at=24;offsets=self.take(f'{definitions}I')
  for offset in offsets:
   self.at=24+offset;dti,count,flags=self.take('IHH');properties=[]
   if count>256:raise ValueError('Invalid property count')
   for index in range(count):
    self.at=24+offset+8+40*index
    name,kind,attr,size=self.take('IBBH')
    saved=self.at;self.at=24+name;label=self.string();self.at=saved
    properties.append((label,kind,attr,size))
   self.schemas.append((dti,properties))
  self.at=24+bytes_;self.root=self.object()
  if self.at!=len(data):raise ValueError('Trailing XFS data')
 def take(self,fmt):
  n=struct.calcsize('<'+fmt)
  if self.at+n>len(self.data):raise ValueError('Truncated XFS')
  values=struct.unpack_from('<'+fmt,self.data,self.at);self.at+=n
  return values
 def string(self):
  end=self.data.index(0,self.at);value=self.data[self.at:end].decode('utf8');self.at=end+1
  return value
 def object(self):
  tag,identity=self.take('HH')
  if (tag,identity)==(0,0):return None
  if not tag&1:raise ValueError('Unsupported object reference')
  index=tag>>1
  if index>=len(self.schemas):raise ValueError('Invalid class index')
  start=self.at;length,=self.take('I');end=start+length
  if end>len(self.data):raise ValueError('Object exceeds file')
  dti,properties=self.schemas[index];result={'class':f'{dti:08x}','identity':identity}
  self.objects.append(result)
  for name,kind,attr,size in properties:
   count,=self.take('I')
   if count>4096:raise ValueError('Invalid value count')
   values=[self.value(kind,size) for _ in range(count)]
   result[name]=values if count!=1 or attr&0x20 else values[0]
  if self.at!=end:raise ValueError(f'Object {identity}: end {self.at:x}, expected {end:x}')
  return result
 def value(self,kind,size):
  if kind in (1,2):return self.object()
  if kind in (14,32):return self.string()
  if kind==128:
   mode,=self.take('B')
   if mode==2:return {'type':self.string(),'path':self.string()}
   if mode in (0,1):return None
   raise ValueError('Unknown resource mode')
  scalars={3:'?',4:'B',5:'H',6:'I',7:'Q',8:'b',9:'h',10:'i',11:'q',12:'f',13:'d'}
  if kind in scalars and struct.calcsize('<'+scalars[kind])==size:return self.take(scalars[kind])[0]
  if kind in (19,20,21,22,64):return list(self.take(f'{size//4}f'))
  if kind==17:return list(self.take('2I'))
  if kind==18:return list(self.take('4I'))
  return self.take(f'{size}s')[0].hex()

if __name__=='__main__':
 import json,sys
 print(json.dumps(Xfs15(Path(sys.argv[1]).read_bytes()).root,indent=2))
