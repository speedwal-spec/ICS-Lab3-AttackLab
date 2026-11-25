#!/usr/bin/env python3
"""Record the arithmetic-command-substitution observation with separate streams."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from run_evidence import prepare_attack

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "logs" / "command_substitution.txt"
INPUT = b"$(./malware)\n"
EXPECTED = b"You have successfully detonated the bomb! Congratulations!"


def main():
    with tempfile.TemporaryDirectory(prefix="attacklab-command-observation-") as tmp:
        lab = prepare_attack(tmp)
        proc = subprocess.run([str(lab / "dark-calc")], cwd=lab, input=INPUT,
                              capture_output=True, timeout=15,
                              env=dict(os.environ, TERM="xterm"))
    text = (f"input=$(./malware) ({len(INPUT) - 1} bytes)\n"
            f"target exit status: {proc.returncode}\n"
            "--- stdout ---\n" + proc.stdout.decode("utf-8", "replace")
            + "--- stderr ---\n" + proc.stderr.decode("utf-8", "replace")
            + "\nThe expected malware banner is in stderr, not stdout; "
            + "this observation does not pass the stdout-only CI predicate.\n")
    if EXPECTED not in proc.stderr or EXPECTED in proc.stdout:
        raise RuntimeError("unexpected command-substitution output streams; inspect before reporting")
    fd, temporary = tempfile.mkstemp(prefix=OUT.name + ".", dir=OUT.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, OUT)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    print(text, end="")


if __name__ == "__main__":
    main()
