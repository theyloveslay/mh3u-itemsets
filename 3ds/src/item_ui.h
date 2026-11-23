#ifndef MH3U_ITEM_UI_H
#define MH3U_ITEM_UI_H
#include "set_service.h"
#include "native_rename.h"
enum { UI_CURRENT=0,UI_REGISTER=1,UI_REORDER=2,UI_UNREGISTER=3 };
enum { UI_BROWSE=0,UI_CONFIRM=1,UI_ACK=2,UI_KEYBOARD=3 };
typedef struct {
    u32 open,action,phase,selected,anchor,choice,preview_page,missing,help;
    RenameSession rename;
} ItemUI;
typedef struct {
    const char *title,*names[8];
    u32 valid_mask,selected_row,anchor_row,page,help,choice;
    u32 pouch_gunner,pouch_page,pouch_pages;
    Slot pouch[32];
} ItemFrame;
extern ItemUI item_ui;
extern BankStore item_store;
/* Character binding is explicit until the native character-load hook is mapped.
 * Passing >=3 unbinds storage and prevents edits/loadout application.
 */
void item_ui_bind(u32 character);
void item_ui_note_character(u32 character);
int item_character_applied(void *save);
void item_ui_set_io(const BankIO *io); /* test/integration injection; no live hook yet */
void item_ui_open(u32 action);
int item_ui_box_step(u8 *lobby);
const ItemFrame *item_ui_frame(void);
void item_draw_list(void *widget,const ItemFrame *);
void item_draw_preview(void *widget,const ItemFrame *);
void item_root_draw(void *root,u8 *state);
void item_draw_options(void *widget,u8 *state);
#endif
