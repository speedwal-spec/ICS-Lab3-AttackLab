# Required length-test stack observations at the instruction after gets().
set pagination off
set confirm off
set disable-randomization off
python
import os
gdb.execute("file " + os.path.join(os.environ["ATTACKLAB_WORKDIR"], "dark-calc"))
end
break *input+0x28
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "len20.bin"))
end
printf "\n### n=20 after gets: saved rbp overwritten, saved return address intact\n"
x/4gx $rbp-0x10
info registers rbp rsp
bt
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "len32.bin"))
end
printf "\n### n=32 after gets: saved rbp and saved return address overwritten\n"
x/4gx $rbp-0x10
info registers rbp rsp
bt
printf "\n### n=24 crash mechanism: NUL clears the lowest return-address byte\n"
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "len24.bin"))
end
continue
printf "SIGBUS observed at the computed return address 0x401a00; do not continue after the fatal signal.\n"
info registers rip rbp rsp
x/i $rip
bt
printf "\n### n=48 crash occurs inside gets at the guard page\n"
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "len48.bin"))
end
info registers rip rbp rsp
bt
quit
