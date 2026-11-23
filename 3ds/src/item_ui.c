/* 3DS Item Sets controller; installed hooks are assembled by build_install.py. */
#include "item_ui.h"
#include "sd_io.h"
#include "native_original.h"
#define WORD(a) (*(volatile u32 *)(a))
#define HALF(a) (*(volatile u16 *)(a))
extern int probe_box_menu(u8 *);
extern void item_layout_stop(void);
extern int capture_native_pouch(Loadout *);
extern int apply_native_pouch(const Loadout *,u32 *missing);
ItemUI item_ui;
BankStore item_store;
static SdSession sd_session;
static BankIO bank_io;
static u32 bound_character=3;
static u32 pending_character=3,bind_pending;
static ItemFrame frame;
static char empty_names[8][BANK_NAME_BYTES];
static const char *titles[4]={"Current Sets","Register Set","Reorder Sets","Unregister Sets"};
enum { HELP_FIRST=599,LOADED=610,PARTIAL=611,BROWSE_PARTIAL=612,EMPTY=613,
 WRONG_POUCH=614,BOX_FULL=615,INVALID=616,REGISTERED=617,UNREGISTERED=618,
 NO_STORAGE=619,SAVE_FAILED=620,NO_KEYBOARD=621 };
static u32 pressed(u8 *lobby,u32 mask){return ((u32 (*)(void *,u32))0x005ca6d4)(lobby,mask);}
static u32 directions(u8 *lobby){return ((u32 (*)(void *))0x005cff40)(lobby);}
static u32 page_wrap(u32 n,u32 pages){return pages==4?n%4:n%3;}
static void sound(u32 id){u32 handle[2];((void (*)(void *,u32))0x002d44c8)(handle,id);}
static void acknowledge(u32 help){item_ui.phase=UI_ACK;item_ui.help=help;}
static void reset_ui(void){
    u8 *p=(u8 *)&item_ui;for(u32 i=0;i<sizeof(item_ui);++i)p[i]=0;
    item_ui.anchor=0xffffffffu;
}
void item_ui_set_io(const BankIO *io){bank_io=*io;}
void item_ui_bind(u32 character){
    reset_ui();bound_character=character<3?character:3;
    pending_character=bound_character;bind_pending=0;
    if(!bank_io.read)sd_bank_io(&bank_io,&sd_session);
    item_store.ready=0;
    bank_defaults(&item_store.collection,bound_character);
    if(bound_character<3)store_load(&item_store,&bank_io,bound_character);
}
void item_ui_note_character(u32 character){
    pending_character=character<3?character:3;bind_pending=1;reset_ui();
}
int item_character_applied(void *save){
    int result=original_apply_character(save);
    /* Native 0x2A2374 applies the decoded hunter and passes this same slot to
     * its secondary data copier. Keep file I/O out of the load callback. */
    item_ui_note_character(result && save?(WORD((u8 *)save+0x260)&0xff):3);
    return result;
}
void item_ui_open(u32 action){
    if(action>UI_UNREGISTER)return;
    item_ui.open=1;item_ui.action=action;item_ui.phase=UI_BROWSE;
    item_ui.anchor=0xffffffffu;item_ui.choice=item_ui.preview_page=item_ui.missing=0;
    if(!item_store.ready)acknowledge(NO_STORAGE);
}
static void execute(void){
    u32 i=item_ui.selected,action=item_ui.action;int result;
    if(!item_store.ready || bound_character!=item_store.collection.character){acknowledge(NO_STORAGE);return;}
    if(action==UI_CURRENT){
        result=apply_native_pouch(&item_store.collection.sets[i],&item_ui.missing);
        acknowledge(result==L_OK?LOADED:result==L_PARTIAL?PARTIAL:
            result==L_WRONG_POUCH?WRONG_POUCH:result==L_BOX_FULL?BOX_FULL:INVALID);
        sound(result==L_OK || result==L_PARTIAL?5:2);
    }else if(action==UI_REGISTER){
        Loadout pouch;
        if(capture_native_pouch(&pouch)!=L_OK){acknowledge(INVALID);return;}
        result=set_register(&item_store,&bank_io,i,&pouch);
        acknowledge(result==SET_SUCCESS?REGISTERED:SAVE_FAILED);sound(result==SET_SUCCESS?5:2);
    }else{
        result=action==UI_REORDER?set_reorder(&item_store,&bank_io,item_ui.anchor,i):
            set_unregister(&item_store,&bank_io,i);
        item_ui.anchor=0xffffffffu;
        if(result==SET_SUCCESS){item_ui.phase=UI_BROWSE;sound(5);}
        else {acknowledge(SAVE_FAILED);sound(2);}
    }
}
static void list_step(u8 *lobby){
    ItemUI *u=&item_ui;
    if(u->phase==UI_KEYBOARD){
        int status=native_rename_poll(&u->rename);if(!status)return;
        u->phase=UI_BROWSE;
        if(status==1){
            int result=set_rename(&item_store,&bank_io,u->selected,u->rename.text);
            if(result!=SET_SUCCESS)acknowledge(SAVE_FAILED);else sound(5);
        }
        return;
    }
    /* Match the native box's ordinary per-frame model/camera update. */
    ((void (*)(void *))0x005faadc)(lobby);
    u32 pages=item_store.collection.sets[u->selected].gunner?4:3;
    if((u->action==UI_REGISTER && u->phase==UI_CONFIRM) ||
       (u->action==UI_CURRENT && u->phase==UI_ACK && u->missing)){
        Loadout now;if(capture_native_pouch(&now)==L_OK)pages=now.gunner?4:3;
    }
    if(pressed(lobby,0x100)){u->preview_page=page_wrap(u->preview_page+pages-1,pages);sound(6);}
    else if(pressed(lobby,0x200)){u->preview_page=page_wrap(u->preview_page+1,pages);sound(6);}
    if(u->phase==UI_ACK){
        if(pressed(lobby,0x30)){u->phase=UI_BROWSE;sound(1);}return;
    }
    if(u->phase==UI_CONFIRM){
        if(directions(lobby)&15){u->choice^=1;sound(3);}
        if(pressed(lobby,0x20)){u->phase=UI_BROWSE;sound(1);}
        else if(pressed(lobby,0x10)){if(u->choice){u->phase=UI_BROWSE;sound(1);}else execute();}
        return;
    }
    if(pressed(lobby,0x20)){
        if(u->anchor<L_SETS)u->anchor=0xffffffffu;
        else {u->open=0;u->missing=0;}
        sound(1);return;
    }
    u32 old=u->selected,dirs=directions(lobby);
    if(dirs&1)u->selected=u->selected%8?u->selected-1:u->selected+7;
    else if(dirs&2)u->selected=u->selected%8==7?u->selected-7:u->selected+1;
    if(dirs&4)u->selected=(u->selected+16)%24;
    else if(dirs&8)u->selected=(u->selected+8)%24;
    if(old!=u->selected){u->preview_page=u->missing=0;sound(dirs&12?6:3);}
    if(pressed(lobby,0x40)){
        /* Same native camera entry as 0x5E8DD4, also available in the added
         * Tavern screen. The outer lobby owns native exit and rotation. */
        u32 app=WORD(0x00c3b9cc);
        if(app && !(WORD(0x00b916c0)&4)){
            lobby[0x67d3]=1;((void (*)(void *,u32))0x00257440)((void *)app,1);sound(0);
        }
        return;
    }
    if(u->anchor>=L_SETS && item_store.collection.sets[u->selected].valid && pressed(lobby,0x80)){
        if(native_rename_begin(&u->rename,item_store.collection.names[u->selected]))u->phase=UI_KEYBOARD;
        else acknowledge(NO_KEYBOARD);
        return;
    }
    if(!pressed(lobby,0x10))return;
    if(u->action!=UI_REGISTER && !item_store.collection.sets[u->selected].valid &&
       !(u->action==UI_REORDER && u->anchor<L_SETS)){acknowledge(EMPTY);return;}
    if(u->action==UI_REORDER){
        if(u->anchor>=L_SETS){u->anchor=u->selected;sound(0);}
        else if(u->anchor==u->selected){u->anchor=0xffffffffu;sound(1);}
        else execute();
    }else{u->phase=UI_CONFIRM;u->choice=0;sound(0);}
}
int item_ui_box_step(u8 *lobby){
    u8 *s=lobby+0x67d0;
    if(s[2]>1){item_layout_stop();reset_ui();return probe_box_menu(lobby);}
    if(bind_pending)item_ui_bind(pending_character);
    if(item_ui.open){
        if(s[0]!=2 || HALF(s+6)!=(s[2]?3:6)){reset_ui();return probe_box_menu(lobby);}
        if(s[3])return 0;
        list_step(lobby);
        if(!item_ui.open){HALF(s+10)=1;HALF(s+8)=(u16)item_ui.action;}
        return 0;
    }
    int result=probe_box_menu(lobby);
    if(result || s[3] || s[0]!=2)item_layout_stop();
    if(result>=0x100 && result<=0x103){item_ui_open((u32)result-0x100);return 0;}
    return result;
}
const ItemFrame *item_ui_frame(void){
    ItemUI *u=&item_ui;SetCollection *c=&item_store.collection;
    frame.title=titles[u->action];frame.page=u->selected/8+1;frame.selected_row=u->selected%8;
    frame.anchor_row=u->anchor<L_SETS && u->anchor/8==u->selected/8?u->anchor%8:0xffffffffu;
    frame.valid_mask=0;
    for(u32 row=0;row<8;++row){
        u32 i=(u->selected/8)*8+row;
        bank_default_name(empty_names[row],i);
        frame.names[row]=c->sets[i].valid?c->names[i]:empty_names[row];
        if(c->sets[i].valid)frame.valid_mask|=1u<<row;
    }
    Loadout pouch=c->sets[u->selected];
    if((u->action==UI_REGISTER && u->phase==UI_CONFIRM) ||
       (u->action==UI_CURRENT && u->phase==UI_ACK && u->missing))capture_native_pouch(&pouch);
    frame.pouch_gunner=pouch.gunner;frame.pouch_pages=pouch.gunner?4:3;
    frame.pouch_page=page_wrap(u->preview_page,frame.pouch_pages);
    for(u32 i=0;i<32;++i)frame.pouch[i]=pouch.valid?pouch.slots[i]:(Slot){0,0};
    frame.help=u->phase==UI_ACK?u->help:
       u->action==UI_CURRENT && u->phase==UI_BROWSE && u->missing?BROWSE_PARTIAL:
       HELP_FIRST+u->action*2+((u->phase==UI_CONFIRM || u->anchor<L_SETS)?1:0);
    frame.choice=u->phase==UI_CONFIRM?u->choice:0xffffffffu;
    return &frame;
}
