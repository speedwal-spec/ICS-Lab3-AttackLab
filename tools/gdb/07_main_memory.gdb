# Required main machine-code memory observation and single-step rip evolution.
set pagination off
set confirm off
set disable-randomization off
python
import os
gdb.execute("file " + os.path.join(os.environ["ATTACKLAB_WORKDIR"], "dark-calc"))
end
break *main
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "eight.bin"))
end
printf "\n### x/9bx main: bytes in increasing virtual-memory addresses\n"
x/9bx main
printf "[0x401ac3,0x401ac4)  push rbp: 55\n"
printf "[0x401ac4,0x401ac7)  mov rbp,rsp: 48 89 e5\n"
printf "[0x401ac7,0x401acc)  mov eax,0: b8 00 00 00 00\n"
printf "\n### step the first three main instructions\n"
x/3i main
info registers rip rbp rsp
stepi
info registers rip rbp rsp
stepi
info registers rip rbp rsp
stepi
info registers rip rbp rsp
quit
