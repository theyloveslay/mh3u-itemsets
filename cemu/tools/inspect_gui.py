"""Read owned Wii U ARC/rGUI resources for native-widget verification."""
from pathlib import Path
import argparse, hashlib, json, struct, zlib
U32=0xffffffff
TEXTURE_SET=0x4f7228fc
FONT=0x2fb82eae
MARKERS=(0x4d480001,0x4d480002,0x4d480003)
NUMERIC=(1,2,7,8,9,10,11,12,13,14,16,19)
def word(b,a):return struct.unpack_from('>I',b,a)[0]
def put(b,a,v):struct.pack_into('>I',b,a,v)
def align(b,n=16):b.extend(bytes((-len(b))%n))
class Arc:
 def __init__(self,path):
  self.b=Path(path).read_bytes();assert self.b[:6]==b'\0CRA\0\x10','Expected Wii U BE ARC v16'
  self.count=struct.unpack_from('>H',self.b,6)[0];self.entries=[]
  for i in range(self.count):
   at=12+i*80;entry=self.b[at:at+80];name=entry[:64].split(b'\0')[0].decode()
   typ,size,flags,start=struct.unpack_from('>4I',entry,64)
   self.entries.append((name,entry,self.b[start:start+size]))
 def get(self,name):
  _,entry,data=next(e for e in self.entries if e[0]==name);raw=zlib.decompress(data)
  assert len(raw)==word(entry,72)>>3
  return raw
 def replace(self,name,raw):
  # Preserve the original directory, entry flags, payload alignment and every
  # unrelated compressed member byte-for-byte. Only offsets/sizes must move.
  start=word(self.entries[0][1],76);out=bytearray(self.b[:start])
  found=False
  for i,(key,entry,data) in enumerate(self.entries):
   at=12+i*80
   if key==name:
    found=True;data=zlib.compress(raw,9);put(out,at+72,(len(raw)<<3)|(word(entry,72)&7))
   put(out,at+68,len(data));put(out,at+76,len(out));out.extend(data)
  assert found
  return bytes(out)
class Gui:
 def __init__(self,b):
  self.b=b;assert b[:8]==bytes.fromhex('004955470002190f');assert word(b,8)==len(b)
 def w(self,a):return word(self.b,a)
 def string(self,off):
  at=self.w(0xf4)+off;return self.b[at:self.b.index(0,at)].decode()
 def obj(self,i):return list(struct.unpack_from('>9I',self.b,self.w(0xa4)+36*i))
 def props(self,i):
  obj=self.obj(i)
  return [list(struct.unpack_from('>4I',self.b,self.w(0xac)+16*(obj[6]+j))) for j in range(obj[1]>>24)]
 def resources(self):
  for i in range(self.w(0x24)):
   a=self.w(0x9c)+24*i
   yield i,self.string(self.w(a+16)),a
 def section(self,p,end):return self.b[self.w(p):self.w(end)]
