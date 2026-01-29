# 📋 Operating System (QEMU) - Projekt-Fragebogen
## Template: 13-operating-system (C + Assembly + QEMU)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **OS Name** | |
| **Zweck** | Learning, Embedded, Research |
| **Zielarchitektur** | x86_64, ARM, RISC-V |

---

## A. OS-TYP & SCOPE

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | OS-Typ? | [ ] Monolithic [ ] Microkernel [ ] Exokernel [ ] Unikernel | |
| A2 | Scope? | [ ] Toy OS (Learning) [ ] Embedded [ ] Research [ ] Production | |
| A3 | Multitasking? | [ ] None [ ] Cooperative [ ] Preemptive | |
| A4 | Multi-User? | [ ] Ja [ ] Nein | |

---

## B. ARCHITEKTUR

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| B1 | Target Architecture? | [ ] x86_64 (empfohlen) [ ] i386 [ ] ARM64 [ ] RISC-V | |
| B2 | Boot Mode? | [ ] BIOS [ ] UEFI [ ] Both | |
| B3 | Bootloader? | [ ] Custom [ ] GRUB [ ] Limine | |
| B4 | Higher Half Kernel? | [ ] Ja [ ] Nein | |

---

## C. KERNEL FEATURES

| # | Frage | Benötigt? | Details |
|---|-------|-----------|---------|
| C1 | Memory Management? | [ ] Ja [ ] Nein | Physical, Virtual, Heap | |
| C2 | Paging? | [ ] Ja [ ] Nein | 4-level Paging | |
| C3 | Process Scheduler? | [ ] Ja [ ] Nein | Round Robin, Priority | |
| C4 | Interrupt Handling? | [ ] Ja [ ] Nein | IDT, IRQ | |
| C5 | System Calls? | [ ] Ja [ ] Nein | User → Kernel | |
| C6 | File System? | [ ] Ja [ ] Nein | FAT32, ext2, Custom | |
| C7 | Device Drivers? | [ ] Ja [ ] Nein | Keyboard, Screen | |
| C8 | Networking? | [ ] Ja [ ] Nein | TCP/IP Stack | |

---

## D. TECH-STACK ENTSCHEIDUNGEN

### Build System

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Build System? | [ ] Make (traditional) [ ] CMake [ ] Meson | |
| D2 | Cross Compiler? | [ ] GCC Cross [ ] Clang | |
| D3 | Assembler? | [ ] NASM [ ] GAS [ ] FASM | |
| D4 | Linker Script? | [ ] Custom (required) | |

### Languages

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D5 | Kernel Language? | [ ] C (traditional) [ ] C++ [ ] Rust [ ] Zig | |
| D6 | Assembly? | [ ] x86_64 AT&T [ ] x86_64 Intel [ ] ARM | |
| D7 | C Standard? | [ ] C11 [ ] C17 [ ] C23 | |
| D8 | Freestanding? | [ ] Ja (-ffreestanding) | |

### Emulation & Debugging

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D9 | Emulator? | [ ] QEMU (empfohlen) [ ] Bochs [ ] VirtualBox | |
| D10 | Debugger? | [ ] GDB (empfohlen) [ ] LLDB | |
| D11 | Serial Debug? | [ ] QEMU stdio [ ] COM1 | |
| D12 | Debug Symbols? | [ ] DWARF [ ] None | |

---

## E. USERSPACE (falls nötig)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Userspace? | [ ] Ja [ ] Kernel only | |
| E2 | Shell? | [ ] Custom [ ] Port existing | |
| E3 | C Library? | [ ] Custom [ ] Newlib [ ] musl | |
| E4 | ELF Loader? | [ ] Ja [ ] Nein | |

---

## F. HARDWARE SUPPORT

| # | Frage | Benötigt? |
|---|-------|-----------|
| F1 | VGA Text Mode? | [ ] Ja [ ] Nein |
| F2 | Framebuffer Graphics? | [ ] Ja [ ] Nein |
| F3 | PS/2 Keyboard? | [ ] Ja [ ] Nein |
| F4 | PS/2 Mouse? | [ ] Ja [ ] Nein |
| F5 | PCI Enumeration? | [ ] Ja [ ] Nein |
| F6 | ACPI? | [ ] Ja [ ] Nein |
| F7 | Timer (PIT/APIC)? | [ ] Ja [ ] Nein |
| F8 | RTC? | [ ] Ja [ ] Nein |

---

## G. TESTING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Unit Tests? | [ ] Host-side [ ] In-kernel [ ] None | |
| G2 | Integration Tests? | [ ] QEMU Scripts [ ] None | |
| G3 | CI? | [ ] GitHub Actions [ ] None | |

---

## H. DOCUMENTATION

| # | Frage | Benötigt? |
|---|-------|-----------|
| H1 | Boot Process Docs? | [ ] Ja [ ] Nein |
| H2 | Memory Map? | [ ] Ja [ ] Nein |
| H3 | Syscall Table? | [ ] Ja [ ] Nein |
| H4 | Architecture Docs? | [ ] Ja [ ] Nein |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Bootloader
- [ ] Kernel Entry
- [ ] GDT/IDT Setup
- [ ] Memory Manager
- [ ] Interrupt Handlers
- [ ] VGA Driver
- [ ] Keyboard Driver
- [ ] Linker Script
- [ ] Makefile
- [ ] QEMU Run Script
- [ ] GDB Debug Script

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "13-operating-system",
  "kernel": {
    "languages": ["C", "Assembly"],
    "architecture": "x86_64",
    "bootloader": "GRUB / Custom"
  },
  "build": {
    "system": "Make",
    "compiler": "GCC Cross-Compiler",
    "assembler": "NASM"
  },
  "emulation": {
    "emulator": "QEMU",
    "debugger": "GDB"
  },
  "features": {
    "memory": "Paging + Heap",
    "scheduling": "Preemptive",
    "drivers": ["VGA", "Keyboard", "Timer"]
  }
}
```
