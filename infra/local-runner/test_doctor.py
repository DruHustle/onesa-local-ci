"""Fail-closed tests for the read-only local runner health certification."""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("runner_doctor", HERE / "doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


def good_evidence():
    now = datetime.now(timezone.utc)
    run = {
        "id": 1234, "run_attempt": 2, "repository": {"full_name": doctor.boot.REPO},
        "path": ".github/workflows/" + doctor.boot.WORKFLOW,
        "head_branch": "main", "event": "workflow_dispatch",
        "status": "completed", "conclusion": "success",
        "actor": {"login": "DruHustle"}, "triggering_actor": {"login": "DruHustle"},
        "run_started_at": now.isoformat(),
    }
    job = {
        "run_id": 1234, "run_attempt": 2, "name": "local",
        "status": "completed", "conclusion": "success",
        "runner_name": doctor.boot.VM,
        "labels": ["self-hosted", "Linux", "ARM64", doctor.boot.LABEL],
        "steps": [{"name": name, "status": "completed", "conclusion": "success"}
                  for name in doctor.REQUIRED_STEPS],
    }
    return now, run, job


class RunnerDoctorTests(unittest.TestCase):
    def test_accepts_exact_recent_local_execution(self):
        now, run, job = good_evidence()
        self.assertTrue(doctor.verify_dispatch(run, [job], now=now))

    def test_rejects_stale_and_future_evidence(self):
        now, run, job = good_evidence()
        for started in (now-timedelta(hours=3), now+timedelta(minutes=10)):
            with self.subTest(started=started):
                run["run_started_at"] = started.isoformat()
                self.assertFalse(doctor.verify_dispatch(run, [job], now=now))

    def test_rejects_other_repositories_and_untrusted_dispatches(self):
        now, run, job = good_evidence()
        variations = [
            ("repository", {"full_name": "DruHustle/onesa-security"}),
            ("path", ".github/workflows/public-ci.yml"),
            ("head_branch", "pull/123"),
            ("event", "pull_request"),
            ("status", "queued"), ("conclusion", "failure"),
            ("actor", {"login": "another-user"}),
            ("triggering_actor", {"login": "another-user"}),
        ]
        for key, value in variations:
            with self.subTest(key=key, value=value):
                modified = dict(run, **{key: value})
                self.assertFalse(doctor.verify_dispatch(modified, [job], now=now))

    def test_rejects_skips_wrong_runner_or_missing_steps(self):
        now, run, job = good_evidence()
        variations = [
            ("name", "hosted-verification"),
            ("runner_name", "different-runner"),
            ("run_id", 654), ("run_attempt", 1),
            ("status", "in_progress"), ("conclusion", "skipped"),
            ("labels", ["ubuntu-24.04"]),
            ("steps", [{"name": name, "status": "completed", "conclusion": "skipped"}
                       for name in doctor.REQUIRED_STEPS]),
        ]
        for key, value in variations:
            with self.subTest(key=key):
                modified = dict(job, **{key: value})
                self.assertFalse(doctor.verify_dispatch(run, [modified], now=now))
        self.assertFalse(doctor.verify_dispatch(run, [], now=now))
        self.assertFalse(doctor.verify_dispatch(run, [job, job], now=now))

    def test_missing_and_malformed_evidence_is_not_success(self):
        now, run, job = good_evidence()
        for pair in (({}, [job]), (run, {}), (run, [None]), (run, [job]*101)):
            self.assertFalse(doctor.verify_dispatch(*pair, now=now))
        for v in (None, "", "not-a-time", 23):
            with self.subTest(timestamp=v):
                self.assertFalse(doctor.verify_dispatch(dict(run, run_started_at=v), [job], now=now))

    def test_public_controller_is_never_certified_even_if_remote_online(self):
        with patch.object(doctor.platform, "system", return_value="Darwin"), \
             patch.object(doctor.platform, "machine", return_value="arm64"), \
             patch.object(doctor.shutil, "which", return_value="/usr/local/bin/command"), \
             patch.object(doctor, "api", side_effect=lambda path: {
                 "": {"full_name": doctor.boot.REPO, "private": False,
                      "default_branch": "main", "permissions": {"admin": True}},
                 "actions/runners?per_page=100": {"total_count": 1, "runners": [{
                     "id": 45, "name": doctor.boot.VM, "status": "online",
                     "labels": [{"name": v} for v in doctor.REQUIRED_LABELS]}]},
             }[path]), \
             patch.object(doctor, "command", side_effect=OSError("Lima unavailable")):
            report = doctor.probe()
        checks = {x["check"]: x["ok"] for x in report["checks"]}
        self.assertTrue(checks["github_online"])
        self.assertFalse(checks["private_controller"])
        self.assertFalse(checks["guest_running"])
        self.assertFalse(report["certified"])

    def test_cannot_certify_from_historical_green_ci_only(self):
        with patch.object(doctor.platform, "system", return_value="Linux"), \
             patch.object(doctor.platform, "machine", return_value="x86_64"), \
             patch.object(doctor.shutil, "which", return_value=None):
            report = doctor.probe()
        self.assertFalse(report["certified"])
        self.assertFalse({x["check"]: x["ok"] for x in report["checks"]}["recent_local_dispatch"])

    def test_health_check_never_dispatches_or_mutates_runner_registration(self):
        source = (HERE / "doctor.py").read_text()
        self.assertNotIn("workflow run ", source)
        self.assertNotIn('"POST"', source)
        self.assertNotIn("registration-token", source)
        self.assertNotIn("provision_vm(", source)
        self.assertIn("subprocess.PIPE", source)
        self.assertIn("--run-id", source)


if __name__ == "__main__":
    unittest.main()
