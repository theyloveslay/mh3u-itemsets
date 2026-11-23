"""Check the emitted entry guard with Cafe paired-single FPR semantics.

Unicorn PPC32 does not expose the Gekko second FPR lane. This small evaluator
handles only the save/restore entry stub, and treats its C call as clobbering
both lanes. ps_merge10/lfs semantics follow Cemu's Espresso interpreter.
"""
from pathlib import Path
import json,struct
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/'build/mod-manifest.json').read_text())
image=(ROOT/'build/mod.bin').read_bytes();start=m['symbols']['draw_menu_entry']-m['base']
fpr={i:[1.234567890123+i,float(i)+0.25] for i in range(28,32)}
original={i:list(v) for i,v in fpr.items()};regs={0:0,1:0x10000};lr=0x12345678;memory={};call_seen=False;merges=[]
def integer(at):return struct.unpack('>I',memory[at])[0]
for index in range(80):
    word=struct.unpack_from('>I',image,start+4*index)[0]
    op=word>>26;d=(word>>21)&31;a=(word>>16)&31;b=(word>>11)&31
    immediate=word&65535;immediate=immediate-65536 if immediate&0x8000 else immediate
    if word==0x7c0802a6:regs[0]=lr
    elif word==0x7c0803a6:lr=regs[0]
    elif word==0x4e800020:break
    elif op==36:memory[regs[a]+immediate]=struct.pack('>I',regs[d])
    elif op==37:
        new=regs[a]+immediate;memory[new]=struct.pack('>I',regs[d]);regs[a]=new
    elif op==32:regs[d]=integer(regs[a]+immediate)
    elif op==14:regs[d]=regs[a]+immediate
    elif op==54:memory[regs[a]+immediate]=struct.pack('>d',fpr[d][0])
    elif op==52:memory[regs[a]+immediate]=struct.pack('>f',fpr[d][0])
    elif op==48:
        value=struct.unpack('>f',memory[regs[a]+immediate])[0];fpr[d]=[value,value]
    elif op==50:fpr[d][0]=struct.unpack('>d',memory[regs[a]+immediate])[0]
    elif op==4 and word&0x7ff==0x4a0:
        fpr[d]=[fpr[a][1],fpr[b][0]];merges.append(d)
    elif op==18 and word&1:
        call_seen=True;lr=m['base']+start+4*index+4
        for i in range(28,32):fpr[i]=[-999.0,-123.0]
        regs[0]=0xfeed1234
    else:raise AssertionError(f'Unexpected entry instruction {word:08x}')
else:raise AssertionError('Entry guard did not return')
assert call_seen and sorted(merges)==[28,29,30,31]
assert fpr==original and regs[1]==0x10000 and lr==0x12345678
result={'status':'passed','checks':['f28-f31 primary double values preserved','f28-f31 paired-single second lanes preserved','stack and link register restored'],
        'limitations':['Only entry-stub semantics evaluated; not a Cemu gameplay test']}
(ROOT/'build/abi-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
