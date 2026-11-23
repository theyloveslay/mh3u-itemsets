"""Read the optional M3DG runtime UI capture; no game file is required."""
from pathlib import Path
import struct,json,sys
KINDS={1:'menu-state',2:'widget',3:'frame-array',4:'plate-array',5:'font-array',6:'registered-shifts',7:'instance',8:'gui-object',9:'animation-samples',10:'watched-instance',11:'frame-row',12:'plate-row',13:'font-row',0xffffffff:'unreadable'}
def decode(data):
 if len(data)<64:raise ValueError('Short report')
 h=struct.unpack_from('<16I',data)
 if h[0]!=0x4744334d or h[1]!=1 or h[2]!=len(data):raise ValueError('Invalid or incomplete report')
 result={'version':h[1],'bytes':h[2],'build':hex(h[3]),'menu_frames':h[4],'animation_calls':h[5],'scroll_calls':h[6],'divider_calls':h[7],'scroll':hex(h[8]),'divider':hex(h[9]),'shifts_found':h[10],'records':h[11],'invalid_reads':h[12],'truncated_flags':h[13],'animation_sample_count':h[14],'data':[]}
 at=64
 while at<len(data):
  tag,address,aux,size=struct.unpack_from('<4I',data,at);at+=16
  if at+size>len(data) or size%4:raise ValueError('Bad TLV bounds')
  b=data[at:at+size];at+=size
  item={'kind':KINDS.get(tag,str(tag)),'address':hex(address),'aux':aux,'bytes':size}
  if tag in [2,7,8,10,11,12,13]:
   item['fields']={hex(off):hex(struct.unpack_from('<I',b,off)[0]) for off in [0,4,0x10,0x20,0x30,0x40,0x60,0x68,0x70,0x7c,0x80,0x84,0x88,0x98,0x9c,0xa8,0xac,0xbc,0xcc,0xd0,0xf4,0xf8] if off+4<=len(b)}
  elif tag==9:item['samples']=[{'instance':hex(p),'calls':c} for p,c in struct.iter_unpack('<2I',b)]
  else:item['words']=[hex(x[0]) for x in struct.iter_unpack('<I',b)]
  result['data'].append(item)
 if len(result['data'])!=h[11]:raise ValueError('Record count mismatch')
 return result
if __name__=='__main__':print(json.dumps(decode(Path(sys.argv[1]).read_bytes()),indent=2))
