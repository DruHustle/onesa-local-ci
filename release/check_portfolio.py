#!/usr/bin/env python3
"""Validate all 28 Onesa client release decisions; never infer GO from a build."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

PRODUCTS = (
    "onesa-mobile", "pasofi", "onesa-drone", "onesa-robot",
    "smart-farmer", "smart-logistics", "smart-factory", "onesa-ai-platform",
)
WEB_ONLY = ("company-portal", "documents-public", "documents-internal", "identity")
EXPECTED = {(p, c) for p in PRODUCTS for c in ("web", "ios", "android")}
EXPECTED |= {(p, "web") for p in WEB_ONLY}


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def linked_evidence(evidence):
    if not isinstance(evidence, list) or not evidence:
        return False
    for link in evidence:
        if not nonblank(link) or any(ch.isspace() for ch in link):
            return False
        try:
            url = urlsplit(link)
            if url.scheme != "https" or not url.hostname:
                return False
        except ValueError:
            return False
    return True


def observed(row):
    return (nonblank(row.get("observed_result"))
            and row["observed_result"].strip() not in
            ("Not tested on the release candidate", "Not tested at site/provider/hardware"))


def validate(document, require_go=False):
    if not isinstance(document, dict):
        return ["matrix must be an object"]
    rows = document.get("entries")
    if not isinstance(rows, list):
        return ["entries must be an array"]
    errors = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"entry {index}: must be an object")
            continue
        key = (row.get("product"), row.get("platform"))
        if not all(nonblank(part) for part in key):
            errors.append(f"entry {index}: expected product and platform names")
            continue
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
            if not nonblank(row.get("release_url")):
                errors.append(f"{key}: GO requires a deployed URL or installed build reference")
            if not linked_evidence(row.get("evidence")):
                errors.append(f"{key}: GO requires linked acceptance evidence")
            if not all(nonblank(row.get(field)) for field in ("owner", "workflow", "environment", "role_tested")) or not observed(row):
                errors.append(f"{key}: GO requires an observed role-specific workflow and environment")
            if not nonblank(row.get("support_owner")) or not nonblank(row.get("operating_limits")) or row["operating_limits"].strip() == "Not qualified":
                errors.append(f"{key}: GO requires support ownership and operating limits")
            if row.get("platform") in ("ios", "android") and (
                row.get("store_submission") != "accepted" or not nonblank(row.get("store_receipt"))
            ):
                errors.append(f"{key}: GO requires native store acceptance receipt")
            if row.get("blocker"):
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
        key = (row.get("product"), row.get("kind"), row.get("scope"))
        if not all(nonblank(part) for part in key):
            errors.append(f"scope {index}: expected product, kind and scope names")
            continue
        if key in observed_scopes:
            errors.append(f"duplicate scope {key}")
        observed_scopes.add(key)
        if key not in required_scopes:
            errors.append(f"unknown scope {key}")
        if row.get("decision") not in ("GO", "NO-GO"):
            errors.append(f"{key}: invalid scope decision")
        if not nonblank(row.get("owner")):
            errors.append(f"{key}: scope owner required")
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{key}: scope evidence must be an array")
        for field in ("candidate", "environment", "role_tested",
                      "observed_result", "support_owner", "operating_limits"):
            if not isinstance(row.get(field), str):
                errors.append(f"{key}: {field} must be text")
        if row.get("decision") == "GO":
            if not linked_evidence(evidence):
                errors.append(f"{key}: GO requires scope acceptance evidence")
            if not all(nonblank(row.get(field)) for field in (
                "candidate", "environment", "role_tested", "observed_result",
                "support_owner", "operating_limits"
            )) or row["operating_limits"].strip() == "Not qualified" or not observed(row):
                errors.append(f"{key}: GO requires scoped candidate, observed result, operator and limits")
            if row.get("blocker"):
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
