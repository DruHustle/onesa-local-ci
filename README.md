# onesa-local-ci
Public repository for credential-free GitHub-hosted CI. The historical trusted local-runner workflow is **disabled for public-controller use**: its private-repository condition must not be relaxed, and the Mac self-hosted runner must never be registered to this public repository.

The `Public hosted CI` workflow runs isolated Python regression tests on GitHub-hosted Ubuntu without repository secrets or self-hosted runners.

## Historical local-runner instructions — not authorized on this public repository

**Do not run the bootstrap against this public controller.** It deliberately rejects public visibility. These instructions are retained for reference only and require a separately authorized private controller before use.

## Set up the local runner

On the intended Apple Silicon Mac, install Lima and GitHub CLI and authenticate `gh` as the repository owner on github.com. Run as your regular macOS user with Python 3.9 or later. A fresh guest needs network access to Ubuntu and GitHub plus capacity for four virtual CPUs, 6 GiB RAM, and its virtual disk.

```sh
gh repo clone DruHustle/onesa-local-ci
cd onesa-local-ci
python3 infra/local-runner/bootstrap.py
```

The bootstrap requires a clean checkout from the canonical `DruHustle/onesa-local-ci` origin at the exact current owner-reviewed `main` commit. It refuses dirty, untracked or stale local controller code before provisioning or changing the guest. The root `.gitignore` keeps Python test bytecode and macOS metadata from making a reviewed checkout appear modified.

The bootstrap checks the controller is private and owner-only, then verifies every active workflow against this checkout. Only the trusted Portal dispatcher and, once merged, the separate GitHub-hosted portfolio release gate are allowed; unknown or altered workflows block registration and resumption. It creates a dedicated Ubuntu 24.04 ARM64 Lima guest in plain mode, with no host filesystem mounts. It verifies the official runner archive's SHA-256, registers a repository-scoped account, enables its unprivileged systemd service, enables the VM at Mac login, and reads its online labels back from GitHub. Owner `gh` credentials stay on the Mac. Rerun the same command to resume setup or verify the existing guest. It refuses to replace an existing registration on another machine or reuse a changed guest definition.

## Verify a reviewed Portal revision

```sh
portal_sha=$(git ls-remote https://github.com/DruHustle/onesa-portal.git refs/heads/main | cut -f1)
gh workflow run trusted-portal.yml --repo DruHustle/onesa-local-ci --ref main -f source_sha="$portal_sha" -f run_local=true
gh run list --repo DruHustle/onesa-local-ci --workflow trusted-portal.yml --event workflow_dispatch --limit 5
```

Match the source SHA to the reviewed revision before dispatch. Use `gh run watch RUN_ID --repo DruHustle/onesa-local-ci --exit-status` to follow the selected run. GitHub evaluates the owner, private controller, main ref and manual-event conditions before assigning a job. The default local path requires only the ARM64 runner. It fetches public Portal main, matches the requested SHA, validates documentation and runs the system appearance tests. It then reads the independent public `Portal verification` main-push run at that SHA and requires a successful `verify` job on GitHub-hosted Ubuntu. The summary links the exact public run attempt. If public verification is pending, rerun after it finishes. No private GitHub-hosted runner is scheduled on the local path.

An optional `-f run_local=false` dispatch runs the documentation and appearance checks entirely on a private GitHub-hosted runner, subject to the account’s included Actions capacity and spending controls. A hosted-only dispatch records its scope. Product PRs keep their GitHub-hosted jobs.

## Local runner trust boundary

The local workflow executes the selected public Portal source as the same unprivileged
`onesa-ci` account that owns the runner installation. Treat that source as trusted code:
a job can read or alter runner-account files, including the runner's own registration
state. The Lima guest isolates the Mac (no host filesystem mounts or forwarded SSH
agent); it is **not** a sandbox between a job and the runner account. Dispatch only an
owner-reviewed commit that is the exact current public Portal `main` SHA. Never run
pull-request heads, unreviewed branches or arbitrary repositories on this runner.
After suspected execution of untrusted code, take the runner offline and replace its
registration and guest before trusting it again. Do not place production credentials
or unrelated deployment secrets in this guest.


## Release evidence policy

A source commit URL plus a successful workflow-run URL is not sufficient by itself to
approve a product launch. The release verifier also checks the exact run attempt and
the required acceptance job inventory for that attempt.

Before any product can be marked GO, an owner must independently review that source
repository's acceptance contract and populate its exact workflow path and required
job name in `APPROVED_SOURCE_WORKFLOWS` and `APPROVED_SOURCE_JOBS` in
`release/check_portfolio.py`. These are code-reviewed allowlists, not values copied
from a release-matrix row or supplied by the evidence URL. They are intentionally
empty until that review occurs, so every product remains fail-closed rather than
accepting an arbitrary workflow under `.github/workflows/`.

The verifier reads public GitHub Actions run and attempt-job metadata without
credentials. Private source repositories, incomplete job inventories, missing jobs,
skipped/failed jobs, unreviewed workflow paths and unavailable API responses cannot
qualify as GO. Do not add production credentials to work around inaccessible evidence;
use a separately approved least-privilege read-only evidence mechanism if private
source evidence is later required.

## Stop and resume

```sh
limactl start-at-login --enabled=false onesa-portal-local-arm64
limactl stop onesa-portal-local-arm64
```

The offline registration remains available for the same guest. If the installer stopped after GitHub reported `Settings Saved`, update the existing checkout on the Mac and resume:

```sh
cd ~/onesa-local-ci
git pull --ff-only origin main
python3 infra/local-runner/bootstrap.py
```

The bootstrap checks the saved runner ID against GitHub and finishes installing the service with that registration. An existing active service keeps its current job. An upgraded unit starts the official service wrapper on its next normal start. Before retiring the guest permanently, verify it is idle, remove its registration in this repository's Actions runner settings, and then remove the dedicated VM and its matching `~/Library/Application Support/Onesa/local-ci/guest.sha256` marker. The bootstrap never deletes another host's registration.

Run the configuration regression suite with `python3 -m unittest discover -s infra/local-runner -v`. An actual local verification requires an online ARM64 registration and a successful trusted dispatch.
