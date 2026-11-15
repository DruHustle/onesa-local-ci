import datetime as dt
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("cleanup_artifacts.py")
spec = importlib.util.spec_from_file_location("cleanup_artifacts", MODULE)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class ArtifactCleanupTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 15, tzinfo=dt.timezone.utc)
        self.repo_id = 1455347405

    def item(self, name, created, expired=False):
        return {"id": 123, "name": name, "created_at": created,
                "expired": expired, "size_in_bytes": 500,
                "workflow_run": {"id": 456, "repository_id": self.repo_id,
                                 "head_repository_id": self.repo_id}}

    def test_old_disposable_artifact_is_eligible(self):
        self.assertTrue(cleanup.eligible(
            self.item("browser-test", "2026-10-01T00:00:00Z"),
            self.now, 14, self.repo_id))

    def test_recent_artifact_is_preserved(self):
        self.assertFalse(cleanup.eligible(
            self.item("browser-test", "2026-11-14T00:00:00Z"),
            self.now, 14, self.repo_id))

    def test_release_artifacts_are_preserved(self):
        for name in ("SmartFactory-qualification-apk", "signed-ios-archive",
                     "production-rollback", "pasofi-payment-receipt"):
            self.assertFalse(cleanup.eligible(
                self.item(name, "2026-09-01T00:00:00Z"),
                self.now, 14, self.repo_id))

    def test_missing_or_invalid_creation_time_never_authorizes_deletion(self):
        for timestamp in (None, "", "not-a-timestamp", "2026-09-01T00:00:00"):
            artifact = self.item("ci-old", "2026-09-01T00:00:00Z")
            if timestamp is None:
                artifact.pop("created_at")
            else:
                artifact["created_at"] = timestamp
            with self.subTest(timestamp=timestamp):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))

    def test_missing_or_non_string_artifact_name_is_never_deleted(self):
        for name in (None, 42, [], {}):
            artifact = self.item("ci-old", "2026-09-01T00:00:00Z")
            if name is None:
                artifact.pop("name")
            else:
                artifact["name"] = name
            with self.subTest(name=name):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))

    def test_untrusted_artifact_id_and_expiration_fail_closed(self):
        valid = self.item("ci-old", "2026-09-01T00:00:00Z")
        self.assertTrue(cleanup.eligible(valid, self.now, 14, self.repo_id))
        for invalid in (None, [], "bad", 12):
            with self.subTest(record=invalid):
                self.assertFalse(cleanup.eligible(invalid, self.now, 14, self.repo_id))
        for bad_id in (None, True, "123", 0, -2):
            artifact = dict(valid, id=bad_id)
            with self.subTest(id=bad_id):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))
        for bad_expired in (None, "false", 0):
            artifact = dict(valid, expired=bad_expired)
            with self.subTest(expired=bad_expired):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))

    def test_artifacts_must_be_source_bound_and_have_valid_size(self):
        valid = self.item("ci-old", "2026-09-01T00:00:00Z")
        self.assertTrue(cleanup.eligible(valid, self.now, 14, self.repo_id))
        for bad_run in (None, {}, {"id": 456, "repository_id": self.repo_id,
                                   "head_repository_id": 999},
                        {"id": False, "repository_id": self.repo_id,
                         "head_repository_id": self.repo_id}):
            artifact = dict(valid, workflow_run=bad_run)
            with self.subTest(provenance=bad_run):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))
        for bad_size in (None, -1, "500", True):
            artifact = dict(valid, size_in_bytes=bad_size)
            with self.subTest(size=bad_size):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))

    def test_apply_refuses_deletion_without_explicit_artifact_ids(self):
        from unittest.mock import patch
        with patch("sys.argv", ["cleanup_artifacts", "--apply", "--confirm-repo",
                                "DruHustle/onesa-local-ci"]), \
             patch.object(cleanup, "gh") as gh:
            with self.assertRaises(SystemExit):
                cleanup.main()
            gh.assert_not_called()

    def test_expired_artifacts_not_redeleted(self):
        self.assertFalse(cleanup.eligible(
            self.item("ci-old", "2026-09-01T00:00:00Z", True),
            self.now, 14, self.repo_id))


if __name__ == "__main__":
    unittest.main()
