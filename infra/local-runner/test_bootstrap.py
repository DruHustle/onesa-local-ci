import base64
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
        self.assertIn('needs: [preflight, local]', workflow)
        self.assertEqual(workflow.count('scripts/validate-docs.py'), 2)
        self.assertEqual(workflow.count('scripts/test_system_appearance.mjs'), 2)


if __name__ == '__main__':
    unittest.main()
