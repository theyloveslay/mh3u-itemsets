#include "set_service.h"
static void copy_name(char *d,const char *s){for(u32 i=0;i<20;++i)d[i]=s[i];}
static int available(const BankStore *s,u32 i){return s && s->ready && i<L_SETS;}
static int replace(BankStore *s,const BankIO *io,u32 i,const Loadout *set,const char *name){
    Loadout old=s->collection.sets[i];char previous[20];copy_name(previous,s->collection.names[i]);
    s->collection.sets[i]=*set;copy_name(s->collection.names[i],name);
    if(store_save(s,io))return SET_SUCCESS;
    s->collection.sets[i]=old;copy_name(s->collection.names[i],previous);return SET_STORAGE_FAILED;
}
int set_register(BankStore *s,const BankIO *io,u32 i,const Loadout *pouch){
    if(!available(s,i) || !pouch || pouch->valid!=1 || pouch->gunner>1)return SET_BAD_INPUT;
    char name[20];copy_name(name,s->collection.names[i]);
    if(!s->collection.sets[i].valid)bank_default_name(name,i);
    return replace(s,io,i,pouch,name);
}
int set_rename(BankStore *s,const BankIO *io,u32 i,const char *name){
    if(!available(s,i) || !name || !name[0])return SET_BAD_INPUT;
    if(!s->collection.sets[i].valid)return SET_EMPTY;
    char copy[20]={0};u32 n=0;
    while(n<20 && name[n]){
        if((u8)name[n]<32 || n==19)return SET_BAD_INPUT;
        copy[n]=name[n];++n;
    }
    return replace(s,io,i,&s->collection.sets[i],copy);
}
int set_unregister(BankStore *s,const BankIO *io,u32 i){
    if(!available(s,i))return SET_BAD_INPUT;
    if(!s->collection.sets[i].valid)return SET_EMPTY;
    Loadout empty={0};char name[20];bank_default_name(name,i);
    return replace(s,io,i,&empty,name);
}
int set_reorder(BankStore *s,const BankIO *io,u32 from,u32 to){
    if(!available(s,from) || to>=L_SETS)return SET_BAD_INPUT;
    if(!s->collection.sets[from].valid)return SET_EMPTY;
    if(from==to)return SET_SUCCESS;
    Loadout a=s->collection.sets[from],b=s->collection.sets[to];char an[20],bn[20];
    copy_name(an,s->collection.names[from]);copy_name(bn,s->collection.names[to]);
    s->collection.sets[from]=b;s->collection.sets[to]=a;
    copy_name(s->collection.names[from],bn);copy_name(s->collection.names[to],an);
    if(store_save(s,io))return SET_SUCCESS;
    s->collection.sets[from]=a;s->collection.sets[to]=b;
    copy_name(s->collection.names[from],an);copy_name(s->collection.names[to],bn);
    return SET_STORAGE_FAILED;
}
