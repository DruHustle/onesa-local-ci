#!/usr/bin/env python3
"""Validate all 28 Onesa client release decisions; never infer GO from a build."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PRODUCTS = (
    "onesa-mobile", "pasofi", "onesa-drone", "onesa-robot",
    "smart-farmer", "smart-logistics", "smart-factory", "onesa-ai-platform",
)
WEB_ONLY = ("company-portal", "documents-public", "documents-internal", "identity")
EXPECTED = {(p, c) for p in PRODUCTS for c in ("web", "ios", "android")}
EXPECTED |= {(p, "web") for p in WEB_ONLY}

SOURCE_REPOSITORIES = {
    "onesa-mobile": "onesa-mobile",
    "pasofi": "pasofi",
    "onesa-drone": "onesa-drone",
    "onesa-robot": "onesa-robot",
    "smart-farmer": "smart-farmer",
    "smart-logistics": "smart-logistics",
    "smart-factory": "smart-factory",
    "onesa-ai-platform": "onesa-ai-platform",
    "company-portal": "onesa-portal",
    "documents-public": "onesa-documents",
    "documents-internal": "onesa-documents",
    "identity": "onesa-identity",
}

# A source run is not acceptance merely because its workflow file is under
# .github/workflows/. Populate these exact paths and required job names only
# after independently reviewing that product repository's acceptance contract.
# Empty entries deliberately fail closed; this controller does not guess.
APPROVED_SOURCE_WORKFLOWS = {product: frozenset() for product in SOURCE_REPOSITORIES}
APPROVED_SOURCE_JOBS = {product: frozenset() for product in SOURCE_REPOSITORIES}

# Only reviewed production web hosts may be promoted to GO. Preview hosts and
# unregistered product domains remain NO-GO until an owner reviews this list.
PRODUCTION_WEB_HOSTS = {
    "smart-farmer": frozenset({"farmer.onesa.eu"}),
    "smart-logistics": frozenset({"logistics.onesa.eu"}),
    "smart-factory": frozenset({"factory.onesa.eu"}),
    "onesa-ai-platform": frozenset({"platform.onesa.eu"}),
    "onesa-drone": frozenset({"drone.onesa.eu"}),
    "onesa-robot": frozenset({"robot.onesa.eu"}),
    "onesa-mobile": frozenset({"mobile.onesa.eu"}),
    "pasofi": frozenset({"pasofi.mobile.onesa.eu"}),
    "company-portal": frozenset({"portal.onesa.eu"}),
    "documents-public": frozenset({"docs.onesa.eu"}),
    "documents-internal": frozenset({"docs.internal.onesa.eu"}),
    # auth.onesa.eu is the DNS-only Auth0 issuer, not the protected Onesa
    # Account application. Its availability cannot qualify the Identity UI.
    "identity": frozenset({"account.onesa.eu"}),
}


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def valid_evidence(link):
    # urlsplit silently strips tabs/newlines and leading C0 controls.
    # Evidence must be an exact, unambiguous URL rather than one repaired
    # during parsing. Reject nonnumeric and out-of-range ports as well.
    if not nonblank(link) or any(
        char.isspace() or ord(char) < 0x20 or ord(char) == 0x7f for char in link
    ):
        return False
    try:
        parsed = urlsplit(link)
        parsed.port
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def valid_production_web_url(product, link):
    if not valid_evidence(link):
        return False
    parsed = urlsplit(link)
    return (parsed.hostname in PRODUCTION_WEB_HOSTS.get(product, ())
            and parsed.port in (None, 443))


UNVERIFIED_MARKERS = (
    "unverified", "not tested", "not run", "not observed", "not verified",
    "pending", "unknown", "no evidence",
)
OWNER_PLACEHOLDER_MARKERS = (
    "tbd", "to be determined", "unassigned", "not assigned", "n/a", "not applicable", "none",
)
OBSERVED_FAILURE_MARKERS = (
    "failed", "failure", "unsuccessful", "not passed", "did not pass",
    "error", "blocked", "incomplete", "timed out", "timeout",
    "cancelled", "canceled", "aborted",
)
UNQUALIFIED_LIMIT_MARKERS = (
    "not qualified", "unqualified", "unknown", "pending", "unverified",
    "not established", "not tested",
)


def verified_text(value):
    return (nonblank(value) and
            not any(marker in value.casefold() for marker in UNVERIFIED_MARKERS))


def verified_owner(value):
    return (verified_text(value) and
            not any(marker in value.casefold() for marker in OWNER_PLACEHOLDER_MARKERS))


def has_observation(row):
    # A GO must identify the workflow, tested role, environment and observed
    # outcome. A nonblank phrase such as "not tested" is not acceptance.
    fields = ("workflow", "environment", "role_tested", "observed_result")
    values = [row.get(field) for field in fields if field in row]
    if not all(nonblank(value) for value in values) or len(values) < 3:
        return False
    evidence_text = " ".join(values).casefold()
    if any(marker in evidence_text for marker in UNVERIFIED_MARKERS):
        return False
    outcome = row.get("observed_result", "").casefold()
    return not any(re.search(r"(?<!\w)" + re.escape(marker) + r"(?!\w)", outcome)
                   for marker in OBSERVED_FAILURE_MARKERS)


def has_source_bound_evidence(product, candidate, evidence):
    # A generic HTTPS URL or PR link does not bind acceptance to the exact
    # candidate. Require the product's own repository commit URL and a
    # workflow-run URL in that repository for the same full commit SHA.
    repository = SOURCE_REPOSITORIES.get(product)
    if not repository or not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate):
        return False
    if not isinstance(evidence, list):
        return False
    prefix = f"/DruHustle/{repository}"
    has_commit = False
    has_run = False
    for link in evidence:
        if not valid_evidence(link):
            continue
        parsed = urlsplit(link)
        if parsed.hostname != "github.com" or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
            continue
        has_commit |= parsed.path == f"{prefix}/commit/{candidate}"
        has_run |= re.fullmatch(re.escape(prefix) + r"/actions/runs/[0-9]+(?:/attempts/[0-9]+)?", parsed.path) is not None
    return has_commit and has_run


def source_run_references(product, evidence):
    """Return each cited workflow-run ID and any explicitly linked attempt."""
    repository = SOURCE_REPOSITORIES.get(product)
    if not repository or not isinstance(evidence, list):
        return []
    prefix = f"/DruHustle/{repository}/actions/runs/"
    run_refs = []
    for link in evidence:
        if not valid_evidence(link):
            continue
        parsed = urlsplit(link)
        if parsed.hostname != "github.com" or parsed.port not in (None, 443):
            continue
        match = re.fullmatch(re.escape(prefix) + r"([0-9]+)(?:/attempts/([0-9]+))?", parsed.path)
        if match:
            reference = (int(match.group(1)), int(match.group(2)) if match.group(2) else None)
            if reference not in run_refs:
                run_refs.append(reference)
    return run_refs


def fetch_source_run(repository, run_id):
    """Read public Actions metadata without credentials; inaccessible evidence fails closed."""
    url = f"https://api.github.com/repos/DruHustle/{repository}/actions/runs/{run_id}"
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "onesa-local-ci-release-evidence",
    })
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned a non-object workflow-run response")
    return payload


def fetch_source_run_jobs(repository, run_id, attempt):
    """Read jobs for the exact source workflow-run attempt, without credentials."""
    url = (
        f"https://api.github.com/repos/DruHustle/{repository}/actions/"
        f"runs/{run_id}/attempts/{attempt}/jobs?per_page=100"
    )
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "onesa-local-ci-release-evidence",
    })
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned a non-object workflow-jobs response")
    return payload


def verify_source_runs(document, fetch_json=fetch_source_run, fetch_jobs=fetch_source_run_jobs):
    """Require each GO source run and its allowlisted acceptance jobs to pass."""
    if not isinstance(document, dict):
        return ["source workflow evidence: release matrix must be an object"]
    errors = []
    cache = {}
    jobs_cache = {}
    for group in ("entries", "scope_gates"):
        rows = document.get(group)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("decision") != "GO":
                continue
            product = row.get("product")
            candidate = row.get("candidate")
            if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate):
                continue  # Static validation reports the malformed candidate.
            repository = SOURCE_REPOSITORIES.get(product)
            run_refs = source_run_references(product, row.get("evidence"))
            if not repository or not run_refs:
                continue  # Static validation reports missing source-bound links.
            approved_workflows = APPROVED_SOURCE_WORKFLOWS.get(product, frozenset())
            approved_jobs = APPROVED_SOURCE_JOBS.get(product, frozenset())
            for run_id, cited_attempt in run_refs:
                cache_key = (repository, run_id)
                label = f"{group}[{index}] ({product}): workflow run {run_id}"
                if cited_attempt is not None:
                    label += f" attempt {cited_attempt}"
                if not approved_workflows or not approved_jobs:
                    errors.append(
                        f"{label} has no reviewed acceptance workflow/job allowlist for {product}; refusing GO"
                    )
                    continue
                if cache_key not in cache:
                    try:
                        cache[cache_key] = fetch_json(repository, run_id)
                    except Exception as exc:
                        cache[cache_key] = exc
                payload = cache[cache_key]
                if isinstance(payload, Exception):
                    errors.append(f"{label} could not be verified ({type(payload).__name__}); refusing GO")
                    continue
                if not isinstance(payload, dict):
                    errors.append(f"{label} returned malformed metadata; refusing GO")
                    continue
                head_repository = payload.get("head_repository")
                repository_data = payload.get("repository")
                attempt = payload.get("run_attempt")
                valid = (
                    type(payload.get("id")) is int and payload.get("id") == run_id
                    and payload.get("head_sha") == candidate
                    and payload.get("head_branch") == "main"
                    and payload.get("status") == "completed"
                    and payload.get("conclusion") == "success"
                    and payload.get("event") in ("push", "workflow_dispatch")
                    and isinstance(head_repository, dict)
                    and head_repository.get("full_name") == f"DruHustle/{repository}"
                    and isinstance(repository_data, dict)
                    and repository_data.get("full_name") == f"DruHustle/{repository}"
                    and type(payload.get("workflow_id")) is int and payload["workflow_id"] > 0
                    and isinstance(payload.get("path"), str)
                    and payload["path"] in approved_workflows
                    and type(attempt) is int and attempt > 0
                    and (cited_attempt is None or attempt == cited_attempt)
                )
                if not valid:
                    errors.append(
                        f"{label} must be a completed successful push/dispatch on source main "
                        f"at candidate {candidate}, using an allowlisted workflow path and matching attempt"
                    )
                    continue
                jobs_key = (repository, run_id, attempt)
                if jobs_key not in jobs_cache:
                    try:
                        jobs_cache[jobs_key] = fetch_jobs(repository, run_id, attempt)
                    except Exception as exc:
                        jobs_cache[jobs_key] = exc
                job_payload = jobs_cache[jobs_key]
                if isinstance(job_payload, Exception):
                    errors.append(
                        f"{label} acceptance jobs could not be verified "
                        f"({type(job_payload).__name__}); refusing GO"
                    )
                    continue
                if not isinstance(job_payload, dict):
                    errors.append(f"{label} returned malformed acceptance-job metadata; refusing GO")
                    continue
                jobs = job_payload.get("jobs")
                total_count = job_payload.get("total_count")
                if (not isinstance(jobs, list) or type(total_count) is not int
                        or total_count != len(jobs) or any(not isinstance(job, dict) for job in jobs)):
                    errors.append(f"{label} acceptance-job inventory is incomplete or malformed; refusing GO")
                    continue
                for job_name in sorted(approved_jobs):
                    matches = [job for job in jobs if job.get("name") == job_name]
                    if (len(matches) != 1 or matches[0].get("status") != "completed"
                            or matches[0].get("conclusion") != "success"):
                        errors.append(
                            f"{label} required acceptance job {job_name!r} must appear exactly once "
                            "and complete successfully"
                        )
    return errors


def has_qualified_limits(row):
    limits = row.get("operating_limits")
    return (nonblank(limits) and
            not any(marker in limits.strip().casefold() for marker in UNQUALIFIED_LIMIT_MARKERS))


def validate(document, require_go=False):
    if not isinstance(document, dict):
        return ["release matrix must be an object"]
    rows = document.get("entries")
    if not isinstance(rows, list):
        return ["entries must be an array"]
    errors = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"entry {index}: must be an object")
            continue
        if not isinstance(row.get("product"), str) or not isinstance(row.get("platform"), str):
            errors.append(f"entry {index}: product and platform must be text")
            continue
        key = (row["product"], row["platform"])
        if key in seen:
            errors.append(f"duplicate client {key}")
        seen.add(key)
        if key not in EXPECTED:
            errors.append(f"unknown client {key}")
        if row.get("decision") not in ("GO", "NO-GO"):
            errors.append(f"{key}: invalid decision")
        for field in ("owner", "workflow", "blocker", "environment",
                      "role_tested", "observed_result", "support_owner",
                      "operating_limits"):
            if not isinstance(row.get(field), str):
                errors.append(f"{key}: {field} must be text")
        if not isinstance(row.get("candidate"), str):
            errors.append(f"{key}: candidate must be text")
        release_url = row.get("release_url")
        if release_url is not None and not nonblank(release_url):
            errors.append(f"{key}: release_url must be nonblank text or null")
        elif row["platform"] == "web" and release_url is not None and not valid_evidence(release_url):
            errors.append(f"{key}: web release_url must be a credential-free HTTPS URL")
        elif isinstance(release_url, str) and release_url.startswith(("http://", "https://")) and not valid_evidence(release_url):
            errors.append(f"{key}: URL release_url must be a credential-free HTTPS URL")
        if row.get("store_receipt") is not None and not isinstance(row.get("store_receipt"), str):
            errors.append(f"{key}: store_receipt must be text or null")
        for field in ("owner", "workflow", "environment", "observed_result",
                      "support_owner", "operating_limits"):
            if not nonblank(row.get(field)):
                errors.append(f"{key}: {field} must be nonblank")
        for field in ("owner", "support_owner"):
            if nonblank(row.get(field)) and not verified_owner(row.get(field)):
                errors.append(f"{key}: {field} must be verified, not unknown or pending")
        if row.get("decision") == "NO-GO" and not nonblank(row.get("blocker")):
            errors.append(f"{key}: NO-GO requires a concrete blocker")
        if row.get("platform") in ("ios", "android"):
            if row.get("store_submission") not in (
                "not-submitted", "submitted", "accepted", "rejected"
            ):
                errors.append(f"{key}: invalid store submission status")
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{key}: evidence must be an array")
        else:
            for evidence_index, link in enumerate(evidence):
                if not valid_evidence(link):
                    errors.append(f"{key}: evidence[{evidence_index}] must be a credential-free HTTPS URL")
        if row.get("decision") == "GO":
            if not nonblank(row.get("candidate")):
                errors.append(f"{key}: GO requires an exact release candidate")
            if not nonblank(row.get("release_url")) or (
                row["platform"] == "web" and not valid_evidence(row.get("release_url"))
            ):
                errors.append(f"{key}: GO requires a deployed URL or installed build reference")
            environment = row.get("environment")
            if row["platform"] == "web" and (
                not valid_production_web_url(row["product"], row.get("release_url"))
                or not isinstance(environment, str)
                or environment.strip().casefold() != "production"
            ):
                errors.append(f"{key}: web GO requires an allowlisted production host and exact production environment")
            if not isinstance(row.get("evidence"), list) or not row["evidence"] or not all(
                valid_evidence(link) for link in row["evidence"]
            ):
                errors.append(f"{key}: GO requires linked acceptance evidence")
            if not has_source_bound_evidence(row["product"], row.get("candidate"), row.get("evidence")):
                errors.append(f"{key}: GO requires exact candidate commit and workflow-run evidence in its source repository")
            if not all(nonblank(row.get(field)) for field in (
                "owner", "workflow", "environment", "role_tested", "observed_result"
            )) or not has_observation(row):
                errors.append(f"{key}: GO requires an observed role-specific workflow")
            if not nonblank(row.get("support_owner")) or not has_qualified_limits(row):
                errors.append(f"{key}: GO requires support ownership and qualified operating limits")
            if row["platform"] in ("ios", "android"):
                receipt = row.get("store_receipt")
                receipt_is_unverified = (not nonblank(receipt) or any(
                    marker in receipt.casefold() for marker in UNVERIFIED_MARKERS
                ))
                if row.get("store_submission") != "accepted" or receipt_is_unverified:
                    errors.append(f"{key}: GO requires native store acceptance receipt")
            if not isinstance(row.get("blocker"), str) or row["blocker"].strip():
                errors.append(f"{key}: GO cannot have an open blocker")
        elif require_go:
            errors.append(f"{key}: NO-GO")
    for key in sorted(EXPECTED - seen):
        errors.append(f"missing client {key}")
    required_scopes = (
        {("pasofi", "wifi-site", site) for site in ("K0", "K1", "G0", "G1", "G2", "G3")}
        | {("pasofi", "payment-channel", channel) for channel in (
            "Stripe web card", "Apple Pay iPhone", "Google Pay Android"
        )}
        | {("onesa-drone", "physical-task", "Chubory A77 supervised inspection"),
           ("onesa-robot", "physical-task", "supervised inspection on actual controller")}
        | {(product, "operational-pilot", "customer site operational workflow")
           for product in ("smart-farmer", "smart-logistics", "smart-factory")}
        | {("onesa-mobile", "provider-integration", "satellite-to-phone partner adapter")}
    )
    scope_rows = document.get("scope_gates")
    if not isinstance(scope_rows, list):
        errors.append("scope_gates must be an array")
        return errors
    observed_scopes = set()
    for index, row in enumerate(scope_rows):
        if not isinstance(row, dict):
            errors.append(f"scope {index}: must be an object")
            continue
        if not all(isinstance(row.get(field), str) for field in ("product", "kind", "scope")):
            errors.append(f"scope {index}: product, kind and scope must be text")
            continue
        key = (row["product"], row["kind"], row["scope"])
        if key in observed_scopes:
            errors.append(f"duplicate scope {key}")
        observed_scopes.add(key)
        if key not in required_scopes:
            errors.append(f"unknown scope {key}")
        if row.get("decision") not in ("GO", "NO-GO"):
            errors.append(f"{key}: invalid scope decision")
        if not nonblank(row.get("owner")):
            errors.append(f"{key}: scope owner required")
        elif not verified_owner(row.get("owner")):
            errors.append(f"{key}: scope owner must be verified, not unknown or pending")
        if not isinstance(row.get("blocker"), str):
            errors.append(f"{key}: scope blocker must be text")
        elif row.get("decision") == "NO-GO" and not nonblank(row.get("blocker")):
            errors.append(f"{key}: NO-GO scope requires a concrete blocker")
        for field in ("environment", "observed_result", "support_owner", "operating_limits"):
            if not nonblank(row.get(field)):
                errors.append(f"{key}: scope {field} must be nonblank")
        if nonblank(row.get("support_owner")) and not verified_owner(row.get("support_owner")):
            errors.append(f"{key}: scope support_owner must be verified, not unknown or pending")
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{key}: scope evidence must be an array")
        else:
            for evidence_index, link in enumerate(evidence):
                if not valid_evidence(link):
                    errors.append(f"{key}: scope evidence[{evidence_index}] must be a credential-free HTTPS URL")
        for field in ("candidate", "environment", "role_tested",
                      "observed_result", "support_owner", "operating_limits"):
            if not isinstance(row.get(field), str):
                errors.append(f"{key}: {field} must be text")
        if row.get("decision") == "GO":
            if not isinstance(evidence, list) or not evidence or not all(
                valid_evidence(link) for link in evidence
            ):
                errors.append(f"{key}: GO requires scope acceptance evidence")
            if not has_source_bound_evidence(row["product"], row.get("candidate"), evidence):
                errors.append(f"{key}: GO requires exact candidate commit and workflow-run evidence in its source repository")
            if not all(nonblank(row.get(field)) for field in (
                "owner", "candidate", "environment", "role_tested", "observed_result",
                "support_owner"
            )) or not has_qualified_limits(row) or not has_observation(row):
                errors.append(f"{key}: GO requires scoped candidate, observed result, operator and qualified limits")
            if not isinstance(row.get("blocker"), str) or row["blocker"].strip():
                errors.append(f"{key}: GO cannot retain scope blocker")
        elif require_go:
            errors.append(f"{key}: scope NO-GO")
    for key in sorted(required_scopes - observed_scopes):
        errors.append(f"missing scope {key}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--require-go", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.matrix.read_text())
    errors = validate(document, args.require_go)
    if not errors:
        errors.extend(verify_source_runs(document))
    if errors:
        for error in errors:
            print("FAIL:", error)
        raise SystemExit(1)
    print("PASS: complete 28-client inventory and evidence gates")


if __name__ == "__main__":
    main()
