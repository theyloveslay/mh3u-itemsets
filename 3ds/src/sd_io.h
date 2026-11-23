#ifndef MH3U_SD_IO_H
#define MH3U_SD_IO_H
#include "store.h"
typedef struct {u32 session;} SdSession;
/* Dedicated fs:USER session; files at SD root use the Cemu basenames.
 * No game save archive, native save client or emulator host API is used.
 */
void sd_bank_io(BankIO *io,SdSession *session);
/* Diagnostic-only fixed filename; never opens a bank or game-save path. */
int sd_write_layout_report(const u8 *data,u32 length);
#endif
