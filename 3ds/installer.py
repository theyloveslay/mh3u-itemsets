"""Prepare MH3U US/EU Item Sets files in a NEW folder; requires Python 3 only.

Combines the supplied experimental build with the user's existing BPS patch,
rejecting conflicting edits or a different code layout. Inputs are never changed.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
from tools.inspect_inputs import apply_bps
from tools.bps import aligned_delta
from tools.exheader import extend_exheader
ROOT=Path(__file__).resolve().parent
def merge_current(code,baseline,current,mod):
 if len(current)!=len(baseline):raise ValueError('Existing patch changes the code layout; rebuild from source to preserve it')
 target=bytearray(mod);conflicts=[]
 for i,(old,new) in enumerate(zip(baseline,current)):
  if old!=new:
   if target[i]!=old and target[i]!=new:conflicts.append(hex(i+0x100000))
   else:target[i]=new
 if conflicts:raise ValueError('Existing patch conflicts at '+', '.join(conflicts[:8]))
 return bytes(target)
def prepare(code_path,current_path,ex_path,lobby_path,output,patches=None):
 output=Path(output)
 if output.exists():raise ValueError('Choose a new output folder; existing folders are not overwritten')
 patches=Path(patches) if patches else ROOT/'patches'
 info=json.loads((patches/'manifest.json').read_text())
 code=Path(code_path).read_bytes()
 if hashlib.sha256(code).hexdigest()!=info['source_sha256']:raise ValueError('Executable does not match this regional build')
 clean=info.get('existing_patch_sha256') is None
 baseline=code if clean else apply_bps(code,(patches/'baseline-code.bps').read_bytes())
 current=apply_bps(code,Path(current_path).read_bytes()) if current_path else code
 mod=apply_bps(code,(patches/'code.bps').read_bytes())
 merged=merge_current(code,baseline,current,mod)
 ex=apply_bps(Path(ex_path).read_bytes(),(patches/'exheader.bps').read_bytes()) if clean else extend_exheader(Path(ex_path).read_bytes(),len(merged)-len(current),len(current))
 lobby=apply_bps(Path(lobby_path).read_bytes(),(patches/'ID_lb_eng.arc.bps').read_bytes())
 bps=aligned_delta(code,merged)
 if apply_bps(code,bps)!=merged:raise ValueError('Final patch roundtrip failed')
 # All validation happens before any output directory or game file is written.
 title=output/info['title_id'];arc=title/'romfs/arc/ID/ID_lb_eng.arc';arc.parent.mkdir(parents=True)
 (title/'code.bps').write_bytes(bps);(title/'exheader.bin').write_bytes(ex);arc.write_bytes(lobby)
 result={'title_id':info['title_id'],'experimental':True,'live_tested':False,'preserved_existing_patch':hashlib.sha256(Path(current_path).read_bytes()).hexdigest() if current_path else None,'target_code_sha256':hashlib.sha256(merged).hexdigest(),'files':[str(p.relative_to(output)) for p in [title/'code.bps',title/'exheader.bin',arc]]}
 (output/'prepared-build.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['code','exheader','lobby','out']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--existing-bps',type=Path)
 p.add_argument('--patches',type=Path)
 a=p.parse_args()
 try:r=prepare(a.code,a.existing_bps,a.exheader,a.lobby,a.out,a.patches)
 except (ValueError,AssertionError,OSError) as e:p.exit(1,f'Preparation stopped: {e}\n')
 print(json.dumps(r,indent=2));print('Prepared an experimental build; no emulator or SD installation was changed.')
