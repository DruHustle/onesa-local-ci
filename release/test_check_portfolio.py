import copy
import json
import unittest
from pathlib import Path
from release.check_portfolio import validate

MATRIX = Path(__file__).with_name("portfolio-gates-20261115.json")


class PortfolioGateTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(MATRIX.read_text())

    def test_all_28_client_rows_are_present(self):
        self.assertEqual(len(self.document["entries"]), 28)
        self.assertEqual(validate(self.document), [])

    def test_incomplete_portfolio_cannot_launch(self):
        self.assertEqual(len(validate(self.document, require_go=True)), 41)

    def test_all_thirteen_scope_gates_are_present(self):
        self.assertEqual(len(self.document["scope_gates"]), 13)
        self.assertEqual(validate(self.document), [])

    def test_scope_go_requires_real_candidate_and_operating_limits(self):
        gate = self.document["scope_gates"][0]
        gate.update(decision="GO", blocker="",
                    evidence=["https://github.com/DruHustle/pasofi/actions/runs/123"])
        self.assertTrue(any("scoped candidate" in x for x in validate(self.document)))

    def test_missing_wifi_site_is_rejected(self):
        self.document["scope_gates"] = [
            row for row in self.document["scope_gates"]
            if not (row["kind"] == "wifi-site" and row["scope"] == "G3")
        ]
        self.assertTrue(any("missing scope" in x for x in validate(self.document)))

    def test_duplicate_client_is_rejected(self):
        self.document["entries"].append(copy.deepcopy(self.document["entries"][0]))
        self.assertTrue(any("duplicate" in x for x in validate(self.document)))

    def test_unverified_go_is_rejected(self):
        row = self.document["entries"][0]
        row["decision"] = "GO"
        self.assertTrue(any("GO requires" in x for x in validate(self.document)))

    def test_native_go_requires_store_receipt(self):
        row = next(x for x in self.document["entries"] if x["platform"] == "ios")
        row.update(decision="GO", candidate="signed-1", release_url="build-1",
                   evidence=["https://github.com/DruHustle/onesa-mobile/actions/runs/123"],
                   role_tested="customer", observed_result="Installed workflow completed",
                   operating_limits="Tested hardware", blocker="")
        self.assertTrue(any("store acceptance receipt" in x for x in validate(self.document)))

    def test_malformed_release_identifiers_are_rejected_without_crashing(self):
        self.document["entries"][0]["product"] = ["onesa-mobile"]
        self.document["scope_gates"][0]["scope"] = {"site": "K1"}
        errors = validate(self.document)
        self.assertTrue(any("product and platform must be text" in x for x in errors))
        self.assertTrue(any("product, kind and scope must be text" in x for x in errors))

    def test_client_go_cannot_use_blank_metadata_or_hostless_evidence(self):
        row = self.document["entries"][0]
        row.update(decision="GO", candidate="  ", release_url="https://",
                   evidence=["https://"], role_tested=" ", observed_result=" ",
                   support_owner=" ", operating_limits=" ", blocker="")
        errors = validate(self.document)
        self.assertTrue(any("exact release candidate" in x for x in errors))
        self.assertTrue(any("deployed URL" in x for x in errors))
        self.assertTrue(any("linked acceptance evidence" in x for x in errors))
        self.assertTrue(any("observed role-specific workflow" in x for x in errors))
        self.assertTrue(any("support ownership" in x for x in errors))

    def test_scope_go_cannot_use_blank_or_fake_evidence(self):
        row = self.document["scope_gates"][0]
        row.update(decision="GO", blocker="", candidate="  ",
                   environment="  ", role_tested="  ", observed_result="  ",
                   support_owner="  ", operating_limits="  ",
                   evidence=["https://user:pass@example.com/path"])
        errors = validate(self.document)
        self.assertTrue(any("scope acceptance evidence" in x for x in errors))
        self.assertTrue(any("scoped candidate" in x for x in errors))

    def test_malformed_evidence_urls_are_not_accepted(self):
        from release.check_portfolio import valid_evidence
        for url in ("https://", "https://[broken", "http://example.com",
                    "https://user:pass@example.com/path", "not-a-link", ""):
            with self.subTest(url=url):
                self.assertFalse(valid_evidence(url))
        self.assertTrue(valid_evidence("https://github.com/DruHustle/onesa-local-ci/actions/runs/123"))

    def test_evidence_url_is_not_silently_normalized(self):
        from release.check_portfolio import valid_evidence
        for url in (
            "https://github.com/\nrelease/evidence",
            "https://github.com/\tbad",
            "https://github.com/\rbad",
            " https://github.com/release/evidence",
            "https://github.com:invalid/path",
            "https://github.com:65536/path",
            "https://github.com/\x7fbad",
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_evidence(url))
        self.assertTrue(valid_evidence("https://github.com:443/DruHustle/onesa-local-ci"))

    def test_matrix_root_must_be_object(self):
        self.assertIn("release matrix must be an object", validate([]))

    def test_unverified_environment_or_unobserved_results_cannot_pass(self):
        for group in ("entries", "scope_gates"):
            for field, value in (("environment", " "), ("environment", "production (unverified)"),
                                 ("environment", "production (unverified) with an assumed pass"),
                                 ("operating_limits", ""), ("operating_limits", "Not qualified for production"),
                                 ("operating_limits", "Pending qualification"),
                                 ("observed_result", "Not tested at site/provider/hardware"),
                                 ("observed_result", "Not tested on the release candidate; assumed complete"),
                                 ("observed_result", "Pending acceptance"),
                                 ("evidence", ["https://"])):
                with self.subTest(group=group, field=field):
                    doc = copy.deepcopy(self.document)
                    row = doc[group][0]
                    row.update(decision="GO", candidate="build-1", environment="pilot", role_tested="operator",
                               observed_result="Completed", support_owner="operator", operating_limits="One pilot",
                               evidence=["https://example.org/receipt"], blocker="")
                    # A valid GO fixture is essential: otherwise this test
                    # could pass for unrelated missing release metadata.
                    self.assertEqual(validate(doc), [])
                    row[field] = value
                    reason = (
                        {"environment": "observed role-specific workflow",
                         "operating_limits": "support ownership",
                         "observed_result": "observed role-specific workflow",
                         "evidence": "linked acceptance evidence"}
                        if group == "entries" else
                        {"environment": "scoped candidate",
                         "operating_limits": "scoped candidate",
                         "observed_result": "scoped candidate",
                         "evidence": "scope acceptance evidence"}
                    )[field]
                    self.assertTrue(any(reason in error for error in validate(doc)),
                                    (group, field, validate(doc)))

    def test_no_go_rows_require_nonblank_owners_and_concrete_blockers(self):
        doc = copy.deepcopy(self.document)
        doc["entries"][0]["owner"] = " "
        doc["entries"][1]["support_owner"] = ""
        doc["entries"][2]["blocker"] = " "
        doc["scope_gates"][0]["owner"] = " "
        doc["scope_gates"][1]["support_owner"] = ""
        doc["scope_gates"][2]["blocker"] = None
        errors = validate(doc)
        self.assertTrue(any("owner must be nonblank" in error for error in errors))
        self.assertTrue(any("support_owner must be nonblank" in error for error in errors))
        self.assertTrue(any("NO-GO requires a concrete blocker" in error for error in errors))
        self.assertTrue(any("scope owner required" in error for error in errors))
        self.assertTrue(any("scope support_owner must be nonblank" in error for error in errors))
        self.assertTrue(any("scope blocker must be text" in error for error in errors))

    def test_verified_candidate_has_no_blocker(self):
        row = self.document["entries"][0]
        row.update(decision="GO", candidate="sha256:verified", environment="pilot",
                   release_url="https://mobile.onesa.eu",
                   evidence=["https://github.com/DruHustle/onesa-mobile/actions/runs/123"],
                   role_tested="customer", observed_result="Customer task completed",
                   operating_limits="Web-only validated scope", support_owner="mobile",
                   blocker="")
        self.assertEqual(validate(self.document), [])


if __name__ == "__main__":
    unittest.main()
