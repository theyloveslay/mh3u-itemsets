"""Check EU v32 mapping against user-provided US and EU RPX executables.

No proprietary code is embedded. Reports contain addresses and hashes only.
"""
from pathlib import Path
import argparse,hashlib,json,re,struct,zlib
from inspect_rpx import sections
ROOT=Path(__file__).resolve().parents[1]
def module_crc(path):
    blob=Path(path).read_bytes();offset=struct.unpack_from('>I',blob,32)[0]
    stride,count,names=struct.unpack_from('>HHH',blob,46)
    headers=[struct.unpack_from('>10I',blob,offset+i*stride) for i in range(count)]
    sym=next(i for i,h in enumerate(headers) if h[1]==2)
    strings=next(i for i,h in enumerate(headers) if h[1]==3 and i!=names)
    crc=zlib.crc32(b'\x7fRPX');crc=zlib.crc32(struct.pack('<4i',count,sym,strings,names),crc)
    for name,typ,flags,address,pos,size,link,info,align,entsize in headers:
        data=b'' if typ==8 else blob[pos:pos+size]
        if flags&0x08000000:data=zlib.decompress(data[4:])
        crc=zlib.crc32(struct.pack('<6I',name,typ,flags,address,size if typ==8 else len(data),align),crc)
        if data:crc=zlib.crc32(data,crc)
    return crc
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--us-rpx',required=True);parser.add_argument('--eu-rpx',required=True)
    args=parser.parse_args();us=sections(args.us_rpx);eu=sections(args.eu_rpx)
    config=json.loads((ROOT/'regions/EU_v32.json').read_text())
    mapping={int(k,16):v for k,v in config['code_map'].items()}
    assert module_crc(args.us_rpx)==0x9d2f15e5
    assert module_crc(args.eu_rpx)==config['module_crc']
    assert hashlib.sha256(Path(args.eu_rpx).read_bytes()).hexdigest()==config['source_rpx_sha256']
    def data(ss,a,n):
        s=next(s for s in ss if s['addr']<=a<s['addr']+len(s['data']) and s['name'] in ['.text','.data','.rodata'])
        return s['data'][a-s['addr']:a-s['addr']+n]
    # Differences in these windows are region relocations: two keyboard float
    # constants, a switch-table code pointer and three native code references.
    # The newly audited text-index helper embeds its own regional switch
    # dispatch address in an addic low-half immediate at US 0213DB5C.
    exceptions={0x0213db5c:-0x88,0x0211b990:4,0x0211b99c:4,0x0265f0cc:-0x88,
                0x02bdbf24:-0x88,0x02bdbf4c:-0x88,0x02adf6e8:-0x88}
    exact=branches=relocated=0
    for source,target in mapping.items():
        a=data(us,source,256);b=data(eu,target,256)
        for off in range(0,256,4):
            x=int.from_bytes(a[off:off+4],'big');y=int.from_bytes(b[off:off+4],'big')
            if x==y:exact+=1;continue
            if x>>26==18 and y>>26==18:
                def branch(word,pc):
                    d=word&0x03fffffc;d=d-(1<<26) if d&(1<<25) else d
                    return (d if word&2 else pc+d)&0xffffffff
                p=branch(x,source+off);q=branch(y,target+off)
                assert x&3==y&3
                if p in mapping:assert q==mapping[p]
                else:assert q-p in (0,4,-0x8c,-0x88),(hex(source+off),hex(p),hex(q))
                branches+=1;continue
            assert source+off in exceptions,(hex(source+off),hex(x),hex(y))
            assert x>>16==y>>16 and ((y-x)&65535)==(exceptions[source+off]&65535)
            relocated+=1
    manifest=json.loads((ROOT/'build-eu/mod-manifest.json').read_text())
    hooks=[]
    for address,name in manifest['hooks'].items():
        target=int(address,16);source=next(a for a,b in mapping.items() if b==target)
        assert data(us,source,4)==data(eu,target,4)
        hooks.append({'name':name,'us':hex(source),'eu':hex(target)})
    for address,size in [(0x1005f6e4,16),(0x10170f30,48),(0x1005c520,24)]:
        assert data(us,address,size)==data(eu,address,size)
    for name in ['.rodata','.data','.bss']:
        a=next(s for s in us if s['name']==name);b=next(s for s in eu if s['name']==name)
        assert a['addr']==b['addr'] and len(a['data'])==len(b['data'])
    # This native accessor explicitly selects the blade/gunner pouch offsets.
    assert data(us,0x02199eac,0x54)==data(eu,0x02199e24,0x54)
    result={'status':'passed','eu_module_crc':f"0x{config['module_crc']:08X}",
            'eu_rpx_sha256':config['source_rpx_sha256'],'mapped_code_sites':len(mapping),
            'compared_instruction_windows':{'exact':exact,'branches':branches,'explicit_relocations':relocated},
            'hooks':hooks,'checks':['Cemu checksum algorithm reproduced and checked against known US checksum',
            'Seven displaced hook instructions match','Region-addressed native code windows match with known relocations',
            'Native pouch-offset accessor identical','Menu row IDs, option tables and float geometry identical',
            'Data and BSS section placement unchanged'],
            'limitations':['No Cemu launch or EU save load performed','Code-window comparisons do not prove every game function identical']}
    (ROOT/'build-eu/region-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
