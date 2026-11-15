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
                                 "head_repository_id": self.repo_id,
                                 "head_sha": "a" * 40, "head_branch": "feature/ci-cleanup-test"}}

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

    def test_apply_only_deletes_confirmed_eligible_ids(self):
        import json
        from unittest.mock import patch
        old = self.item("ci-old", "2026-09-01T00:00:00Z")
        other = dict(old, id=789, name="test-transient")
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args == ("api", "repos/DruHustle/onesa-local-ci"):
                return json.dumps({"full_name": "DruHustle/onesa-local-ci", "id": self.repo_id})
            if args[:2] == ("api", "--paginate"):
                return "\n".join(json.dumps(item) for item in (old, other))
            if args[:3] == ("api", "-X", "DELETE"):
                return ""
            raise AssertionError(args)

        with patch.object(cleanup, "gh", side_effect=fake_gh):
            with patch("sys.argv", ["cleanup", "--apply", "--confirm-repo",
                                    "DruHustle/onesa-local-ci", "--confirm-id", "123"]):
                cleanup.main()
            self.assertIn(("api", "-X", "DELETE",
                           "repos/DruHustle/onesa-local-ci/actions/artifacts/123"), calls)
            self.assertNotIn(("api", "-X", "DELETE",
                              "repos/DruHustle/onesa-local-ci/actions/artifacts/789"), calls)
            calls.clear()
            with patch("sys.argv", ["cleanup", "--apply", "--confirm-repo",
                                    "DruHustle/onesa-local-ci", "--confirm-id", "999"]):
                with self.assertRaises(SystemExit):
                    cleanup.main()
            self.assertFalse(any(x[:3] == ("api", "-X", "DELETE") for x in calls))

    def test_artifact_provenance_requires_exact_source_revision(self):
        valid = self.item("ci-old", "2026-09-01T00:00:00Z")
        self.assertTrue(cleanup.eligible(valid, self.now, 14, self.repo_id))
        for bad_sha in (None, "", "a" * 39, "a" * 41, "not-a-sha", True):
            provenance = dict(valid["workflow_run"], head_sha=bad_sha)
            artifact = dict(valid, workflow_run=provenance)
            with self.subTest(head_sha=bad_sha):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))
        for bad_branch in (None, "", "   ", 7):
            provenance = dict(valid["workflow_run"], head_branch=bad_branch)
            artifact = dict(valid, workflow_run=provenance)
            with self.subTest(head_branch=bad_branch):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))

    def test_protected_and_release_branch_artifacts_are_never_eligible(self):
        valid = self.item("ci-old", "2026-09-01T00:00:00Z")
        for branch in ("main", "master", "release", "release/portfolio-gates-20261115",
                       "production", "production/hotfix", "hotfix", "hotfix/urgent"):
            artifact = dict(valid, workflow_run=dict(valid["workflow_run"], head_branch=branch))
            with self.subTest(branch=branch):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14, self.repo_id))
        malformed = dict(valid, workflow_run=dict(valid["workflow_run"], head_branch=" main "))
        self.assertFalse(cleanup.eligible(malformed, self.now, 14, self.repo_id))

    def test_unprintable_artifact_names_are_not_eligible(self):
        for name in ("ci-old\nDELETE 9", "preview-\x1b[31m", "test-\u2028other"):
            with self.subTest(name=name):
                self.assertFalse(cleanup.eligible(self.item(name, "2026-09-01T00:00:00Z"),
                                                  self.now, 14, self.repo_id))

    def test_duplicate_inventory_aborts_before_any_delete(self):
        import json
        from unittest.mock import patch
        old = self.item("ci-old", "2026-09-01T00:00:00Z")
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args == ("api", "repos/DruHustle/onesa-local-ci"):
                return json.dumps({"full_name": "DruHustle/onesa-local-ci", "id": self.repo_id})
            if args[:2] == ("api", "--paginate"):
                return "\n".join(json.dumps(item) for item in (old, old))
            raise AssertionError(args)

        with patch.object(cleanup, "gh", side_effect=fake_gh):
            with patch("sys.argv", ["cleanup", "--apply", "--confirm-repo",
                                    "DruHustle/onesa-local-ci", "--confirm-id", "123"]):
                with self.assertRaises(SystemExit):
                    cleanup.main()
        self.assertFalse(any(call[:3] == ("api", "-X", "DELETE") for call in calls))

    def test_duplicate_id_with_ineligible_copy_aborts_before_any_delete(self):
        import json
        from unittest.mock import patch
        valid = self.item("ci-old", "2026-09-01T00:00:00Z")
        malformed_duplicate = dict(valid, created_at="not-a-timestamp")
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args == ("api", "repos/DruHustle/onesa-local-ci"):
                return json.dumps({"full_name": "DruHustle/onesa-local-ci", "id": self.repo_id})
            if args[:2] == ("api", "--paginate"):
                return "\n".join(json.dumps(item) for item in (valid, malformed_duplicate))
            raise AssertionError(args)

        with patch.object(cleanup, "gh", side_effect=fake_gh):
            with patch("sys.argv", ["cleanup", "--apply", "--confirm-repo",
                                    "DruHustle/onesa-local-ci", "--confirm-id", "123"]):
                with self.assertRaises(SystemExit):
                    cleanup.main()
        self.assertFalse(any(call[:3] == ("api", "-X", "DELETE") for call in calls))

    def test_malformed_inventory_records_abort_before_any_delete(self):
        import json
        from unittest.mock import patch
        valid = self.item("ci-old", "2026-09-01T00:00:00Z")
        malformed_records = (
            dict(valid, id="123"),
            dict(valid, id=123.0),
            dict(valid, id=True),
            None,
            ["not", "an", "artifact"],
        )
        for malformed in malformed_records:
            with self.subTest(record=malformed):
                calls = []

                def fake_gh(*args):
                    calls.append(args)
                    if args == ("api", "repos/DruHustle/onesa-local-ci"):
                        return json.dumps({"full_name": "DruHustle/onesa-local-ci", "id": self.repo_id})
                    if args[:2] == ("api", "--paginate"):
                        return "\n".join(json.dumps(item) for item in (valid, malformed))
                    raise AssertionError(args)

                with patch.object(cleanup, "gh", side_effect=fake_gh):
                    with patch("sys.argv", ["cleanup", "--apply", "--confirm-repo",
                                            "DruHustle/onesa-local-ci", "--confirm-id", "123"]):
                        with self.assertRaises(SystemExit):
                            cleanup.main()
                self.assertFalse(any(call[:3] == ("api", "-X", "DELETE") for call in calls))

    def test_expired_artifacts_not_redeleted(self):
        self.assertFalse(cleanup.eligible(
            self.item("ci-old", "2026-09-01T00:00:00Z", True),
            self.now, 14, self.repo_id))


if __name__ == "__main__":
    unittest.main()
