#include "loadouts.h"

static u32 take(Slot *slots, u32 count, u16 item, u32 wanted) {
    u32 taken=0;
    for (u32 i=0; i<count && wanted; ++i) {
        if (slots[i].id != item) continue;
        u32 n=slots[i].count < wanted ? slots[i].count : wanted;
        slots[i].count=(u16)(slots[i].count-n);
        if (!slots[i].count) slots[i].id=0;
        wanted-=n; taken+=n;
    }
    return taken;
}

static int canonical(Slot s) { return (!s.id)==(!s.count); }

int plan_loadout(const Slot *target, u32 target_count,
                 const Slot *donor, u32 donor_count,
                 const Slot *box, u32 box_count,
                 const Loadout *want, const ItemRule *rules, Transaction *tx) {
    if (!target || !donor || !box || !want || !rules || !tx ||
        !((target_count==24 && donor_count==32) || (target_count==32 && donor_count==24)) ||
        !box_count || box_count>L_BOX || !want->valid || want->gunner>1)
        return L_INVALID;
    if (want->gunner != (target_count==32)) return L_WRONG_POUCH;
    tx->direct_units=tx->box_units=tx->missing_units=0;
    for (u32 i=0;i<L_SLOTS;++i) {
        tx->target[i]=(Slot){0,0};
        tx->remaining[i]=(Slot){0,0};
        tx->donor[i]=(Slot){0,0};
        Slot w=want->slots[i];
        if (!canonical(w) || (i>=target_count && w.id)) return L_INVALID;
        if (w.id && (w.id>=L_ITEMS || !rules[w.id].allowed || !rules[w.id].limit ||
            w.count>rules[w.id].limit ||
            (i>=24 && rules[w.id].category!=1 && rules[w.id].category!=4))) return L_INVALID;
    }
    for (u32 i=0;i<target_count;++i) {
        if (!canonical(target[i]) || target[i].id>=L_ITEMS) return L_INVALID;
        tx->remaining[i]=target[i];
    }
    for (u32 i=0;i<donor_count;++i) {
        if (!canonical(donor[i]) || donor[i].id>=L_ITEMS) return L_INVALID;
        tx->donor[i]=donor[i];
    }
    for (u32 i=0;i<box_count;++i) {
        if (!canonical(box[i]) || box[i].id>=L_ITEMS || box[i].count>99) return L_INVALID;
        tx->box[i]=box[i];
    }
    for (u32 i=0;i<target_count;++i) {
        Slot w=want->slots[i];
        if (!w.id) continue;
        u32 need=w.count;
        need-=take(tx->remaining,target_count,w.id,need);
        u32 n=take(tx->donor,donor_count,w.id,need);
        need-=n; tx->direct_units+=n;
        n=take(tx->box,box_count,w.id,need);
        need-=n; tx->box_units+=n;
        tx->missing_units+=need;
        tx->target[i]=need==w.count?(Slot){0,0}:(Slot){w.id,(u16)(w.count-need)};
    }
    /* Withdrawals precede surplus deposits: a full box can still succeed when
       the desired loadout frees enough room. Cross-pouch items bypass the box. */
    for (u32 i=0;i<target_count;++i) {
        Slot s=tx->remaining[i];
        if (!s.id) continue;
        for (u32 j=0;j<box_count && s.count;++j) {
            Slot *b=&tx->box[j];
            if (b->id!=s.id || b->count>=99) continue;
            u32 n=99-b->count;
            if (n>s.count) n=s.count;
            b->count=(u16)(b->count+n);s.count=(u16)(s.count-n);
        }
        for (u32 j=0;j<box_count && s.count;++j) {
            Slot *b=&tx->box[j];
            if (b->id) continue;
            u32 n=s.count>99?99:s.count;
            *b=(Slot){s.id,(u16)n};s.count=(u16)(s.count-n);
        }
        if (s.count) return L_BOX_FULL;
    }
    return tx->missing_units?L_PARTIAL:L_OK;
}

void commit_loadout(Slot *target,u32 target_count,Slot *donor,u32 donor_count,
                    Slot *box,u32 box_count,const Transaction *tx) {
    for(u32 i=0;i<target_count;++i)
        if(target[i].id!=tx->target[i].id || target[i].count!=tx->target[i].count) target[i]=tx->target[i];
    for(u32 i=0;i<donor_count;++i)
        if(donor[i].id!=tx->donor[i].id || donor[i].count!=tx->donor[i].count) donor[i]=tx->donor[i];
    for(u32 i=0;i<box_count;++i)
        if(box[i].id!=tx->box[i].id || box[i].count!=tx->box[i].count) box[i]=tx->box[i];
}
