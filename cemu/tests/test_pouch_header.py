"""Compiled controller selects stock title widget and leaves its artwork alone."""
from test_ui import UI
from game_harness import *
TITLE=0x111a0000
for gunner in [False,True]:
 for action in range(4):
  g=UI();g.register(0,gunner,[(9,10)]);g.enter_action(action)
  g.write32(0x11150000+0x350,TITLE);g.write32(TITLE,0x10069958)
  def draw():
   g.gui.clear();g.render();events=[e for e in g.gui if e[0]=='pouch_title']
   assert len(events)==1 and events[0][1]==TITLE
   assert g.title_pouch==int(gunner)
   assert g.preview_title not in g.texts
   assert not any(e[0].startswith('dialog') for e in g.gui)
  draw();g.input(0x200);draw()
  g.gui.clear();g.input(0x40);g.render();assert not any(e[0]=='pouch_title' for e in g.gui)
  g.input(0x40);draw()
  if action==0:
   g.gui.clear();g.input(0x80);g.render();assert not any(e[0]=='pouch_title' for e in g.gui)
   g.keyboard_ready=True;g.input();g.input(0x20)
  g.gui.clear();g.exit_list();g.render();assert not any(e[0]=='pouch_title' for e in g.gui)
# Absent or wrong widget must never be passed to the native title routine.
g=UI();g.register(0,False,[(9,10)]);g.enter_action(0)
for pointer,typ in [(0,0),(TITLE,0x100554ac)]:
 g.write32(0x11150000+0x350,pointer)
 if pointer:g.write32(pointer,typ)
 g.gui.clear();g.render();assert not any(e[0]=='pouch_title' for e in g.gui)
result={'status':'passed','checks':['Stock root+350 title widget used for all four lists and both pouches','Paging retains native Blade/Gunner selection','View Mode, keyboard and exit do not draw the title','Wrong widget type fails closed','No title-font setter, Item List replacement or dialog configuration'], 'limitations':['Compiled controller callbacks simulated; native helper tested separately; no live Cemu render']}
(ROOT/'build/pouch-header-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
