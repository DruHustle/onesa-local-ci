#!/usr/bin/env bash
# Root installs only this reviewed unit. The Actions service runs unprivileged.
set -euo pipefail
umask 077
exec 9>/run/lock/onesa-local-ci.lock
flock -n 9 || { echo 'Another runner setup is active' >&2; exit 1; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && $(uname -m) == aarch64 ]]
if findmnt -rn -t virtiofs,9p,fuse.sshfs,nfs,nfs4,cifs | grep -q .; then
  echo 'A host or network filesystem is mounted in the CI guest' >&2
  exit 1
fi
[[ -z ${SSH_AUTH_SOCK:-} ]]
work=/opt/onesa-actions-runner
account=onesa-ci
service=onesa-local-ci.service
validate_runner_account() {
  local account="$1" record passwd_name passwd_password passwd_uid passwd_gid passwd_gecos passwd_home passwd_shell
  record=$(getent passwd "$account") || {
    echo 'Runner account is missing' >&2
    return 1
  }
  IFS=: read -r passwd_name passwd_password passwd_uid passwd_gid passwd_gecos passwd_home passwd_shell <<< "$record"
  [[ "$passwd_name" == "$account" && "$passwd_uid" =~ ^[0-9]+$ && "$passwd_gid" =~ ^[0-9]+$ ]] || {
    echo 'Runner account identity is malformed' >&2
    return 1
  }
  (( passwd_uid > 0 && passwd_gid > 0 )) || {
    echo 'Runner account and primary group must not be root' >&2
    return 1
  }
  [[ "$passwd_home" == /var/lib/onesa-ci && "$passwd_shell" == /usr/sbin/nologin ]] || {
    echo 'Runner account home or shell is not the expected locked-down configuration' >&2
    return 1
  }
  [[ $(id -u "$account") == "$passwd_uid" && $(id -gn "$account") == "$account" && $(id -nG "$account") == "$account" ]] || {
    echo 'Runner account must have only its dedicated unprivileged primary group' >&2
    return 1
  }
}
if ! getent passwd "$account" >/dev/null; then
  useradd --system --user-group --create-home --home-dir /var/lib/onesa-ci --shell /usr/sbin/nologin "$account"
fi
validate_runner_account "$account"
if [[ ! -f "$work/.runner" ]]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get -q update >/dev/null
  apt-get -q install -y --no-install-recommends ca-certificates curl git libicu74 libssl3t64 liblttng-ust1t64 >/dev/null
  install -d -o "$account" -g "$account" -m 0700 "$work"
  cd "$work"
  runuser -u "$account" -- bash -ec '
    set -o pipefail
    archive=$(mktemp); trap '\''rm -f "$archive"'\'' EXIT
    curl --fail --silent --show-error --location --proto "=https" --proto-redir "=https" --retry 3 -o "$archive" https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-arm64-2.338.2.tar.gz
    printf "%s  %s\n" 670adb2f268fe21dcbb58b3db0e0aa9d5b3bddfe2c651481336e561ff86de945 "$archive" | sha256sum --check --status
    tar -xzf "$archive"
    IFS= read -r ACTIONS_RUNNER_INPUT_TOKEN
    [[ -n "$ACTIONS_RUNNER_INPUT_TOKEN" ]]; export ACTIONS_RUNNER_INPUT_TOKEN
    ./config.sh --unattended --url https://github.com/DruHustle/onesa-local-ci --name onesa-portal-local-arm64 --labels onesa-portal-local --work _work
  '
fi
cd "$work"
python3 - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('.runner').read_bytes())
assert r['agentName'] == 'onesa-portal-local-arm64'
assert r['gitHubUrl'].rstrip('/') == 'https://github.com/DruHustle/onesa-local-ci'
PY
runuser -u "$account" -- "$work/externals/node24/bin/node" -e 'if (process.versions.node.split(".")[0] !== "24") process.exit(1)'
ln -sfn "$work/externals/node24/bin/node" /usr/local/bin/onesa-ci-node
# GitHub's service wrapper launches its Node supervisor relative to the runner root.
runuser -u "$account" -- sh -eu -c '
  if ! cmp -s bin/runsvc.sh runsvc.sh; then
    staged=$(mktemp ./runsvc.XXXXXX)
    trap '\''rm -f "$staged"'\'' EXIT
    install -m 0755 bin/runsvc.sh "$staged"
    mv -f "$staged" runsvc.sh
  fi
  chmod 0755 runsvc.sh
'
unit=/etc/systemd/system/onesa-local-ci.service
active_legacy=false
if grep -Fqx "ExecStart=$work/run.sh" "$unit" 2>/dev/null && systemctl is-active --quiet "$service"; then
  active_legacy=true
fi
cat > "$unit" <<'UNIT'
[Unit]
Description=Onesa private GitHub Actions runner
After=network-online.target
Wants=network-online.target
[Service]
User=onesa-ci
Group=onesa-ci
WorkingDirectory=/opt/onesa-actions-runner
Environment=HOME=/var/lib/onesa-ci
ExecStart=/opt/onesa-actions-runner/runsvc.sh
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$unit"
systemctl daemon-reload
systemctl enable "$service"
if ! systemctl is-active --quiet "$service"; then
  systemctl start "$service"
elif "$active_legacy"; then
  echo "Active runner kept running. Its next normal service start will use runsvc.sh."
fi
systemctl is-active --quiet "$service"
