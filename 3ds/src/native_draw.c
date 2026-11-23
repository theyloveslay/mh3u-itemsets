/* Native US 3DS GUI binding. The preview router 0x371B44 was matched against
 * the Wii U renderer by its nine arguments, row descriptors and flag handling.
 * Actual screen placement still requires a live-game check.
 */
#include "item_ui.h"
#include "native_original.h"
#include "item_text.h"
#include "layout_diagnostics.h"
#define WORD(a) (*(volatile u32 *)(a))
#define HALF(a) (*(volatile u16 *)(a))
typedef void (*V2)(void *,u32);
extern void item_layout_refresh(void *widget);
extern void item_layout_refresh_mode(void *widget,u32 tavern);
extern void item_layout_stop(void);
static u32 length(const char *p){u32 n=0;while(p[n])++n;return n;}
static void virtual_call(void *p,u32 offset,u32 value){
    if(p)((V2)WORD(WORD(p)+offset))(p,value);
}
static void font(void *p,const char *text){
    if(!p)return;((V2)0x0013fbd4)(p,1);
    ((void (*)(void *,const char *,u32))0x00323098)(p,text,length(text));
}
static u8 entries[8*24+4];
static u32 shown_root,shown_maki,shown_preview,old_selector,selector_address;
static u8 shadow[0xc60];
/* The native help-ID setter resolves to setText(widget, text, 0).
 * Supply our text directly so a missing/overridden lobby ARC cannot yield
 * DUMMY or an out-of-range appended message. Ordinary help remains native. */
