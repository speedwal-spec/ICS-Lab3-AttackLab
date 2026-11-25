# GDB session 4b: control case -- a 288-byte input also overwrites the canary.
set pagination off
set confirm off
set disable-randomization off
python
import os
gdb.execute("file " + os.path.join(os.environ["ATTACKLAB_WORKDIR"], "dark-log"))
end
break *input
python
gdb.execute("run < " + os.path.join(os.environ["ATTACKLAB_FIXTURE_DIR"], "smash.bin"))
end
nexti
nexti
nexti
nexti
nexti
printf "canary before input: "
p/x *(unsigned long *)($rbp - 0x8)
break *input+0x105
continue
printf "canary after 288-byte input: "
p/x *(unsigned long *)($rbp - 0x8)
printf "TLS canary: "
p/x *(unsigned long *)($fs_base + 0x28)
printf "\n### continue: the canary check must abort the process\n"
continue
printf "\n### inferior state\n"
info registers rip
bt
quit
