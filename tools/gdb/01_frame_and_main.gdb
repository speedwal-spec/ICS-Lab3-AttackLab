# GDB session 1: observe the input() stack frame and main's machine code (dark-calc).
set pagination off
set confirm off
set disable-randomization off
file ~/lab3/dark-calc
break *input
run < /tmp/lab3-inputs/eight.bin
printf "\n### stopped at input() entry, before the prologue runs\n"
info registers rip rbp rsp rdi rsi
printf "\n### instructions at entry\n"
x/8i $pc
printf "\n### caller frame (main) before the prologue\n"
up
info registers rbp rsp
down
printf "\n### single-step the prologue: push rbp; mov rbp,rsp; sub rsp,0x10\n"
nexti
nexti
nexti
info registers rbp rsp
printf "\n### frame geometry\n"
printf "expression buffer      = rbp-0x10 = 0x%lx\n", $rbp - 0x10
printf "saved rbp slot         = rbp      = 0x%lx\n", $rbp
printf "saved return address   = rbp+8    = 0x%lx\n", $rbp + 8
set $buf = (unsigned long)$rbp - 0x10
printf "fixed_stack_top        = 0x721000801000\n"
printf "buffer-to-guard-page   = %ld bytes\n", 0x721000801000 - $buf
printf "\n### stack contents at the frame before gets()\n"
x/6gx $rbp - 0x10
printf "\n### break after gets() and read the buffer back\n"
break *input+0x28
continue
info registers rbp rsp
printf "buffer contents: "
x/s $rbp - 0x10
printf "saved rbp value = 0x%lx\n", *(unsigned long *)$rbp
printf "return address  = 0x%lx\n", *(unsigned long *)($rbp + 8)
printf "\n### backtrace\n"
bt
printf "\n### main's machine code with raw bytes\n"
disassemble /r main
printf "\n### main's instructions\n"
x/14i main
printf "\n### done\n"
quit
