/* Altered minimal bindings based on devkitPro/libctru's svc.s / svc.h.
 * See THIRD_PARTY.md. No libctru initialization or global state is used.
 */
.syntax unified
.arm
.text
.global mhl_ipc_buffer
.type mhl_ipc_buffer,%function
mhl_ipc_buffer:
    mrc p15,0,r0,c13,c0,3
    add r0,r0,#0x80
    bx lr
.global mhl_connect
.type mhl_connect,%function
mhl_connect:
    push {r0}
    svc #0x2d
    pop {r3}
    str r1,[r3]
    bx lr
.global mhl_send
.type mhl_send,%function
mhl_send:
    svc #0x32
    bx lr
.global mhl_close
.type mhl_close,%function
mhl_close:
    svc #0x23
    bx lr

/* Integer-register wrappers around VFP arithmetic and the native hard-float
 * position setter. C payload ABI remains soft-float; s0/s1 are volatile. */
.fpu vfp
.global item_add_float
.type item_add_float,%function
item_add_float:
    vmov s0,r0
    vmov s1,r1
    vadd.f32 s0,s0,s1
    vmov r0,s0
    bx lr
.global item_mul_float
.type item_mul_float,%function
item_mul_float:
    vmov s0,r0
    vmov s1,r1
    vmul.f32 s0,s0,s1
    vmov r0,s0
    bx lr
.global item_int_float
.type item_int_float,%function
item_int_float:
    vmov s0,r0
    vcvt.f32.s32 s0,s0
    vmov r0,s0
    bx lr
.global item_set_inst_y
.type item_set_inst_y,%function
item_set_inst_y:
    vmov s0,r1
    ldr r12,=0x00292e68
    bx r12

/* Bounded diagnostic reads: query each memory region before dereferencing.
 * svcQueryMemory returns base/size/permissions in r1/r2/r3. */
.global item_memory_readable
.type item_memory_readable,%function
item_memory_readable:
    push {r4-r8,lr}
    mov r6,r0
    mov r7,r1
    mov r2,r0
    svc #0x02
    cmp r0,#0
    bmi 1f
    cmp r6,r1
    blo 1f
    adds r8,r6,r7
    bcs 1f
    sub r8,r8,r1
    cmp r8,r2
    bhi 1f
    tst r3,#1
    moveq r0,#0
    movne r0,#1
    pop {r4-r8,pc}
1:
    mov r0,#0
    pop {r4-r8,pc}
