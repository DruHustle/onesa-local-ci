# onesa-local-ci

Public workflow controller for **free standard GitHub-hosted Portal verification**. The repository is intentionally public to avoid consuming private-repository GitHub-hosted minutes. Jobs fetch only the exact reviewed source commit from the public Portal `main` branch. No repository credentials, secrets, production access, or private source are needed.

## Run Portal verification on a GitHub-hosted runner

Authenticate GitHub CLI as the owner, then dispatch the owner-only `trusted-portal.yml` workflow from the protected controller `main` branch:

```sh
portal_sha=$(git ls-remote https://github.com/DruHustle/onesa-company-portal.git refs/heads/main | cut -f1)
gh workflow run trusted-portal.yml --repo DruHustle/onesa-local-ci --ref main -f source_sha="$portal_sha" -f run_local=false
gh run list --repo DruHustle/onesa-local-ci --workflow trusted-portal.yml --event workflow_dispatch --limit 5
```

Match the source SHA to the intended reviewed revision. Use `gh run watch RUN_ID --repo DruHustle/onesa-local-ci --exit-status` to follow the selected run. The public-hosted job runs on standard `ubuntu-24.04`, verifies the exact public Portal `main` SHA, and executes its documentation and system-appearance tests. Its summary explicitly states that **local Mac validation did not run**. Portal's own GitHub-hosted `Portal verification` pipeline must independently pass before the product is merged or released.

The hosted job runs only on an explicit manual dispatch by the `DruHustle` owner from the controller's `main` branch, with minimal workflow token permissions. Fork and pull-request events do not schedule a job. Standard hosted runners in public repositories do not consume the private-repository Actions minutes. Artifact and cache storage limits, runner availability and abuse limits are separate considerations.

## Trusted Mac runner — private-only, not enabled by this public workflow

**Do not register or route your self-hosted Mac runner through the public controller.** The `run_local=true` branch intentionally requires a private owner-only controller and will be skipped while this repository is public. This is a security boundary, not a GitHub Actions billing failure. A public repository may receive untrusted content; the Mac runner must not execute it.

If you later establish an independently restricted **private** controller for the Mac, its owner-reviewed equivalent may use the steps below. They are preserved for recovery of the already-defined Mac setup, not a recommendation to make this public repository private.

On the intended Apple Silicon Mac install Lima and GitHub CLI and authenticate `gh` as repository owner. Run as the normal macOS user with Python 3.9 or later. The private controller requires four virtual CPUs, 6 GiB RAM and network access to Ubuntu and GitHub.

```sh
gh repo clone DruHustle/onesa-local-ci
cd onesa-local-ci
python3 infra/local-runner/bootstrap.py
```

The bootstrap **refuses public visibility**. It checks the private controller is owner-only and that its workflow matches the reviewed checkout, then provisions a dedicated Ubuntu ARM64 guest without host filesystem mounts. It validates the runner archive checksum, uses an unprivileged `systemd` service and checks the expected GitHub registration. Rerunning resumes a matching guest; it cannot replace another host's registration. macOS `gh` credentials remain on the host.

To stop a previously configured Lima guest:

```sh
limactl start-at-login --enabled=false onesa-portal-local-arm64
limactl stop onesa-portal-local-arm64
```

Before permanently retiring a guest, verify it is idle and remove its registration in GitHub Actions runner settings. Then delete only the matched guest and its `~/Library/Application Support/Onesa/local-ci/guest.sha256` marker. Bootstrap never deletes another host's runner.

Run configuration regression checks with:

```sh
python3 -m unittest discover -s infra/local-runner -v
```

A green GitHub-hosted run is **not** proof of an installed Mac runner, live product acceptance, or successful production deployment.
