"""Fail closed if the public controller ever permits the private Mac runner."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class PublicControllerSafetyTests(unittest.TestCase):
    def test_bootstrap_requires_private_controller(self):
        source = (ROOT / "infra/local-runner/bootstrap.py").read_text()
        self.assertIn("metadata.get('private') is True", source)
        configure = source.split("\ndef configure():", 1)[1]
        self.assertLess(configure.index("    controller()"), configure.index("        provision_vm(state)"))

    def test_trusted_dispatch_rejects_public_controller(self):
        source = (ROOT / ".github/workflows/trusted-portal.yml").read_text()
        job_blocks = {
            name: re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", source)
            for name in ("local", "hosted-verification")
        }
        for name, match in job_blocks.items():
            self.assertIsNotNone(match, f"Missing workflow job {name}")
            self.assertIn("github.event.repository.private == true", match.group(1))
        self.assertIn("runs-on: [self-hosted, Linux, ARM64, onesa-portal-local]", source)

    def test_public_workflow_never_schedules_self_hosted(self):
        source = (ROOT / ".github/workflows/public-ci.yml").read_text()
        self.assertIn("runs-on: ubuntu-24.04", source)
        self.assertNotIn("runs-on: self-hosted", source)
        self.assertNotIn("runs-on: [self-hosted", source)
        self.assertIn("permissions:\n  contents: read", source)


if __name__ == "__main__":
    unittest.main()
