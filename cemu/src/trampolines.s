    .text
    .balign 4
    .global original_box_step
original_box_step:
    stwu 1,-56(1)
    lis 12,0x021f
    ori 12,12,0x0e80
    mtctr 12
    bctr
    .global original_text
original_text:
    mflr 0
    lis 12,0x0214
    ori 12,12,0x1de4
    mtctr 12
    bctr
    .global original_character
original_character:
    mflr 0
    lis 12,0x020e
    ori 12,12,0x62b0
    mtctr 12
    bctr
    .global original_draw_options
original_draw_options:
    stwu 1,-32(1)
    lis 12,0x026a
    ori 12,12,0x6b84
    mtctr 12
    bctr
    .global original_draw_menu
original_draw_menu:
    stwu 1,-176(1)
    lis 12,0x0268
    ori 12,12,0x7d3c
    mtctr 12
    bctr
    .global original_root_draw
original_root_draw:
    stwu 1,-104(1)
    lis 12,0x0270
    ori 12,12,0xa73c
    mtctr 12
    bctr
    .global original_animation
original_animation:
    mflr 0
    lis 12,0x02ae
    ori 12,12,0x1e44
    mtctr 12
    bctr

    # Before an Item Box session, retain native UI entry/return behavior:
    # do not enter any C wrapper or create an extra stack frame. r3-r10,
    # LR, SP and every FPR reach the displaced native prologue unchanged.
    .macro box_guard name, native, wrapper
    .global \name
\name:
    lis 12,ui_box_enabled@ha
    lwz 12,ui_box_enabled@l(12)
    cmpwi 12,0
    beq \native
    b \wrapper
    .endm
    # Never call C or allocate a stack frame from the native text lookup.
    # Non-item-set requests tail-delegate with the original r3-r10 and LR.
    .global text_entry,text_hook
text_entry:
text_hook:
    lis 12,ui_box_enabled@ha
    lwz 12,ui_box_enabled@l(12)
    cmpwi 12,0
    beq original_text
    cmpwi 4,0x2e
    beq text_labels
    cmpwi 4,0x2f
    bne original_text
    lis 12,ui_text_ready@ha
    lwz 12,ui_text_ready@l(12)
    cmpwi 12,0
    beq original_text
    lis 12,ui_main_active@ha
    lwz 12,ui_main_active@l(12)
    cmpwi 12,0
    beq text_list
    addi 11,5,-180
    cmplwi 11,4
    bgt text_list
    slwi 11,11,2
    lis 12,ui_text_main@ha
    addi 12,12,ui_text_main@l
    lwzx 3,12,11
    blr
text_list:
    lis 12,ui_list_open@ha
    lwz 12,ui_list_open@l(12)
    cmpwi 12,0
    beq original_text
    addi 11,5,-0x114
    cmplwi 11,7
    bgt original_text
    slwi 11,11,2
    lis 12,ui_text_list@ha
    addi 12,12,ui_text_list@l
    lwzx 3,12,11
    blr
text_labels:
    cmpwi 5,395
    beq text_title
    cmpwi 5,392
    bne text_actions
    lis 12,ui_tavern@ha
    lwz 12,ui_tavern@l(12)
    cmpwi 12,0
    beq original_text
text_title:
    lis 12,ui_text_title@ha
    lwz 3,ui_text_title@l(12)
    blr
text_actions:
    addi 11,5,-433
    cmplwi 11,3
    bgt original_text
    slwi 11,11,2
    lis 12,ui_text_actions@ha
    addi 12,12,ui_text_actions@l
    lwzx 3,12,11
    blr
    box_guard options_entry,original_draw_options,draw_options
    box_guard menu_entry,original_draw_menu,draw_menu_entry
    box_guard root_entry,original_root_draw,root_draw

    # Transform interception is needed only while menu objects are shifted.
    # All startup/title/ordinary UI instances otherwise keep their native path.
    .global animation_entry
animation_entry:
    lis 12,shift_count@ha
    lwz 12,shift_count@l(12)
    cmpwi 12,0
    beq original_animation
    b animation_hook

    # Cafe/Gekko nonvolatile FPRs have a paired-single second lane that Clang's
    # ordinary PPC ABI does not save. draw_menu uses f28-f31. Preserve both
    # lanes with the same merge10 + stfs / lfs + lfd pattern used by MH3U.
    .global draw_menu_entry
draw_menu_entry:
    mflr 0
    stw 0,4(1)
    stwu 1,-96(1)
    stfd 28,16(1)
    stfd 29,32(1)
    stfd 30,48(1)
    stfd 31,64(1)
    .long 0x139ce4a0
    .long 0x13bdeca0
    .long 0x13def4a0
    .long 0x13fffca0
    stfs 28,24(1)
    stfs 29,40(1)
    stfs 30,56(1)
    stfs 31,72(1)
    bl draw_menu
    lfs 28,24(1)
    lfs 29,40(1)
    lfs 30,56(1)
    lfs 31,72(1)
    lfd 28,16(1)
    lfd 29,32(1)
    lfd 30,48(1)
    lfd 31,64(1)
    lwz 0,100(1)
    addi 1,1,96
    mtlr 0
    blr
