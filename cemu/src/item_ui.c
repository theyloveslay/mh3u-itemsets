#include "loadouts.h"
extern Loadout sets[L_SETS];
extern char set_names[L_SETS][20];
extern void default_name(u32);
extern u32 selected;
extern u32 load_missing_units;
extern const char *message;
extern const char *storage_error(void);
extern int ensure_loaded(void),persist(void);
extern void capture(void);
extern int apply(void);
extern int original_box_step(u8 *);
extern const char *original_text(void *,u32,u32);
extern void original_draw_options(void *,u8 *),original_draw_menu(void *,u8 *);
extern void original_root_draw(void *,u8 *),original_animation(void *,const void *);

#define WORD(a) (*(volatile u32 *)(a))
#define HALF(a) (*(volatile u16 *)(a))
#define P(a) ((void *)(a))
typedef void (*V1)(void *);
typedef void (*V2)(void *,u32);
typedef void (*V3)(void *,void *,u32);
typedef u32 (*Q1)(void *);
typedef u32 (*Q2)(void *,u32);
enum { CURRENT=0,REGISTER=1,REORDER=2,UNREGISTER=3 };
enum { BROWSE=0,CONFIRM=1,ACK=2,KEYBOARD=3 };
/* Match the native Equipment Sets input routine (021FB524). These are
   game action masks, not raw VPAD button bits: View Mode is physical +. */
enum { VIEW_PLUS=0x40,RENAME_Y=0x80 };
u32 ui_list_open,ui_action,ui_phase,ui_main_active,ui_box_enabled,ui_tavern;
u32 ui_anchor=0xffffffffu,ui_choice,ui_preview_page;
static u8 list_state[32],shadow[0xc60];
static char row_names[L_SETS][32];
static char rename_buffer[20];
static Slot preview_slots[32];
/* Lookup interception is stackless assembly. Prepare native-derived wording
   in the ordinary box update, outside the game's text callback. */
u32 ui_text_ready;
const char *ui_text_title="Item Sets";
const char *ui_text_actions[4]={"Current Sets","Register Set","Reorder Sets","Unregister Sets"};
const char *ui_text_main[5],*ui_text_list[8];
static const char *list_help_base[8];
static void prepare_item_text(void),refresh_item_text(void);
static void release_layout(void);
static u8 preview_entries[8*0x18+4];
static u32 displayed_maki,display_root,maki_schedule;
static u32 displayed_preview,preview_root,preview_schedule;
static const u16 order[7]={0,1,2,6,3,4,5};
static const u16 position[7]={0,1,2,4,5,6,3};

/* Tavern uses a three-row item-only box (mode 1). Borrow its fourth row,
   keeping the room-only equipment rows inaccessible. Native submenu tables
   are swapped only while the relevant native routine runs. */
