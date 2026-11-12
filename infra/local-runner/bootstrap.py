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


def run(*args, data=None, capture=False):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE if capture else None,
                          check=True).stdout


def api(path, method='GET'):
    return json.loads(run('gh', 'api', '--hostname', 'github.com', '--method', method,
                          f'repos/{REPO}/{path}'.rstrip('/'), capture=True))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reviewed_workflow():
    return HERE.parents[1] / '.github/workflows' / WORKFLOW


def controller():
    metadata = api('')
    require(metadata.get('full_name') == REPO and metadata.get('private') is True
            and metadata.get('default_branch') == 'main' and metadata.get('permissions', {}).get('admin'),
            'The owner-administered private controller with default main is required.')
    collaborators = api('collaborators?per_page=100')
    require({item['login'] for item in collaborators} == {REPO.split('/')[0]},
            'Dedicated controller requires owner-only access.')
    entries = api('contents/.github/workflows?ref=main')
    require([entry['name'] for entry in entries] == [WORKFLOW], 'Unexpected private controller workflows.')
    content = api(f'contents/.github/workflows/{WORKFLOW}?ref=main')
    require(base64.b64decode(content['content']) == reviewed_workflow().read_bytes(),
            'The active controller workflow differs from this reviewed bootstrap.')


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
        guest('sudo', 'install', '-m', '0700', '/dev/stdin', '/run/onesa-ci-bootstrap', data=(HERE / 'guest.sh').read_bytes())
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
