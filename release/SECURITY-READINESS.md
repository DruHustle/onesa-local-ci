# SECURITY-READINESS — 20 November 2026

**Overall security release gate: NOT TESTED / NO-GO.** Source policy and DNS review were performed, but current deployed APIs were not attacked, authenticated as alternate tenants, or independently qualified.

## Positive configuration/source evidence (not penetration-test evidence)

- Auth0 `auth.onesa.eu` is DNS-only to provider-owned custom domain; `account.onesa.eu` uses separate Cloudflare Tunnel ingress.
- Onesa Identity source defines independent product roles, UUID-bound registration and explicit return URLs; actual production Auth0 clients, MFA and token grant enforcement remain to be tested.
- PasoFi source policy insists on verified signed payment events and provider reconciliation before provisioning; actual live payment/RADIUS authorization is not demonstrated.
- The public `onesa-local-ci` repository forbids privileged self-hosted runners; [release matrix CI #17](https://github.com/DruHustle/onesa-local-ci/pull/17) passed and retained fail-closed NO-GO gates.
- AI Platform [Work/Plugins PR #353](https://github.com/DruHustle/onesa-ai-platform/pull/353) added bounded allowlisted tools and source-level checks; no production unrestricted tool permissions were enabled by this effort.

## High-priority unresolved verification

| Boundary | Required negative test | Status |
|---|---|---|
| Auth0 JWT issuer/audience/alg/nonce/PKCE | Wrong issuer, audience, algorithm, expired and rotated signing keys rejected | NOT TESTED |
| Product authorization | Authenticated user without product grant denied; privilege escalation/admin step-up blocked | NOT TESTED |
| Tenant/organization/farm/site | Cross-tenant IDOR/BOLA, resource membership changes and revoked admin denied | NOT TESTED |
| Internal Documents | Anonymous access to private bytes/search metadata denied across Safari/Chrome | NOT TESTED; [#12](https://github.com/DruHustle/onesa-documents/issues/12) open |
| Onesa Security | Application runtime DB user subject to RLS, secure collectors and audit immutability | NOT TESTED |
| PasoFi payments | Forged, duplicated, reversed and partially provisioned events cannot grant unpaid Internet | NOT TESTED; [#142](https://github.com/DruHustle/pasofi/issues/142) open |
| AI agents | Prompt injection, unauthorized tool calls, secret leakage and cross-tenant retrieval rejected | Source checks passed on dev PR #353; live acceptance NOT TESTED |
| Drone/robot/factory | Simulation never enables unsupervised hardware, dangerous physical actions, or uncontrolled commands | NOT TESTED |
| Supply chain | Critical dependency advisories, hard-coded secrets, trusted Actions permissions and artifact provenance | NOT TESTED portfolio-wide |

## Operational restrictions

Keep production keys, token contents, audit logs, identity records, certificate data and private recovery evidence out of the public CI repository. Never weaken failing policy/security checks to obtain green CI. Run scanners and penetration tests only against explicitly authorized environments; preserve formal review for payment, physical networking and actuation. Require demonstrated rollback, restore, session revocation window, incident response, retention approvals and privacy deletion rules before production GO.
