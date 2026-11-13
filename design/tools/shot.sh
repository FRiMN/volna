#!/usr/bin/env bash
# Screenshot an OpenDesign preview URL to a crisp PNG.
# Usage: shot.sh <preview-url> <out.png> [width] [height]
set -euo pipefail
URL="${1:?usage: shot.sh <preview-url> <out.png> [width] [height]}"
OUT="${2:?usage: shot.sh <preview-url> <out.png> [width] [height]}"
W="${3:-1600}"
H="${4:-1000}"
PROFILE="$(mktemp -d /tmp/chrome-shot-XXXXXX)"
trap 'rm -rf "$PROFILE"' EXIT
chromium --headless --no-sandbox --disable-gpu --disable-dev-shm-usage --hide-scrollbars \
  --user-data-dir="$PROFILE" --force-device-scale-factor=2 \
  --window-size="${W},${H}" --virtual-time-budget=4000 \
  --screenshot="$OUT" "$URL" 2>/dev/null
echo "saved: $OUT"