static u32 item_row(const u8 *state){return state[2]==1?3:6;}
static void tavern_tables(u16 *saved,int restore){
    const u32 table[3]={0x10170f36,0x10170f46,0x10170f56};
    for(u32 i=0;i<3;++i){
        if(restore)HALF(table[i])=saved[i];
        else {saved[i]=HALF(table[i]);HALF(table[i])=HALF(table[i]+6);}
    }
}
static void native_root(void *root,u8 *state){
    u16 saved[3];if(state[2]==1)tavern_tables(saved,0);
    original_root_draw(root,state);
    if(state[2]==1)tavern_tables(saved,1);
}
static void clear(void *at,u32 count){u8 *p=at;for(u32 i=0;i<count;++i)p[i]=0;}
static void copy(void *at,const void *from,u32 count){u8 *p=at;const u8 *q=from;for(u32 i=0;i<count;++i)p[i]=q[i];}
static u32 length(const char *p){u32 n=0;while(p[n])++n;return n;}
static u32 sid(void){return WORD(0x10314578);}
static u32 directions(u8 *lobby){return ((Q1)0x0221a430)(lobby);}
static u32 pressed(u8 *lobby,u32 mask){return ((Q2)0x0221a1c8)(lobby,mask);}
static void sound(u32 id){u32 handle[2];((V2)0x020bfc74)(handle,id);}
static void call_virtual(u32 object,u32 offset,u32 argument){
    if(object)((V2)WORD(WORD(object)+offset))(P(object),argument);
}
static void name_rows(void){
    for(u32 i=0;i<L_SETS;++i){
        const char *prefix=sets[i].valid?set_names[i]:"----------";
        copy(row_names[i],prefix,length(prefix)+1);
    }
}
void reset_item_ui(void){release_layout();ui_text_ready=0;load_missing_units=0;ui_tavern=0;ui_box_enabled=0;ui_list_open=ui_main_active=0;ui_phase=0;ui_anchor=0xffffffffu;ui_preview_page=0;}
static void set_position(u32 value){
    selected=value%L_SETS;list_state[4]=(u8)selected;list_state[5]=L_SETS;
    list_state[0x1c]=(u8)(selected/8);list_state[0x1d]=(u8)(selected%8);
    list_state[6]=(u8)(ui_anchor<L_SETS?ui_anchor:selected);
    list_state[3]=(u8)ui_action;
    list_state[0]=(u8)(ui_phase==CONFIRM || (ui_action==REORDER&&ui_anchor<L_SETS));
}
static void acknowledge(const char *text){message=text;ui_phase=ACK;sound(2);}
static void preview_input(u8 *lobby){
    u32 ud=WORD(0x10315f50),pages=sets[selected].gunner?4:3;
    if(ui_action==REGISTER && ui_phase==CONFIRM && ud)
        pages=((u32(*)(void *,void *))0x02199e48)(P(ud),P(ud+0x38))?4:3;
    if(pressed(lobby,0x100)){ui_preview_page=(ui_preview_page+pages-1)%pages;sound(6);}
    else if(pressed(lobby,0x200)){ui_preview_page=(ui_preview_page+1)%pages;sound(6);}
}
static void save_reorder_or_clear(void){
    Loadout old=sets[selected];
    char old_name[20];copy(old_name,set_names[selected],20);
    if(ui_action==REORDER){
        Loadout source=sets[ui_anchor];char source_name[20];copy(source_name,set_names[ui_anchor],20);
        sets[ui_anchor]=old;sets[selected]=source;copy(set_names[ui_anchor],old_name,20);copy(set_names[selected],source_name,20);
        if(!persist()){sets[ui_anchor]=source;sets[selected]=old;copy(set_names[ui_anchor],source_name,20);copy(set_names[selected],old_name,20);acknowledge("Could not save the new order.\r\nThe previous order was retained.");}
        else {message="Item sets reordered.";ui_phase=BROWSE;sound(5);}
        ui_anchor=0xffffffffu;
    } else {
        clear(&sets[selected],sizeof(Loadout));
        default_name(selected);
        if(!persist()){sets[selected]=old;copy(set_names[selected],old_name,20);acknowledge("Could not unregister the item set.\r\nThe previous registration was retained.");}
        else {message="Item set unregistered.";ui_phase=BROWSE;sound(5);}
    }
    name_rows();
}
static void list_input(u8 *lobby){
    if(ui_phase==KEYBOARD){
        u32 game=WORD(0x101fdb9c);
        if(!game || !((Q1)0x0211db4c)(P(game)))return;
        int accepted=((int(*)(void *,void *,u32,u32,u32,u32,u32,u32))0x0211db48)
            (P(game),rename_buffer,19,1,0,0xffffffffu,0xffffffffu,0xffffffffu);
        WORD(0x10167d20)&=~4u;ui_phase=BROWSE;rename_buffer[19]=0;
        ((V1)0x02141da4)(P(sid()));
        if(accepted && rename_buffer[0]){
            char old[20];copy(old,set_names[selected],20);copy(set_names[selected],rename_buffer,20);
            if(!persist()){copy(set_names[selected],old,20);acknowledge("Could not save the new set name.\r\nThe previous name was retained.");}
            else sound(5);
            name_rows();
        }return;
    }
    /* Normalized sPad L/R are 0x100/0x200 (VPAD 0x20/0x10). */
    preview_input(lobby);
    if(ui_phase==ACK){
        if(pressed(lobby,0x10)||pressed(lobby,0x20)){ui_phase=BROWSE;sound(1);}return;
    }
    if(ui_phase==CONFIRM){
        u32 buttons=((Q1)0x0221a4a4)(lobby);
        int answer=((int(*)(u32 *,u32,u32,u32,u32))0x02043308)(&ui_choice,buttons&0xffff,1,2,0xffff);
        if(answer==2){ui_phase=BROWSE;return;}
        if(answer==1){
            ui_phase=BROWSE;
            if(ui_action==REGISTER){capture();ui_phase=ACK;sound(5);name_rows();}
            else if(ui_action==CURRENT){int success=apply();ui_phase=ACK;sound(success?5:2);}
            else save_reorder_or_clear();
        }return;
    }
    if(pressed(lobby,0x20)){
        if(ui_anchor<L_SETS){ui_anchor=0xffffffffu;set_position(selected);sound(1);return;}
        load_missing_units=0;ui_list_open=0;ui_phase=BROWSE;sound(1);return;
    }
    u32 dirs=directions(lobby),old=selected;
    /* Match the native Equipment Sets column/page navigation: vertical wrap
       stays within its eight-row column; horizontal moves by a page. */
    if(dirs&1)selected=selected%8?selected-1:selected+7;
    else if(dirs&2)selected=selected%8==7?selected-7:selected+1;
    if(dirs&4)selected=(selected+16)%24;
    else if(dirs&8)selected=(selected+8)%24;
    if(old!=selected){load_missing_units=0;ui_preview_page=0;set_position(selected);sound(dirs&12?6:3);}
    if(pressed(lobby,VIEW_PLUS) && !(WORD(0x10167d20)&4)){
        ((void(*)(void *,void *))0x021f0bf4)(lobby,lobby+0x6f10);return;
    }
    /* Equipment Sets uses Y to edit a registered name through sGame's native
       keyboard request, completion query and result collector. */
    if(ui_anchor>=L_SETS && sets[selected].valid && pressed(lobby,RENAME_Y)){
        u32 game=WORD(0x101fdb9c);
        if(!game){acknowledge("The keyboard is unavailable.");return;}
        WORD(0x10167d20)|=4;((V1)0x02141030)(P(sid()));
        clear(rename_buffer,sizeof(rename_buffer));
        ((void(*)(void *,u32,const char *))0x0211b8b8)(P(game),6,set_names[selected]);
        ui_phase=KEYBOARD;return;
    }
    if(!pressed(lobby,0x10))return;
    if(ui_action!=REGISTER && !sets[selected].valid && !(ui_action==REORDER&&ui_anchor<L_SETS)){
        acknowledge("No items are registered in this set.");return;
    }
    if(ui_action==REORDER){
        if(ui_anchor>=L_SETS){ui_anchor=selected;sound(0);}
        else if(ui_anchor==selected){ui_anchor=0xffffffffu;sound(1);}
        else save_reorder_or_clear();
    }else{ui_phase=CONFIRM;ui_choice=0;sound(0);}
    set_position(selected);
}

