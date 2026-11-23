"""End-to-end file preparation and preservation/refusal tests; no emulator I/O."""
from pathlib import Path
import hashlib,json,sys,tempfile,os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from installer import prepare
from tools.inspect_inputs import apply_bps
from tools.bps import aligned_delta
code,current,header,lobby=map(Path,sys.argv[1:5])
patches=ROOT/os.environ.get('MH3U_INSTALLED_BUILD_DIR','install-build')
source=code.read_bytes();baseline=apply_bps(source,current.read_bytes())
manifest=json.loads((patches/'manifest.json').read_text())
with tempfile.TemporaryDirectory() as td:
 td=Path(td);out=td/'ready'
 result=prepare(code,current,header,lobby,out,patches)
 title=out/manifest['title_id']
 target=apply_bps(source,(title/'code.bps').read_bytes())
 assert hashlib.sha256(target).hexdigest()==manifest['target_sha256']
 assert (title/'romfs/arc/ID/ID_lb_eng.arc').read_bytes()==apply_bps(lobby.read_bytes(),(patches/'ID_lb_eng.arc.bps').read_bytes())
 assert (title/'exheader.bin').read_bytes()==apply_bps(header.read_bytes(),(patches/'exheader.bps').read_bytes())
 try:prepare(code,current,header,lobby,out,patches)
 except ValueError:pass
 else:raise AssertionError('Existing folder overwritten')
 extra=bytearray(baseline);extra[0x12340]^=1
 custom=td/'custom.bps';custom.write_bytes(aligned_delta(source,extra))
 prepare(code,custom,header,lobby,td/'merged',patches)
 merged=apply_bps(source,(td/'merged'/manifest['title_id']/'code.bps').read_bytes())
 assert merged[0x12340]==extra[0x12340]
 hook=0x5e8d30-0x100000
 extra[hook:hook+4]=b'\0\0\0\0';custom.write_bytes(aligned_delta(source,extra))
 for label,candidate in [('conflict',custom),('bad-crc',td/'bad.bps')]:
  if label=='bad-crc':candidate.write_bytes(current.read_bytes()[:-1]+bytes([current.read_bytes()[-1]^1]))
  dest=td/label
  try:prepare(code,candidate,header,lobby,dest,patches)
  except (ValueError,AssertionError):pass
  else:raise AssertionError(label+' accepted')
  assert not dest.exists()
report={'status':'passed','checks':['Complete preparation matches built code, metadata and ARC deltas','Existing output refused','Unrelated existing code edit preserved','Conflicting hook and bad CRC refused before output creation'],'live_tested':False}
(ROOT/'build/installer-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
