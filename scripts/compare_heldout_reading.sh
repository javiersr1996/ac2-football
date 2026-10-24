#!/usr/bin/env bash
# Compare the held-out artefacts committed in reports/heldout/ with a reproduction of the reading.
#
#   bash scripts/compare_heldout_reading.sh [--expect-diff FILE] <reproduced-dir> [committed-dir]
#
# The reproduction is `ac2fb heldout read --reports-dir <reproduced-dir>` run in a git worktree at
# the reading commit (the only place the held-out opens; see .github/workflows/full-build.yml).
# This script reads no data and no git: it says how many files it compared byte for byte and
# exits 1 if any differs, is missing from either side, or if there is none to compare.
#   committed-dir  default: reports/heldout/ of the repo this script is in.
#   --expect-diff FILE  accept the reproduction only if it differs from the committed files in
#                  exactly the way FILE says: the `diff` output of every differing file, each under
#                  a "== <name>" header, in name order, must equal FILE byte for byte. Any other
#                  difference, and no difference at all, fails. Without it every file must be equal.
set -euo pipefail

expect=""
if [ "${1:-}" = "--expect-diff" ]; then
  expect="$(cd "$(dirname "${2:?--expect-diff needs a file}")" && pwd)/$(basename "$2")"
  [ -f "$expect" ] || { echo "  - $2: no such expected-diff file"; exit 1; }
  shift 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Both directories as absolute paths first: the listing below changes directory.
reproduced="$(cd "${1:?usage: $0 <reproduced-dir> [committed-dir]}" && pwd)"
committed="$(cd "${2:-$here/reports/heldout}" && pwd)"

failed=0
compared=0
actual="$(mktemp)"
trap 'rm -f "$actual"' EXIT
names="$( (cd "$committed" && ls -A; cd "$reproduced" && ls -A) | sort -u)"
for name in $names; do
  if [ ! -f "$committed/$name" ]; then
    echo "  - $name: reproduced, but not committed"; failed=1; continue
  fi
  if [ ! -f "$reproduced/$name" ]; then
    echo "  - $name: committed, but not reproduced"; failed=1; continue
  fi
  compared=$((compared + 1))
  if ! cmp -s "$committed/$name" "$reproduced/$name"; then
    echo "  - $name: differs from the reproduction"
    [ -n "$expect" ] || failed=1
    # Name what differs: the first 20 differing lines, committed then reproduced.
    diff "$committed/$name" "$reproduced/$name" | grep '^[<>]' | head -n 40 | sed 's/^/      /' || true
    { echo "== $name"; diff "$committed/$name" "$reproduced/$name" || true; } >> "$actual"
  fi
done
if [ "$compared" -eq 0 ]; then
  echo "  - no file to compare"; failed=1
fi
if [ -n "$expect" ] && ! cmp -s "$expect" "$actual"; then
  echo "  - the differences are not exactly those pinned in $expect"; failed=1
fi
if [ "$failed" -ne 0 ]; then
  echo "heldout: FAILED ($compared files compared)"
  exit 1
fi
if [ -n "$expect" ]; then
  echo "verified: $compared files against the reproduction from the reading commit; the differences are exactly those pinned in $expect"
else
  echo "verified: $compared files byte for byte against the reproduction from the reading commit"
fi
echo "heldout: OK"
