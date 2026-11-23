/* US 3DS native Equipment Sets keyboard methods traced from 0x00613AF0.
 * UI entry/button legends still require the list controller and rendering hook.
 */
#include "native_rename.h"
#define WORD(a) (*(volatile u32 *)(a))
typedef void (*One)(void *);
int native_rename_begin(RenameSession *s,const char *name){
    if(!s || !name || s->active || (WORD(0x00b916c0)&4))return 0;
    u32 game=WORD(0x00c3b978),ui=WORD(0x00c406a0);
    if(!game || !ui)return 0;
    for(u32 i=0;i<20;++i)s->text[i]=0;
    WORD(0x00b916c0)|=4;
    ((One)0x00526268)((void *)ui);
    ((void (*)(void *,u32,const char *))0x00590540)((void *)game,6,name);
    s->active=1;return 1;
}
int native_rename_poll(RenameSession *s){
    if(!s || !s->active)return -1;
    u32 game=WORD(0x00c3b978),ui=WORD(0x00c406a0);int accepted=0;
    if(game){
        if(!((u32 (*)(void *))0x0058eb40)((void *)game))return 0;
        accepted=((int (*)(void *,void *,u32,u32,u32,u32,u32,u32))0x0058dbe4)
            ((void *)game,s->text,19,1,0,0xffffffffu,0xffffffffu,0xffffffffu);
    }
    WORD(0x00b916c0)&=~4u;s->active=0;s->text[19]=0;
    if(ui)((One)0x00525dbc)((void *)ui);
    return accepted && s->text[0]?1:-1;
}
