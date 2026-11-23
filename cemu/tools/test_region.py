"""Build a region-addressed fixture workspace and run existing PPC tests.

Native helper tests consume the supplied regional RPX. No game bytes are
copied into release artifacts. Usage: python tools/test_region.py --rpx RPX
"""
from pathlib import Path
import argparse,json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--rpx',type=Path,required=True)
args=parser.parse_args();rpx=args.rpx.resolve()
config=json.loads((ROOT/'regions/EU_v32.json').read_text())
mapping={int(k,16):v for k,v in config['code_map'].items()}
build=ROOT/'build-eu';work=build/'test-workspace'
if work.exists():shutil.rmtree(work)
(work/'tests').mkdir(parents=True);(work/'build').mkdir()
for p in (ROOT/'tests').glob('*.py'):
    text=p.read_text()
    text=re.sub(r'0x[0-9a-fA-F]+',lambda m:hex(mapping[int(m[0],16)]) if int(m[0],16) in mapping else m[0],text)
    text=text.replace('MH3U_ItemLoadouts_US_v32','MH3U_ItemLoadouts_EU_v32')
    (work/'tests'/p.name).write_text(text)
for p in build.iterdir():
    if p.is_file() and p.suffix in ('.bin','.json','.so','.elf'):shutil.copy2(p,work/'build'/p.name)
shutil.copytree(ROOT/'graphicPacks/MH3U_ItemLoadouts_EU_v32',work/'graphicPacks/MH3U_ItemLoadouts_EU_v32')
for name in ['test_transaction','test_ui','test_pack','test_cafe_abi','test_startup_guards','test_view_mode','test_list_visibility','test_animation','test_tavern','test_text_entry','test_storage_diagnostics','test_no_popup','test_pouch_header','test_layout_lifetime']:
    command=[sys.executable,str(work/'tests'/f'{name}.py')]
    if name in ['test_view_mode','test_list_visibility','test_animation','test_tavern','test_text_entry']:command += [str(rpx),str(ROOT/'tools')]
    subprocess.run(command,cwd=work,check=True)
for p in (work/'build').glob('*-validation.json'):shutil.copy2(p,build/p.name)
print('Regional compiled tests passed. External GUI/OS callbacks are fixtures; Cemu verification remains required.')
