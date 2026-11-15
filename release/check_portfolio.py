#!/usr/bin/env python3
"""Validate all 28 Onesa client release decisions; never infer GO from a build."""
import argparse
import json
from pathlib import Path

PRODUCTS = (
    "onesa-mobile", "pasofi", "onesa-drone", "onesa-robot",
    "smart-farmer", "smart-logistics", "smart-factory", "onesa-ai-platform",
)
WEB_ONLY = ("company-portal", "documents-public", "documents-internal", "identity")
EXPECTED = {(p, c) for p in PRODUCTS for c in ("web", "ios", "android")}
EXPECTED |= {(p, "web") for p in WEB_ONLY}


def validate(document, require_go=False):
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
            if not row.get("candidate"):
                errors.append(f"{key}: GO requires an exact release candidate")
            if not row.get("release_url"):
                errors.append(f"{key}: GO requires a deployed URL or installed build reference")
            if not row.get("evidence") or not all(
                isinstance(link, str) and link.startswith("https://")
                for link in row["evidence"]
            ):
                errors.append(f"{key}: GO requires linked acceptance evidence")
            if not row.get("role_tested") or row.get("observed_result") in (
                "", "Not tested on the release candidate"
            ):
                errors.append(f"{key}: GO requires an observed role-specific workflow")
            if not row.get("support_owner") or row.get("operating_limits") == "Not qualified":
                errors.append(f"{key}: GO requires support ownership and operating limits")
            if row.get("platform") in ("ios", "android") and (
                row.get("store_submission") != "accepted" or not row.get("store_receipt")
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
        if row.get("decision") == "GO":
            if not evidence or not all(isinstance(link, str) and link.startswith("https://") for link in evidence):
                errors.append(f"{key}: GO requires scope acceptance evidence")
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
