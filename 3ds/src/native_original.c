/* Research-only original entry points. An installed patch must replace these
 * with verified displaced-instruction trampolines to avoid recursive hooks.
 */
#include "native_original.h"
int original_box_input(u8 *p){return ((int (*)(u8 *))0x005e8d30)(p);}
void original_root_screen(void *p,u8 *s){((void (*)(void *,u8 *))0x003be3b0)(p,s);}
void original_options(void *p,u8 *s){((void (*)(void *,u8 *))0x002b24e0)(p,s);}
int original_apply_character(void *p){return ((int (*)(void *))0x002a2374)(p);}
void original_animation(void *p,const void *m,const void *v,u32 a){((void (*)(void *,const void *,const void *,u32))0x003e4a44)(p,m,v,a);}
void original_menu(void *p,u8 *s){((void (*)(void *,u8 *))0x00974fc0)(p,s);}
