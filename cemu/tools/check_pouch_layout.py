"""Verify an English Wii U pouch layout against the v32 initializer's caches.

US uIDCommonPauch::init 0265E500 (EU 0265E478) directly indexes uGUI+F8
using four 8-entry tables. uGUI::vf24 allocates exactly header+40 pointers
(US 02A72E50..02A72F74). Beyond that count, native startup reads heap data
as a cGUIInstance pointer, before the custom Item Sets renderer is called.
"""
from pathlib import Path
import argparse,json,struct
from inspect_gui import Arc,Gui
CACHES={
 'row':(6,8,9,10,11,12,13,14),
 'row_extra':(45,46,47,48,49,50,51,52),
 'row_selected':(7,31,32,33,34,35,36,37),
 'row_text':(20,21,22,23,24,25,26,27),
}
def check(gui):
 count=gui.w(0x40)
 missing={k:[i for i in v if i>=count] for k,v in CACHES.items()}
 missing={k:v for k,v in missing.items() if v}
 if missing:
  raise ValueError(f'Incompatible v32 pouch UI: only {count} instances; native startup requires index 52 (53 instances minimum). Out-of-bounds caches: {missing}. Supply ID_com_eng.arc from the matching v32 update, not an older/base content archive.')
 expected={3:('menuy_up',0x723d0214)}
 expected.update({45+i:(f'b{i+1}0',0x723d0214) for i in range(8)})
 for index,(name,typ) in expected.items():
  at=gui.w(0xb4)+index*36
  actual_name=gui.string(gui.w(at+20));actual_type=gui.w(at+24)
  if (actual_name,actual_type)!=(name,typ):
   raise ValueError(f'Incompatible v32 instance {index}: expected {name}/{typ:08x}, got {actual_name}/{actual_type:08x}')
 return count

def main():
 p=argparse.ArgumentParser();p.add_argument('arc',type=Path);a=p.parse_args()
 gui=Gui(Arc(a.arc).get('GUI\\lobby\\com_m_menu_n'))
 try:check(gui)
 except ValueError as error:print(error);raise SystemExit(1)
 print('Native v32 pouch instance-cache bounds passed.')
if __name__=='__main__':main()
