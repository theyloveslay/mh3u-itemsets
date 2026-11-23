"""Inspect owned US 3DS inputs and existing BPS without distributing game bytes.
Usage: python tools/inspect_inputs.py CODE EXHEADER EXISTING_BPS OUTPUT_JSON
"""
from pathlib import Path
import hashlib,json,struct,sys,zlib

def apply_bps(source,patch):
    assert patch[:4]==b'BPS1'
    assert zlib.crc32(patch[:-4])==struct.unpack_from('<I',patch,len(patch)-4)[0]
    pos=4
    def number():
        nonlocal pos
        value=0;shift=1
        while True:
            byte=patch[pos];pos+=1;value+=(byte&127)*shift
            if byte&128:return value
            shift<<=7;value+=shift
    size=number();target_size=number();metadata=number();pos+=metadata
    assert size==len(source)
    assert zlib.crc32(source)==struct.unpack_from('<I',patch,len(patch)-12)[0]
    out=bytearray();src_rel=tgt_rel=0
    while len(out)<target_size:
        command=number();length=(command>>2)+1;kind=command&3
        if kind==0:out+=source[len(out):len(out)+length]
        elif kind==1:out+=patch[pos:pos+length];pos+=length
        else:
            delta=number();delta=-(delta>>1) if delta&1 else delta>>1
            if kind==2:
                src_rel+=delta;assert src_rel>=0
                out+=source[src_rel:src_rel+length];src_rel+=length
            else:
                tgt_rel+=delta;assert tgt_rel>=0
                for _ in range(length):out.append(out[tgt_rel]);tgt_rel+=1
    assert len(out)==target_size and pos==len(patch)-12
    assert zlib.crc32(out)==struct.unpack_from('<I',patch,len(patch)-8)[0]
    return bytes(out)

def intervals(indices):
    out=[]
    for i in indices:
        if out and i==out[-1][1]:out[-1][1]+=1
        else:out.append([i,i+1])
    return out

def main():
    code_path,ex_path,bps_path,out_path=map(Path,sys.argv[1:]);code=code_path.read_bytes();ex=ex_path.read_bytes();bps=bps_path.read_bytes()
    patched=apply_bps(code,bps)
    changed=intervals(i for i in range(len(code)) if code[i]!=patched[i])
    # Exact changed byte ranges are reported as addresses/sizes only.
    report={'inputs':{p.name:{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (code_path,ex_path,bps_path)},'code_source_crc32':hex(zlib.crc32(code)),'existing_bps_valid':True,'patched_size':len(patched),'patched_sha256':hashlib.sha256(patched).hexdigest(),'existing_patch_changed_ranges':[{'file_start':hex(a),'file_end':hex(b),'size':b-a} for a,b in changed],'existing_patch_appended_bytes':len(patched)-len(code),'exheader_segments':{name:dict(zip(['address','pages','size'],struct.unpack_from('<III',ex,off))) for name,off in [('text',0x10),('rodata',0x20),('data',0x30)]},'exheader_bss_size':struct.unpack_from('<I',ex,0x3c)[0],'limitations':['Native runtime mappings and actual UI/storage integration still require verification']}
    out_path.parent.mkdir(parents=True,exist_ok=True);out_path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
