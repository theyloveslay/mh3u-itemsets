#include "loadouts.h"
#include "native_original.h"
#include "layout_diagnostics.h"
#define WORD(a) (*(volatile u32 *)(a))
#define HALF(a) (*(volatile u16 *)(a))
extern u32 item_add_float(u32 a,u32 b);
extern u32 item_mul_float(u32 a,u32 b);
extern u32 item_int_float(int value);
extern void item_set_inst_y(void *instance,u32 bits);
extern u32 item_memory_readable(u32 address,u32 length);
typedef struct {u32 instance,id,type,base_y,written_y,base_scale,written_scale;} Target;
/* IDs, hierarchy and dimensions verified in the user's v3 hardware capture.
 * Parent 574 held Y=8 but world Y=-32 (old -12 + parent -44): changing a
 * Null instance's property during drawing does not rebuild its cached matrix.
 * Apply before child animation matrices, and explicitly rebuild this parent.
 * 450 has a visible 160x2 divider; body 438 is 170x146; bottom 431 is Y180. */
static Target targets[4];
static u32 layout_widget,layout_tavern,viewport_copy[2],have_viewport;
static int live(Target *t){
    u32 p=t->instance;
    return p && item_memory_readable(p,0x120) && WORD(p)==t->type
        && WORD(p+0x68)==t->id && WORD(p+0x60)==layout_widget;
}
static void base_matrix(u32 p,const void *viewport,u32 arg4){
    u32 parent=WORD(p+0x88);
    if(parent && item_memory_readable(parent,0x120))
        ((void (*)(void *,const void *,const void *,u32))0x00292418)
            ((void *)p,(void *)(parent+0x10),viewport,arg4);
}
static void apply(Target *t){
    item_set_inst_y((void *)t->instance,t->written_y);
    if(WORD(t->instance+0xbc)!=t->written_scale){
        WORD(t->instance+0xbc)=t->written_scale;
        WORD(t->instance+0x70)|=0x10000;
    }
}
static void dirty_children(u32 p){
    /* Captured parent contains only a bounded sibling chain of row nodes.
     * Invalidate the rows so restoring the parent also restores their matrices. */
    u32 child=WORD(p+0x80);
    for(u32 n=0;child && n<16;++n){
        if(!item_memory_readable(child,0x120) || WORD(child+0x88)!=p)break;
        WORD(child+0x70)|=0x10000;child=WORD(child+0x84);
    }
}
void item_layout_stop(void){
    for(u32 i=0;i<4;++i){
        Target *t=&targets[i];if(!live(t))continue;
        if(WORD(t->instance+0xac)==t->written_y)
            item_set_inst_y((void *)t->instance,t->base_y);
        if(WORD(t->instance+0xbc)==t->written_scale){
            WORD(t->instance+0xbc)=t->base_scale;WORD(t->instance+0x70)|=0x10000;
        }
        if(!i){if(have_viewport)base_matrix(t->instance,viewport_copy,0);dirty_children(t->instance);}
    }
    for(u32 i=0;i<4;++i)targets[i].instance=0;
    layout_widget=layout_tavern=have_viewport=0;
}
void item_layout_refresh_mode(void *widget,u32 tavern){
    tavern=!!tavern;
    if(layout_widget!=(u32)widget || layout_tavern!=tavern || !live(&targets[tavern?2:0])){
        item_layout_stop();layout_widget=(u32)widget;layout_tavern=tavern;
        const u32 ids[4]={574,450,431,438};
        const u32 delta[4]={0x41a00000,0x41a00000,0x41a00000,0x41200000};
        for(u32 i=0;i<4;++i){
            if(tavern && i<2)continue;
            Target *t=&targets[i];u32 p=((u32 (*)(void *,u32,u32))0x00a2dd50)(widget,ids[i],1);
            t->instance=p;t->id=ids[i];t->type=i?0x00b5ea6c:0x00b51280;
            if(!live(t)){t->instance=0;continue;}
            t->base_y=WORD(p+0xac);t->written_y=item_add_float(t->base_y,delta[i]);
            t->base_scale=WORD(p+0xbc);
            /* Add one 20px row even when Tavern's base body is scaled.
             * Multiplying by 166/146 only adds 20px for a unit-scale body. */
            t->written_scale=i==3?item_add_float(t->base_scale,0x3e0c4623):t->base_scale;
        }
    }
    /* Property writes are useful for diagnostics, but animation hook below
     * is where matrices must be rebuilt for the actual drawing pass. */
    for(u32 i=0;i<4;++i)if(live(&targets[i]))apply(&targets[i]);
    u32 scroll=((u32 (*)(void *,u32,u32))0x00a2dd50)(widget,428,1);
    item_diag_targets(scroll,targets[1].instance,targets,0);
}
void item_layout_refresh(void *widget){item_layout_refresh_mode(widget,0);}
/* Preserve all four incoming native register arguments. */
void item_animation_step(void *instance,const void *parent_matrix,const void *viewport,u32 native_arg4){
    item_diag_animation(instance);
    u32 inst=(u32)instance;
    if(layout_widget){
        for(u32 i=1;i<4;++i)if(targets[i].instance==inst && live(&targets[i]))apply(&targets[i]);
        Target *group=&targets[0];
        if(group->instance && (u32)parent_matrix==group->instance+0x10 && live(group)){
            /* Null 574 has no 3E4A44 callback of its own. Rebuild it through
             * the real native base transform before any of its child rows. */
            apply(group);WORD(group->instance+0x70)|=0x10000;
            base_matrix(group->instance,viewport,native_arg4);
            WORD(inst+0x70)|=0x10000;
            viewport_copy[0]=WORD((u32)viewport);viewport_copy[1]=WORD((u32)viewport+4);have_viewport=1;
        }
    }
    original_animation(instance,parent_matrix,viewport,native_arg4);
}
void item_menu_draw(void *widget,u8 *state){
    original_menu(widget,state);
    if(state[2] || state[3] || HALF(state+12)!=7 || !HALF(state+10))return;
    u32 option=HALF(state+6);if(option<3 || option>6)return;
    /* Native 3DS popup: 20-pixel pitch, 8-pixel section gap, header +20,
     * text +46, height 10+20*action_count, lower edge 208. The inserted
     * item row has no preceding section gap; equipment advances one row. */
    int row=option==6?3:(int)option+1,gap=option==6?0:8;
    int header=row*20+20+gap,text=row*20+46+gap;
    int bottom=header+10+20*HALF(state+14),adjust=bottom>208?208-bottom:0;
    const u32 ids[3]={559,474,600};
    for(u32 i=0;i<3;++i){
        u32 obj=((u32 (*)(void *,u32,u32))0x00a2dd50)(widget,ids[i],1);
        if(obj)item_set_inst_y((void *)obj,item_int_float((i?text:header)+adjust));
    }
}
