"""Build a US/EU 3DS/Azahar Item Sets patch from user-owned inputs.

The existing patch is applied first and preserved. No game file is included in
the output: code/ARC/exheader changes are BPS deltas. This does not establish
live-game stability or correct visual placement.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
from elftools.elf.elffile import ELFFile
from build import compile_arm,run,FLAGS,ROOT
sys.path.insert(0,str(ROOT/'tools'))
from inspect_inputs import apply_bps
from prepare_ui_text import prepare
from bps import aligned_delta,arc_delta
from exheader import extend_exheader
CODE_SHA='80db9caa329faacfaa580e435fce99614029a4bc201b5a898f56ff8a9a2b9006'
REGIONS={CODE_SHA:('US','00040000000AE400'),'fb60817c7dbc0c246f14c4525bfc5ff7fc14698b99781e3d9f77fdeec0e83b6d':('EU','00040000000B1D00')}
BASE=0x100000;BOOT=0xaff800
HOOKS={0x5e8d30:('item_ui_box_step','original_box_input'),0x3be3b0:('item_root_draw','original_root_screen'),0x2b24e0:('item_draw_options','original_options'),0x2a2374:('item_character_applied','original_apply_character'),0x3e4a44:('item_animation_step','original_animation'),0x974fc0:('item_menu_draw','original_menu')}
def align(n):return (n+4095)&~4095
def branch(site,target):
 delta=target-site-8
 if delta%4 or not -(1<<25)<=delta<(1<<25):raise ValueError('ARM branch range')
 return 0xea000000|((delta>>2)&0xffffff)
def branch_target(site,word):
 if word>>24!=0xea:raise ValueError('Expected existing ARM entry branch')
 d=((word&0xffffff)^0x800000)-0x800000;return site+8+4*d
def image(path,base):
 with open(path,'rb') as f:
  elf=ELFFile(f);sections=[s for s in elf.iter_sections() if s['sh_flags']&2 and s['sh_size']]
  size=align(max(s['sh_addr']+s['sh_size'] for s in sections)-base);data=bytearray(size)
  for s in sections:
   if s['sh_type']!='SHT_NOBITS':data[s['sh_addr']-base:s['sh_addr']-base+s['sh_size']]=s.data()
  syms={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
 return bytes(data),syms
def make(code_path,patch_path,ex_path,arc_path,destination):
 code=Path(code_path).read_bytes();patch=Path(patch_path).read_bytes() if patch_path else None;ex=bytearray(Path(ex_path).read_bytes())
 source_sha=hashlib.sha256(code).hexdigest()
 if source_sha not in REGIONS:raise ValueError('Unsupported US/EU executable')
 region,title_id=REGIONS[source_sha]
 if len(ex) not in (0x400,0x800) or struct.unpack_from('<Q',ex,0x200)[0]!=int(title_id,16):raise ValueError('Executable/exheader region mismatch')
 target=bytearray(apply_bps(code,patch) if patch else code);out=Path(destination);out.mkdir(parents=True,exist_ok=True)
 if not patch:
  # Materialize the original zero-initialized data BEFORE appending payload.
  # Otherwise injected code would occupy memory belonging to native globals.
  data_address,data_pages,data_size=struct.unpack_from('<III',ex,0x30)
  bss=struct.unpack_from('<I',ex,0x3c)[0]
  if data_address+data_pages*4096!=BASE+len(code):raise ValueError('Unsupported clean data mapping')
  data_extent=align(data_size+bss)
  if data_extent<data_pages*4096:raise ValueError('Invalid clean data extent')
  target+=bytes(data_extent-data_pages*4096)
  struct.pack_into('<II',ex,0x34,data_extent//4096,data_extent)
  struct.pack_into('<I',ex,0x3c,0)
 work=out/'work';work.mkdir(exist_ok=True)
 if len(target)%4096 or len(ex) not in [0x400,0x800]:raise ValueError('Unsupported input layout')
 text_pages,ro_pages,data_pages=[struct.unpack_from('<I',ex,o)[0] for o in [0x14,0x24,0x34]]
 if (text_pages+ro_pages+data_pages)*4096!=len(target) or struct.unpack_from('<I',ex,0x3c)[0]:raise ValueError('Existing exheader does not describe patched code')
 if struct.unpack_from('<I',ex,0x30)[0]+data_pages*4096!=BASE+len(target):raise ValueError('Non-contiguous data mapping')
 entry=struct.unpack_from('<I',target)[0]
 clean_entry=not patch
 if clean_entry:
  if entry>>24!=0xeb:raise ValueError('Expected clean ARM BL entry')
  continuation=branch_target(BASE,entry^0x01000000)
 else:continuation=branch_target(BASE,entry)
 boot_end=BOOT-BASE+256
 if any(target[BOOT-BASE:boot_end]):raise ValueError('Bootstrap cave occupied by another patch')
 for addr in HOOKS:
  if target[addr-BASE:addr-BASE+16]!=code[addr-BASE:addr-BASE+16]:raise ValueError(f'Existing patch conflicts at {addr:08X}')
 asm=['.syntax unified','.arm','.text']
 for addr,(hook,original) in HOOKS.items():
  asm += [f'.global {original}',f'.type {original},%function',f'{original}:']
  for i,w in enumerate(struct.unpack_from('<4I',code,addr-BASE)):
   if w>>24==0xeb:
    # Relocate the native animation prologue's BL. Copying the encoded word
    # would branch relative to the payload instead of the original function.
    d=((w&0xffffff)^0x800000)-0x800000;callee=addr+i*4+8+4*d
    asm += [f'ldr r12, =0x{callee:08x}','blx r12']
   else:asm += [f'.word 0x{w:08x}']
  asm += ['ldr pc,[pc,#-4]',f'.word 0x{addr+16:08x}']
 asm+=['.ltorg']
 trampoline=work/'original.S';trampoline.write_text('\n'.join(asm)+'\n')
 payload_base=BASE+len(target);elf=compile_arm(work,payload_base,trampoline);payload,symbols=image(elf,payload_base)
 target+=payload
 entry_return='ldr lr,=0x100004' if clean_entry else ''
 bootstrap=f'''.syntax unified
.arm
.text
.global _start
_start:
 push {{r0-r12,lr}}
 ldr r1,=0xffff8001
 svc #0x35
 cmp r0,#0
 blt failed
 svc #0x33
 cmp r0,#0
 blt failed
 mov r6,r1
 mov r0,r6
 ldr r1,=0x{payload_base:x}
 mov r2,r1
 ldr r3,=0x{len(payload):x}
 mov r4,#6
 mov r5,#7
 svc #0x70
 mov r7,r0
 mov r0,r6
 svc #0x23
 cmp r7,#0
 blt failed
 pop {{r0-r12,lr}}
 {entry_return}
 ldr pc,=0x{continuation:x}
failed:
 mov r0,#1
 svc #0x3c
 b failed
.ltorg
'''
 boot_source=work/'boot.S';boot_source.write_text(bootstrap)
 run(sys.executable,'-m','ziglang','cc',*FLAGS,'-c',boot_source,'-o',work/'boot.o')
 (work/'boot.ld').write_text(f'ENTRY(_start)\nSECTIONS {{ . = 0x{BOOT:x}; .text : {{ *(.text*) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) }} }}\n')
 run(sys.executable,'-m','ziglang','cc',*FLAGS,'-nostdlib','-Wl,-T,'+str(work/'boot.ld'),work/'boot.o','-o',work/'boot.elf')
 # Read the small bootstrap without page-padding the text cave.
 with open(work/'boot.elf','rb') as f:boot=ELFFile(f).get_section_by_name('.text').data()
 if len(boot)>256:raise ValueError('Bootstrap cave overflow')
 target[BOOT-BASE:BOOT-BASE+len(boot)]=boot;struct.pack_into('<I',target,0,branch(BASE,BOOT))
 for addr,(hook,original) in HOOKS.items():struct.pack_into('<I',target,addr-BASE,branch(addr,symbols[hook]))
 ex=bytearray(extend_exheader(ex,len(payload),payload_base-BASE))
 lobby,bindings=prepare(arc_path)
 outputs={'code.bps':aligned_delta(code,bytes(target)),'exheader.bps':aligned_delta(Path(ex_path).read_bytes(),bytes(ex)),'ID_lb_eng.arc.bps':arc_delta(Path(arc_path).read_bytes(),lobby)}
 for name,data in outputs.items():(out/name).write_bytes(data)
 if patch is not None:(out/'baseline-code.bps').write_bytes(patch)
 assert apply_bps(code,outputs['code.bps'])==target
 assert apply_bps(Path(ex_path).read_bytes(),outputs['exheader.bps'])==ex
 assert apply_bps(Path(arc_path).read_bytes(),outputs['ID_lb_eng.arc.bps'])==lobby
 manifest={'title_id':title_id,'region':region,'experimental':True,'live_tested':False,'source_sha256':source_sha,'existing_patch_sha256':hashlib.sha256(patch).hexdigest() if patch else None,'payload_base':hex(payload_base),'payload_bytes':len(payload),'bootstrap':hex(BOOT),'bootstrap_bytes':len(boot),'existing_entry':hex(continuation),'hooks':{hex(a):{'handler':h,'address':hex(symbols[h]),'original':hex(symbols[o])} for a,(h,o) in HOOKS.items()},'text_bindings':bindings,'target_sha256':hashlib.sha256(target).hexdigest(),'exheader_changes':['Data segment expanded for payload and zero-initialized state','Direct SD read/write and ARM9 SD capability','Required SVCs including OpenProcess'],'outputs':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in outputs.items()},'limitations':['No live Azahar or 3DS test','Native screen placement and popup alignment need visual verification','Character creation path not yet tested','Supplied baseline existing patch may differ from a later combined Raw Unbloat patch']}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['code','exheader','lobby','out']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--existing-bps',type=Path)
 a=p.parse_args();print(json.dumps(make(a.code,a.existing_bps,a.exheader,a.lobby,a.out.resolve()),indent=2))
