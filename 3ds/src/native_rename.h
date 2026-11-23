#ifndef MH3U_NATIVE_RENAME_H
#define MH3U_NATIVE_RENAME_H
#include "loadouts.h"
typedef struct {u32 active;char text[20];} RenameSession;
int native_rename_begin(RenameSession *,const char *name);
/* 0=pending, 1=accepted, -1=cancelled/unavailable. */
int native_rename_poll(RenameSession *);
#endif
