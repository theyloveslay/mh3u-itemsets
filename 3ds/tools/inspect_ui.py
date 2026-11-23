"""Validate user-owned MH3U UI archives and export structural metadata only."""
from pathlib import Path
import argparse,hashlib,json
from arc import read_arc
from gmd import Gmd
from xfs15 import Xfs15

def inspect(paths):
 report={'archives':[],'layouts':[],'text_roundtrips':0,'layout_validations':0}
 for path in paths:
  rows=read_arc(path);record={'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'resources':len(rows),'text_resources':0,'layouts':0}
  for name,typ,data in rows:
   if data[:4]==b'GMD\0':
    g=Gmd(data)
    if g.encode()!=data:raise ValueError(f'{name}: roundtrip changed bytes')
    record['text_resources']+=1;report['text_roundtrips']+=1
   elif data[:4]==b'XFS\0':
    x=Xfs15(data);record['layouts']+=1;report['layout_validations']+=1
    if name.endswith(('sta_myset_1_eng','sta_soubi_1_eng','sta_soubi_2_eng')):
     report['layouts'].append({'resource':name,'objects':[{'id':o['identity'],'class':o['class'],'name':o.get('mName'),'position':o.get('mPos'),'visible':o.get('mVisible')} for o in x.objects if 'mName' in o]})
  report['archives'].append(record)
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archives',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 r=inspect(args.archives);args.output.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='layouts'},indent=2))
