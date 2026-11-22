#!/usr/bin/env bash
# Privacy check over the WHOLE git history (WORKFLOW 9.3; CLAUDE.md §7; doc 19).
# Fails if any commit ever added video, images (other than the allow-listed synthetic figures),
# datasets, model weights or archives, or a blob over 1 MB, or if an e-mail address appears in
# file contents (commit author metadata is not file content). Also checks that the folders that
# hold footage, data and weights are git-ignored.
# Usage (repo root, Git Bash):  bash scripts/privacy_check.sh
set -u
cd "$(git rev-parse --show-toplevel)"
fail=0

# Committed figures checked by eye on 2026-11-22: synthetic charts / dashboard screenshots, no people.
ALLOW='^reports/figures/(crowdsim_v1_spring_fest_day1_regimea_seed2027-0|ms2_live_page_synthetic_replay)\.png$'
MEDIA='\.(mp4|avi|mov|mkv|webm|jpg|jpeg|png|gif|bmp|tif|tiff|webp|parquet|csv|npy|npz|onnx|pt|pth|pkl|joblib|h5|zip|tar|gz|7z|mat)$'

echo "commits scanned: $(git rev-list --all | wc -l)"

hits=$(git log --all --pretty=format: --name-only --diff-filter=A | sort -u | grep -iE "$MEDIA" | grep -vE "$ALLOW" || true)
if [ -n "$hits" ]; then echo "FAIL media/data/weight files in history:"; echo "$hits"; fail=1
else echo "ok   no media, dataset or weight files in history (allow-listed figures: 2)"; fi

big=$(git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' \
      | awk '$1=="blob" && $2>1048576 {print $2, $3}')
if [ -n "$big" ]; then echo "FAIL blobs over 1 MB:"; echo "$big"; fail=1
else echo "ok   no blob over 1 MB"; fi

emails=$(git log --all -p --format= \
         | grep -oiE '[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z.]{2,}' \
         | grep -vE '^\+?@' | grep -viE '@example\.(com|org|edu)$|noreply' | sort -u || true)
if [ -n "$emails" ]; then echo "FAIL e-mail addresses in file contents:"; echo "$emails"; fail=1
else echo "ok   no e-mail addresses in file contents (example.* addresses excluded)"; fi

for p in data/x.parquet videos/x.mp4 models/x.onnx runs/x.json .playwright-mcp/x.png; do
  if git check-ignore -q "$p"; then :; else echo "FAIL not git-ignored: $p"; fail=1; fi
done
[ $fail -eq 0 ] && echo "ok   data/, videos/, models/, runs/, .playwright-mcp/ are git-ignored"

[ $fail -eq 0 ] && echo "PRIVACY CHECK PASSED" || echo "PRIVACY CHECK FAILED"
exit $fail
