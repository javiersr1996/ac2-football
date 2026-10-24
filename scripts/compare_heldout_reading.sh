#!/usr/bin/env bash
# Compare the held-out artefacts committed in reports/heldout/ with a reproduction of the reading.
#
#   bash scripts/compare_heldout_reading.sh <reproduced-dir> [committed-dir]
#
# The reproduction is `ac2fb heldout read --reports-dir <reproduced-dir>` run in a git worktree at
# the reading commit (the only place the held-out opens; see .github/workflows/full-build.yml).
# This script reads no data and no git: it says how many files it compared byte for byte and
# exits 1 if any differs, is missing from either side, or if there is none to compare.
#   committed-dir  default: reports/heldout/ of the repo this script is in.
set -euo pipefail

reproduced="${1:?usage: $0 <reproduced-dir> [committed-dir]}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
committed="${2:-$here/reports/heldout}"

failed=0
compared=0
names="$( (cd "$committed" && ls; cd "$reproduced" && ls) | sort -u)"
for name in $names; do
  if [ ! -f "$committed/$name" ]; then
    echo "  - $name: reproduced, but not committed"; failed=1; continue
  fi
  if [ ! -f "$reproduced/$name" ]; then
    echo "  - $name: committed, but not reproduced"; failed=1; continue
  fi
  compared=$((compared + 1))
  if ! cmp -s "$committed/$name" "$reproduced/$name"; then
    echo "  - $name: differs from the reproduction"; failed=1
  fi
done
if [ "$compared" -eq 0 ]; then
  echo "  - no file to compare"; failed=1
fi
if [ "$failed" -ne 0 ]; then
  echo "heldout: FAILED ($compared files compared)"
  exit 1
fi
echo "verified: $compared files byte for byte against the reproduction from the reading commit"
echo "heldout: OK"