static int box_step_impl(u8 *lobby){
    ui_box_enabled=1;
    u8 *state=lobby+0x6f10;
    if(state[2]>1){reset_item_ui();return original_box_step(lobby);}
    ui_tavern=state[2]==1;
    HALF(0x10170f3c)=4;HALF(0x10170f4c)=433;HALF(0x10170f5c)=180;
    if(ui_tavern)HALF(state+12)=4;
    else if(HALF(state+12)==6)HALF(state+12)=7;
    if(ui_list_open){
        if(state[3]){((void(*)(void *,void *,u32))0x021f0d44)(lobby,state,0);return 0;}
        if(ui_phase!=KEYBOARD)((V1)0x021f0cb8)(lobby);
        ui_main_active=1;list_input(lobby);set_position(selected);
        if(!ui_list_open){HALF(state+10)=1;HALF(state+8)=(u16)ui_action;}
        return 0;
    }
    u16 before=HALF(state+6),level=HALF(state+10);
    u16 saved[3];if(ui_tavern)tavern_tables(saved,0);
    int result=original_box_step(lobby);
    if(ui_tavern)tavern_tables(saved,1);
    u16 after=HALF(state+6);
    if(!ui_tavern && level==0 && HALF(state+10)==0 && before<7 && after!=before){
        int delta=(after-before+7)%7;
        if(delta==1 || delta==6){
            int pos=(int)position[before]+(delta==1?1:6);
            HALF(state+6)=order[pos%7];
        }
    }
    ui_main_active=result!=2 && HALF(state+6)==item_row(state);
    if(result==2){ui_tavern=0;ui_box_enabled=0;ui_text_ready=0;}
    if(result==1 || result==2 || state[3])release_layout();
    if(ui_main_active && result==1){
        if(!ensure_loaded()){message=storage_error();ui_phase=ACK;}
        else ui_phase=BROWSE;
        ui_action=HALF(state+8);if(ui_action>3)ui_action=0;
        load_missing_units=0;ui_list_open=1;ui_anchor=0xffffffffu;ui_preview_page=0;
        clear(list_state,sizeof(list_state));set_position(0);name_rows();sound(0);
        return 0;
    }
    return result;
}

