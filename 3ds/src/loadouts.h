#ifndef MH3U_LOADOUTS_H
#define MH3U_LOADOUTS_H
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
enum { L_SLOTS=32, L_BOX=1000, L_SETS=24, L_ITEMS=0x5fd };
typedef struct { u16 id, count; } Slot;
typedef struct { u8 valid, gunner; u16 reserved; Slot slots[L_SLOTS]; } Loadout;
typedef struct { u8 limit, category, allowed, reserved; } ItemRule;
typedef struct {
    Slot target[L_SLOTS], donor[L_SLOTS], box[L_BOX];
    Slot remaining[L_SLOTS];
    u32 direct_units, box_units, missing_units;
} Transaction;
enum { L_OK=0, L_INVALID=1, L_WRONG_POUCH=2, L_PARTIAL=3, L_BOX_FULL=4 };
/* All arrays are native-endian. plan() never writes the caller's inventories.
   target_count/donor_count are 24 or 32 and opposite; box_count is unlocked slots.
   Commit after L_OK or L_PARTIAL. Shortages fill saved slots with available
   quantities, leaving completely unavailable slots empty. missing_units is
   the total shortfall. Invalid inputs and box-capacity failures do not commit.
*/
int plan_loadout(const Slot *target, u32 target_count,
                 const Slot *donor, u32 donor_count,
                 const Slot *box, u32 box_count,
                 const Loadout *want, const ItemRule *rules, Transaction *tx);
void commit_loadout(Slot *target, u32 target_count, Slot *donor, u32 donor_count,
                    Slot *box, u32 box_count, const Transaction *tx);
#endif
