#!/usr/bin/env bash
# Capture GDB evidence into analysis/gdb/ with fresh, atomic output files.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
tmp=''
lab_root="$(mktemp -d /tmp/attacklab-gdb.XXXXXXXX)"
trap 'rm -rf -- "$lab_root"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

workdir="$(bash tools/prepare_lab.sh "$lab_root/lab")"
if [ -z "$workdir" ] || [ ! -d "$workdir" ]; then
  echo "prepare_lab.sh did not create a work directory" >&2
  exit 1
fi
ATTACKLAB_WORKDIR="$workdir"
ATTACKLAB_FIXTURE_DIR="$lab_root/fixtures"
export ATTACKLAB_WORKDIR ATTACKLAB_FIXTURE_DIR
python3 tools/make_inputs.py
mkdir -p analysis/gdb

run_gdb() {
  local script=$1 out=$2 tmp
  out="analysis/gdb/$out"
  tmp="$(mktemp "$out.tmp.XXXXXX")"
  trap 'rm -f -- "$tmp"; rm -rf -- "$lab_root"' EXIT
  echo "== $script -> $out"
  # The same fixture path is visible to the script and its inferior process.
  if ATTACKLAB_FIXTURE_DIR="$ATTACKLAB_FIXTURE_DIR" \
      ATTACKLAB_WORKDIR="$ATTACKLAB_WORKDIR" \
      timeout 30s gdb -q -nx -batch -x "$script" > "$tmp" 2>&1; then
    if [ ! -s "$tmp" ]; then
      rm -f -- "$tmp" "$out"
      echo "gdb produced no evidence for $script" >&2
      return 1
    fi
    mv -f -- "$tmp" "$out"
    trap 'rm -rf -- "$lab_root"' EXIT
  else
    local status=$?
    rm -f -- "$tmp" "$out"
    echo "gdb failed for $script (exit $status)" >&2
    return "$status"
  fi
}

run_gdb tools/gdb/00_call_return.gdb 00_call_return.txt
run_gdb tools/gdb/01_frame_and_main.gdb 01_frame_and_main.txt
run_gdb tools/gdb/02_fixed_stack.gdb 02_fixed_stack.txt
run_gdb tools/gdb/03_nx.gdb 03_nx.txt
run_gdb tools/gdb/04_canary.gdb 04_canary.txt
run_gdb tools/gdb/04b_canary_smash.gdb 04b_canary_smash.txt
run_gdb tools/gdb/05_system_epilogue.gdb 05_system_epilogue.txt
run_gdb tools/gdb/06_length_overflow.gdb 06_length_overflow.txt
run_gdb tools/gdb/07_main_memory.gdb 07_main_memory.txt
echo "done"
