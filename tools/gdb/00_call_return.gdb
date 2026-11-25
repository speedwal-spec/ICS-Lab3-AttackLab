# Required task-1 observations: call, prologue, leave and ret.
set pagination off
set confirm off
set disable-randomization off
python
import os
gdb.execute("file " + os.path.join(os.environ["ATTACKLAB_WORKDIR"], "dark-calc"))
end
break *main+9
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "eight.bin"))
end
printf "\n### Q4: main immediately before call input\n"
info registers rip rbp rsp
x/i $rip
printf "stack before call:\n"
x/2gx $rsp-8
stepi
printf "\n### Q4: first instruction of input after call\n"
info registers rip rbp rsp
printf "saved return address at [rsp] (later rbp+8):\n"
x/gx $rsp
printf "\n### Q2: each prologue instruction\n"
stepi
info registers rip rbp rsp
x/gx $rsp
stepi
info registers rip rbp rsp
stepi
info registers rip rbp rsp
printf "current rbp saved-slot and return-slot:\n"
x/2gx $rbp
printf "\n### Q5: step leave\n"
break *input+94
continue
info registers rip rbp rsp
x/3gx $rbp-8
stepi
info registers rip rbp rsp
printf "\n### Q5: step ret and return into caller\n"
stepi
info registers rip rbp rsp
bt
printf "\n### Q1: input is called by main\n"
disassemble /r main
quit
