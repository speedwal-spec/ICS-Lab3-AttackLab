# GDB session 2: dark-calc's dedicated executable stack and shellcode execution.
set pagination off
set confirm off
set disable-randomization off
file ~/lab3/dark-calc
break *main
run < /tmp/lab3-inputs/shellcode.bin
printf "\n### at main(), called through __wrap_main on the fixed stack\n"
info registers rip rbp rsp
bt
printf "\n### anonymous mapping for the fixed stack\n"
info proc mappings
printf "\n### break after gets(); inspect the injected shellcode\n"
break *input+0x28
continue
printf "buffer = rbp-0x10 = 0x%lx\n", $rbp - 0x10
printf "shellcode bytes:\n"
x/24bx $rbp - 0x10
printf "\n### disassemble the injected bytes\n"
x/6i $rbp - 0x10
printf "\n### saved return address now points back into the fixed stack\n"
x/4gx $rbp
printf "\n### watch grade_eval receive edi=4\n"
break *0x401a87
continue
info registers rdi rsp rbp rip
bt
printf "\n### continue to program exit\n"
continue
quit
