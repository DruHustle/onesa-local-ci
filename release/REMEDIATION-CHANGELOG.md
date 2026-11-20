# REMEDIATION-CHANGELOG — verified changes on 20 November 2026

This record distinguishes code/CI changes actually performed from read-only configuration findings.

| Repo | Change | Exact head / merge SHA | Validation | Deployment |
|---|---|---|---|---|
| `DruHustle/onesa-ai-platform` | [PR #353](https://github.com/DruHustle/onesa-ai-platform/pull/353): bounded Work/Plugins interface, scoped tool execution and agent run reports merged to **dev** | head `5606e079cd53f6d9fca0b8a28808a494c0b912d7`; squash merge `b3f4bfb9f4e2e6ce00f920a73adc35fb4567e938` | Exact PR-head 11 required CI jobs completed successfully; run `44812968698` | **NOT DEPLOYED** by this work; Vercel main production remains at `d83f7ce07eb62002516594468ea52004bb5fdba8` |
| `DruHustle/onesa-local-ci` | [PR #17](https://github.com/DruHustle/onesa-local-ci/pull/17): new current matrix, historical snapshot retained, release workflow and regression tests updated, PasoFi source/deployment truth readback | head `446a3a40676f017493daaf3af64d7b6a425fdd0d`; squash merge `abb659e1ab6cf098907cb144d9add57f839ef421` | `Portfolio release matrix / validate` job success, run `44825633125` | GitHub-hosted **CI controller only**; no production app deployed |

## Read-only changes to investigation records

- [PasoFi #144](https://github.com/DruHustle/pasofi/issues/144): issue comment `7051638316` documents current production Vercel READY exact-`main` source `51f3a0f92680e3fc00a3de51ed2529ca48ffa58f`, resolves *historical frontend version mismatch only*. Oracle and real customer acceptance remain open.
- [Onesa Identity #30](https://github.com/DruHustle/onesa-identity/issues/30): issue comment `7051761310` documents corrected production `ONESA_IDENTITY_UI_ORIGIN`, Cloudflare healthy account Tunnel/route and enduring need to qualify live Auth0/Identity.
- [Smart Farmer PR #52](https://github.com/DruHustle/smart-farmer/pull/52): read-only exact-head CI reported SUCCESS while separate native acceptance was still running; **not merged** as part of this report.

## Controlled changes and rollback

No production DNS, Vercel config, Oracle service, live DB, router, payment provider or app-store publication was changed. No customer was charged or physical actuator commanded. For merge rollback, use the owning repository's normal Git revert PR, retain the original PR and exact merge SHA, and validate dependent stages. A Git revert does not restore external data or deployed images; independent operational rollback and backups are still mandatory.
