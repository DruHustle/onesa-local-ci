# Safe GitHub Actions artifact review

Use this utility only when recovering storage capacity for an explicitly reviewed repository. **No deletion is performed by default.** Never use artifact cleanup to replace investigation of GitHub Actions billing, storage or runner failures; preserve release, acceptance, receipt and rollback evidence.

```sh
python3 infra/local-runner/cleanup_artifacts.py --repo DruHustle/onesa-local-ci --older-than-days 14
```

The dry run lists only artifacts whose metadata is complete, whose originating workflow run and head repository match the repository's verified GitHub ID, whose source branch is not the repository's current default branch, `main`, `master`, `release/*`, `production/*` or `hotfix/*`, whose names have a disposable test/preview prefix, and whose age is at least the configured retention period (minimum seven days). Old age or a disposable-looking name alone is **not** authorization to delete. Missing, malformed or ambiguous fields fail closed.

If and only if the owner reviews the output and explicitly approves particular IDs, re-run with both the exact repository confirmation and **one `--confirm-id` per artifact**:

```sh
python3 infra/local-runner/cleanup_artifacts.py \
  --repo DruHustle/onesa-local-ci --older-than-days 14 \
  --apply --confirm-repo DruHustle/onesa-local-ci --confirm-id 123
```

The ID above is illustrative. The script refuses unconfirmed, duplicate, missing or newly ineligible IDs before making any DELETE request. Approval does not permit deletion of unrelated artifacts in the same repository. Run only from the owner's trusted workstation; GitHub CLI credentials must remain local. Record the dry-run review and any approved deletions in the release evidence ledger. Never assume these operations establish deployment or product launch readiness.
