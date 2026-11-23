"""Build a relocatable Cemu code-cave patch and an identical PPC test image.

Dependencies: ziglang, pyelftools. No proprietary game bytes are embedded.
"""
from pathlib import Path
import argparse,hashlib,json,re,struct,subprocess,sys
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

ROOT=Path(__file__).resolve().parent
BUILD=ROOT/'build'
PACK=ROOT/'graphicPacks/MH3U_ItemLoadouts_US_v32'
BASE=0x01800000

def run(args):subprocess.run(args,cwd=ROOT,check=True)
def main():
    global BUILD,PACK
    parser=argparse.ArgumentParser();parser.add_argument('--region',choices=['US','EU'],default='US')
    args=parser.parse_args();region=args.region
    config=json.loads((ROOT/'regions/EU_v32.json').read_text()) if region=='EU' else {}
    mapping={int(k,16):v for k,v in config.get('code_map',{}).items()}
    module_crc=config.get('module_crc',0x9D2F15E5)
    title_id=config.get('title_id','0005000010118300')
    if region=='EU':BUILD=ROOT/'build-eu';PACK=ROOT/'graphicPacks/MH3U_ItemLoadouts_EU_v32'
    BUILD.mkdir(exist_ok=True);PACK.mkdir(parents=True,exist_ok=True)
    flags=['-target','powerpc-freestanding','-mcpu=750','-ffreestanding','-fno-pic','-fno-stack-protector','-fno-builtin','-fomit-frame-pointer','-g0','-O2']
    names=['loadouts','adapter','item_ui','trampolines','memory']
    for name in names:
        source=ROOT/'src'/(name+('.s' if name=='trampolines' else '.c'))
        if region=='EU':
            generated=BUILD/'generated';generated.mkdir(exist_ok=True)
            content=source.read_text()
            if name=='trampolines':
                def trampoline(match):
                    address=(int(match[1],16)<<16)|int(match[2],16)
                    target=mapping[address-4]+4
                    return f'lis 12,0x{target>>16:04x}\n    ori 12,12,0x{target&65535:04x}'
                content=re.sub(r'lis 12,(0x[0-9a-f]+)\n    ori 12,12,(0x[0-9a-f]+)',trampoline,content)
            else:
                content=re.sub(r'0x[0-9a-fA-F]+',lambda m:hex(mapping[int(m[0],16)]) if int(m[0],16) in mapping else m[0],content)
            source=generated/source.name;source.write_text(content)
            (generated/'loadouts.h').write_bytes((ROOT/'src/loadouts.h').read_bytes())
        if name=='trampolines':
            run([sys.executable,'-m','ziglang','cc',*flags,'-c',str(source),'-o',str(BUILD/(name+'.o'))])
        else:
            # The driver defaults this freestanding target to soft-float, even
            # for a 750. Call Clang's bundled frontend explicitly so native
            # float arguments (GUI coordinates) use Cafe's f1 ABI.
            run([sys.executable,'-m','ziglang','-cc1','-triple','powerpc-unknown-unknown-eabi',
                 '-target-cpu','750','-target-feature','+fpu','-target-feature','+hard-float',
                 '-mfloat-abi','hard','-mrelocation-model','static','-mframe-pointer=none',
                 '-ffreestanding','-fno-builtin','-O2','-emit-obj',str(source),'-o',str(BUILD/(name+'.o'))])
    run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'src/loadouts.c'),'-o',str(BUILD/'loadouts-host.so')])
    run([sys.executable,'-m','ziglang','cc','-target','powerpc-freestanding','-nostdlib','-Wl,-T,'+str(ROOT/'link.ld'),str(BUILD/'loadouts.o'),'-o',str(BUILD/'loadouts-ppc.elf')])
    streams=[open(BUILD/(n+'.o'),'rb') for n in names]
    objects=[ELFFile(f) for f in streams]
    placement={};size=0
    for family in ['.text','.rodata','.data','.bss']:
        size=(size+63)&~63 if family!='.text' else size
        for oi,obj in enumerate(objects):
            for si,sec in enumerate(obj.iter_sections()):
                if not (sec.name==family or sec.name.startswith(family+'.')):continue
                alignment=max(1,sec['sh_addralign']);size=(size+alignment-1)&~(alignment-1)
                placement[oi,si]=size;size+=sec['sh_size']
    size=(size+3)&~3
    image=bytearray(size);globals_={};symvalues={}
    for oi,obj in enumerate(objects):
        for si,sec in enumerate(obj.iter_sections()):
            if (oi,si) in placement and sec['sh_type']!='SHT_NOBITS':
                at=placement[oi,si];image[at:at+sec['sh_size']]=sec.data()
        for index,sym in enumerate(obj.get_section_by_name('.symtab').iter_symbols()):
            sec=sym['st_shndx'];value=None
            if isinstance(sec,int) and (oi,sec) in placement:value=placement[oi,sec]+sym['st_value']
            if value is not None:
                symvalues[oi,index]=value
                if sym['st_info']['bind']!='STB_LOCAL' and sym.name:globals_[sym.name]=value
    relocs=[]
    for oi,obj in enumerate(objects):
        for sec in obj.iter_sections():
            if not isinstance(sec,RelocationSection) or (oi,sec['sh_info']) not in placement:continue
            symbols=obj.get_section(sec['sh_link'])
            for r in sec.iter_relocations():
                symbol=symbols.get_symbol(r['r_info_sym'])
                value=symvalues.get((oi,r['r_info_sym']))
                if value is None:
                    if symbol.name not in globals_:raise ValueError('Unresolved '+symbol.name)
                    value=globals_[symbol.name]
                target=value+r['r_addend'];at=placement[oi,sec['sh_info']]+r['r_offset'];typ=r['r_info_type']
                if typ in (10,11):
                    displacement=target-at;bits=25 if typ==10 else 15
                    assert -(1<<bits)<=displacement<(1<<bits) and not displacement%4
                    mask=0x03fffffc if typ==10 else 0xfffc
                    word=struct.unpack_from('>I',image,at)[0]
                    struct.pack_into('>I',image,at,(word&~mask)|(displacement&mask))
                elif typ in (4,5,6):
                    address=BASE+target
                    half=address if typ==4 else address>>16 if typ==5 else (address+0x8000)>>16
                    struct.pack_into('>H',image,at,half&0xffff)
                elif typ==1:struct.pack_into('>I',image,at,BASE+target)
                else:raise ValueError(f'Unsupported allocated relocation {typ}')
                relocs.append({'offset':at,'type':typ,'target':target})
    # Every absolute internal reference is represented symbolically in the pack.
    # Relative branches remain invariant when the whole image is moved.
    symbolic={r['offset']:r for r in relocs if r['type'] not in (10,11)}
    label_offsets=set(globals_.values())|{r['target'] for r in relocs if r['type'] not in (10,11)}
    labels={o:f'_mhl_{o:05x}' for o in label_offsets}
    text=[f'[MH3U_ItemLoadouts_{region}_v32]',f'moduleMatches = 0x{module_crc:08X}','','.origin = codecave','_mhl_base:']
    i=0;emitted=set()
    while i<len(image):
        if i in labels:text.append(labels[i]+':');emitted.add(i)
        if i in symbolic:
            r=symbolic[i];label=labels[r['target']]
            if r['type']==1:text.append('.int '+label);i+=4
            else:
                suffix={4:'@l',5:'@h',6:'@ha'}[r['type']]
                text.append('.short '+label+suffix);i+=2
        elif i+1 in labels or i+1 in symbolic or i%2:
            text.append(f'.byte 0x{image[i]:02X}');i+=1
        elif i+2 in symbolic or i%4 or i+2 in labels or i+3 in labels:
            text.append(f'.short 0x{struct.unpack_from(">H",image,i)[0]:04X}');i+=2
        else:
            text.append(f'.int 0x{struct.unpack_from(">I",image,i)[0]:08X}');i+=4
    if i in labels:text.append(labels[i]+':');emitted.add(i)
    assert emitted==set(labels),'An internal symbolic label was skipped'
    hooks={0x021f0e7c:'box_step',0x02141de0:'text_hook',0x020e62ac:'track_character',
           0x026a6b80:'draw_options',0x02687d38:'draw_menu_entry',0x0270a738:'root_draw',0x02ae1e40:'animation_hook'}
    # Keep the original native UI path until an Item Box session on both regions.
    entries={'text_hook':'text_entry','draw_options':'options_entry','draw_menu_entry':'menu_entry','root_draw':'root_entry','animation_hook':'animation_entry'}
    hooks={mapping.get(a,a):entries.get(name,name) for a,name in hooks.items()}
    for address,name in hooks.items():text.append(f'0x{address:08X} = b {labels[globals_[name]]}')
    (PACK/'patch_loadouts.asm').write_text('\n'.join(text)+'\n')
    display_name='Item Sets (EU v32 storage diagnostic v0.3.7)' if region=='EU' else 'Item Sets (experimental v0.2.12 Linux test)'
    (PACK/'rules.txt').write_text(f'[Definition]\ntitleIds = {title_id}\nname = {display_name}\npath = "Monster Hunter 3 Ultimate/Mods/Item Loadouts"\ndescription = Adds item sets to the game. Verified for US v32, untested on EU and JP.\nversion = 6\n')
    (BUILD/'mod.bin').write_bytes(image)
    manifest={'base':BASE,'size':len(image),'symbols':{k:BASE+v for k,v in globals_.items()},'relocations':relocs,
              'hooks':{hex(k):v for k,v in hooks.items()},'payload_sha256':hashlib.sha256(image).hexdigest()}
    manifest.update(region=region,module_crc=module_crc,title_id=title_id)
    # Include named local state for integration probes, without exposing host addresses.
    locals_={}
    for oi,obj in enumerate(objects):
        for ix,sym in enumerate(obj.get_section_by_name('.symtab').iter_symbols()):
            if sym.name and (oi,ix) in symvalues:locals_[names[oi]+':'+sym.name]=BASE+symvalues[oi,ix]
    manifest['locals']=locals_
    (BUILD/'mod-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for f in streams:f.close()
    print(f'Built {len(image)}-byte relocatable payload, {len(relocs)} relocations, {len(hooks)} hooks')

if __name__=='__main__':main()
