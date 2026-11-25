#!/usr/bin/env python3
"""Build GDB stdin fixtures in a configurable, safely-created directory.

ATTACKLAB_FIXTURE_DIR must be absolute when set. Its default is the repository's
attacklab_fixtures directory. All generators finish in a temporary directory
before any fixture in the destination is replaced.
"""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def fixture_directory():
    configured = os.environ.get("ATTACKLAB_FIXTURE_DIR")
    if configured is not None:
        if not configured.strip() or not Path(configured).is_absolute():
            raise ValueError("ATTACKLAB_FIXTURE_DIR must be a non-empty absolute path")
        return Path(configured)
    return ROOT / "attacklab_fixtures"


def main():
    out = fixture_directory()
    parent = out.parent
    # Resolve the parent, not out: out may not exist yet and must not be a symlink.
    parent.mkdir(parents=True, exist_ok=True)
    parent = parent.resolve(strict=True)
    out = parent / out.name
    if out.is_symlink():
        raise RuntimeError(f"refusing symlink fixture directory: {out}")

    files = {
        "eight.bin": b"ABCDEFGH\n",
        "arith.bin": b"1+1\n",
        "empty.bin": b"\n",
        # The smash control keeps a valid length while overwriting the canary.
        "smash.bin": b"A" * 256 + struct.pack("<I", 0xA0) + b"B" * 20 + b"C" * 8 + b"\n",
    }
    files.update({f"len{n}.bin": b"1" * n + b"\n" for n in (20, 24, 32, 48)})
    payloads = {
        "shellcode.bin": "payload_dark.py",
        "canary.bin": "payload_canary.py",
        "overflow_system.bin": "payload.py",
    }

    # Create beside the destination so os.replace stays on the same filesystem.
    # A random temporary subdirectory avoids shared /tmp/lab3-inputs collisions.
    tmp = Path(tempfile.mkdtemp(prefix=".attacklab-fixtures-", dir=parent))
    try:
        for name, script in payloads.items():
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            proc = subprocess.run([sys.executable, str(ROOT / script)],
                                  cwd=ROOT, capture_output=True, timeout=15, env=env)
            if proc.returncode != 0:
                raise RuntimeError(f"{script} failed (rc={proc.returncode}):\n"
                                   + proc.stderr.decode("utf-8", "replace"))
            if not proc.stdout:
                raise RuntimeError(f"{script} produced an empty fixture")
            files[name] = proc.stdout
        for name, data in files.items():
            (tmp / name).write_bytes(data)

        out.mkdir(mode=0o700, exist_ok=True)
        if not out.is_dir() or out.is_symlink():
            raise RuntimeError(f"fixture destination is not a real directory: {out}")
        for name in files:
            os.replace(tmp / name, out / name)
        # Never sweep unknown files from a caller-selected directory. The
        # capture script uses a fresh directory, so it cannot see stale files.
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("wrote fixtures to", out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"make_inputs: {exc}", file=sys.stderr)
        sys.exit(1)