static char converted[16][512];
static u32 converted_keys[16],converted_count;
static int starts(const char *p,const char *word){while(*word){if(*p++!=*word++)return 0;}return 1;}
static const char *item_wording(const char *text,u32 key){
    if(!text)return text;
    int found=0;for(u32 n=0;text[n];++n)if(starts(text+n,"Equipment")||starts(text+n,"equipment")){found=1;break;}
    if(!found)return text;
    u32 slot=0;while(slot<converted_count&&converted_keys[slot]!=key)++slot;
    if(slot==converted_count){if(converted_count==16)return text;converted_keys[slot]=key;++converted_count;}
    char *out=converted[slot];u32 j=0;
    for(u32 i=0;text[i]&&j<500;){
        const char *replacement=0;u32 consume=0;
        if(starts(text+i,"Equipment Set")){replacement="Item Set";consume=13;}
        else if(starts(text+i,"equipment set")){replacement="item set";consume=13;}
        else if(starts(text+i,"Equipment")){replacement="Items";consume=9;}
        else if(starts(text+i,"equipment")){replacement="items";consume=9;}
        if(replacement){for(u32 k=0;replacement[k]&&j<500;++k)out[j++]=replacement[k];i+=consume;}
        else out[j++]=text[i++];
    }out[j]=0;return out;
}
static const char *shortage_help(const char *text){
    static char buffer[1024];
    static const char warning[]="\r\n(Some items were insufficient or missing.)";
    if(!text || !load_missing_units || ui_action!=CURRENT)return text;
    u32 n=length(text);if(n>900)n=900;
    copy(buffer,text,n);copy(buffer+n,warning,sizeof(warning));return buffer;
}
static void prepare_item_text(void){
    u32 ui=sid();if(!ui)return;
    for(u32 i=0;i<5;++i){
        ui_text_main[i]=i==2?"Register your item pouch as a new set.":
            item_wording(original_text(P(ui),0x2f,175+i),0x2f0000u+180+i);
    }
    for(u32 i=0;i<8;++i)
        list_help_base[i]=item_wording(original_text(P(ui),0x2f,0x114+i),0x2f0114u+i);
    ui_text_ready=1;
}
static void refresh_item_text(void){
    if(!ui_text_ready)return;
    const char *ack=ui_phase==ACK?shortage_help(message):0;
    for(u32 i=0;i<8;++i)
        ui_text_list[i]=ui_phase==ACK?ack:
            (i==0 && ui_phase==BROWSE?shortage_help(list_help_base[i]):list_help_base[i]);
}
int box_step(u8 *lobby){
    if(!ui_text_ready && lobby[0x6f12]<=1)prepare_item_text();
    int result=box_step_impl(lobby);
    refresh_item_text();
    return result;
}

/* Native Equipment Sets uses these exact eight row objects, page indicator,
   text drawing and colour themes. Only the row data is supplied by this mod. */
static void draw_set_list(u32 widget){
    ((void(*)(void *,u32,u32,u32))0x026a5020)(P(widget),0x52,8,0);
    ((void(*)(void *,u32,u32,u32,u32))0x026a5668)(P(widget),selected/8+1,3,5,0);
    u32 objects=WORD(widget+0xf8);
    u32 page=selected/8;
    for(u32 row=0;objects && row<8;++row){
        u32 idx=page*8+row,id=HALF(0x1005f6e4+row*2),item=WORD(objects+id*4);
        if(!item)continue;
        int chosen=idx==selected,anchor=ui_action==REORDER && idx==ui_anchor;
        u32 theme=anchor?(chosen?9:8):(chosen?(sets[idx].valid?1:0x24):(sets[idx].valid?0:3));
        ((V3)0x0228d438)(P(widget),P(item),theme);
        u32 group=WORD(item+0xf8),text=group?WORD(group+8):0;
        if(text){
            ((V2)0x02af349c)(P(text),1);
            ((void(*)(void *,const char *,u32))0x02aff91c)(P(text),row_names[idx],length(row_names[idx]));
        }
    }
    /* drawEquipmentSets (027056EC) ends with vf+1D4. Layout/text setters
       alone do not submit this shared widget to the unit draw pass. The
       neutral root screen also bypasses its usual activation state. */
    call_virtual(widget,0x1d4,0);
    WORD(widget+0xc)|=0x130000;
}
/* Item List uses only its own preview widget. Do not borrow the resident
   Yes/No dialog: 021421F4/021433C4 configure that modal, not a banner. */
