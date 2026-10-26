#!/bin/bash
# Store the Formula 1 account used to read livetiming.formula1.com (needs F1TV Access or higher).
#
#   bash scripts/set_f1_credentials.sh
#
# Writes ~/.config/f1cc/f1tv.env, owner-read-only, outside the repo: the unattended updater has no
# shell profile to read, and a secret in the working tree is one `git add -A` from being published.
# The password is read without echo, so it never lands in the shell history or on screen.
set -euo pipefail

DEST="$HOME/.config/f1cc/f1tv.env"

read -r -p "F1 account email: " F1_USER
read -r -s -p "F1 account password: " F1_PASS
echo

if [ -z "$F1_USER" ] || [ -z "$F1_PASS" ]; then
    echo "Both fields are required; nothing written." >&2
    exit 1
fi

mkdir -p "$(dirname "$DEST")"
umask 077                                 # create it unreadable to anyone else from the start
printf 'F1_USERNAME=%s\nF1_PASSWORD=%s\n' "$F1_USER" "$F1_PASS" > "$DEST"
chmod 600 "$DEST"

echo "Wrote $DEST ($(stat -f '%Sp' "$DEST"))"
echo "Now verify with:  .venv/bin/python scripts/check_f1_auth.py"
