# onesa-local-ci
Private workflow controller for trusted Onesa local CI and GitHub-hosted verification.

## Set up the local runner

On the intended Apple Silicon Mac, install Lima and GitHub CLI and authenticate `gh` as the repository owner on github.com. Run as your regular macOS user with Python 3.9 or later. A fresh guest needs network access to Ubuntu and GitHub plus capacity for four virtual CPUs, 6 GiB RAM, and its virtual disk.

```sh
gh repo clone DruHustle/onesa-local-ci
cd onesa-local-ci
python3 infra/local-runner/bootstrap.py
```

The bootstrap checks the controller is private and owner-only, then checks its single workflow against this checkout. It creates a dedicated Ubuntu 24.04 ARM64 Lima guest in plain mode, with no host filesystem mounts. It verifies the official runner archive's SHA-256, registers a repository-scoped account, enables its unprivileged systemd service, enables the VM at Mac login, and reads its online labels back from GitHub. Owner `gh` credentials stay on the Mac. Rerun the same command to resume setup or verify the existing guest. It refuses to replace an existing registration on another machine or reuse a changed guest definition.

## Verify a reviewed Portal revision

```sh
portal_sha=$(git ls-remote https://github.com/DruHustle/onesa-company-portal.git refs/heads/main | cut -f1)
gh workflow run trusted-portal.yml --repo DruHustle/onesa-local-ci --ref main -f source_sha="$portal_sha" -f run_local=true
gh run list --repo DruHustle/onesa-local-ci --workflow trusted-portal.yml --event workflow_dispatch --limit 5
```

Match the source SHA to the reviewed revision before dispatch. Use `gh run watch RUN_ID --repo DruHustle/onesa-local-ci --exit-status` to follow the selected run. GitHub evaluates the owner, private controller, main ref and manual-event conditions before assigning a job. The default local path requires only the ARM64 runner. It fetches public Portal main, matches the requested SHA, validates documentation and runs the system appearance tests. It then reads the independent public `Portal verification` main-push run at that SHA and requires a successful `verify` job on GitHub-hosted Ubuntu. The summary links the exact public run attempt. If public verification is pending, rerun after it finishes. No private GitHub-hosted runner is scheduled on the local path.

An optional `-f run_local=false` dispatch runs the documentation and appearance checks entirely on a private GitHub-hosted runner, subject to the account’s included Actions capacity and spending controls. A hosted-only dispatch records its scope. Product PRs keep their GitHub-hosted jobs.

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
