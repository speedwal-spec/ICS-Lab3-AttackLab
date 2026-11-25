# GDB session 5: where does dark-calc go after payload.py's system() returns?
set pagination off
set confirm off
set disable-randomization off
python
import os
gdb.execute("file " + os.path.join(os.environ["ATTACKLAB_WORKDIR"], "dark-calc"))
gdb.execute("cd " + os.environ["ATTACKLAB_WORKDIR"])
end
# Run from the isolated directory so ./malware resolves without using ~/lab3.
set environment TERM=xterm
break *0x401a6b
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "overflow_system.bin"))
end
printf "\n### returned into eval's system call site\n"
info registers rip rdi rsp
x/s 0x6030d0
printf "\n### after system() returns: main's fixed frame pointer is preserved\n"
break *0x401a75
continue
info registers rip rbp rsp
printf "\n### eval's leave restores the wrapper return path; the inferior exits normally\n"
continue
printf "\n### clean process termination confirmed; no register state remains after exit\n"
quit
