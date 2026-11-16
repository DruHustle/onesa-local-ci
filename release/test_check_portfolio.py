import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from release.check_portfolio import (APPROVED_SOURCE_JOBS, APPROVED_SOURCE_WORKFLOWS,
                                     SOURCE_REPOSITORIES, validate, verify_source_runs)

MATRIX = Path(__file__).with_name("portfolio-gates-20261115.json")


class PortfolioGateTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(MATRIX.read_text())
        # Test-only policy fixture. Production allowlists remain empty until
        # each source repository's exact acceptance workflow/job is reviewed.
        self.workflow_policy = patch.dict(
            APPROVED_SOURCE_WORKFLOWS,
            {product: frozenset({".github/workflows/verify.yml@refs/heads/main"})
             for product in SOURCE_REPOSITORIES},
        )
        self.job_policy = patch.dict(
            APPROVED_SOURCE_JOBS,
            {product: frozenset({"verify"}) for product in SOURCE_REPOSITORIES},
        )
        self.workflow_policy.start()
        self.job_policy.start()
        self.addCleanup(self.workflow_policy.stop)
        self.addCleanup(self.job_policy.stop)

    def successful_jobs(self, _repository, _run_id, _attempt):
        return {"total_count": 1, "jobs": [
            {"name": "verify", "status": "completed", "conclusion": "success"}
        ]}

    def evidence_for(self, product, sha):
        repositories = {
            "onesa-mobile": "onesa-mobile", "pasofi": "pasofi",
            "onesa-drone": "onesa-drone", "onesa-robot": "onesa-robot",
            "smart-farmer": "smart-farmer", "smart-logistics": "smart-logistics",
            "smart-factory": "smart-factory", "onesa-ai-platform": "onesa-ai-platform",
            "company-portal": "onesa-company-portal",
            "documents-public": "onesa-documents", "documents-internal": "onesa-documents",
            "identity": "onesa-identity",
        }
        repository = repositories[product]
        base = f"https://github.com/DruHustle/{repository}"
        return [f"{base}/commit/{sha}", f"{base}/actions/runs/123"]

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
        candidate = "a" * 40
        row.update(decision="GO", candidate=candidate, release_url="build-1",
                   evidence=self.evidence_for(row["product"], candidate),
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

    def test_malformed_web_environment_never_crashes_validation(self):
        doc = copy.deepcopy(self.document)
        row = doc["entries"][0]
        candidate = "a" * 40
        row.update(decision="GO", candidate=candidate, release_url="https://mobile.onesa.eu",
                   evidence=self.evidence_for(row["product"], candidate), workflow="Customer sign-in",
                   environment=["production"], role_tested="customer", observed_result="Sign-in completed",
                   support_owner="mobile", operating_limits="Production web only", blocker="")
        errors = validate(doc)
        self.assertTrue(any("environment must be text" in error for error in errors))
        self.assertTrue(any("allowlisted production host" in error for error in errors))

    def test_no_go_candidate_and_release_urls_are_typed_and_safe(self):
        doc = copy.deepcopy(self.document)
        doc["entries"][0]["candidate"] = ["not", "a", "commit"]
        doc["entries"][0]["release_url"] = "https://user:password@example.com/private"
        doc["entries"][1]["release_url"] = "https://user:password@example.com/native"
        doc["entries"][2]["release_url"] = ["https://example.com"]
        doc["entries"][3]["store_receipt"] = {"receipt": "untrusted"}
        errors = validate(doc)
        self.assertTrue(any("candidate must be text" in error for error in errors))
        self.assertTrue(any("web release_url must be a credential-free HTTPS URL" in error for error in errors))
        self.assertTrue(any("URL release_url must be a credential-free HTTPS URL" in error for error in errors))
        self.assertTrue(any("release_url must be nonblank text or null" in error for error in errors))
        self.assertTrue(any("store_receipt must be text or null" in error for error in errors))

    def test_no_go_evidence_urls_are_validated_for_clients_and_scopes(self):
        doc = copy.deepcopy(self.document)
        doc["entries"][0]["evidence"] = ["https://user:password@example.com/private"]
        doc["scope_gates"][0]["evidence"] = ["https://github.com/release/evidence?token=secret"]
        errors = validate(doc)
        self.assertTrue(any("evidence[0]" in error and "credential-free" in error for error in errors))
        self.assertTrue(any("scope evidence[0]" in error and "credential-free" in error for error in errors))

    def test_owner_and_support_owner_reject_unverified_markers(self):
        doc = copy.deepcopy(self.document)
        doc["entries"][0]["owner"] = "unknown"
        doc["entries"][1]["support_owner"] = "pending"
        doc["scope_gates"][0]["owner"] = "pending"
        doc["scope_gates"][1]["support_owner"] = "unknown"
        errors = validate(doc)
        self.assertTrue(any("owner must be verified" in error for error in errors))
        self.assertTrue(any("support_owner must be verified" in error for error in errors))
        self.assertTrue(any("scope owner must be verified" in error for error in errors))
        self.assertTrue(any("scope support_owner must be verified" in error for error in errors))

    def test_web_go_requires_allowlisted_production_host_and_environment(self):
        doc = copy.deepcopy(self.document)
        row = doc["entries"][0]
        candidate = "f" * 40
        row.update(decision="GO", candidate=candidate, release_url="https://mobile.onesa.eu",
                   evidence=self.evidence_for(row["product"], candidate), workflow="Customer sign-in",
                   environment="production", role_tested="customer", observed_result="Sign-in completed",
                   support_owner="mobile", operating_limits="Production web only", blocker="")
        self.assertEqual(validate(doc), [])
        row["release_url"] = "https://mobile-preview.vercel.app"
        self.assertTrue(any("allowlisted production host" in error for error in validate(doc)))
        row["release_url"] = "https://mobile.onesa.eu"
        row["environment"] = "Vercel preview"
        self.assertTrue(any("allowlisted production host" in error for error in validate(doc)))

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
                    candidate = "b" * 40
                    row.update(decision="GO", candidate=candidate, environment="production", role_tested="operator",
                               observed_result="Completed", support_owner="operator", operating_limits="One pilot",
                               evidence=self.evidence_for(row["product"], candidate), blocker="")
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

    def test_go_requires_full_source_commit_and_same_repository_workflow_run(self):
        row = self.document["entries"][0]
        candidate = "d" * 40
        row.update(decision="GO", candidate=candidate, release_url="https://mobile.onesa.eu",
                   evidence=self.evidence_for(row["product"], candidate), workflow="Customer sign-in",
                   environment="production", role_tested="customer", observed_result="Sign-in completed",
                   support_owner="mobile", operating_limits="Web production only", blocker="")
        self.assertEqual(validate(self.document), [])
        row["candidate"] = candidate[:8]
        self.assertTrue(any("exact candidate commit" in error for error in validate(self.document)))
        row["candidate"] = candidate
        row["evidence"] = self.evidence_for(row["product"], candidate)
        row["evidence"][1] = "https://github.com/DruHustle/onesa-documents/actions/runs/123"
        self.assertTrue(any("exact candidate commit" in error for error in validate(self.document)))
        row["evidence"] = [f"https://github.com/DruHustle/onesa-mobile/actions/runs/123"]
        self.assertTrue(any("exact candidate commit" in error for error in validate(self.document)))

    def test_go_rejects_unverified_test_role_and_store_receipt(self):
        row = next(x for x in self.document["entries"] if x["platform"] == "ios")
        candidate = "e" * 40
        row.update(decision="GO", candidate=candidate, release_url="build-1",
                   evidence=self.evidence_for(row["product"], candidate), workflow="Native customer flow",
                   environment="TestFlight", role_tested="not tested", observed_result="Completed",
                   support_owner="mobile", operating_limits="Tested device", blocker="",
                   store_submission="accepted", store_receipt="pending")
        errors = validate(self.document)
        self.assertTrue(any("observed role-specific workflow" in error for error in errors))
        row["role_tested"] = "customer"
        self.assertTrue(any("store acceptance receipt" in error for error in validate(self.document)))

    def test_verified_candidate_has_no_blocker(self):
        row = self.document["entries"][0]
        candidate = "c" * 40
        row.update(decision="GO", candidate=candidate, environment="production",
                   release_url="https://mobile.onesa.eu",
                   evidence=self.evidence_for(row["product"], candidate),
                   role_tested="customer", observed_result="Customer task completed",
                   operating_limits="Web-only validated scope", support_owner="mobile",
                   blocker="")
        self.assertEqual(validate(self.document), [])


    def test_source_workflow_run_must_match_exact_successful_main_candidate(self):
        row = self.document["entries"][0]
        candidate = "d" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate))
        valid = {
            "id": 123, "head_sha": candidate, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/onesa-mobile"},
            "repository": {"full_name": "DruHustle/onesa-mobile"},
            "workflow_id": 7, "path": ".github/workflows/verify.yml@refs/heads/main",
            "run_attempt": 1,
        }
        calls = []
        def fetch(repository, run_id):
            calls.append((repository, run_id))
            return valid
        self.assertEqual(verify_source_runs(self.document, fetch, self.successful_jobs), [])
        self.assertEqual(calls, [("onesa-mobile", 123)])

        invalid_cases = (
            {"head_sha": "e" * 40},
            {"head_branch": "feature/release"},
            {"status": "in_progress", "conclusion": None},
            {"conclusion": "failure"},
            {"event": "pull_request"},
            {"head_repository": {"full_name": "attacker/onesa-mobile"}},
            {"repository": {"full_name": "DruHustle/onesa-documents"}},
            {"id": 999},
            {"workflow_id": 0},
            {"path": "README.md"},
            {"run_attempt": 0},
        )
        for changes in invalid_cases:
            payload = dict(valid, **changes)
            with self.subTest(changes=changes):
                errors = verify_source_runs(self.document, lambda _repo, _id: payload, self.successful_jobs)
                self.assertTrue(any("must be a completed successful" in error for error in errors), errors)

    def test_failed_observed_outcomes_cannot_be_promoted_to_go(self):
        for group in ("entries", "scope_gates"):
            for outcome in ("Failed: customer sign-in", "Customer workflow timed out",
                            "Payment returned an error", "Operator task was blocked",
                            "Deployment was cancelled"):
                with self.subTest(group=group, outcome=outcome):
                    doc = copy.deepcopy(self.document)
                    row = doc[group][0]
                    candidate = "8" * 40
                    row.update(decision="GO", candidate=candidate, blocker="",
                               environment="production", role_tested="operator",
                               observed_result="Completed successfully",
                               support_owner="operations", operating_limits="Verified pilot limits",
                               evidence=self.evidence_for(row["product"], candidate))
                    if group == "entries":
                        row.update(release_url="https://mobile.onesa.eu",
                                   workflow="Customer sign-in")
                    self.assertEqual(validate(doc), [])
                    row["observed_result"] = outcome
                    self.assertTrue(any("observed role-specific workflow" in error
                                        or "scoped candidate" in error
                                        for error in validate(doc)),
                                    (group, outcome, validate(doc)))

    def test_placeholder_owner_and_support_owner_are_not_verified(self):
        doc = copy.deepcopy(self.document)
        doc["entries"][0]["owner"] = "unassigned"
        doc["entries"][1]["support_owner"] = "TBD"
        doc["scope_gates"][0]["owner"] = "N/A"
        doc["scope_gates"][1]["support_owner"] = "not assigned"
        errors = validate(doc)
        self.assertTrue(any("owner must be verified" in error for error in errors))
        self.assertTrue(any("support_owner must be verified" in error for error in errors))
        self.assertTrue(any("scope owner must be verified" in error for error in errors))
        self.assertTrue(any("scope support_owner must be verified" in error for error in errors))

    def test_cited_workflow_run_attempt_must_match_exact_attempt_url(self):
        row = self.document["entries"][0]
        candidate = "9" * 40
        evidence = self.evidence_for(row["product"], candidate)
        evidence[-1] = f"https://github.com/DruHustle/onesa-mobile/actions/runs/123/attempts/2"
        row.update(decision="GO", candidate=candidate, evidence=evidence)
        valid = {
            "id": 123, "head_sha": candidate, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/onesa-mobile"},
            "repository": {"full_name": "DruHustle/onesa-mobile"},
            "workflow_id": 7, "path": ".github/workflows/verify.yml@refs/heads/main",
            "run_attempt": 1,
        }
        errors = verify_source_runs(self.document, lambda _repo, _run_id: valid, self.successful_jobs)
        self.assertTrue(any("attempt 2" in error and "must be a completed successful" in error
                            for error in errors), errors)
        evidence[-1] = "https://github.com/DruHustle/onesa-mobile/actions/runs/123/attempts/1"
        row["evidence"] = evidence
        self.assertEqual(verify_source_runs(self.document, lambda _repo, _run_id: valid, self.successful_jobs), [])

    def test_every_cited_source_run_is_checked_not_just_one_matching_run(self):
        row = self.document["entries"][0]
        candidate = "f" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate) + [
                       "https://github.com/DruHustle/onesa-mobile/actions/runs/456"
                   ])
        good = {
            "id": 123, "head_sha": candidate, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/onesa-mobile"},
            "repository": {"full_name": "DruHustle/onesa-mobile"},
            "workflow_id": 7, "path": ".github/workflows/verify.yml",
            "run_attempt": 1,
        }
        calls = []
        def fetch(repository, run_id):
            calls.append(run_id)
            return dict(good, id=run_id, head_sha=("a" * 40 if run_id == 456 else candidate))
        errors = verify_source_runs(self.document, fetch, self.successful_jobs)
        self.assertEqual(calls, [123, 456])
        self.assertTrue(any("workflow run 456" in error for error in errors), errors)

    def test_source_workflow_run_lookup_failure_fails_closed(self):
        row = self.document["entries"][0]
        candidate = "b" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate))
        errors = verify_source_runs(
            self.document,
            lambda _repo, _run_id: (_ for _ in ()).throw(TimeoutError("unavailable")),
            self.successful_jobs,
        )
        self.assertTrue(any("could not be verified" in error for error in errors), errors)


    def test_go_requires_an_explicit_reviewed_workflow_and_job_allowlist(self):
        row = self.document["entries"][0]
        candidate = "a" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate))
        calls = []
        with patch.dict(APPROVED_SOURCE_WORKFLOWS, {"onesa-mobile": frozenset()}), patch.dict(
            APPROVED_SOURCE_JOBS, {"onesa-mobile": frozenset()}
        ):
            errors = verify_source_runs(
                self.document, lambda *args: calls.append(args), self.successful_jobs
            )
        self.assertTrue(any("no reviewed acceptance workflow/job allowlist" in error for error in errors))
        self.assertEqual(calls, [])

    def test_source_run_rejects_unapproved_workflow_path(self):
        row = self.document["entries"][0]
        candidate = "a" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate))
        payload = {
            "id": 123, "head_sha": candidate, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/onesa-mobile"},
            "repository": {"full_name": "DruHustle/onesa-mobile"},
            "workflow_id": 7, "path": ".github/workflows/unreviewed.yml@refs/heads/main",
            "run_attempt": 1,
        }
        job_calls = []
        errors = verify_source_runs(
            self.document, lambda _repo, _run_id: payload,
            lambda *args: job_calls.append(args) or self.successful_jobs(*args),
        )
        self.assertTrue(any("allowlisted workflow path" in error for error in errors), errors)
        self.assertEqual(job_calls, [])

    def test_source_run_requires_the_named_acceptance_job_to_succeed_exactly_once(self):
        row = self.document["entries"][0]
        candidate = "a" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate))
        payload = {
            "id": 123, "head_sha": candidate, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/onesa-mobile"},
            "repository": {"full_name": "DruHustle/onesa-mobile"},
            "workflow_id": 7, "path": ".github/workflows/verify.yml@refs/heads/main",
            "run_attempt": 1,
        }
        bad_job_sets = (
            [],
            [{"name": "verify", "status": "completed", "conclusion": "failure"}],
            [{"name": "verify", "status": "completed", "conclusion": "skipped"}],
            [{"name": "verify", "status": "in_progress", "conclusion": None}],
            [{"name": "verify", "status": "completed", "conclusion": "success"}] * 2,
        )
        for jobs in bad_job_sets:
            with self.subTest(jobs=jobs):
                errors = verify_source_runs(
                    self.document, lambda _repo, _run_id: payload,
                    lambda _repo, _run_id, _attempt: {"total_count": len(jobs), "jobs": jobs},
                )
                self.assertTrue(any("required acceptance job" in error for error in errors), errors)

    def test_source_run_rejects_truncated_acceptance_job_inventory(self):
        row = self.document["entries"][0]
        candidate = "a" * 40
        row.update(decision="GO", candidate=candidate,
                   evidence=self.evidence_for(row["product"], candidate))
        payload = {
            "id": 123, "head_sha": candidate, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/onesa-mobile"},
            "repository": {"full_name": "DruHustle/onesa-mobile"},
            "workflow_id": 7, "path": ".github/workflows/verify.yml@refs/heads/main",
            "run_attempt": 1,
        }
        errors = verify_source_runs(
            self.document, lambda _repo, _run_id: payload,
            lambda _repo, _run_id, _attempt: {"total_count": 101, "jobs": [
                {"name": "verify", "status": "completed", "conclusion": "success"}
            ]},
        )
        self.assertTrue(any("inventory is incomplete" in error for error in errors), errors)

    def test_no_go_matrix_does_not_make_external_evidence_requests(self):
        calls = []
        self.assertEqual(verify_source_runs(self.document, lambda *args: calls.append(args)), [])
        self.assertEqual(calls, [])

    def test_scope_go_also_requires_live_source_run_verification(self):
        gate = self.document["scope_gates"][0]
        candidate = "c" * 40
        gate.update(decision="GO", candidate=candidate, blocker="",
                    evidence=self.evidence_for("pasofi", candidate))
        payload = {
            "id": 123, "head_sha": "9" * 40, "head_branch": "main",
            "status": "completed", "conclusion": "success", "event": "push",
            "head_repository": {"full_name": "DruHustle/pasofi"},
            "repository": {"full_name": "DruHustle/pasofi"},
            "workflow_id": 8, "path": ".github/workflows/verify.yml",
            "run_attempt": 1,
        }
        errors = verify_source_runs(self.document, lambda _repo, _run_id: payload, self.successful_jobs)
        self.assertTrue(any("scope_gates[0]" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
