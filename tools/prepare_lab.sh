#!/usr/bin/env bash
# Verify the supplied course assets, then prepare an isolated executable copy.
# stdout is intentionally only the absolute work-directory path for scripting.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
export LC_ALL=C

sha256sum --check --strict --status - <<'EOF'
a9c3d4a5eed6a937e85884f6a53faa39613d49e04792e2c411620fcc74f79097  attack/dark-calc
86c2c8dfaf4a89eb7a1396d9731bfb7ee085f0b45c86687b41547a30b5b1c613  attack/dark-calc-nx
9a4479f2a522d377055b54d328d5c0e0f3ca1327708ac792028ec03cadaee31d  attack/dark-log
03289add49f13e8573d125c8949bd88c9892e84f205802613a6baa2318fb18bc  attack/malware
EOF

if (($# > 1)); then
    printf 'usage: bash tools/prepare_lab.sh [new-work-directory]\n' >&2
    exit 2
fi
if (($# == 1)); then
    dest=$1
    if [[ $dest != /* ]]; then
        printf 'work directory must be absolute: %s\n' "$dest" >&2
        exit 2
    fi
    if [[ -e $dest ]]; then
        printf 'refusing existing work directory: %s\n' "$dest" >&2
        exit 1
    fi
    parent=$(dirname -- "$dest")
    base=$(basename -- "$dest")
    if [[ ! -d $parent || $base == '.' || $base == '..' || $dest == '/' ]]; then
        printf 'invalid work directory: %s\n' "$dest" >&2
        exit 1
    fi
    mkdir -- "$dest"
else
    dest=$(mktemp -d /tmp/attacklab-lab.XXXXXXXX)
fi

for name in dark-calc dark-calc-nx dark-log malware; do
    install -m 755 -- "attack/$name" "$dest/$name"
done
printf '%s\n' "$dest"
