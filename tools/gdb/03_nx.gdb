# GDB session 3: dark-calc-nx has a non-executable stack (NX).
set pagination off
set confirm off
set disable-randomization off
file ~/lab3/dark-calc-nx
break *input
run < /tmp/lab3-inputs/shellcode.bin
nexti
nexti
nexti
printf "\n### input() frame on the ordinary thread stack (NX)\n"
info registers rbp rsp
printf "buffer = rbp-0x10 = 0x%lx\n", $rbp - 0x10
printf "\n### the thread stack mapping has no execute permission\n"
info proc mappings
printf "\n### force the CPU to fetch from the stack buffer\n"
break *input+0x28
continue
x/16bx $rbp - 0x10
set $pc = $rbp - 0x10
x/4i $pc
stepi
printf "\n### after stepi: the fetch faulted, so the stack is not executable\n"
info registers rip
x/i $pc
bt
quit
