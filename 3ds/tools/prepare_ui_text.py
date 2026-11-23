"""Prepare Item Sets message resources, not a working mod by itself.

Only modifies the supplied lobby archive when an output path is given. Never
overwrites an input. Existing equipment help and equipment labels are retained.
Appended list strings need a future executable hook; they are not activated here.
"""
import argparse,json
from pathlib import Path
from arc import read_arc,replace_resources
from gmd import Gmd

SHOP='GUI\\font\\lobby\\Shop_eng'
HELP='GUI\\font\\lobby\\Help_eng'
def prepare(path):
 rows=read_arc(path);changes={};bindings={}
 for name,typ,data in rows:
  if name not in (SHOP,HELP):continue
  g=Gmd(data);before=list(g.strings)
  if name==SHOP:
   if g.strings[395]!='DUMMY' or g.strings[394]!='Equipment Sets':raise ValueError('Unexpected Shop message layout')
   updates={395:'Item Sets',433:'Current Sets',434:'Register Set',435:'Reorder Sets',436:'Unregister Sets'}
  else:
   if len(g.strings)!=599:raise ValueError('Unexpected Help message count')
   if g.strings[180:183]!=['DUMMY']*3:raise ValueError('Unexpected Help message layout')
   updates={180:g.strings[175].replace('equipment','items'),181:g.strings[176].replace('equipment','item'),182:'Register your item pouch as a new set.',183:g.strings[178].replace('equipment','item'),184:g.strings[179].replace('equipment','item')}
   bindings['list_help_first']=len(g.strings)
   g.strings.extend(s.replace('equipment','item') for s in before[276:284])
   bindings['warning']=len(g.strings);g.strings.append('(Some items were insufficient or missing.)')
   bindings['blade_banner']=len(g.strings);g.strings.append('Item Pouch (Blade)')
   bindings['gunner_banner']=len(g.strings);g.strings.append('Item Pouch (Gunner)')
   # The register action has deliberately shorter, item-specific wording.
   g.strings[bindings['list_help_first']+2]='Register your item pouch as a new set.\r\nSelect a slot to store it in.'
   messages=[
    ('result_loaded','Item set loaded.'),
    ('result_partial','Item set loaded.\r\n(Some items were insufficient or missing.)'),
    ('browse_partial',g.strings[bindings['list_help_first']]+'\r\n(Some items were insufficient or missing.)'),
    ('error_empty','No items are registered in this set.'),
    ('error_wrong_pouch',"Equip this set's weapon type\r\nbefore loading its Item Pouch."),
    ('error_box_full','No room to store leftover items.\r\nNothing changed.'),
    ('error_invalid','The set contains invalid items\r\nor quantities. Nothing changed.'),
    ('result_registered','Item set registered.'),
    ('result_unregistered','Item set unregistered.'),
    ('error_storage','Item set storage is unavailable.\r\nNo items or saved sets were changed.'),
    ('error_save','Could not save the change.\r\nThe previous registration was kept.'),
    ('error_keyboard','The keyboard is unavailable.'),
   ]
   for label,text in messages:bindings[label]=len(g.strings);g.strings.append(text)
  for index,text in updates.items():g.strings[index]=text
  encoded=g.encode();check=Gmd(encoded)
  for index,text in enumerate(before):
   if index not in updates and check.strings[index]!=text:raise ValueError('Unrelated message changed')
  changes[name,typ]=encoded
 if len(changes)!=2:raise ValueError('Missing message resources')
 bindings.update({'main_label':395,'submenu_first':433,'main_help_first':180})
 return replace_resources(path,changes),bindings

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path);p.add_argument('--bindings',type=Path,required=True);a=p.parse_args()
 if a.archive.resolve()==a.output.resolve():raise ValueError('Refusing to overwrite input')
 data,bindings=prepare(a.archive);a.output.write_bytes(data);a.bindings.write_text(json.dumps(bindings,indent=2)+'\n')
 print('Prepared text assets only; executable/menu hooks are not installed.')
