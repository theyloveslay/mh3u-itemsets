"""Validate region filtering and exact regional payloads in one pack."""
from pathlib import Path
import re,json,subprocess,sys,tempfile,shutil
ROOT=Path(__file__).resolve().parents[1]
pack=ROOT/'graphicPacks/MH3U_ItemSets_US_EU_v32'
text=(pack/'patch_loadouts.asm').read_text()
groups=re.findall(r'(\[.*?\]\nmoduleMatches = 0x([0-9A-F]+)\n.*?)(?=\n\[|\Z)',text,re.S)
assert len(groups)==2
all_labels=re.findall(r'^(_mhl_\w+):',text,re.M);assert len(all_labels)==len(set(all_labels))
for region,crc,build in [('US',0x9d2f15e5,'build'),('EU',0xada406e7,'build-eu')]:
 selected=[g for g,c in groups if int(c,16)==crc];assert len(selected)==1
 expected=(ROOT/f'graphicPacks/MH3U_ItemLoadouts_{region}_v32/patch_loadouts.asm').read_text()
 assert selected[0].strip()==expected.replace('_mhl_',f'_mhl_{region.lower()}_').strip()
 # Existing assembler-directive test validates bytes and hooks at three bases.
 with tempfile.TemporaryDirectory() as tmp:
  work=Path(tmp);(work/'tests').mkdir();shutil.copytree(ROOT/build,work/'build',ignore=shutil.ignore_patterns('test-workspace','generated'))
  dest=work/'graphicPacks/MH3U_ItemLoadouts_US_v32';dest.mkdir(parents=True)
  (dest/'patch_loadouts.asm').write_text(selected[0])
  shutil.copy(ROOT/'tests/test_pack.py',work/'tests/test_pack.py')
  subprocess.run([sys.executable,str(work/'tests/test_pack.py')],check=True,stdout=subprocess.DEVNULL)
assert not [g for g,c in groups if int(c,16)==0x12345678]
rules=(pack/'rules.txt').read_text();assert '0005000010118300,0005000010117200' in rules
assert rules.count('[Definition]')==1
assert not (pack/'content').exists(), 'Obsolete custom banner archive retained'
result={'status':'passed','checks':['One graphics-pack entry contains both title IDs','Two checksum-selected patch groups; unknown modules select neither','All regional labels unique','Both group payloads and seven hooks exactly match regional builds at three cave bases'],'limitations':['Cemu parser/game launch not executed']}
(ROOT/'build/combined-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
