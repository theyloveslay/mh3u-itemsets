#ifndef MH3U_BANK_H
#define MH3U_BANK_H
#include "loadouts.h"
enum { BANK_V1_BYTES=2688, BANK_BYTES=3712, BANK_NAME_BYTES=20 };
typedef struct {
    u32 character,sequence;
    Loadout sets[L_SETS];
    char names[L_SETS][BANK_NAME_BYTES];
} SetCollection;
/* Cemu v2 wire format: big endian on every platform. Decode validates before
 * touching output. v1 upgrades the old 20-set format with default names.
 * expected_character is a zero-based save slot (0,1,2), not an account ID.
 */
int bank_decode(const u8 *wire,u32 length,u32 expected_character,SetCollection *out);
int bank_encode(const SetCollection *in,u8 wire[BANK_BYTES]);
int bank_newer(u32 candidate,u32 baseline);
void bank_defaults(SetCollection *out,u32 character);
void bank_default_name(char name[BANK_NAME_BYTES],u32 index);
#endif
