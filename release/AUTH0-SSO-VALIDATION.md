# AUTH0-SSO-VALIDATION — 20 November 2026

**Production release decision: NO-GO.** All thirty functional test scenarios below are **NOT TESTED** during the current connector-only inspection. No test account was registered, no MFA token entered, and no downstream product access token was issued.

## Confirmed configuration facts

- Auth0 issuer `auth.onesa.eu` is a Cloudflare **DNS-only** CNAME to Auth0-managed custom-domain infrastructure.
- Onesa Account UI `account.onesa.eu` has a distinct proxied tunnel DNS entry. The target `onesa-oracle-production-api` Tunnel reported `healthy`, four connections, and a configured `account.onesa.eu` ingress. This is **network-level**, not application readiness.
- Onesa Portal Vercel **production** `ONESA_IDENTITY_UI_ORIGIN` exists and was privately compared with `https://account.onesa.eu` (exact match). The variable's update predates latest READY Portal deployment; no credential was exposed or changed.
- The `DruHustle/onesa-identity` production return registry in `src/registration-returns.js` has explicit web/native landing URLs, and `src/store.js` defines product and administrator roles. Source inspection does **not** prove active Auth0 tenant/client registry, email delivery, MFA, recipient session, or authorization.
- There is no connected Auth0 management integration available to this session, and the connected browser tab control was unavailable. Actual Auth0 tenant status and end-to-end client flows are **NOT TESTED**.

## Mandatory test matrix

| ID | Scenario | Evidence level | Status |
|---|---|---|---|
| AUTH-001 | New user registration | Real authorized web/native workflow required | NOT TESTED |
| AUTH-002 | Existing user login | Real authorized web/native workflow required | NOT TESTED |
| AUTH-003 | Email verification | Real authorized web/native workflow required | NOT TESTED |
| AUTH-004 | Expired verification link | Real authorized web/native workflow required | NOT TESTED |
| AUTH-005 | Forgot password | Real authorized web/native workflow required | NOT TESTED |
| AUTH-006 | MFA enrollment | Real authorized web/native workflow required | NOT TESTED |
| AUTH-007 | MFA challenge | Real authorized web/native workflow required | NOT TESTED |
| AUTH-008 | Administrator step-up | Real authorized web/native workflow required | NOT TESTED |
| AUTH-009 | Central account approval | Real authorized web/native workflow required | NOT TESTED |
| AUTH-010 | Suspended user denied | Real authorized web/native workflow required | NOT TESTED |
| AUTH-011 | Revoked product grant denied | Real authorized web/native workflow required | NOT TESTED |
| AUTH-012 | Unauthorized tenant access denied | Real authorized web/native workflow required | NOT TESTED |
| AUTH-013 | SSO Portal → Farmer | Real authorized web/native workflow required | NOT TESTED |
| AUTH-014 | SSO Portal → Logistics | Real authorized web/native workflow required | NOT TESTED |
| AUTH-015 | SSO Portal → Factory | Real authorized web/native workflow required | NOT TESTED |
| AUTH-016 | SSO Portal → AI Platform | Real authorized web/native workflow required | NOT TESTED |
| AUTH-017 | Internal Documents explicit access | Real authorized web/native workflow required | NOT TESTED |
| AUTH-018 | Cross-product administrator isolation | Real authorized web/native workflow required | NOT TESTED |
| AUTH-019 | iOS registration callback | Real authorized web/native workflow required | NOT TESTED |
| AUTH-020 | Android registration callback | Real authorized web/native workflow required | NOT TESTED |
| AUTH-021 | Browser refresh and session renewal | Real authorized web/native workflow required | NOT TESTED |
| AUTH-022 | Token expiration and rotation | Real authorized web/native workflow required | NOT TESTED |
| AUTH-023 | Logout and revocation | Real authorized web/native workflow required | NOT TESTED |
| AUTH-024 | Existing-account linking | Real authorized web/native workflow required | NOT TESTED |
| AUTH-025 | Repeated registration | Real authorized web/native workflow required | NOT TESTED |
| AUTH-026 | Separate staging and production | Real authorized web/native workflow required | NOT TESTED |
| AUTH-027 | Browser privacy restrictions | Real authorized web/native workflow required | NOT TESTED |
| AUTH-028 | iOS Safari authentication | Real authorized web/native workflow required | NOT TESTED |
| AUTH-029 | Auth0 outage/recovery | Real authorized web/native workflow required | NOT TESTED |
| AUTH-030 | Cloudflare Access plus product authentication | Real authorized web/native workflow required | NOT TESTED |

For every test, retain exact repository SHA, staging/production URL, role/persona, browser or signed device, test identity with private reference, expected vs observed result, and *restricted* screenshot/network/audit evidence. Reject invalid issuer, wrong audience, malicious redirect, cross-tenant ID, stale MFA, revoked grants and duplicate sign-ups. Every product initiates its own Code + PKCE flow; central authentication does not grant a product entitlement.

## Independent gates

[Identity #30](https://github.com/DruHustle/onesa-identity/issues/30) remains open for Auth0 Account app, tenant Actions, SMTP verification, Oracle Identity readiness and real cross-product registration. [Documents #12](https://github.com/DruHustle/onesa-documents/issues/12) remains open for Safari internal-docs/Auth0 access. Native installed iOS Farmer/Drone callbacks are separately unqualified. Preserve legacy production access until the authorized replacement is proven. No DNS, Auth0 Actions, login bypass or Vercel environment mutations were made here.
