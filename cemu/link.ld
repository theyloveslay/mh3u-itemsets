ENTRY(plan_loadout)
SECTIONS {
  . = 0x01800000;
  .text : { *(.text*) }
  . = ALIGN(64);
  .rodata : { *(.rodata*) }
  . = ALIGN(64);
  .data : { *(.data*) }
  . = ALIGN(64);
  .bss : { *(.bss*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) }
}
