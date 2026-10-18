#!/usr/bin/env bash
# Run a README block (quick or full) in a fresh temporary directory and check the result.
#
#   bash scripts/clean_clone_check.sh <quick|full>
#
# Environment:
#   AC2_REPO     what the README's `git clone` clones. Default: the GitHub URL in the README.
#                While the repo is private, set it to a local path (committed state only).
#   README_FILE  README to read the block from. Default: README.md next to this script's repo.
#   KEEP=1       do not delete the temporary directory.
#   TMPDIR       where mktemp creates the directory.
set -euo pipefail

mode="${1:-}"
case "$mode" in
  quick) expected_files=5; expected_silver=1 ;;
  full) expected_files=85; expected_silver=20 ;;
  *) echo "usage: $0 <quick|full>" >&2; exit 2 ;;
esac
quick_match=1874553

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readme="${README_FILE:-$here/README.md}"
github_url="https://github.com/javiersr1996/ac2-football"
repo="${AC2_REPO:-$github_url}"

# The lines between the markers, minus the code fences.
block="$(awk -v s="<!-- clean-clone:$mode:start -->" -v e="<!-- clean-clone:$mode:end -->" '
  $0 == s { on = 1; next }
  $0 == e { on = 0 }
  on && $0 !~ /^```/ { print }
' "$readme" | tr -d '\r')"
[ -n "$block" ] || { echo "FAIL: no $mode block in $readme" >&2; exit 2; }
[ "$(printf '%s\n' "$block" | wc -l)" -le 5 ] || { echo "FAIL: block has more than 5 commands" >&2; exit 2; }
# Only the clone source is swapped, and only when asked to.
block="${block//"$github_url"/$repo}"
[ "$repo" = "$github_url" ] || echo "note: cloning from $repo instead of $github_url"

work="$(mktemp -d)"
cleanup() { [ "${KEEP:-0}" = 1 ] || rm -rf "$work"; }
trap cleanup EXIT
echo "work dir: $work"
echo "--- $mode block ---"
printf '%s\n' "$block"
echo "-------------------"

fail() { echo "FAIL: $*" >&2; exit 1; }

start=$SECONDS
(cd "$work" && bash -euo pipefail -c "$block")
clone="$work/ac2-football"
[ -d "$clone/.git" ] || fail "the block did not leave a clone at $clone"
cd "$clone"

data="${FTBASE_DATA_ROOT:-data}"
receipt="$data/raw/opendata-football/_receipt.json"
[ -f "$receipt" ] || fail "no ingest receipt at $receipt"
grep -Eq '"failed": \[\]' "$receipt" || fail "the receipt lists failed files"
grep -Eq "\"verified\": $expected_files," "$receipt" || fail "verified is not $expected_files"
if [ "$mode" = quick ]; then
  grep -Eq "\"match_id\": $quick_match," "$receipt" || fail "the receipt is not for match $quick_match"
  grep -Eq "\"manifest_files\": 85" "$receipt" || fail "the receipt does not say PARTIAL $expected_files/85"
else
  grep -Eq '"match_id": null' "$receipt" || fail "the full receipt is partial"
fi
echo "receipt: verified=$expected_files failed=0 ($mode)"
grep -E '"downloaded"' "$receipt" || true

silver="$(find "$data/silver/frames" -name '*.parquet' | wc -l)"
[ "$silver" -eq "$expected_silver" ] || fail "silver has $silver matches, expected $expected_silver"
if [ "$mode" = quick ]; then
  [ -f "$data/silver/frames/$quick_match.parquet" ] || fail "silver lacks match $quick_match"
fi
echo "silver: $silver match(es)"

dirty="$(git status --porcelain)"
[ -z "$dirty" ] || fail "the clone is not clean:
$dirty"

echo "CLEAN CLONE OK in $((SECONDS - start)) s"
