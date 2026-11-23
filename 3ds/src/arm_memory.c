/* Freestanding ARM EABI entry points used for structure assignment. */
#include "loadouts.h"
void __aeabi_memcpy(void *to,const void *from,u32 n){
    u8 *d=to;const u8 *s=from;for(u32 i=0;i<n;++i)d[i]=s[i];
}
void __aeabi_memcpy4(void *to,const void *from,u32 n){__aeabi_memcpy(to,from,n);}
void __aeabi_memmove4(void *to,const void *from,u32 n){
    u8 *d=to;const u8 *s=from;
    if((u32)d>(u32)s){while(n){--n;d[n]=s[n];}}
    else __aeabi_memcpy(to,from,n);
}
void __aeabi_memclr8(void *to,u32 n){u8 *d=to;for(u32 i=0;i<n;++i)d[i]=0;}
