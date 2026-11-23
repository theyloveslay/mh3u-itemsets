/* Existing Cemu M3LD v1/v2 format, encoded independently of CPU byte order. */
#include "bank.h"
enum { MAGIC=0x4d334c44, HEADER=48, RECORD=132, NAMES=3216 };
static u16 be16(const u8 *p){return (u16)(((u16)p[0]<<8)|p[1]);}
static u32 be32(const u8 *p){return ((u32)be16(p)<<16)|be16(p+2);}
static void put16(u8 *p,u16 v){p[0]=(u8)(v>>8);p[1]=(u8)v;}
static void put32(u8 *p,u32 v){put16(p,(u16)(v>>16));put16(p+2,(u16)v);}
static u32 checksum(const u8 *p,u32 length){
    u32 value=2166136261u;
    for(u32 i=0;i<length;++i)value=(value^((i>=16 && i<20)?0:p[i]))*16777619u;
    return value;
}
static void number(char *name,u32 n){
    for(u32 j=0;j<20;++j)name[j]=0;
    name[0]='S';name[1]='e';name[2]='t';name[3]=' ';
    u32 at=4;if(n>=10)name[at++]=(char)('0'+n/10);name[at]=(char)('0'+n%10);
}
void bank_default_name(char name[BANK_NAME_BYTES],u32 index){number(name,index+1);}
void bank_defaults(SetCollection *out,u32 character){
    u8 *p=(u8 *)out;for(u32 i=0;i<sizeof(*out);++i)p[i]=0;
    out->character=character;
    for(u32 i=0;i<L_SETS;++i)number(out->names[i],i+1);
}
int bank_newer(u32 candidate,u32 baseline){
    u32 distance=candidate-baseline;return distance && distance<0x80000000u;
}
int bank_decode(const u8 *wire,u32 length,u32 character,SetCollection *out){
    if(!wire || !out || character>2 || (length!=BANK_BYTES && length!=BANK_V1_BYTES))return 0;
    u32 version=be32(wire+4),count=version==1?20:24;
    if(be32(wire)!=MAGIC || be32(wire+8)!=character ||
       !((version==1 && length==BANK_V1_BYTES)||(version==2 && length==BANK_BYTES)) ||
       be32(wire+16)!=checksum(wire,length))return 0;
    for(u32 i=0;i<count;++i){const u8 *p=wire+HEADER+i*RECORD;if(p[0]>1 || p[1]>1)return 0;}
    bank_defaults(out,character);out->sequence=be32(wire+12);
    for(u32 i=0;i<count;++i){
        const u8 *p=wire+HEADER+i*RECORD;Loadout *s=&out->sets[i];
        s->valid=p[0];s->gunner=p[1];s->reserved=be16(p+2);
        for(u32 j=0;j<32;++j){s->slots[j].id=be16(p+4+j*4);s->slots[j].count=be16(p+6+j*4);}
    }
    if(version==2)for(u32 i=0;i<L_SETS;++i){
        char *name=out->names[i];const u8 *p=wire+NAMES+i*20;
        for(u32 j=0;j<19;++j)name[j]=(char)p[j];name[19]=0;
        const char *prefix="Item Set ";u32 j=0;while(j<9 && name[j]==prefix[j])++j;
        if(j==9 && name[9]>='0' && name[9]<='2' && name[10]>='0' && name[10]<='9' && !name[11]){
            u32 n=(u32)(name[9]-'0')*10+(u32)(name[10]-'0');if(n>=1 && n<=L_SETS)number(name,n);
        }
    }
    return 1;
}
int bank_encode(const SetCollection *in,u8 wire[BANK_BYTES]){
    if(!in || !wire || in->character>2)return 0;
    for(u32 i=0;i<L_SETS;++i)if(in->sets[i].valid>1 || in->sets[i].gunner>1)return 0;
    for(u32 i=0;i<BANK_BYTES;++i)wire[i]=0;
    put32(wire,MAGIC);put32(wire+4,2);put32(wire+8,in->character);put32(wire+12,in->sequence);
    for(u32 i=0;i<L_SETS;++i){
        u8 *p=wire+HEADER+i*RECORD;const Loadout *s=&in->sets[i];
        p[0]=s->valid;p[1]=s->gunner;put16(p+2,s->reserved);
        for(u32 j=0;j<32;++j){put16(p+4+j*4,s->slots[j].id);put16(p+6+j*4,s->slots[j].count);}
        for(u32 j=0;j<19;++j)wire[NAMES+i*20+j]=(u8)in->names[i][j];
    }
    put32(wire+16,checksum(wire,BANK_BYTES));return 1;
}
