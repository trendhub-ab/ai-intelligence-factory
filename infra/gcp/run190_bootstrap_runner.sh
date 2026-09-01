#!/usr/bin/env bash
set -euo pipefail

# Run once inside the Run190 Compute Engine VM.
# Obtain a fresh token from:
# GitHub repo -> Settings -> Actions -> Runners -> New self-hosted runner
# Then:
#   export GITHUB_RUNNER_TOKEN='...'
#   bash infra/gcp/run190_bootstrap_runner.sh

: "${GITHUB_RUNNER_TOKEN:?Set GITHUB_RUNNER_TOKEN to a fresh self-hosted runner registration token}"
REPO_URL="${GITHUB_REPO_URL:-https://github.com/trendhub-ab/ai-intelligence-factory}"
RUNNER_LABEL="${GITHUB_RUNNER_LABEL:-aiif-note-cloud}"
RUNNER_DIR="${GITHUB_RUNNER_DIR:-$HOME/actions-runner}"
PROFILE_DIR="${NOTE_CHROME_USER_DATA_DIR:-$HOME/.aiif-note/chrome-profile}"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates curl gnupg jq git python3 python3-pip python3-venv xvfb

# Install the stable Google Chrome package from Google's signed Debian repository.
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
  | sudo gpg --dearmor --yes -o /etc/apt/keyrings/google-chrome.gpg
printf '%s\n' \
  'deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main' \
  | sudo tee /etc/apt/sources.list.d/google-chrome.list >/dev/null
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y google-chrome-stable

mkdir -p "$PROFILE_DIR"
chmod 700 "$(dirname "$PROFILE_DIR")" "$PROFILE_DIR"

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [ ! -x ./config.sh ]; then
  RUNNER_VERSION="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/^v//')"
  if [ -z "$RUNNER_VERSION" ] || [ "$RUNNER_VERSION" = "null" ]; then
    echo 'Could not resolve the latest GitHub Actions runner version.' >&2
    exit 1
  fi
  ARCHIVE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
  curl -fL --retry 3 -o "$ARCHIVE" \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${ARCHIVE}"
  tar xzf "$ARCHIVE"
  rm -f "$ARCHIVE"
  sudo ./bin/installdependencies.sh
fi

# Replace is intentional: re-running the bootstrap repairs an old registration without
# creating duplicate cloud runners.
./config.sh \
  --url "$REPO_URL" \
  --token "$GITHUB_RUNNER_TOKEN" \
  --name "$(hostname)-note" \
  --labels "$RUNNER_LABEL" \
  --work _work \
  --unattended \
  --replace

sudo ./svc.sh install "$USER" || true
sudo ./svc.sh stop || true
sudo ./svc.sh start

python3 - <<'PY'
from pathlib import Path
import os
profile = Path(os.environ.get('NOTE_CHROME_USER_DATA_DIR') or (Path.home() / '.aiif-note' / 'chrome-profile'))
profile.mkdir(parents=True, exist_ok=True)
print(f'Persistent Chrome profile: {profile}')
PY

cat <<'EOF'

Run190 VM bootstrap completed.
- Google Chrome stable: installed
- Xvfb: installed
- GitHub self-hosted runner label: aiif-note-cloud (unless overridden)
- Runner service: started and enabled
- Chrome profile: persistent under the runner user's home directory

You can now stop the VM. The Create note Draft workflow will start it on demand, run the
browser job on this runner, and stop it afterward. NOTE_STORAGE_STATE_B64 is used only as
an optional note.com bootstrap if the persistent profile has not yet established a session.
EOF
