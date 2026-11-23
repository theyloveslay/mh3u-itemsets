"""Narrow exheader changes for appended code and dedicated SD-sidecar I/O."""
import struct
REQUIRED_SVCS={0x02,0x23,0x2d,0x32,0x33,0x35,0x3c,0x70}
def allow_svcs(ex,base):
 for svc in REQUIRED_SVCS:
  group=svc//24;bit=1<<(svc%24);found=False
  for at in range(base+0x170,base+0x1e0,4):
   w=struct.unpack_from('<I',ex,at)[0]
   if w>>27==0x1e and ((w>>24)&7)==group:
    struct.pack_into('<I',ex,at,w|bit);found=True;break
  if not found:
   for at in range(base+0x170,base+0x1e0,4):
    if struct.unpack_from('<I',ex,at)[0]==0xffffffff:
     struct.pack_into('<I',ex,at,0xf0000000|(group<<24)|bit);found=True;break
   if not found:raise ValueError('No free kernel capability descriptor')
def extend_exheader(original,extra,old_code_bytes):
 ex=bytearray(original)
 if len(ex) not in (0x400,0x800) or extra%4096:raise ValueError('Unsupported exheader size')
 if struct.unpack_from('<Q',ex,0x200)[0] not in (0x00040000000ae400,0x00040000000b1d00):raise ValueError('Exheader is not for MH3U US/EU')
 pages=[struct.unpack_from('<I',ex,o)[0] for o in (0x14,0x24,0x34)]
 if sum(pages)*4096!=old_code_bytes or struct.unpack_from('<I',ex,0x3c)[0]:raise ValueError('Exheader does not describe the existing patched code')
 if struct.unpack_from('<I',ex,0x30)[0]+pages[2]*4096!=0x100000+old_code_bytes:raise ValueError('Data mapping is not contiguous')
 struct.pack_into('<I',ex,0x34,pages[2]+extra//4096)
 struct.pack_into('<I',ex,0x38,struct.unpack_from('<I',ex,0x38)[0]+extra)
 for caps in [0x200]+([0x600] if len(ex)==0x800 else []):
  ex[caps+0x48]|=0x80;ex[caps+0x49]|=0x80;ex[caps+0x1f1]|=2
  allow_svcs(ex,caps)
 return bytes(ex)
