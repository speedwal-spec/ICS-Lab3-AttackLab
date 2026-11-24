#!/bin/bash
# Prepare the fixtures the five capture scenes expect (run once per guest boot).
set -u
cd "$(dirname "$0")/../.." || exit 1
python3 tools/make_inputs.py
rm -rf "$HOME/lab3" && mkdir -p "$HOME/lab3"
cp attack/* "$HOME/lab3/"
chmod +x "$HOME/lab3"/*
python3 payload_canary.py > /tmp/lab3-inputs/canary.bin
python3 payload.py > /tmp/lab3-inputs/p5.bin
ls -l "$HOME/lab3" /tmp/lab3-inputs/eight.bin
