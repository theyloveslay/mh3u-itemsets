/* US 3DS inventory bridge. Not hooked into a live game in this checkpoint. */
#include "loadouts.h"
#define WORD(a) (*(volatile u32 *)(a))
static ItemRule rules[L_ITEMS];
static Transaction transaction;
static int is_gunner(u32 ud,u32 hunter) {
    return ((u32 (*)(void *,void *))0x009987ac)((void *)ud,(void *)hunter)!=0;
}
int capture_native_pouch(Loadout *out) {
    u32 ud=WORD(0x00c43360);
    if(!ud || !out)return L_INVALID;
    u32 hunter=ud+0x18,g=is_gunner(ud,hunter),count=g?32:24;
    Slot *pouch=(Slot *)(hunter+(g?0x108:0xa8));
    out->valid=1;out->gunner=(u8)g;out->reserved=0;
    for(u32 i=0;i<L_SLOTS;++i)out->slots[i]=i<count?pouch[i]:(Slot){0,0};
    return L_OK;
}
int apply_native_pouch(const Loadout *want,u32 *missing) {
    if(missing)*missing=0;
    u32 ud=WORD(0x00c43360),table=WORD(0x00cb9954);
    if(!ud || !table || !want)return L_INVALID;
    for(u32 i=0;i<L_ITEMS;++i){
        const u8 *row=(const u8 *)(table+20*i);
        /* Verified against 3DS Item00_eng: action-only mask entries, not items. */
        rules[i]=(ItemRule){row[3],row[0],(u8)(i>1 && !(i>=0x4db && i<=0x4de) && i!=0x5f3),0};
    }
    u32 hunter=ud+0x18,g=is_gunner(ud,hunter);
    u32 count=g?32:24,opposite=g?24:32;
    Slot *target=(Slot *)(hunter+(g?0x108:0xa8));
    Slot *donor=(Slot *)(hunter+(g?0xa8:0x108));
    Slot *box=(Slot *)(hunter+0x188);
    /* Explicit hunter argument: this is not the Wii U helper's ABI. */
    u32 capacity=((u32 (*)(void *,void *))0x00999ffc)((void *)ud,(void *)hunter);
    int result=plan_loadout(target,count,donor,opposite,box,capacity,want,rules,&transaction);
    if(result==L_OK || result==L_PARTIAL){
        commit_loadout(target,count,donor,opposite,box,capacity,&transaction);
        if(missing)*missing=transaction.missing_units;
    }
    return result;
}