/* Reuse the stock Item Box title widget, not a new layout/font. Native
   MyhBox initialization stores uIDLobbyMyhTitle at root+350; its GUI is
   myh_p_title_n and includes the baked Item Pouch / Blade / Gunner lettering.
   02688C68 is the exact helper used by the stock pouch pages to draw it.
   Its only state read is byte 5 (pouch type); flag bit 0 inverts that choice. */
static void draw_pouch_title(u32 root,int gunner){
    u32 title=WORD(root+0x350);
    if(!title||WORD(title)!=0x10069958)return;
    u8 pouch_state[8]={0};pouch_state[5]=gunner!=0;
    ((void(*)(void *,void *,u32))0x02688c68)(P(title),pouch_state,0);
}
static void draw_preview(u32 root){
    u32 ui=sid();if(!ui)return;
    u32 widget=((Q1)0x0214380c)(P(ui));if(!widget)return;
    if(!displayed_preview){displayed_preview=widget;preview_schedule=WORD(widget+0xc)&0x30000;}
    clear(preview_slots,sizeof(preview_slots));
    u32 count=sets[selected].gunner?32:24;
    if((ui_action==REGISTER && ui_phase==CONFIRM) ||
       (ui_action==CURRENT && ui_phase==ACK && load_missing_units)){
        /* A partial-load result previews the pouch that was actually filled.
           Returning to BROWSE previews the unmodified registration again. */
        u32 ud=WORD(0x10315f50);if(!ud)return;
        int g=((u32(*)(void *,void *))0x02199e48)(P(ud),P(ud+0x38))!=0;
        count=g?32:24;copy(preview_slots,P(ud+0x38+(g?0x108:0xa8)),count*4);
    }else if(sets[selected].valid)copy(preview_slots,sets[selected].slots,count*4);
    u32 pages=count/8,page=ui_preview_page%pages;
    clear(preview_entries,sizeof(preview_entries));
    for(u32 i=0;i<8;++i){preview_entries[i*0x18+2]=1;HALF(preview_entries+i*0x18+4)=(u16)(page*8+i);}
    u32 selector=((Q1)0x0214218c)(P(ui));if(selector)WORD(selector)=6;
    HALF(widget+0x3f4)=8;
    ((V2)0x0203787c)(P(widget+0x2d4),0);
    ((void(*)(void *,u32,u32))0x02037600)(P(widget+0x2d4),3,0);
    WORD(widget+0xc)|=0x100000;call_virtual(widget,0xe4,1);
    ((V1)0x0265e308)(P(widget));((V2)0x0265f010)(P(widget),1);
    ((void(*)(void *,u32,u32))0x0265fae4)(P(widget),8,0);HALF(widget+0x52c)=0;
    ((void(*)(void *,void *,void *,u32,u32,u32,u32,void *,u32))0x026611b8)
        (P(widget),preview_slots,preview_entries,page+1,pages,0,0x800,preview_entries+8*0x18,8);
    draw_pouch_title(root,count==32);
    WORD(widget+0xc)|=0x30000;
}
void root_draw(void *root,u8 *state){
    /* Release before another page reuses the shared scroll; never on a timer. */
    if(ui_list_open || state[0]!=2 || state[3])release_layout();
    int valid=ui_list_open && state[0]==2 && HALF(state+6)==item_row(state);
    int visible=valid && !state[3] && ui_phase!=KEYBOARD;
    if(displayed_maki && (display_root!=(u32)root || !visible)){
        /* Only dereference a widget while its owning root is still current. */
        if(display_root==(u32)root){
            call_virtual(displayed_maki,0x1dc,0);
            WORD(displayed_maki+0xc)=(WORD(displayed_maki+0xc)&~0x30000u)|maki_schedule;
        }
        displayed_maki=display_root=0;
    }
    if(displayed_preview && (preview_root!=(u32)root || !visible)){
        if(preview_root==(u32)root){
            call_virtual(displayed_preview,0xe4,0);
            WORD(displayed_preview+0xc)=(WORD(displayed_preview+0xc)&~0x30000u)|preview_schedule;
            u32 ui=sid(),selector=ui?((Q1)0x0214218c)(P(ui)):0;if(selector)WORD(selector)=0;
        }
        displayed_preview=preview_root=0;
    }
    if(!ui_list_open){native_root(root,state);return;}
    if(state[0]!=2 || HALF(state+6)!=item_row(state)){reset_item_ui();native_root(root,state);return;}
    /* Native View Mode renders and rotates the hunter using the real state.
       The parent box state machine keeps the item-list selection intact. */
    if(state[3]){native_root(root,state);return;}
    copy(shadow,state,sizeof(shadow));shadow[0]=20; /* native unused/neutral screen */
    native_root(root,shadow);
    if(ui_phase==KEYBOARD)return;
    u32 ui=sid();if(!ui)return;
    u32 maki=((Q1)0x02143abc)(P(ui));
    if(maki && !displayed_maki){displayed_maki=maki;display_root=(u32)root;maki_schedule=WORD(maki+0xc)&0x30000;}
    set_position(selected);if(maki)draw_set_list(maki);preview_root=(u32)root;draw_preview((u32)root);
    /* Native Equipment Sets control legend: includes Y/name edit and +/view. */
    ((V2)0x02144574)(P(ui),ui_phase==BROWSE && ui_anchor>=L_SETS?0x14:0x2c);
    u32 help=0x114+ui_action*2;
    if(ui_phase==CONFIRM || (ui_action==REORDER&&ui_anchor<L_SETS))++help;
    ((V2)0x02145c7c)(P(ui),ui_phase==CONFIRM?ui_choice:0xffffffffu);
    ((V2)0x02144ca8)(P(ui),help);
}

