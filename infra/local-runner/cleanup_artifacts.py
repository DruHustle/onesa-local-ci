#!/usr/bin/env python3
"""Review disposable GitHub Actions artifacts without deleting release evidence."""
import argparse
import datetime as dt
import json
import subprocess

DISPOSABLE_PREFIXES = ("ci-", "preview-", "browser-", "test-")
UTC = dt.timezone.utc


def eligible(artifact, now, days):
    if not artifact.get("id") or artifact.get("expired"):
        return False
    name = artifact.get("name", "")
    if not any(name.startswith(prefix) for prefix in DISPOSABLE_PREFIXES):
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
    parser.add_argument("--repo", default="DruHustle/onesa-local-ci")
    parser.add_argument("--older-than-days", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-repo", default="")
    args = parser.parse_args()
    if args.older_than_days < 7:
        parser.error("Retention cannot be shorter than seven days")
    if args.apply and args.confirm_repo != args.repo:
        parser.error("Deletion requires --confirm-repo matching --repo")
    lines = gh("api", "--paginate", "--jq", ".artifacts[] | @json",
               f"repos/{args.repo}/actions/artifacts").splitlines()
    now = dt.datetime.now(UTC)
    candidates = [item for line in lines if (item := json.loads(line))
                  and eligible(item, now, args.older_than_days)]
    total = sum(int(item.get("size_in_bytes", 0)) for item in candidates)
    for item in candidates:
        print(f"{'DELETE' if args.apply else 'DRY-RUN'} "
              f"{item['id']} {item['name']} {item.get('size_in_bytes', 0)} bytes")
        if args.apply:
            gh("api", "-X", "DELETE", f"repos/{args.repo}/actions/artifacts/{item['id']}")
    print(f"eligible={len(candidates)} bytes={total} applied={args.apply}")


if __name__ == "__main__":
    main()
