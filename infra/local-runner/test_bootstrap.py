import base64
import io
import json
import os
import textwrap
import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
