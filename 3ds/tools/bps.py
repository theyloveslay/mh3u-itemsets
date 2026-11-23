"""BPS writer for aligned executable deltas and ARC chunk relocation."""
import struct,zlib
def number(value):
 out=bytearray()
 while True:
  byte=value&127;value>>=7
  if not value:out.append(byte|128);return out
  out.append(byte);value-=1
class Writer:
 def __init__(self,source,target):
  self.source,self.target=source,target;self.out=bytearray(b'BPS1')+number(len(source))+number(len(target))+number(0);self.relative=0;self.position=0
 def read(self,length):
  if length:self.out+=number(((length-1)<<2)|0);self.position+=length
 def literal(self,data):
  if data:self.out+=number(((len(data)-1)<<2)|1)+data;self.position+=len(data)
 def copy(self,offset,length):
  if not length:return
  delta=offset-self.relative;self.out+=number(((length-1)<<2)|2)+number((abs(delta)<<1)|int(delta<0));self.relative=offset+length;self.position+=length
 def finish(self):
  if self.position!=len(self.target):raise ValueError('Incomplete BPS target')
  self.out+=struct.pack('<II',zlib.crc32(self.source),zlib.crc32(self.target));self.out+=struct.pack('<I',zlib.crc32(self.out));return bytes(self.out)
def aligned_delta(source,target):
 w=Writer(source,target);i=0;limit=min(len(source),len(target))
 while i<limit:
  start=i
  if source[i]==target[i]:
   while i<limit and source[i]==target[i]:i+=1
   w.read(i-start)
  else:
   i+=1
   while i<limit and source[i]!=target[i]:i+=1
   w.literal(target[start:i])
 w.literal(target[i:]);return w.finish()
def arc_delta(source,target):
 magic,version,count=struct.unpack_from('<4sHH',source)
 if magic!=b'ARC\0' or (magic,version,count)!=struct.unpack_from('<4sHH',target):raise ValueError('ARC layout mismatch')
 w=Writer(source,target);end=12+80*count;w.literal(target[:end])
 for i in range(count):
  at=12+80*i;old_size,old_start=struct.unpack_from('<I4xI',source,at+68);size,start=struct.unpack_from('<I4xI',target,at+68)
  if start!=w.position:raise ValueError('Expected packed target ARC')
  data=target[start:start+size]
  if size==old_size and data==source[old_start:old_start+size]:w.copy(old_start,size)
  else:w.literal(data)
 return w.finish()
