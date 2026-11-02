# GDB session 5: where does dark-calc go after payload.py's system() returns?
set pagination off
set confirm off
set disable-randomization off
file ~/lab3/dark-calc
break *0x401a6b
run < /tmp/lab3-inputs/overflow_system.bin
printf "\n### returned into eval's system call site\n"
info registers rip rdi rsp
x/s 0x6030d0
printf "\n### after system() returns: the frame pointer is attacker-controlled\n"
break *0x401a75
continue
info registers rip rbp rsp
printf "\n### let eval's epilogue run to its natural end\n"
continue
info registers rip
bt
quit
