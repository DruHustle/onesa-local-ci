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
        self.assertEqual(len(validate(self.document, require_go=True)), 28)

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

    def test_verified_candidate_has_no_blocker(self):
        row = self.document["entries"][0]
        row.update(decision="GO", candidate="sha256:verified",
                   release_url="https://mobile.onesa.eu",
                   evidence=["https://github.com/DruHustle/onesa-mobile/actions/runs/123"],
                   role_tested="customer", observed_result="Customer task completed",
                   operating_limits="Web-only validated scope", support_owner="mobile",
                   blocker="")
        self.assertEqual(validate(self.document), [])


if __name__ == "__main__":
    unittest.main()
