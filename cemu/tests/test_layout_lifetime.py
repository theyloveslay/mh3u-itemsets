"""Keep box geometry stable until an explicit page transition, no frame timeout."""
from test_ui import UI
from game_harness import *
def fixture():
 g=UI();g.half(g.state()+12,7)
 inst,root=0x111b0000,0x111b1000
 g.write32(g.maki+0xf4,inst);g.write32(inst+4,428);g.write32(inst+0xfc,root)
 nodes=[0x111b2000+i*0x200 for i in range(5)];g.write32(root+0x68,nodes[0])
 for i,n in enumerate(nodes):
  g.write32(n,0x100a7cb0 if i==4 else 0x100a7f30);g.u.mem_write(n+0x84,struct.pack('>f',100))
  if i<4:g.write32(n+0x6c,nodes[i+1])
 g.call('draw_options',[g.maki,g.state()])
 return g,inst,nodes
def pos(g,nodes):return [struct.unpack('>f',g.u.mem_read(n+0x84,4))[0] for n in nodes]
checks=[]
for option,label in [(6,'Item Sets'),(5,'Equipment Sets')]:
 g,inst,nodes=fixture();assert pos(g,nodes)==[100,154,154,100,154]
 for _ in range(40):g.call('animation_hook',[inst,0x111bf000])
 assert pos(g,nodes)==[100,154,154,100,154]
 g.half(g.state()+6,option);g.half(g.state()+8,0);g.half(g.state()+10,1);g.result=1;g.input();g.result=0
 assert g.get('shift_count')==0 and pos(g,nodes)==[100]*5
 assert g.get('ui_list_open')==int(option==6)
 for _ in range(40):g.call('animation_hook',[inst,0x111bf000])
 assert pos(g,nodes)==[100]*5
 checks.append(label+' transition removes the main-box extension immediately, with no later countdown resize')
g,inst,nodes=fixture();g.result=2;g.input();assert g.get('shift_count')==0 and pos(g,nodes)==[100]*5
checks.append('Closing the box restores geometry before returning to normal gameplay')
result={'status':'passed','checks':['Extended geometry present on first draw and stable beyond 40 animation ticks',*checks], 'limitations':['Compiled PPC state/geometry execution with native UI callbacks simulated; Cemu visual confirmation pending']}
(ROOT/'build/layout-lifetime-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
