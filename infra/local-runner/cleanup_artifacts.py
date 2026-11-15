#!/usr/bin/env python3
"""Review disposable GitHub Actions artifacts without deleting release evidence."""
import argparse
import datetime as dt
import json
import re
import subprocess

REPOSITORY = "DruHustle/onesa-local-ci"
DISPOSABLE_PREFIXES = ("ci-", "preview-", "browser-", "test-")
UTC = dt.timezone.utc


def eligible(artifact, now, days, repo_id, default_branch="main"):
    # Treat API response metadata as untrusted. Only a real positive artifact
    # ID is eligible; booleans and malformed records must never be deleted.
    if not isinstance(artifact, dict):
        return False
    if (type(repo_id) is not int or repo_id <= 0
            or not isinstance(default_branch, str) or not default_branch
            or default_branch != default_branch.strip()
            or not isinstance(now, dt.datetime) or now.tzinfo is None):
        return False
    provenance = artifact.get("workflow_run")
    if not isinstance(provenance, dict) or type(provenance.get("id")) is not int or provenance["id"] <= 0:
        return False
    if any(type(provenance.get(field)) is not int or provenance[field] != repo_id
           for field in ("repository_id", "head_repository_id")):
        return False
    # Repository IDs alone do not identify the source revision. Require the
    # full workflow head SHA and branch before treating an artifact as bound
    # to an auditable source run.
    branch = provenance.get("head_branch")
    if (not isinstance(provenance.get("head_sha"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", provenance["head_sha"]
    ) or not isinstance(branch, str) or not branch or branch != branch.strip()):
        return False
    # Never clean artifacts originating from protected/release branches,
    # even when their names happen to use a disposable prefix.
    protected_branch = branch.casefold()
    protected_names = {"main", "master", "release", "production", "hotfix",
                       default_branch.casefold()}
    if (protected_branch in protected_names
            or protected_branch.startswith(("release/", "production/", "hotfix/"))):
        return False
    size = artifact.get("size_in_bytes")
    if type(size) is not int or size < 0:
        return False
    artifact_id = artifact.get("id")
    if type(artifact_id) is not int or artifact_id <= 0 or artifact.get("expired") is not False:
        return False
    name = artifact.get("name")
    if not isinstance(name, str) or not name.isprintable() or not any(
        name.startswith(prefix) for prefix in DISPOSABLE_PREFIXES
    ):
        return False
    # Untrusted/incomplete API metadata must fail closed. Never delete an
    # artifact when its creation time cannot be verified as UTC-aware.
    raw_created = artifact.get("created_at")
    if not isinstance(raw_created, str):
        return False
    try:
        created = dt.datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
    except ValueError:
        return False
    if created.tzinfo is None:
        return False
    return now - created >= dt.timedelta(days=days)


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=REPOSITORY)
    parser.add_argument("--older-than-days", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-repo", default="")
    parser.add_argument("--confirm-id", type=int, action="append", default=[], metavar="ARTIFACT_ID",
                        help="Explicitly approve this artifact ID for deletion; repeat for each ID")
    args = parser.parse_args()
    if args.repo != REPOSITORY:
        parser.error(f"This cleanup utility is restricted to {REPOSITORY}")
    if args.older_than_days < 7:
        parser.error("Retention cannot be shorter than seven days")
    if args.apply and args.confirm_repo != args.repo:
        parser.error("Deletion requires --confirm-repo matching --repo")
    if args.apply and not args.confirm_id:
        parser.error("Deletion requires each artifact ID to be approved with --confirm-id")
    metadata = json.loads(gh("api", f"repos/{args.repo}"))
    if not isinstance(metadata, dict) or metadata.get("full_name") != args.repo or (
        type(metadata.get("id")) is not int or metadata["id"] <= 0
        or not isinstance(metadata.get("default_branch"), str)
        or not metadata["default_branch"] or metadata["default_branch"] != metadata["default_branch"].strip()
    ):
        parser.error("Repository identity or default branch could not be verified")
    lines = gh("api", "--paginate", "--jq", ".artifacts[] | @json",
               f"repos/{args.repo}/actions/artifacts").splitlines()
    records = [json.loads(line) for line in lines]
    # Check the complete paginated inventory, not only eligible candidates:
    # a duplicate whose second copy has malformed metadata is still ambiguous.
    # Abort before any DELETE rather than letting the valid-looking copy win.
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        parser.error("Malformed artifact record in API listing; no deletion permitted")
    ids = []
    for item in records:
        artifact_id = item.get("id")
        # Do not silently ignore malformed IDs: a string/float/bool copy of
        # an otherwise valid ID is still an ambiguous inventory record.
        if type(artifact_id) is not int or artifact_id <= 0:
            parser.error("Malformed artifact ID in API listing; no deletion permitted")
        ids.append(artifact_id)
    if len(ids) != len(set(ids)):
        parser.error("Duplicate artifact IDs in API listing; no deletion permitted")
    now = dt.datetime.now(UTC)
    candidates = [item for item in records
                  if eligible(item, now, args.older_than_days, metadata["id"], metadata["default_branch"])]
    if args.apply:
        approved = set(args.confirm_id)
        if len(approved) != len(args.confirm_id) or not approved <= {item["id"] for item in candidates}:
            parser.error("Every confirmed artifact ID must be unique and currently eligible")
        candidates = [item for item in candidates if item["id"] in approved]
    total = sum(int(item.get("size_in_bytes", 0)) for item in candidates)
    for item in candidates:
        print(f"{'DELETE' if args.apply else 'DRY-RUN'} "
              f"{item['id']} {item['name']} {item.get('size_in_bytes', 0)} bytes")
        if args.apply:
            gh("api", "-X", "DELETE", f"repos/{args.repo}/actions/artifacts/{item['id']}")
    print(f"eligible={len(candidates)} bytes={total} applied={args.apply}")


if __name__ == "__main__":
    main()