static void item_show_help(u32 ui,u32 id){
    const char *text=item_help_text(id);
    if(!text){((V2)0x00526a74)((void *)ui,id);return;}
    u32 group=WORD(ui+0x2c),help=group?WORD(group+0x84):0;
    if(help)((void (*)(void *,const char *,u32))0x003686cc)((void *)help,text,0);
}
void item_draw_list(void *widget,const ItemFrame *f){
    item_layout_stop();
    /* Native generic eight-row list, with native page indicator and themes. */
    ((void (*)(void *,u32,u32))0x002b1918)(widget,0x20,8);
    ((void (*)(void *,u32,u32,u32))0x002b0c30)(widget,f->page,3,5);
    u32 bg=WORD((u8 *)widget+0x224),overlay=WORD((u8 *)widget+0x228),texts=WORD((u8 *)widget+0x230);
    for(u32 row=0;row<8;++row){
        u32 chosen=row==f->selected_row;
        if(bg)((void (*)(void *,void *,u32))0x00535d70)(widget,(void *)WORD(bg+row*4),chosen);
        if(overlay)((void (*)(void *,void *,u32))0x00535d70)(widget,(void *)WORD(overlay+row*4),1);
        u32 text=texts?WORD(texts+row*4):0;
        if(text){
            font((void *)text,f->names[row]);
            u32 colour=((u32 (*)(void *,u32,u32,u32,u32))0x005991d4)
                ((void *)WORD(0x00c40728),!!(f->valid_mask&(1u<<row)),chosen,1,0);
            if(row==f->anchor_row && (f->valid_mask&(1u<<row)))colour=0xff82d6f0u;
            ((void (*)(void *,const u32 *))0x00324680)((void *)text,&colour);
        }
    }
    u32 title=WORD((u8 *)widget+0x21c);
    if(title){
        ((void (*)(void *,void *,u32))0x00535d70)(widget,(void *)title,1);
        ((void (*)(void *,const char *,u32))0x003ae1e0)((void *)title,f->title,length(f->title));
    }
    virtual_call(widget,0xd4,0);virtual_call(widget,0x70,1);
}
void item_draw_preview(void *widget,const ItemFrame *f){
    u32 selector=WORD((u8 *)widget+0x228);if(selector)WORD(selector)=6;
    virtual_call(widget,0xd4,0);virtual_call(widget,0x70,1);
    ((void (*)(void *))0x0036feb8)(widget);
    ((V2)0x0037bb98)(widget,1);
    ((void (*)(void *,u32,u32))0x0037c790)(widget,8,0);
    HALF((u8 *)widget+0x464)=0;
    for(u32 i=0;i<sizeof(entries);++i)entries[i]=0;
    u32 page=f->pouch_pages==4?f->pouch_page%4:f->pouch_page%3;
    for(u32 row=0;row<8;++row){entries[row*24+2]=1;HALF(entries+row*24+4)=(u16)(page*8+row);}
    ((void (*)(void *,const Slot *,const void *,u32,u32,u32,u32,const void *,u32))0x00371b44)
        (widget,f->pouch,entries,page+1,f->pouch_pages,0,0x800,entries+192,8);
    /* Keep the native Item List title; paging stays in this same header. */
}
static void tavern_tables(u16 old[3],int restore){
    const u32 table[3]={0x00b9b696,0x00b9b6a4,0x00b9b6b2};
    for(u32 i=0;i<3;++i){
        if(restore)HALF(table[i])=old[i];
        else {old[i]=HALF(table[i]);HALF(table[i])=HALF(table[i]+6);}
    }
}
static void native_root(void *root,u8 *state){
    u16 saved[3];if(state[2]==1)tavern_tables(saved,0);
    original_root_screen(root,state);
    if(state[2]==1)tavern_tables(saved,1);
}
static void release(u32 live_maki,u32 live_preview){
    /* Only dereference an object returned afresh by the current sID getters. */
    if(shown_maki && shown_maki==live_maki)virtual_call((void *)shown_maki,0xd8,0);
    if(shown_preview && shown_preview==live_preview){
        virtual_call((void *)shown_preview,0xd8,0);
        if(selector_address && WORD(shown_preview+0x228)==selector_address && WORD(selector_address)==6)
            WORD(selector_address)=old_selector;
    }
    shown_root=shown_maki=shown_preview=selector_address=0;
}
void item_root_draw(void *root,u8 *state){
    u32 ui=WORD(0x00c406a0),maki=0,preview=0;
    if(ui){
        maki=((u32 (*)(void *))0x00523bf4)((void *)ui);
        preview=((u32 (*)(void *))0x005242e0)((void *)ui);
    }
    int visible=item_ui.open && state[2]<=1 && state[0]==2 && HALF(state+6)==(state[2]?3:6) &&
        !state[3] && item_ui.phase!=UI_KEYBOARD;
    if(!visible || (shown_root && shown_root!=(u32)root) ||
       (shown_maki && shown_maki!=maki) || (shown_preview && shown_preview!=preview))release(maki,preview);
    if(!visible){
        native_root(root,state);
        if(ui && state[0]==2 && state[2]<=1 && !state[3] &&
           HALF(state+6)==(state[2]?3:6)){
            u32 id=180;if(HALF(state+10)==1)id+=1+HALF(state+8);
            item_show_help(ui,id);
            if(HALF(state+10)==1){
                static const char *actions[4]={"Current Sets","Register Set","Reorder Sets","Unregister Sets"};
                u32 group=WORD(ui+0x3c),box=group?WORD(group+0x98):0;
                /* Native 0x975018 requests font array 0 from the inline
                 * popup instance +0x260; 0x51E500 returns +0x6C. */
                if(box)for(u32 i=0;i<4;++i)font((void *)WORD(box+0x2cc+i*4),actions[i]);
            }
        }
        return;
    }
    for(u32 i=0;i<sizeof(shadow);++i)shadow[i]=state[i];
    shadow[0]=20;native_root(root,shadow);
    const ItemFrame *f=item_ui_frame();
    if(!shown_root)shown_root=(u32)root;
    if(maki){shown_maki=maki;item_draw_list((void *)maki,f);}
    if(preview){
        if(!shown_preview){
            shown_preview=preview;selector_address=WORD(preview+0x228);
            old_selector=selector_address?WORD(selector_address):0;
        }
        item_draw_preview((void *)preview,f);
    }
    /* Same root-owned myh_p_title_n instance and texture selector used by
     * native pouch pages. 0x975F48 selects baked Blade/Gunner lettering;
     * it does not configure the resident Yes/No dialog. Native root hides
     * this widget before dispatch, including when leaving this screen. */
    u32 pouch_title=WORD((u8 *)root+0x2c8);
    if(pouch_title){
        u8 pouch_state[8]={0};pouch_state[5]=!!f->pouch_gunner;
        ((void (*)(void *,const u8 *,u32))0x00975f48)
            ((void *)pouch_title,pouch_state,0);
    }
    if(ui){
        u32 legend=item_ui.phase==UI_BROWSE && item_ui.anchor>=L_SETS &&
            item_store.collection.sets[item_ui.selected].valid?0x0f:0x26;
        ((V2)0x005269f0)((void *)ui,legend);
        if(f->choice!=0xffffffffu)((V2)0x00523bb8)((void *)ui,f->choice);
        item_show_help(ui,f->help);
    }
}
void item_draw_options(void *widget,u8 *state){
    if(state[2]==1 && HALF(state+12)==4){
        item_layout_refresh_mode(widget,1);
        u32 frames=WORD((u8 *)widget+0x224),texts=WORD((u8 *)widget+0x230),plates=WORD((u8 *)widget+0x228);
        u32 old_frame=frames?WORD(frames+16):0,old_text=texts?WORD(texts+16):0;
        if(frames)WORD(frames+16)=WORD(frames+12);
        if(texts)WORD(texts+16)=WORD(texts+12);
        original_options(widget,state);
        if(texts)font((void *)WORD(texts+16),"Item Sets");
        if(frames)WORD(frames+16)=old_frame;
        if(texts)WORD(texts+16)=old_text;
        if(old_text)((V2)0x0013fbd4)((void *)old_text,0);
        if(plates)for(u32 i=3;i<8;++i){u32 obj=WORD(plates+4*i);if(obj)((void (*)(void *,void *,u32))0x00535d70)(widget,(void *)obj,i==3);}
        item_layout_refresh_mode(widget,1);
        return;
    }
    if(!state[2] && HALF(state+12)==7){
        /* Hardware capture: row 7 is dormant (parent flag 8 clear). Keep
         * equipment on its original active rows 4..6; route only logical
         * Item Sets to reserved row 3. Move the actual section parent below. */
        static const u32 map[8]={0,1,2,7,4,5,6,3};
        static const char *labels[7]={"Store Items","Remove Items","Combine/Manage Items",
            "Manage Equipment","Change Appearance","Equipment Sets","Item Sets"};
        item_layout_refresh(widget);
        u32 frames=WORD((u8 *)widget+0x224),texts=WORD((u8 *)widget+0x230),plates=WORD((u8 *)widget+0x228);
        u32 old_frames[8],old_texts[8];
        for(u32 i=0;i<8;++i){old_frames[i]=frames?WORD(frames+4*i):0;old_texts[i]=texts?WORD(texts+4*i):0;}
        for(u32 i=0;i<8;++i){if(frames)WORD(frames+4*i)=old_frames[map[i]];if(texts)WORD(texts+4*i)=old_texts[map[i]];}
        original_options(widget,state);
        if(texts)for(u32 i=0;i<7;++i){u32 slot=i<3?i:i+1;font((void *)WORD(texts+4*slot),labels[i]);}
        for(u32 i=0;i<8;++i){if(frames)WORD(frames+4*i)=old_frames[i];if(texts)WORD(texts+4*i)=old_texts[i];}
        if(plates)for(u32 i=3;i<8;++i){u32 obj=WORD(plates+4*i);if(obj)((void (*)(void *,void *,u32))0x00535d70)(widget,(void *)obj,i<7);}
        if(texts){if(old_texts[7])((V2)0x0013fbd4)((void *)old_texts[7],0);}
        item_layout_refresh(widget);
        item_diag_menu(widget,state);
        return;
    }
    item_layout_stop();
    original_options(widget,state);
}
