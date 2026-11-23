"""Regression: Item Sets rendering must leave the resident modal untouched.
The v0.4 banner path fails this check: it configures/enables a Yes/No dialog.
"""
from test_ui import UI
from game_harness import *
for gunner in [False,True]:
 for action in range(4):
  g=UI();g.register(0,gunner,[(9,10)]);g.enter_action(action)
  sentinel=bytes((i*17+3)&255 for i in range(32))
  g.u.mem_write(g.dialog_state+0x2f0,sentinel)
  g.write32(g.dialog+0x148,0);g.write32(g.dialog+0x14c,0x123400)
  before=bytes(g.u.mem_read(g.dialog_state+0x2f0,32))
  def check():
   g.gui.clear();g.render()
   assert not any(e[0] in ['dialog','dialog_setup','dialog_visible'] for e in g.gui),'Item Sets touched resident Yes/No dialog'
   assert bytes(g.u.mem_read(g.dialog_state+0x2f0,32))==before
   assert g.number(g.dialog+0x148)==0 and g.number(g.dialog+0x14c)==0x123400
   assert g.preview_title not in g.texts,'Item List title replaced'
  check()
  for _ in range(5):g.input(0x200);check()
  g.input(0x10);check();g.input(0x20);check()
  g.input(0x40);check();g.input(0x40);check()
  g.exit_list();check()
# The screenshot's registered-set case, including native rename entry.
g=UI();g.register(0,False,[(9,10)]);g.enter_action(0);g.render()
g.gui.clear();g.input(0x80);g.render()
assert not any(e[0] in ['dialog','dialog_setup','dialog_visible'] for e in g.gui)
result={'status':'passed','checks':['All four lists, both pouch types, preview paging and confirmations leave resident dialog state/style/visibility untouched','No dialog getter/configurator/activation runs while rendering Item Sets','View Mode, keyboard and exit do not touch resident dialog','Item List title is retained'],'limitations':['Native GUI/GPU fixtures; no live Cemu run','Separate pouch banner rendering requires a live Cemu check']}
(ROOT/'build/no-popup-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
