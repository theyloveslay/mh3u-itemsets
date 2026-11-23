"""Read MT Framework 3DS ARC v16 resources from user-owned files."""
from pathlib import Path
import hashlib,json,struct,sys,zlib

def read_arc(path):
 blob=Path(path).read_bytes();magic,version,count=struct.unpack_from('<4sHH',blob)
 assert magic==b'ARC\0' and version==16
 rows=[]
 for i in range(count):
  at=12+80*i;raw=blob[at:at+64];name=raw.split(b'\0')[0].decode('utf8')
  typ,compressed,flags_size,start=struct.unpack_from('<4I',blob,at+64)
  data=zlib.decompress(blob[start:start+compressed]);assert len(data)==flags_size&0x3fffffff
  rows.append((name,typ,data))
 return rows

def replace_resources(path,replacements):
 """Rebuild only when explicitly requested; retain resource order and flags."""
 blob=Path(path).read_bytes();rows=read_arc(path);found=set();directory=bytearray(blob[:12+80*len(rows)])
 payload=bytearray();start=len(directory)
 for i,(name,typ,data) in enumerate(rows):
  key=(name,typ);at=12+80*i
  compressed,flags,old_start=struct.unpack_from('<3I',blob,at+68)
  if key in replacements:
   data=replacements[key];packed=zlib.compress(data,9);found.add(key)
  else:packed=blob[old_start:old_start+compressed]
  struct.pack_into('<3I',directory,at+68,len(packed),(flags&0xc0000000)|len(data),start+len(payload))
  payload.extend(packed)
 if found!=set(replacements):raise ValueError('Replacement resource missing')
 return bytes(directory+payload)

def main():
 path,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True);rows=[]
 for name,typ,data in read_arc(path):
  parts=name.replace('\\','/').split('/');assert '..' not in parts
  ext={b'GMD\0':'.gmd',b'GUI\0':'.gui',b'TEX\0':'.tex',b'XFS\0':'.xfs'}.get(data[:4],f'.{typ:08x}.bin')
  p=out/('/'.join(parts)+ext);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  rows.append({'path':name,'type':hex(typ),'size':len(data),'magic':data[:4].hex(),'sha256':hashlib.sha256(data).hexdigest()})
 (out/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n');print(path.name,len(rows),'resources')
if __name__=='__main__':main()
