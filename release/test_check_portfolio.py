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

    def test_blank_or_unobserved_evidence_cannot_pass(self):
        for group in ("entries", "scope_gates"):
            for field, value in (("environment", " "), ("environment", "production (unverified)"), ("operating_limits", ""), ("observed_result", "Not tested at site/provider/hardware"), ("evidence", ["https://"])):
                with self.subTest(group=group, field=field):
                    doc = copy.deepcopy(self.document)
                    row = doc[group][0]
                    row.update(decision="GO", candidate="build-1", environment="pilot", role_tested="operator",
                               observed_result="Completed", support_owner="operator", operating_limits="One pilot",
                               evidence=["https://example.org/receipt"], blocker="")
                    row[field] = value
                    self.assertTrue(validate(doc))

    def test_malformed_keys_report_validation_errors(self):
        self.document["entries"][0]["product"] = []
        self.document["scope_gates"][0]["scope"] = {}
        self.assertTrue(validate(self.document))
        self.assertTrue(validate([]))

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
