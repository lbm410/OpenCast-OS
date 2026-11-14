/* SPDX-License-Identifier: GPL-3.0-only
 * Local build experiment. Never deployed or executed by the build script.
 * Linux ARM EABI: r7 = syscall, r0-r2 = arguments, svc 0.
 */
.syntax unified
.arch armv6kz
.arm
.eabi_attribute 28, 0 /* Base AAPCS; no VFP argument registers. */
.section .text.start, "ax", %progbits
.balign 4
.global _start
.type _start, %function
_start:
    mov r0, #1                 /* Inherited stdout; no file is opened. */
    adr r1, marker
    mov r2, #marker_length
    mov r7, #4                 /* __NR_write: exactly one attempt. */
    svc #0
    cmp r0, #marker_length
    moveq r0, #0               /* A full write reports success. */
    movne r0, #1               /* Short/error write: no retries. */
    mov r7, #1                 /* __NR_exit: this program creates no threads. */
    svc #0
    udf #0                    /* Fail closed if exit unexpectedly returns. */
.size _start, . - _start
.type marker, %object
marker:
    .ascii "OPENCAST_NATIVE_PROBE_1\n"
.set marker_length, . - marker
.size marker, marker_length
.section .note.GNU-stack, "", %progbits
