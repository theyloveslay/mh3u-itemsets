#ifndef MH3U_NATIVE_ORIGINAL_H
#define MH3U_NATIVE_ORIGINAL_H
#include "loadouts.h"
int original_box_input(u8 *lobby);
void original_root_screen(void *root,u8 *state);
void original_options(void *widget,u8 *state);
int original_apply_character(void *save);
void original_animation(void *instance,const void *parent_matrix,const void *viewport,u32 native_arg4);
void original_menu(void *widget,u8 *state);
#endif
