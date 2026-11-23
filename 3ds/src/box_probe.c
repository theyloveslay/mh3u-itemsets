/* Research adapter. This is called only by tests, not installed into a game.
 * Native menu input is executed; drawing/storage/list actions are not ported.
 */
#include "loadouts.h"
#include "native_original.h"
#define HALF(p) (*(volatile u16 *)(p))
#define WORD(p) (*(volatile u32 *)(p))
typedef int (*NativeInput)(u8 *);
int probe_box_menu(u8 *lobby) {
    static const u16 order[7]={0,1,2,6,3,4,5};
    static const u16 position[7]={0,1,2,4,5,6,3};
    u8 *s=lobby+0x67d0;
    int tavern=s[2]==1;
    if(s[2]>1)return original_box_input(lobby);
    HALF(0x00b9b69c)=4;HALF(0x00b9b6aa)=433;HALF(0x00b9b6b8)=180;
    if(tavern)HALF(s+12)=4;
    else if(HALF(s+12)==6)HALF(s+12)=7;
    u16 before=HALF(s+6),level=HALF(s+10),saved[3];
    const u32 tables[3]={0x00b9b696,0x00b9b6a4,0x00b9b6b2};
    if(tavern)for(u32 i=0;i<3;++i){saved[i]=HALF(tables[i]);HALF(tables[i])=HALF(tables[i]+6);}
    int result=original_box_input(lobby);
    if(tavern)for(u32 i=0;i<3;++i)HALF(tables[i])=saved[i];
    u16 after=HALF(s+6);
    if(!tavern && level==0 && HALF(s+10)==0 && before<7 && after!=before){
        u32 delta=(after-before+7)%7;
        if(delta==1 || delta==6)HALF(s+6)=order[(position[before]+(delta==1?1:6))%7];
    }
    /* A distinct probe result proves that all four actions can be dispatched.
       No native caller is patched to use this provisional return contract. */
    if(result==1 && HALF(s+6)==(tavern?3:6))return 0x100+HALF(s+8);
    return result;
}

/* Native option emission probe. Eight physical slots include the separator
 * at slot 3. Borrow it for the new logical row 6; restore widget arrays after
 * emission. GUI geometry/separator animation still needs a live render check.
 */
void probe_room_options(u8 *widget,u8 *state) {
    u32 background=WORD(widget+0x224),text=WORD(widget+0x230);
    if(state[2] || HALF(state+12)!=7 || !background || !text){
        original_options(widget,state);return;
    }
    u32 arrays[2]={background,text},saved[4];
    for(u32 i=0;i<2;++i){
        saved[i*2]=WORD(arrays[i]+12);saved[i*2+1]=WORD(arrays[i]+28);
        WORD(arrays[i]+12)=saved[i*2+1];WORD(arrays[i]+28)=saved[i*2];
    }
    original_options(widget,state);
    for(u32 i=0;i<2;++i){
        WORD(arrays[i]+12)=saved[i*2];WORD(arrays[i]+28)=saved[i*2+1];
    }
}
