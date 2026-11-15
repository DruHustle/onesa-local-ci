#!/usr/bin/env python3
"""Validate all 28 Onesa client release decisions; never infer GO from a build."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

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
    "company-portal": "onesa-company-portal",
    "documents-public": "onesa-documents",
    "documents-internal": "onesa-documents",
    "identity": "onesa-identity",
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
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


UNVERIFIED_MARKERS = (
    "unverified", "not tested", "not run", "not observed", "not verified",
    "pending", "unknown", "no evidence",
)
UNQUALIFIED_LIMIT_MARKERS = (
    "not qualified", "unqualified", "unknown", "pending", "unverified",
    "not established", "not tested",
)


def has_observation(row):
    # A GO must identify the workflow, tested role, environment and observed
    # outcome. A nonblank phrase such as "not tested" is not acceptance.
    fields = ("workflow", "environment", "role_tested", "observed_result")
    values = [row.get(field) for field in fields if field in row]
    if not all(nonblank(value) for value in values) or len(values) < 3:
        return False
    evidence_text = " ".join(values).casefold()
    return not any(marker in evidence_text for marker in UNVERIFIED_MARKERS)


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
        for field in ("owner", "workflow", "environment", "observed_result",
                      "support_owner", "operating_limits"):
            if not nonblank(row.get(field)):
                errors.append(f"{key}: {field} must be nonblank")
        if row.get("decision") == "NO-GO" and not nonblank(row.get("blocker")):
            errors.append(f"{key}: NO-GO requires a concrete blocker")
        if row.get("platform") in ("ios", "android"):
            if row.get("store_submission") not in (
                "not-submitted", "submitted", "accepted", "rejected"
            ):
                errors.append(f"{key}: invalid store submission status")
        if not isinstance(row.get("evidence"), list):
            errors.append(f"{key}: evidence must be an array")
        if row.get("decision") == "GO":
            if not nonblank(row.get("candidate")):
                errors.append(f"{key}: GO requires an exact release candidate")
            if not nonblank(row.get("release_url")) or (
                row["platform"] == "web" and not valid_evidence(row.get("release_url"))
            ):
                errors.append(f"{key}: GO requires a deployed URL or installed build reference")
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
            if row["platform"] in ("ios", "android") and (
                row.get("store_submission") != "accepted" or not nonblank(row.get("store_receipt"))
            ):
                errors.append(f"{key}: GO requires native store acceptance receipt")
            if not isinstance(row.get("blocker"), str) or row["blocker"].strip():
                errors.append(f"{key}: GO cannot have an open blocker")
        elif require_go:
            errors.append(f"{key}: NO-GO")
    for key in sorted(EXPECTED - seen):
        errors.append(f"missing client {key}")
    required_scopes = (
        {("pasofi", "wifi-site", site) for site in ("K1", "G1", "G2", "G3")}
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
        if not isinstance(row.get("blocker"), str):
            errors.append(f"{key}: scope blocker must be text")
        elif row.get("decision") == "NO-GO" and not nonblank(row.get("blocker")):
            errors.append(f"{key}: NO-GO scope requires a concrete blocker")
        for field in ("environment", "observed_result", "support_owner", "operating_limits"):
            if not nonblank(row.get(field)):
                errors.append(f"{key}: scope {field} must be nonblank")
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{key}: scope evidence must be an array")
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
    errors = validate(json.loads(args.matrix.read_text()), args.require_go)
    if errors:
        for error in errors:
            print("FAIL:", error)
        raise SystemExit(1)
    print("PASS: complete 28-client inventory and evidence gates")


if __name__ == "__main__":
    main()