/* Main box row layout: Item Sets immediately after Combine/Manage Items, with
   the separator and lower equipment rows moved down one native row (54 px). */
typedef struct {u32 instance,root,object,type;float base,written;} Shift;
static Shift shifts[4];u32 shift_count;static u32 shifted_widget;
static u32 find_instance(u32 widget,u32 id){
    u32 stack[128],n=0,visited=0,root=WORD(widget+0xf4);if(root)stack[n++]=root;
    while(n && visited++<600){
        u32 obj=stack[--n];if(WORD(obj+4)==id)return obj;
        u32 child=WORD(obj+0x60),next=WORD(obj+0x64);
        if(next&&n<128)stack[n++]=next;if(child&&n<128)stack[n++]=child;
    }return 0;
}
static u32 child(u32 obj,u32 index){u32 p=obj?WORD(obj+0x68):0;while(p&&index--){p=WORD(p+0x6c);}return p;}
static void add_shift(u32 instance,u32 root,u32 object,u32 type){
    if(!object||WORD(object)!=type||shift_count==4)return;
    float y=*(float *)(object+0x84);shifts[shift_count++]=(Shift){instance,root,object,type,y,y};
}
static void locate_shifts(u32 widget){
    shifted_widget=widget;shift_count=0;
    u32 scroll=find_instance(widget,428),line=find_instance(widget,593);
    if(scroll){u32 root=WORD(scroll+0xfc);add_shift(scroll,root,child(root,1),0x100a7f30);add_shift(scroll,root,child(root,2),0x100a7f30);add_shift(scroll,root,child(root,4),0x100a7cb0);}
    if(line){u32 root=WORD(line+0xfc);add_shift(line,root,child(root,0),0x100a7f30);}
}
static void update_shift(Shift *s,int active){
    if(WORD(s->instance+0xfc)!=s->root || WORD(s->object)!=s->type)return;
    float y=*(float *)(s->object+0x84);
    if(y!=s->written)s->base=y; /* native animation supplied a fresh base */
    s->written=s->base+(active?54.0f:0.0f);
    if(y!=s->written){
        *(float *)(s->object+0x84)=s->written;
        WORD(s->object+0x54)|=0x20000;WORD(s->root+0x8c)|=2;
    }
}
static void release_layout(void){
    for(u32 i=0;i<shift_count;++i)update_shift(&shifts[i],0);
    shift_count=0;shifted_widget=0;
}
static void request_layout(u32 widget){
    if(widget!=shifted_widget){release_layout();locate_shifts(widget);}
    else if(!shift_count)locate_shifts(widget); /* native root may load lazily */
    /* Apply on the first menu draw too, rather than waiting for a subsequent
       animation update before the four-/eight-row frame becomes visible. */
    for(u32 i=0;i<shift_count;++i)update_shift(&shifts[i],1);
}
void animation_hook(void *instance,const void *parent_matrix){
    u32 inst=(u32)instance;
    for(u32 i=0;i<shift_count;++i)
        if(shifts[i].instance==inst)update_shift(&shifts[i],1);
    original_animation(instance,parent_matrix);
}
void draw_options(void *ptr,u8 *state){
    u32 widget=(u32)ptr;
    if(state[2]==1 && HALF(state+12)==4){
        request_layout(widget);
        u32 frames=WORD(widget+0x2ac),texts=WORD(widget+0x2b8),plates=WORD(widget+0x2b0);
        u32 old_frame=frames?WORD(frames+16):0,old_text=texts?WORD(texts+16):0;
        if(frames)WORD(frames+16)=WORD(frames+12);
        if(texts)WORD(texts+16)=WORD(texts+12);
        original_draw_options(ptr,state);
        if(frames)WORD(frames+16)=old_frame;
        if(texts)WORD(texts+16)=old_text;
        if(texts && old_text)((V2)0x02af349c)(P(old_text),0);
        if(plates)for(u32 i=3;i<8;++i){u32 obj=WORD(plates+i*4);if(obj)((V3)0x0228d1b4)(ptr,P(obj),i==3);}
        /* Tavern's native 4A preset always uses the three-row scroll animation
           (frame 68), even when its row-count parameter is four. Reuse the
           room menu's one-row extension so the original footer clears row 4.
           The separator is hidden in Tavern mode; it shares the same safe
           shift/restoration path when returning to the room box. */
        return;
    }
    if(HALF(state+12)!=7 || state[2]){original_draw_options(ptr,state);return;}
    request_layout(widget);
    u32 frames=WORD(widget+0x2ac),texts=WORD(widget+0x2b8),plates=WORD(widget+0x2b0);
    static const u8 map[8]={0,1,2,4,5,6,7,3};
    u32 old_frames[8],old_texts[8];
    for(u32 i=0;i<8;++i){old_frames[i]=frames?WORD(frames+i*4):0;old_texts[i]=texts?WORD(texts+i*4):0;}
    for(u32 i=0;i<8;++i){if(frames)WORD(frames+i*4)=old_frames[map[i]];if(texts)WORD(texts+i*4)=old_texts[map[i]];}
    original_draw_options(ptr,state);
    for(u32 i=0;i<8;++i){if(frames)WORD(frames+i*4)=old_frames[i];if(texts)WORD(texts+i*4)=old_texts[i];}
    if(plates){
        for(u32 i=3;i<8;++i){u32 obj=WORD(plates+i*4);if(obj)((V3)0x0228d1b4)(ptr,P(obj),i!=4);}
    }
    if(texts){if(old_texts[4])((V2)0x02af349c)(P(old_texts[4]),0);if(old_texts[7])((V2)0x02af349c)(P(old_texts[7]),1);}
}
void draw_menu(void *ptr,u8 *state){
    u16 saved[3];if(state[2]==1)tavern_tables(saved,0);
    original_draw_menu(ptr,state);
    if(state[2]==1){
        tavern_tables(saved,1);
        if(HALF(state+12)==4){u32 frame=WORD((u32)ptr+0x2e4);if(frame)((void(*)(void *,u32,u32,u32))0x026a5020)(P(frame),0x4a,4,0);}
        return;
    }
    if(HALF(state+12)!=7||state[2]||state[3]||HALF(state+10)==0)return;
    u32 option=HALF(state+6);if(option<3||option>6)return;
    u32 row=option==6?3:option+2;
    float height=*(float *)0x1005c520,extra=*(float *)0x1005c524,pad=*(float *)0x1005c530,limit=*(float *)0x1005c534;
    float y0=(float)(int)WORD((u32)ptr+0x418)+row*height;
    float y1=(float)(int)WORD((u32)ptr+0x41c)+row*height;
    float bottom=y0+HALF(state+14)*height+extra,offset=bottom>limit?limit-bottom:pad;
    u32 ids[3]={0x22f,0x1da,600};
    for(u32 i=0;i<3;++i){
        u32 obj=((u32(*)(void *,u32,u32))0x02a72ce8)(ptr,ids[i],1);
        if(obj)((void(*)(void *,float))0x02adef64)(P(obj),(i?y1:y0)+offset);
    }
}
