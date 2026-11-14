/* SPDX-License-Identifier: GPL-3.0-only */
OUTPUT_FORMAT(elf32-littlearm)
OUTPUT_ARCH(arm)
ENTRY(_start)
PHDRS
{
    image PT_LOAD FILEHDR PHDRS FLAGS(5); /* R-X, no writable image data. */
    stack PT_GNU_STACK FLAGS(6);         /* RW-, never executable. */
}
SECTIONS
{
    . = 0x10000 + SIZEOF_HEADERS;
    .text : ALIGN(4) { *(.text.start) *(.text .text.*) *(.rodata .rodata.*) } :image
    .ARM.attributes 0 : { *(.ARM.attributes) }
    /DISCARD/ : { *(.comment) *(.note.GNU-stack) }
}
