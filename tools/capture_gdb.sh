#!/usr/bin/env bash
# Capture GDB evidence into analysis/gdb/.
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
python3 tools/make_inputs.py || exit 1
mkdir -p analysis/gdb
run_gdb() {
  local script=$1 out=$2
  echo "== $script -> analysis/gdb/$out"
  gdb -q -batch -x "$script" > "analysis/gdb/$out" 2>&1
}
run_gdb tools/gdb/01_frame_and_main.gdb 01_frame_and_main.txt
run_gdb tools/gdb/02_fixed_stack.gdb 02_fixed_stack.txt
run_gdb tools/gdb/03_nx.gdb 03_nx.txt
run_gdb tools/gdb/04_canary.gdb 04_canary.txt
run_gdb tools/gdb/04b_canary_smash.gdb 04b_canary_smash.txt
run_gdb tools/gdb/05_system_epilogue.gdb 05_system_epilogue.txt
echo "done"
