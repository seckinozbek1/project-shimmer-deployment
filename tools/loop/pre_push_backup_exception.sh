# BEGIN D-616 backup-private exception (template: tools/loop/pre_push_backup_exception.sh)
# A push is let through here ONLY when $1 is exactly the remote name backup-private AND $2 is exactly the
# private repository's URL (with or without .git), its visibility reads exactly true then private through the
# GitHub API, the scan code is the pinned code, and the backup tool's scan of every pushed commit passes (all 7
# CLAUDE.md key patterns, case-insensitive, the D-614 allowlist, no seals/ or audit/model_replies/ path, no
# delete, no replace refs). The pinned code is one fixed directory whose four files have sha256 values recorded in
# this hook (updated by hand). The four files are COPIED into a fresh temporary folder, their sha256 is checked on
# the copies, and the scan runs from the copy with python -I -S -B and a fresh PYTHONPYCACHEPREFIX, so no other file of
# the pinned folder, no PYTHONPATH, no user site, no site-packages .pth or sitecustomize and no .pyc is read; the folder is removed on every exit.
# Anything else falls through to the refusal below. No --no-verify and no SHIMMER_PUSH_OK shortcut is read on this
# path. origin is never matched.
# The @...@ words are filled in when the block is installed in the private hook.
backup_name="backup-private"
backup_url="https://github.com/seckinozbek1/project-shimmer-backup-private"
backup_repo="seckinozbek1/project-shimmer-backup-private"
backup_tool_dir="@TOOL_DIR@"
backup_sha_tool="@SHA_TOOL@"
backup_sha_allow="@SHA_ALLOW@"
backup_sha_guard="@SHA_GUARD@"
backup_sha_common="@SHA_COMMON@"
backup_pin_ok() { [ -f "$1" ] && [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ]; }
if [ "$1" = "$backup_name" ] && { [ "$2" = "$backup_url" ] || [ "$2" = "$backup_url.git" ]; }; then
  backup_lines=$(cat)
  backup_vis=$(gh api --hostname github.com "repos/$backup_repo" --jq '.private,.visibility' 2>/dev/null | tr -d '\r')
  if [ "$backup_vis" != "$(printf 'true\nprivate')" ]; then
    echo "pre-push: refused, the backup-private visibility did not read true and private" >&2
    exit 1
  fi
  backup_tmp=$(mktemp -d) || { echo "pre-push: refused, no temporary folder" >&2; exit 1; }
  trap 'rm -r "$backup_tmp"' EXIT
  backup_tree="$backup_tmp/tree"
  backup_copy() { mkdir -p "$backup_tree/$(dirname "$1")" && cp "$backup_tool_dir/$1" "$backup_tree/$1"; }
  if ! backup_copy tools/loop/backup_private.py \
     || ! backup_copy tools/loop/backup_allowlist.json \
     || ! backup_copy scripts/guard_secrets.py \
     || ! backup_copy tools/cloud_run_common.py \
     || ! backup_pin_ok "$backup_tree/tools/loop/backup_private.py" "$backup_sha_tool" \
     || ! backup_pin_ok "$backup_tree/tools/loop/backup_allowlist.json" "$backup_sha_allow" \
     || ! backup_pin_ok "$backup_tree/scripts/guard_secrets.py" "$backup_sha_guard" \
     || ! backup_pin_ok "$backup_tree/tools/cloud_run_common.py" "$backup_sha_common"; then
    echo "pre-push: refused, the backup scan code is missing or is not the pinned code" >&2
    exit 1
  fi
  mkdir "$backup_tmp/pyc"
  export GIT_NO_REPLACE_OBJECTS=1
  if printf '%s\n' "$backup_lines" | PYTHONPYCACHEPREFIX="$backup_tmp/pyc" py -3.12 -I -S -B -X utf8 "$backup_tree/tools/loop/backup_private.py" --hook-scan "$2"; then
    exit 0
  fi
  echo "pre-push: refused, the backup-private scan did not pass" >&2
  exit 1
fi
# END D-616 backup-private exception
