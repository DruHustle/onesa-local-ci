"""Fail closed if the public controller ever permits the private Mac runner."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class PublicControllerSafetyTests(unittest.TestCase):
    def test_bootstrap_requires_private_controller(self):
        source = (ROOT / "infra/local-runner/bootstrap.py").read_text()
        self.assertIn("metadata.get('private') is True", source)
        self.assertIn("controller()\n    state =", source)
        self.assertLess(source.index("controller()\n    state ="), source.index("provision_vm(state)"))

    def test_trusted_dispatch_rejects_public_controller(self):
        source = (ROOT / ".github/workflows/trusted-portal.yml").read_text()
        self.assertIn("github.event.repository.private == true", source)
        for job in ("local:", "hosted-verification:"):
            start = source.index("  " + job)
            end = source.find("\n  ", start + 3)
            header = source[start:end if end != -1 else None]
            self.assertIn("github.event.repository.private == true", header)
        self.assertIn("runs-on: [self-hosted, Linux, ARM64, onesa-portal-local]", source)

    def test_public_workflow_never_schedules_self_hosted(self):
        source = (ROOT / ".github/workflows/public-ci.yml").read_text()
        self.assertIn("runs-on: ubuntu-24.04", source)
        self.assertNotIn("runs-on: self-hosted", source)
        self.assertNotIn("runs-on: [self-hosted", source)
        self.assertIn("permissions:\n  contents: read", source)


if __name__ == "__main__":
    unittest.main()
