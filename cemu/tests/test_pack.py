"""Structural validation of the emitted Cemu directives against the test image.
This is a deliberately narrow reader, not a substitute for Cemu's own parser.
"""
from pathlib import Path
import json,re,struct
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/'build/mod-manifest.json').read_text())
path=ROOT/'graphicPacks/MH3U_ItemLoadouts_US_v32/patch_loadouts.asm'
lines=path.read_text().splitlines()
labels={};offset=0;directives=[];hooks=[]
for line in lines:
    if not line or line.startswith(('[' ,'moduleMatches','.origin')):continue
    if ' = b ' in line:hooks.append(line);continue
    if line.endswith(':'):
        assert line[:-1] not in labels
        labels[line[:-1]]=offset;continue
    kind,value=line.split(' ',1);size={'.int':4,'.short':2,'.byte':1}[kind]
    assert offset%size==0,(offset,kind,'Cemu would insert alignment padding')
    directives.append((offset,size,value));offset+=size
assert offset==m['size']
for base in (0x01800000,0x01840000,0x019f0100):
    out=bytearray(offset)
    for at,size,value in directives:
        if value.startswith('0x'):number=int(value,16)
        else:
            label,*suffix=value.split('@');assert label in labels
            number=base+labels[label]
            if suffix:number=number&65535 if suffix[0]=='l' else (number+0x8000)>>16 if suffix[0]=='ha' else number>>16
        out[at:at+size]=(number&((1<<(8*size))-1)).to_bytes(size,'big')
    expected=bytearray((ROOT/'build/mod.bin').read_bytes())
    for r in m['relocations']:
        at=r['offset'];n=base+r['target'];typ=r['type']
        if typ==1:struct.pack_into('>I',expected,at,n)
        elif typ in (4,5,6):struct.pack_into('>H',expected,at,(n if typ==4 else n>>16 if typ==5 else (n+0x8000)>>16)&65535)
    assert out==expected,f'Generated pack differs from tested image at base {base:x}'
    for h in hooks:
        source,target=h.split(' = b ')
        displacement=base+labels[target]-int(source,16)
        assert -(1<<25)<=displacement<(1<<25)
result={'status':'passed','payload_bytes':offset,'absolute_relocations':sum(r['type'] not in (10,11) for r in m['relocations']),
        'checks':['all referenced labels emitted','all data directives aligned','pack bytes equal tested payload at three cave bases',f'all {len(hooks)} hook branches in range'],
        'limitations':['Cemu parser and game launch not executed']}
(ROOT/'build/pack-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
