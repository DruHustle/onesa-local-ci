#!/usr/bin/env python3
"""Read-only, fail-closed verification of the Onesa private Mac runner.

This does not register a runner, dispatch workflows or change any settings.
Only a recent *real* trusted self-hosted workflow run can certify execution.
"""
import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bootstrap as boot

SERVICE = "onesa-local-ci.service"
REQUIRED_LABELS = frozenset(("self-hosted", "linux", "arm64", boot.LABEL))
REQUIRED_STEPS = frozenset((
    "Check documentation and system appearance on trusted Portal main",
    "Verify the independent public GitHub-hosted run at the tested SHA",
))


def command(*args, timeout=35):
    """Read only. Never expose stdout/stderr from privileged commands on failure."""
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=True).stdout


def api(path):
    raw = command("gh", "api", "--hostname", "github.com", "--method", "GET",
                  f"repos/{boot.REPO}/{path}".rstrip("/"))
    return json.loads(raw)


def guest(*args):
    return command("limactl", "shell", "--tty=false", "--workdir=/", boot.VM, *args)


def add(report, name, ok, detail):
    report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("Missing GitHub timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def verify_dispatch(run, jobs, *, now=None):
    """Prove a recent owner-dispatched local job ran on the expected runner."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(run, dict) or not isinstance(jobs, list) or len(jobs) > 100:
        return False
    repository = run.get("repository") or {}
    actor = run.get("actor") or {}
    triggering_actor = run.get("triggering_actor") or {}
    if any((
        repository.get("full_name") != boot.REPO,
        run.get("path") != ".github/workflows/" + boot.WORKFLOW,
        run.get("head_branch") != "main",
        run.get("event") != "workflow_dispatch",
        run.get("status") != "completed",
        run.get("conclusion") != "success",
        actor.get("login") != "DruHustle",
        triggering_actor.get("login") != "DruHustle",
    )):
        return False
    try:
        started = parse_utc(run.get("run_started_at") or run.get("created_at"))
        if started > now + timedelta(minutes=5) or now - started > timedelta(hours=2):
            return False
    except (TypeError, ValueError):
        return False
    local = [j for j in jobs if isinstance(j, dict) and j.get("name") == "local"]
    if len(local) != 1:
        return False
    job = local[0]
    if (job.get("run_id") != run.get("id")
            or job.get("run_attempt") != run.get("run_attempt")
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"
            or job.get("runner_name") != boot.VM
            or not REQUIRED_LABELS.issubset({str(v).lower() for v in job.get("labels", [])})):
        return False
    steps = job.get("steps", [])
    if not isinstance(steps, list):
        return False
    passed_steps = {s.get("name") for s in steps
                    if isinstance(s, dict) and s.get("status") == "completed"
                    and s.get("conclusion") == "success"}
    return REQUIRED_STEPS.issubset(passed_steps)


def probe(run_id=None):
    report = {"runner": boot.VM, "repository": boot.REPO, "checks": [], "certified": False}
    is_mac = platform.system() == "Darwin" and platform.machine() == "arm64"
    add(report, "owner_mac", is_mac, "Requires the actual Apple Silicon runner host")
    has_gh = bool(shutil.which("gh"))
    has_lima = bool(shutil.which("limactl"))
    add(report, "github_cli", has_gh, "GitHub CLI must be available on the host")
    add(report, "lima_cli", has_lima, "Lima CLI must be available on the host")

    metadata = None
    if has_gh:
        try:
            metadata = api("")
            valid = (metadata.get("full_name") == boot.REPO
                     and metadata.get("default_branch") == "main"
                     and metadata.get("permissions", {}).get("admin") is True)
            add(report, "owner_controller", valid,
                "Expected canonical controller, main branch and owner admin access")
            add(report, "private_controller", metadata.get("private") is True,
                "The public controller must never dispatch to the Mac runner")
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            add(report, "owner_controller", False, "Could not read controller metadata")
            add(report, "private_controller", False, "Controller privacy unverified")
    else:
        add(report, "owner_controller", False, "GitHub CLI unavailable")
        add(report, "private_controller", False, "GitHub CLI unavailable")

    remote = None
    if has_gh:
        try:
            listing = api("actions/runners?per_page=100")
            candidates = [r for r in listing["runners"] if r.get("name") == boot.VM]
            if listing["total_count"] != len(listing["runners"]) or len(candidates) != 1:
                raise ValueError("Missing, duplicate or incomplete runner inventory")
            remote = candidates[0]
            labels = {str(x["name"]).lower() for x in remote.get("labels", [])}
            add(report, "remote_registration", REQUIRED_LABELS.issubset(labels),
                "Exact runner name and required labels must be registered")
            add(report, "github_online", remote.get("status") == "online",
                "GitHub must report the registered runner online")
        except (ValueError, KeyError, OSError, TypeError,
                subprocess.CalledProcessError, subprocess.TimeoutExpired):
            add(report, "remote_registration", False, "GitHub runner registry inaccessible or invalid")
            add(report, "github_online", False, "Runner online status not proven")
    else:
        add(report, "remote_registration", False, "GitHub CLI unavailable")
        add(report, "github_online", False, "GitHub CLI unavailable")

    vm = None
    if has_lima and is_mac:
        try:
            instances = [json.loads(line) for line in command("limactl", "list", "--json").splitlines() if line]
            candidates = [item for item in instances if item.get("name") == boot.VM]
            if len(candidates) != 1:
                raise ValueError("Expected one dedicated Lima guest")
            vm = candidates[0]
            shape = (vm.get("arch") == "aarch64" and vm.get("vmType") == "vz"
                     and vm.get("cpus") == 4 and vm.get("memory") == 6 * 1024**3
                     and not vm.get("additionalDisks"))
            marker = Path.home() / "Library/Application Support/Onesa/local-ci/guest.sha256"
            actual = hashlib.sha256((Path(vm["dir"]) / "lima.yaml").read_bytes()).hexdigest()
            add(report, "owned_guest", shape and marker.is_file() and marker.read_text().strip() == actual,
                "Guest resources and pinned Lima definition must match")
            add(report, "guest_running", vm.get("status") == "Running",
                "Dedicated Lima guest must be running")
        except (ValueError, KeyError, OSError, TypeError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            add(report, "owned_guest", False, "Could not verify dedicated guest")
            add(report, "guest_running", False, "Guest running state not proven")
    else:
        add(report, "owned_guest", False, "Requires the intended Mac and Lima")
        add(report, "guest_running", False, "Requires the intended Mac and Lima")

    if vm is not None and vm.get("status") == "Running":
        try:
            guest("sudo", "systemctl", "is-active", "--quiet", SERVICE)
            guest("sudo", "systemctl", "is-enabled", "--quiet", SERVICE)
            add(report, "service_running", True, "Runner service is active and enabled")
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            add(report, "service_running", False, "Runner service is not active and enabled")
        try:
            local = json.loads(guest("sudo", "cat", "/opt/onesa-actions-runner/.runner"))
            agrees = (remote is not None and local.get("agentId") == remote.get("id")
                      and local.get("agentName") == boot.VM
                      and local.get("gitHubUrl", "").rstrip("/") == "https://github.com/" + boot.REPO)
            add(report, "registration_identity", agrees,
                "Guest registration must match the exact remote runner ID")
        except (ValueError, TypeError, OSError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            add(report, "registration_identity", False, "Guest registration not readable")
    else:
        add(report, "service_running", False, "Guest not verified running")
        add(report, "registration_identity", False, "Guest not verified running")

    if run_id is not None and has_gh:
        try:
            run = api(f"actions/runs/{run_id}")
            attempt = run["run_attempt"]
            if not isinstance(attempt, int) or attempt < 1:
                raise ValueError("Invalid attempt")
            jobs = api(f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
            if jobs["total_count"] != len(jobs["jobs"]):
                raise ValueError("Incomplete job inventory")
            passed = verify_dispatch(run, jobs["jobs"])
            add(report, "recent_local_dispatch", passed,
                "Must be a recent successful, owner-dispatched run on this exact runner")
        except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            add(report, "recent_local_dispatch", False, "Could not validate workflow run evidence")
    else:
        add(report, "recent_local_dispatch", False,
            "Supply --run-id from a recent trusted manual local dispatch to certify execution")

    report["certified"] = all(x["ok"] for x in report["checks"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, default=None,
                        help="Recent trusted-portal workflow run ID for end-to-end evidence")
    parser.add_argument("--json", action="store_true", help="Machine-readable report without secrets")
    args = parser.parse_args(argv)
    if args.run_id is not None and args.run_id < 1:
        parser.error("--run-id must be positive")
    result = probe(args.run_id)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for check in result["checks"]:
            print(f'{"PASS" if check["ok"] else "FAIL"} {check["check"]}: {check["detail"]}')
        print("CERTIFIED" if result["certified"] else "NOT CERTIFIED")
    return 0 if result["certified"] else 1


if __name__ == "__main__":
    sys.exit(main())
