#!/usr/bin/env bash
# Shared, safe setup for terminal-capture scenes.  No ~/lab3 or shared /tmp inputs.
set -Eeuo pipefail

attacklab_prepare() {
    ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
    cd "$ROOT"
    export ATTACKLAB_WORKDIR="${ATTACKLAB_WORKDIR:-${ATTACKLAB_SCREEN_DIR:-}}"
    if [[ -z $ATTACKLAB_WORKDIR ]]; then
        local container
        container=$(mktemp -d /tmp/attacklab-screens.XXXXXX)
        ATTACKLAB_WORKDIR=$(bash tools/prepare_lab.sh "$container/lab")
    fi
    [[ -d $ATTACKLAB_WORKDIR && $ATTACKLAB_WORKDIR != / ]]
    local name
    for name in dark-calc dark-calc-nx dark-log malware; do
        [[ -f $ATTACKLAB_WORKDIR/$name && -x $ATTACKLAB_WORKDIR/$name ]]
        cmp -s -- "attack/$name" "$ATTACKLAB_WORKDIR/$name"
    done
    export ATTACKLAB_WORKDIR
    export ATTACKLAB_FIXTURE_DIR="${ATTACKLAB_FIXTURE_DIR:-$ATTACKLAB_WORKDIR/fixtures}"
    [[ $ATTACKLAB_FIXTURE_DIR != / ]]
    mkdir -p -- "$ATTACKLAB_FIXTURE_DIR"
}
