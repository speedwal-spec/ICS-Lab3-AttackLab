#!/usr/bin/env bash
# Prepare current fixtures for the five capture scenes.  Existing directories
# are verified and reused; a fresh default is an isolated mktemp work copy.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
attacklab_prepare
printf 'ABCDEFGH\n' > "$ATTACKLAB_FIXTURE_DIR/eight.bin"
python3 tools/make_inputs.py
python3 payload_canary.py > "$ATTACKLAB_FIXTURE_DIR/canary.bin"
python3 payload.py > "$ATTACKLAB_FIXTURE_DIR/p5.bin"
printf 'ATTACKLAB_WORKDIR=%s\nATTACKLAB_FIXTURE_DIR=%s\n' \
    "$ATTACKLAB_WORKDIR" "$ATTACKLAB_FIXTURE_DIR"
ls -l -- "$ATTACKLAB_WORKDIR/dark-calc" "$ATTACKLAB_WORKDIR/dark-calc-nx" \
    "$ATTACKLAB_WORKDIR/dark-log" "$ATTACKLAB_WORKDIR/malware" \
    "$ATTACKLAB_FIXTURE_DIR/eight.bin"
