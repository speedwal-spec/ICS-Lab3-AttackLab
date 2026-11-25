#!/usr/bin/env bash
# Scene 5: payload.py -> dark-calc -> sh -c ./malware -> malware.
# This scene intentionally propagates the real target's exit status.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
attacklab_prepare
python3 payload.py > "$ATTACKLAB_FIXTURE_DIR/p5.bin"
cd "$ATTACKLAB_WORKDIR"
export TERM="${TERM:-xterm}"
"./dark-calc" < "$ATTACKLAB_FIXTURE_DIR/p5.bin"
