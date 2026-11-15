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
            if not all(nonblank(row.get(field)) for field in (
                "owner", "workflow", "environment", "role_tested", "observed_result"
            )) or (isinstance(row.get("observed_result"), str) and
                   row["observed_result"].strip().casefold() == "not tested on the release candidate"):
                errors.append(f"{key}: GO requires an observed role-specific workflow")
            if not nonblank(row.get("support_owner")) or not nonblank(row.get("operating_limits")) or (
                isinstance(row.get("operating_limits"), str) and
                row["operating_limits"].strip().casefold() == "not qualified"
            ):
                errors.append(f"{key}: GO requires support ownership and operating limits")
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
        if not isinstance(row.get("owner"), str) or not row.get("owner"):
            errors.append(f"{key}: scope owner required")
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
            if not all(nonblank(row.get(field)) for field in (
                "owner", "candidate", "environment", "role_tested", "observed_result",
                "support_owner", "operating_limits"
            )) or (
                isinstance(row.get("operating_limits"), str)
                and row["operating_limits"].strip().casefold() == "not qualified"
            ) or (
                isinstance(row.get("observed_result"), str)
                and row["observed_result"].strip().casefold() == "not tested on the release candidate"
            ):
                errors.append(f"{key}: GO requires scoped candidate, observed result, operator and limits")
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
