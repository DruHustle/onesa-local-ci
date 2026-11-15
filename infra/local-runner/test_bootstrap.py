import base64
import io
import json
import os
import socket
import textwrap
import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, call

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('local_ci_bootstrap', HERE / 'bootstrap.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class RunnerTest(unittest.TestCase):
    def metadata(self):
        return {'': {'full_name': boot.REPO, 'private': True, 'default_branch': 'main', 'permissions': {'admin': True}},
                'collaborators?per_page=100': [{'login': 'DruHustle'}],
                'contents/.github/workflows?ref=main': [{'name': boot.WORKFLOW}],
                f'contents/.github/workflows/{boot.WORKFLOW}?ref=main': {
                    'content': base64.b64encode(boot.reviewed_workflow().read_bytes()).decode()}}

    def test_only_expected_private_controller_can_register(self):
        for field, value in [('private', False), ('full_name', 'DruHustle/onesa-company-portal'), ('default_branch', 'dev')]:
            with self.subTest(field=field):
                values = self.metadata()
                values[''][field] = value
                with patch.object(boot, 'api', side_effect=values.__getitem__), self.assertRaises(ValueError):
                    boot.controller()

    def test_dirty_controller_aborts_and_exact_workflow_passes(self):
        for name, value in [('collaborators?per_page=100', [{'login': 'DruHustle'}, {'login': 'another'}]),
                            ('contents/.github/workflows?ref=main', [{'name': 'another.yml'}]),
                            (f'contents/.github/workflows/{boot.WORKFLOW}?ref=main', {'content': 'YQ=='})]:
            with self.subTest(name=name):
                values = self.metadata()
                values[name] = value
                with patch.object(boot, 'api', side_effect=values.__getitem__), self.assertRaises(ValueError):
                    boot.controller()
        with patch.object(boot, 'api', side_effect=self.metadata().__getitem__):
            boot.controller()

    def test_optional_release_gate_cannot_break_or_bypass_workflow_integrity(self):
        values = self.metadata()
        workflow = 'portfolio-gates.yml'
        values['contents/.github/workflows?ref=main'] = [
            {'name': workflow}, {'name': boot.WORKFLOW}
        ]
        key = f'contents/.github/workflows/{workflow}?ref=main'
        values[key] = {'content': base64.b64encode(
            boot.reviewed_workflow(workflow).read_bytes()).decode()}
        # Ordering should not matter, and both checked-out bytes must match.
        with patch.object(boot, 'api', side_effect=values.__getitem__):
            boot.controller()
        # Having a file of an allowed name is not enough: modified content is rejected.
        values[key] = {'content': base64.b64encode(b'unreviewed: true').decode()}
        with patch.object(boot, 'api', side_effect=values.__getitem__), self.assertRaises(ValueError):
            boot.controller()
        # Never accept unexpected workflows, even if the two reviewed files match.
        values['contents/.github/workflows?ref=main'].append({'name': 'untrusted.yml'})
        with patch.object(boot, 'api', side_effect=values.__getitem__), self.assertRaises(ValueError):
            boot.controller()

    def test_truncated_or_malformed_controller_inventory_is_rejected(self):
        for collaborators in ([{'login': 'DruHustle'}] * 100, {'login': 'DruHustle'},
                              [None], [{'login': None}]):
            with self.subTest(collaborators=collaborators):
                values = self.metadata()
                values['collaborators?per_page=100'] = collaborators
                with patch.object(boot, 'api', side_effect=values.__getitem__), self.assertRaises(ValueError):
                    boot.controller()
        values = self.metadata()
        values['contents/.github/workflows?ref=main'] = [{'name': boot.WORKFLOW}] * 1000
        with patch.object(boot, 'api', side_effect=values.__getitem__), self.assertRaises(ValueError):
            boot.controller()

    def test_owner_without_separate_collaborator_entry_can_configure(self):
        values = self.metadata()
        values['collaborators?per_page=100'] = []
        with patch.object(boot, 'api', side_effect=values.__getitem__):
            boot.controller()

    def test_existing_bom_registration_resumes_after_guest_setup_failure(self):
        registered = {'id': 42, 'name': boot.VM, 'status': 'online',
                      'labels': [{'name': x} for x in ['self-hosted', 'Linux', 'ARM64', boot.LABEL]]}
        configured = json.dumps({'agentName': boot.VM, 'agentId': 42,
                                 'gitHubUrl': 'https://github.com/' + boot.REPO}).encode('utf-8-sig')
        offline = dict(registered, status='offline')
        interrupted_setup = subprocess.CalledProcessError(1, 'guest setup after registration')
        with tempfile.TemporaryDirectory() as root, patch.object(Path, 'home', return_value=Path(root)), \
                patch.object(boot.platform, 'system', return_value='Darwin'), \
                patch.object(boot.platform, 'machine', return_value='arm64'), \
                patch.object(boot.shutil, 'which', return_value='/bin/tool'), \
                patch.object(boot.os, 'geteuid', return_value=501), patch.object(boot, 'controller'), \
                patch.object(boot, 'provision_vm'), patch('builtins.print'), \
                patch.object(boot, 'guest', side_effect=[b'', None, interrupted_setup, configured, None, None]) as guest, \
                patch.object(boot, 'remote_runner', side_effect=[None, offline, registered]), \
                patch.object(boot, 'api', return_value={'token': 'synthetic-registration'}) as api, \
                patch.object(boot, 'run') as run:
            with self.assertRaises(subprocess.CalledProcessError):
                boot.configure()
            boot.configure()
            api.assert_called_once_with('actions/runners/registration-token', 'POST')
            self.assertIn(call('sudo', 'bash', '/run/onesa-ci-bootstrap', data=b'synthetic-registration\n'), guest.call_args_list)
            self.assertIn(call('sudo', 'bash', '/run/onesa-ci-bootstrap', data=b''), guest.call_args_list)
            run.assert_called_once_with('limactl', 'start-at-login', boot.VM)

    def test_guest_validates_real_runner_settings_with_and_without_utf8_bom(self):
        guest = (HERE / 'guest.sh').read_text()
        validation = guest.split("python3 - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
        settings = {'agentId': 42, 'agentName': boot.VM, 'gitHubUrl': 'https://github.com/' + boot.REPO}
        cases = [('utf-8', {}, True), ('utf-8-sig', {}, True),
                 ('utf-8-sig', {'agentName': 'a-different-runner'}, False),
                 ('utf-8-sig', {'gitHubUrl': 'https://github.com/example/another'}, False)]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / '.runner'
            for encoding, overrides, valid in cases:
                with self.subTest(encoding=encoding, overrides=overrides):
                    original = json.dumps(dict(settings, **overrides)).encode(encoding)
                    path.write_bytes(original)
                    result = subprocess.run(['python3', '-c', validation], cwd=root, capture_output=True)
                    self.assertEqual(result.returncode == 0, valid, result.stderr)
                    self.assertEqual(path.read_bytes(), original)

    def test_guest_resumes_missing_service_and_preserves_active_work(self):
        # Run the installed-registration path with local account/systemd fixtures.
        guest = (HERE / 'guest.sh').read_text().split('work=/opt/onesa-actions-runner\n', 1)[1]
        guest = guest.replace('unit=/etc/systemd/system/onesa-local-ci.service', 'unit="$fixture/unit"')
        guest = guest.replace('/usr/local/bin/onesa-ci-node', '"$fixture/onesa-ci-node"')
        commands = '''set -eu
getent() { return 0; }
id() { echo onesa-ci; }
apt-get() { echo 'Unexpected reinstall' >&2; exit 1; }
runuser() { [[ $1 == -u && $2 == onesa-ci && $3 == -- ]]; shift 3; "$@"; }
systemctl() {
  echo "$*" >> "$fixture/calls"
  case "$1" in
    is-active) test -e "$fixture/active";;
    start) touch "$fixture/active";;
    daemon-reload|enable) return 0;;
    *) echo "Unexpected $*" >&2; exit 1;;
  esac
}
'''
        with tempfile.TemporaryDirectory() as root:
            fixture = Path(root)
            work = fixture / 'runner'
            node = work / 'externals/node24/bin/node'
            node.parent.mkdir(parents=True)
            node.write_text('#!/bin/sh\nexit 0\n')
            node.chmod(0o755)
            vendor_wrapper = work / 'bin/runsvc.sh'
            vendor_wrapper.parent.mkdir()
            vendor_wrapper.write_text('#!/bin/bash\nexit 0\n')
            settings = {'agentId': 42, 'agentName': boot.VM, 'gitHubUrl': 'https://github.com/' + boot.REPO}
            metadata = json.dumps(settings).encode('utf-8-sig')
            (work / '.runner').write_bytes(metadata)
            env = {**os.environ, 'fixture': root, 'work': str(work)}
            for state in ['missing', 'active legacy', 'active current']:
                with self.subTest(state=state):
                    unit = fixture / 'unit'
                    if state == 'active legacy':
                        unit.write_text(f'ExecStart={work}/run.sh\n')
                    (fixture / 'calls').write_text('')
                    result = subprocess.run(['bash', '-c', commands + guest], env=env, capture_output=True,
                                            stdin=subprocess.DEVNULL)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    calls = (fixture / 'calls').read_text().splitlines()
                    self.assertEqual(calls.count('start onesa-local-ci.service'), int(state == 'missing'))
                    self.assertEqual((work / '.runner').read_bytes(), metadata)
                    self.assertEqual((work / 'runsvc.sh').read_bytes(), vendor_wrapper.read_bytes())
                    self.assertEqual((work / 'runsvc.sh').stat().st_mode & 0o777, 0o755)
                    for directive in ['WorkingDirectory=/opt/onesa-actions-runner',
                                      'ExecStart=/opt/onesa-actions-runner/runsvc.sh', 'KillMode=process',
                                      'KillSignal=SIGTERM', 'TimeoutStopSec=5min']:
                        self.assertIn(directive, unit.read_text().splitlines())

    def test_first_create_then_repeat_without_recreating(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'lima.yaml').write_text('plain: true\n')
            guest = {'name': boot.VM, 'dir': str(root), 'arch': 'aarch64', 'vmType': 'vz', 'cpus': 4,
                     'memory': 6 * 1024**3, 'status': 'Running'}
            with patch.object(boot, 'instances', side_effect=[{}, {boot.VM: guest}, {boot.VM: guest}]), patch.object(boot, 'run') as run:
                boot.provision_vm(root)
                boot.provision_vm(root)
                self.assertEqual(run.call_count, 1)
                self.assertIn('--plain', run.call_args.args)
            (root / 'lima.yaml').write_text('plain: false\n')
            with patch.object(boot, 'instances', return_value={boot.VM: guest}), self.assertRaises(ValueError):
                boot.provision_vm(root)

    def test_refuses_unowned_guest_or_shared_disks(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            data = b'plain: true\n'
            (root / 'lima.yaml').write_bytes(data)
            guest = {'name': boot.VM, 'dir': str(root), 'arch': 'aarch64', 'vmType': 'vz', 'cpus': 4,
                     'memory': 6 * 1024**3, 'additionalDisks': ['extra'], 'status': 'Running'}
            with patch.object(boot, 'instances', return_value={boot.VM: guest}), patch.object(boot, 'run') as run:
                with self.assertRaises(ValueError):
                    boot.provision_vm(root)
                (root / 'guest.sha256').write_text(hashlib.sha256(data).hexdigest())
                with self.assertRaises(ValueError):
                    boot.provision_vm(root)
                run.assert_not_called()

    def test_duplicate_remote_registration_is_never_replaced(self):
        with patch.object(boot, 'api', return_value={'total_count': 2, 'runners': [{'name': boot.VM}, {'name': boot.VM}]}):
            with self.assertRaises(ValueError):
                boot.remote_runner()

    def test_guest_script_staging_preserves_ssh_socket_and_pipe_bytes(self):
        source = (boot.HERE / 'guest.sh').read_bytes()
        for transport in ['pipe', 'socket']:
            with self.subTest(transport=transport), tempfile.TemporaryDirectory() as root:
                target = Path(root) / 'setup'

                def simulate_guest(*args, data):
                    self.assertEqual(args[0], 'sudo')
                    self.assertEqual(args[-1], '/run/onesa-ci-bootstrap')
                    command = [*args[1:-1], str(target)]
                    if transport == 'pipe':
                        subprocess.run(command, input=data, check=True)
                    else:
                        sender, receiver = socket.socketpair()
                        with sender, receiver:
                            sender.sendall(data)
                            sender.shutdown(socket.SHUT_WR)
                            subprocess.run(command, stdin=receiver, check=True)

                with patch.object(boot, 'guest', side_effect=simulate_guest):
                    boot.stage_guest_setup()
                self.assertEqual(target.read_bytes(), source)
                self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_release_gate_validates_all_maintained_runner_modules(self):
        workflow = boot.reviewed_workflow('portfolio-gates.yml').read_text()
        self.assertIn('"infra/local-runner/**"', workflow)
        self.assertIn('".github/workflows/**"', workflow)
        self.assertIn("-p 'test_*.py' -v", workflow)
        self.assertIn("python -m unittest discover -s infra/local-runner", workflow)

    def test_service_setup_shell_and_workflow_contract(self):
        subprocess.run(['bash', '-n', str(HERE / 'guest.sh')], check=True)
        setup = (HERE / 'guest.sh').read_text()
        self.assertIn('NoNewPrivileges=true', setup)
        self.assertNotIn('--replace', setup)
        workflow = boot.reviewed_workflow().read_text()
        self.assertNotIn('pull_request', workflow)
        self.assertIn('permissions: {}', workflow)
        self.assertNotIn('needs:', workflow)
        self.assertIn('if: ${{ inputs.run_local &&', workflow)
        self.assertIn('if: ${{ !inputs.run_local &&', workflow)
        self.assertEqual(workflow.count("github.event.repository.private == true"), 2)
        self.assertEqual(workflow.count('scripts/validate-docs.py'), 2)
        self.assertEqual(workflow.count('scripts/test_system_appearance.mjs'), 2)

    def test_public_receipt_is_bound_to_sha_workflow_and_successful_hosted_job(self):
        section = boot.reviewed_workflow().read_text().split('shell: python3 {0}\n        run: |\n')[1]
        check = compile(textwrap.dedent(section.split('\n  hosted-verification:')[0]), '<receipt>', 'exec')
        sha = 'a' * 40
        run = {'id': 30, 'run_attempt': 2, 'head_sha': sha, 'head_branch': 'main', 'event': 'push',
               'path': '.github/workflows/verify.yml', 'head_repository': {'full_name': 'DruHustle/onesa-company-portal'},
               'status': 'completed', 'conclusion': 'success'}
        job = {'name': 'verify', 'labels': ['ubuntu-24.04'], 'status': 'completed', 'conclusion': 'success'}
        with tempfile.TemporaryDirectory() as root:
            summary = Path(root) / 'summary'
            for updated_run, updated_job, ok in [({}, {}, True), ({'head_sha': 'b' * 40}, {}, False),
                                                  ({'event': 'pull_request'}, {}, False), ({'status': 'in_progress'}, {}, False),
                                                  ({}, {'conclusion': 'skipped'}, False), ({}, {'labels': ['self-hosted']}, False)]:
                with self.subTest(updated_run=updated_run, updated_job=updated_job):
                    replies = [io.BytesIO(json.dumps({'workflow_runs': [dict(run, **updated_run)]}).encode()),
                               io.BytesIO(json.dumps({'jobs': [dict(job, **updated_job)]}).encode())]
                    with patch('urllib.request.urlopen', side_effect=replies) as api, patch.dict(os.environ, {'SOURCE_SHA': sha, 'GITHUB_STEP_SUMMARY': str(summary)}):
                        if ok:
                            exec(check, {})
                            self.assertIn('runs/30/attempts/2', summary.read_text())
                            self.assertIn('head_sha=' + sha, api.call_args_list[0].args[0])
                        else:
                            with self.assertRaises(SystemExit):
                                exec(check, {})


if __name__ == '__main__':
    unittest.main()
