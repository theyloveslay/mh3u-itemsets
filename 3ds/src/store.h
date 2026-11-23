#ifndef MH3U_STORE_H
#define MH3U_STORE_H
#include "bank.h"
typedef struct {
    void *user;
    /* read: 1=file read, 0=not found, -1=other error. length starts at capacity.
     * write: 1 only after full write, close and durable flush/commit succeed.
     * Neither callback may re-enter store_load/store_save.
     */
    int (*read)(void *,u32 character,u32 bank,u8 *,u32 *length);
    int (*write)(void *,u32 character,u32 bank,const u8 *,u32 length);
} BankIO;
typedef struct {
    SetCollection collection;
    int bank_index,ready;
} BankStore;
int store_load(BankStore *,const BankIO *,u32 character);
int store_save(BankStore *,const BankIO *);
#endif
