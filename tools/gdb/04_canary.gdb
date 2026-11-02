# GDB session 4a: dark-log canary is preserved while the return address is overwritten.
set pagination off
set confirm off
set disable-randomization off
file ~/lab3/dark-log
break *input
run < /tmp/lab3-inputs/canary.bin
printf "\n### input() entry\n"
info registers rbp rsp
printf "\n### step the prologue and the canary store\n"
nexti
nexti
nexti
nexti
nexti
printf "after prologue: rbp=0x%lx rsp=0x%lx\n", $rbp, $rsp
printf "stack canary at rbp-0x8 : "
p/x *(unsigned long *)($rbp - 0x8)
printf "TLS canary at fs:0x28   : "
p/x *(unsigned long *)($fs_base + 0x28)
printf "\n### run to the point just after the 128-byte memcpy\n"
break *input+0x105
continue
printf "len (rbp-0x20) = %d  (0x%x)\n", *(int *)($rbp - 0x20), *(int *)($rbp - 0x20)
printf "memcpy destination = logMsg + len = 0x%lx\n", $rbp - 0xa0 + *(int *)($rbp - 0x20)
printf "stack canary at rbp-0x8 : "
p/x *(unsigned long *)($rbp - 0x8)
printf "\n### the overwritten frame tail: saved rbp, return address, canary\n"
x/5gx $rbp - 0x8
printf "\n### continue into grade_eval(4)\n"
break *0x401677
continue
info registers rdi rsp rbp
bt
printf "\n### run to the end\n"
continue
info registers rip
quit
