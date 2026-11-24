#!/bin/bash
# Scene 5: payload.py -> dark-calc -> sh -c ./malware -> malware.
set -u
cd "$(dirname "$0")/../.." || exit 1
python3 payload.py > /tmp/lab3-inputs/p5.bin
( cd "$HOME/lab3" && ./dark-calc < /tmp/lab3-inputs/p5.bin )
