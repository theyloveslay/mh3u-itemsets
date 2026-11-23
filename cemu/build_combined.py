"""Build one graphics-pack entry for US v32 and EU v32."""
from pathlib import Path
import argparse,subprocess,sys
ROOT=Path(__file__).resolve().parent
PACK=ROOT/'graphicPacks/MH3U_ItemSets_US_EU_v32'
def main():
 PACK.mkdir(parents=True,exist_ok=True)
 # The native title widget already includes the proper parchment and lettering.
 # Remove obsolete v0.5 asset overrides on rebuild; none are needed now.
 import shutil
 if (PACK/'content').exists():shutil.rmtree(PACK/'content')
 groups=[]
 for region in ['US','EU']:
  subprocess.run([sys.executable,str(ROOT/'build.py'),'--region',region],check=True)
  source=(ROOT/f'graphicPacks/MH3U_ItemLoadouts_{region}_v32/patch_loadouts.asm').read_text()
  groups.append(source.replace('_mhl_',f'_mhl_{region.lower()}_'))
 (PACK/'patch_loadouts.asm').write_text('\n'.join(groups))
 (PACK/'rules.txt').write_text('''[Definition]
titleIds = 0005000010118300,0005000010117200
name = Item Sets (US/EU v32 v0.6.2-test)
path = "Monster Hunter 3 Ultimate/Mods/Item Loadouts"
description = Adds item sets to the game. Supports US v32 and EU v32; JP unsupported.
version = 6
''')
 print('Built combined US/EU graphics pack:',PACK)
if __name__=='__main__':main()
