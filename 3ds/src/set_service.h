#ifndef MH3U_SET_SERVICE_H
#define MH3U_SET_SERVICE_H
#include "store.h"
enum { SET_SUCCESS=0, SET_BAD_INPUT=1, SET_EMPTY=2, SET_STORAGE_FAILED=3 };
int set_register(BankStore *,const BankIO *,u32 index,const Loadout *pouch);
int set_rename(BankStore *,const BankIO *,u32 index,const char *name);
int set_reorder(BankStore *,const BankIO *,u32 from,u32 to);
int set_unregister(BankStore *,const BankIO *,u32 index);
#endif
