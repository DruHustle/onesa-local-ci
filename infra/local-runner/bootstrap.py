#!/usr/bin/env python3
"""Configure the private CI runner from its owner's Apple Silicon Mac."""
import base64
import fcntl
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = 'DruHustle/onesa-local-ci'
VM = 'onesa-portal-local-arm64'
LABEL = 'onesa-portal-local'
WORKFLOW = 'trusted-portal.yml'
# The release gate is a separate, reviewed, GitHub-hosted workflow. Adding it
# must not prevent verification/resumption of the trusted local runner.
ALLOWED_WORKFLOWS = frozenset({WORKFLOW, 'portfolio-gates.yml'})


def run(*args, data=None, capture=False):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE if capture else None,
                          check=True).stdout


def api(path, method='GET'):
    return json.loads(run('gh', 'api', '--hostname', 'github.com', '--method', method,
                          f'repos/{REPO}/{path}'.rstrip('/'), capture=True))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reviewed_workflow(name=WORKFLOW):
    require(name in ALLOWED_WORKFLOWS, 'Unexpected workflow name.')
    return HERE.parents[1] / '.github/workflows' / name


def controller():
    metadata = api('')
    require(metadata.get('full_name') == REPO and metadata.get('private') is True
            and metadata.get('default_branch') == 'main' and metadata.get('permissions', {}).get('admin'),
            'The owner-administered private controller with default main is required.')
    collaborators = api('collaborators?per_page=100')
    # GitHub returns at most 100 collaborators per page here. Refuse a
    # saturated page rather than accepting a potentially partial permission
    # inventory; this private controller must have owner-only access.
    require(isinstance(collaborators, list) and len(collaborators) < 100
            and all(isinstance(item, dict) and item.get('login') == REPO.split('/')[0]
                    for item in collaborators),
            'Dedicated controller requires a complete owner-only collaborator inventory.')
    entries = api('contents/.github/workflows?ref=main')
    require(isinstance(entries, list) and len(entries) < 1000
            and all(isinstance(entry, dict) for entry in entries),
            'Unexpected or incomplete private controller workflow listing.')
    names = [entry.get('name') for entry in entries]
    require(len(names) == len(set(names)) and WORKFLOW in names
            and set(names) <= ALLOWED_WORKFLOWS,
            'Unexpected private controller workflows.')
    # Check *every* active workflow against this same checkout. Otherwise an
    # added release-gate workflow either blocks local runner resumption or can
    # escape the original single-file integrity check.
    for name in sorted(names):
        content = api(f'contents/.github/workflows/{name}?ref=main')
        require(base64.b64decode(content['content']) == reviewed_workflow(name).read_bytes(),
                f'The active {name} workflow differs from this reviewed checkout.')


def instances():
    raw = run('limactl', 'list', '--json', capture=True)
    return {item['name']: item for item in (json.loads(line) for line in raw.splitlines() if line)}


def digest(instance):
    return hashlib.sha256((Path(instance['dir']) / 'lima.yaml').read_bytes()).hexdigest()


def provision_vm(state):
    marker = state / 'guest.sha256'
    vm = instances().get(VM)
    if vm is None:
        require(not marker.exists(), 'The recorded guest is missing. Reconcile the old registration before replacing it.')
        run('limactl', 'create', '--tty=false', '--plain', '--vm-type=vz', '--arch=aarch64',
            '--cpus=4', '--memory=6', '--name=' + VM, 'template:ubuntu-24.04')
        vm = instances()[VM]
        marker.write_text(digest(vm))
    require(marker.exists() and marker.read_text() == digest(vm), 'Unrecognized Lima guest or changed guest definition.')
    require(vm['arch'] == 'aarch64' and vm['vmType'] == 'vz' and vm['cpus'] == 4
            and vm['memory'] == 6 * 1024**3 and not vm.get('additionalDisks'), 'Unexpected CI guest resources.')
    if vm['status'] != 'Running':
        run('limactl', 'start', '--tty=false', VM)


def guest(*args, **kwargs):
    return run('limactl', 'shell', '--tty=false', '--workdir=/', VM, *args, **kwargs)


def stage_guest_setup():
    # A non-PTY SSH session may deliver stdin through a socket. Read the open descriptor directly.
    guest('sudo', 'sh', '-c', 'umask 077; cat > "$1" && chmod 0700 "$1"', 'sh', '/run/onesa-ci-bootstrap',
          data=(HERE / 'guest.sh').read_bytes())


def remote_runner():
    listing = api('actions/runners?per_page=100')
    require(listing['total_count'] == len(listing['runners']), 'Incomplete registration inventory.')
    runners = [runner for runner in listing['runners'] if runner['name'] == VM]
    require(len(runners) <= 1, 'Duplicate runner name in the private controller.')
    return runners[0] if runners else None


def configure():
    require(platform.system() == 'Darwin' and platform.machine() == 'arm64', 'Run on the intended Apple Silicon Mac.')
    require(shutil.which('gh') and shutil.which('limactl'), 'Install GitHub CLI and Lima on this Mac first.')
    require(os.geteuid() != 0, 'Run as the signed-in macOS user.')
    controller()
    state = Path.home() / 'Library/Application Support/Onesa/local-ci'
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (state / 'setup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        provision_vm(state)
        # The guest receives the reviewed public setup code and a one-hour registration token only.
        local = guest('sudo', 'sh', '-c', 'if test -f /opt/onesa-actions-runner/.runner; then cat /opt/onesa-actions-runner/.runner; fi', capture=True)
        remote = remote_runner()
        if local:
            record = json.loads(local)
            require(remote and record.get('agentId') == remote['id'] and record.get('agentName') == VM
                    and record.get('gitHubUrl', '').rstrip('/') == 'https://github.com/' + REPO,
                    'Local and GitHub registration disagree. Inspect the existing runner before proceeding.')
        else:
            require(not remote, 'The name is already registered to another or missing guest.')
        stage_guest_setup()
        token = b'' if local else api('actions/runners/registration-token', 'POST')['token'].encode() + b'\n'
        guest('sudo', 'bash', '/run/onesa-ci-bootstrap', data=token)
        run('limactl', 'start-at-login', VM)
        for attempt in range(20):
            observed = remote_runner()
            if observed and observed['status'] == 'online':
                labels = {label['name'].lower() for label in observed['labels']}
                require({'self-hosted', 'linux', 'arm64', LABEL} <= labels, 'Unexpected online runner labels.')
                print(f'Online: {REPO} / {VM}. Dispatch {WORKFLOW} with run_local=true for verification.')
                return
            time.sleep(3)
        raise ValueError('Service installed; no online registration observed. Check the guest service journal and rerun.')


if __name__ == '__main__':
    try:
        configure()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
