"""Compile MH3U ARM11 payloads; default output is an execution-test ELF."""
from pathlib import Path
import subprocess,sys,json,hashlib,os
ROOT=Path(__file__).resolve().parent
BUILD=ROOT/'build'
FLAGS=['-target','arm-freestanding-eabi','-mcpu=mpcore','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-O2']
if os.environ.get('MH3U_LAYOUT_DIAGNOSTICS')=='1':FLAGS+=['-DMHL_LAYOUT_DIAGNOSTICS=1']
SOURCES=['loadouts','memory','arm_memory','native_original','box_probe','native_inventory','native_rename','native_draw','native_layout','layout_diagnostics','item_ui','bank','store','set_service','sd_io']
def run(*args):subprocess.run(list(map(str,args)),cwd=ROOT,check=True)
def compile_arm(destination,base,original_asm=None):
 destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
 link=destination/'link.ld'
 link.write_text(f'ENTRY(plan_loadout)\nSECTIONS {{ . = 0x{base:08x}; .text : {{ *(.text*) }} .rodata : {{ *(.rodata*) }} .data : {{ *(.data*) }} .bss : {{ *(.bss*) *(COMMON) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) }} }}\n')
 objects=[]
 for name in SOURCES:
  source=original_asm if name=='native_original' and original_asm else ROOT/'src'/f'{name}.c'
  obj=destination/f'{name}.o';run(sys.executable,'-m','ziglang','cc',*FLAGS,'-c',source,'-o',obj);objects.append(obj)
 obj=destination/'svc.o';run(sys.executable,'-m','ziglang','cc',*FLAGS,'-c',ROOT/'src/svc.S','-o',obj);objects.append(obj)
 elf=destination/'loadouts-arm.elf'
 run(sys.executable,'-m','ziglang','cc',*FLAGS,'-nostdlib','-Wl,--no-gc-sections','-Wl,-e,plan_loadout','-Wl,-T,'+str(link),*objects,'-o',elf)
 return elf

def main():
 elf=compile_arm(BUILD,0x1800000)
 run('gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',ROOT/'src/loadouts.c','-o',BUILD/'loadouts-host.so')
 manifest={'target':'ARM11 MPCore / ARMv6K / little endian','installable':False,'core_source_sha256':hashlib.sha256((ROOT/'src/loadouts.c').read_bytes()).hexdigest(),'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest()}
 (BUILD/'core-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
