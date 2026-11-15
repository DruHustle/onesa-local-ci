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

    def item(self, name, created, expired=False):
        return {"id": 123, "name": name, "created_at": created,
                "expired": expired, "size_in_bytes": 500}

    def test_old_disposable_artifact_is_eligible(self):
        self.assertTrue(cleanup.eligible(
            self.item("browser-test", "2026-10-01T00:00:00Z"),
            self.now, 14))

    def test_recent_artifact_is_preserved(self):
        self.assertFalse(cleanup.eligible(
            self.item("browser-test", "2026-11-14T00:00:00Z"),
            self.now, 14))

    def test_release_artifacts_are_preserved(self):
        for name in ("SmartFactory-qualification-apk", "signed-ios-archive",
                     "production-rollback", "pasofi-payment-receipt"):
            self.assertFalse(cleanup.eligible(
                self.item(name, "2026-09-01T00:00:00Z"),
                self.now, 14))

    def test_missing_or_invalid_creation_time_never_authorizes_deletion(self):
        for timestamp in (None, "", "not-a-timestamp", "2026-09-01T00:00:00"):
            artifact = self.item("ci-old", "2026-09-01T00:00:00Z")
            if timestamp is None:
                artifact.pop("created_at")
            else:
                artifact["created_at"] = timestamp
            with self.subTest(timestamp=timestamp):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14))

    def test_missing_or_non_string_artifact_name_is_never_deleted(self):
        for name in (None, 42, [], {}):
            artifact = self.item("ci-old", "2026-09-01T00:00:00Z")
            if name is None:
                artifact.pop("name")
            else:
                artifact["name"] = name
            with self.subTest(name=name):
                self.assertFalse(cleanup.eligible(artifact, self.now, 14))

    def test_expired_artifacts_not_redeleted(self):
        self.assertFalse(cleanup.eligible(
            self.item("ci-old", "2026-09-01T00:00:00Z", True),
            self.now, 14))


if __name__ == "__main__":
    unittest.main()
