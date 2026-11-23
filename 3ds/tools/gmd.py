"""MH3U 3DS GMD v1.2.1 text access. Preserve labels and control sequences."""
import struct
from pathlib import Path

class Gmd:
 def __init__(self, data):
  self.data=data
  h=struct.unpack_from('<4s7I',data)
  if h[:2]!=(b'GMD\0',0x10201):raise ValueError('Unsupported GMD')
  _,_,self.language,labels,count,label_bytes,text_bytes,filename_bytes=h
  self.start=32+filename_bytes+1+labels*8+label_bytes
  if self.start+text_bytes!=len(data):raise ValueError('GMD length mismatch')
  strings=data[self.start:].split(b'\0')
  if len(strings)!=count+1 or strings[-1]:raise ValueError('GMD count mismatch')
  self.strings=[s.decode('utf8') for s in strings[:-1]]
 def encode(self):
  data=b''.join(s.encode('utf8')+b'\0' for s in self.strings)
  header=bytearray(self.data[:self.start])
  struct.pack_into('<I',header,16,len(self.strings))
  struct.pack_into('<I',header,24,len(data))
  return bytes(header)+data

if __name__=='__main__':
 import sys,json
 g=Gmd(Path(sys.argv[1]).read_bytes())
 print(json.dumps(dict(enumerate(g.strings)),ensure_ascii=False,indent=2))
